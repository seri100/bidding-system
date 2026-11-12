#!/usr/bin/env python3
"""D2B facilities collector, Python 3.7+. Preview only: never sends messages.

Run: python3 d2b_collect.py --from-probe /tmp/d2b_probe.json
Live list: python3 d2b_collect.py
"""
import argparse
import ast
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode, urljoin

import requests
from bs4 import BeautifulSoup

BASE = 'https://www.d2b.go.kr'
KST = timezone(timedelta(hours=9))
NAMES = {'0037': '전기', '0038': '소방(기계)', '0039': '소방(전기)',
         '0040': '전문소방', '6202': '기계설비'}
MAX_BYTES = 25 * 1024 * 1024


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix='.d2b-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out, ensure_ascii=False, indent=2)
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def now():
    return datetime.now(KST)


def date_time(value):
    value = re.sub(r'\D', '', str(value or ''))
    if len(value) not in (12, 14):
        return ''
    try:
        return datetime.strptime(value[:12], '%Y%m%d%H%M').strftime('%Y-%m-%d %H:%M:00')
    except ValueError:
        return ''


def rules_engine(source, config):
    # Compile only these known functions, never execute main_send module code.
    wanted = {'recv_region_key', 'load_alimtalk_recipients',
              'matching_additional_rules', 'additional_rule_receivers',
              'bypass_recipient_min_budget', 'decide_receivers'}
    tree = ast.parse(Path(source).read_text(encoding='REDACTED_PRIVATE_VALUE'))
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            found[node.name] = node
    if set(found) != wanted:
        raise ValueError('수신자 함수 누락: '+str(sorted(wanted-set(found))))
    module = ast.Module(body=[found[n] for n in sorted(found)])
    if hasattr(tree, 'type_ignores'):
        module.type_ignores = []
    namespace = {'__file__': str(source), 'Path': Path, 'os': os, 're': re,
                 'norm': lambda v: str(v or '').strip(),
                 'normalize_phone_list': lambda v: list(dict.fromkeys(v))}
    os.environ['N_DATA_RECIPIENTS_FILE'] = str(config)
    exec(compile(ast.fix_missing_locations(module), '<recipient-functions>', 'exec'), namespace)
    namespace['load_alimtalk_recipients']()
    return namespace


def download(session, url):
    with session.get(url, timeout=(10, 45), stream=True) as r:
        r.raise_for_status()
        parts, size = [], 0
        for block in r.iter_content(65536):
            size += len(block)
            if size > MAX_BYTES:
                raise ValueError('공고문 파일 크기 제한 초과')
            parts.append(block)
        return b''.join(parts)


def hwpx_text(blob):
    lines = []
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = sorted(n for n in z.namelist()
                       if re.fullmatch(r'Contents/section\d+\.xml', n))
        if sum(z.getinfo(n).file_size for n in names) > MAX_BYTES:
            raise ValueError('HWPX XML 크기 제한 초과')
        for name in names:
            root = ET.fromstring(z.read(name))
            # Text nodes in document order: preserve table cell text without duplicates.
            for el in root.iter():
                if el.tag.rsplit('}', 1)[-1] == 't' and el.text:
                    lines.append(el.text)
    return '\n'.join(lines)


def document_text(blob, depth=0):
    if depth > 2:
        raise ValueError('압축 중첩 제한 초과')
    if blob.startswith(b'PK'):
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            if 'Contents/section0.xml' in z.namelist():
                return hwpx_text(blob)
            docs = [i for i in z.infolist() if not i.is_dir()
                    and re.search(r'\.(hwp|hwpx)$', i.filename, re.I)]
            docs.sort(key=lambda i: (not any(k in i.filename for k in
                                            ['공고', '입찰']), i.filename))
            # Never concatenate unrelated documents with conflicting conditions.
            if not docs:
                raise ValueError('ZIP 안에 HWP/HWPX 공고문 없음')
            if len(docs) > 1 and not any(k in docs[0].filename for k in ['공고', '입찰']):
                raise ValueError('ZIP 공고문 식별 필요')
            if docs[0].file_size > MAX_BYTES:
                raise ValueError('ZIP 내부 파일 크기 제한 초과')
            return document_text(z.read(docs[0]), depth+1)
    if blob.startswith(b'\xd0\xcf\x11\xe0'):
        tool = shutil.which('hwp5txt') or str(Path.home()/'.local/bin/hwp5txt')
        with tempfile.TemporaryDirectory(prefix='d2b-hwp-') as tmp:
            file = Path(tmp)/'notice.hwp'
            file.write_bytes(blob)
            p = subprocess.run([tool, str(file)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=45)
            if p.returncode:
                raise ValueError('hwp5txt 공고문 변환 실패')
            return p.stdout.decode('REDACTED_PRIVATE_VALUE')
    raise ValueError('지원하지 않는 공고문 형식')


def amounts_and_joint(text):
    # Match explicit labels only; never infer an estimated price from VAT division.
    compact = re.sub(r'\s+', '', text)
    amounts = set(int(x.replace(',', '')) for x in re.findall(
        r'추정가격[:：]?([0-9][0-9,]*)원', compact))
    for x in re.findall(r'공사비\(추정가격\)[:：][0-9,]+원\(([0-9,]+)원\)', compact):
        amounts.add(int(x.replace(',', '')))
    for x in re.findall(r'공사비\(추정가격\)[:：]([0-9,]+)원(?!\()', compact):

        amounts.add(int(x.replace(',', '')))

    price = next(iter(amounts)) if len(amounts) == 1 else None
    no_joint = bool(re.search(r'공동(?:계약|도급|수급)[:：]?(?:미허용|불허|불가)', compact))
    joint = '미허용' if no_joint else '확인필요'
    return price, joint


def detail_params(row):
    mapping = {'dprt_code': 'dprtCode', 'anmt_divs': 'anmtDivs',
               'anmt_numb': 'anmtNumb', 'rqst_degr': 'rqstDegr',
               'dcsn_numb': 'dcsnNumb', 'rqst_year': 'rqstYear',
               'csrt_numb': 'dcsnNumb', 'anmt_date': 'anmtDate',
               'lv2Divs': 'lv2Divs', 'cont_mthd': 'contMthd',
               'lv1_divs': 'lv1Divs', 'bsic_stat': 'bsicStat',
               'dmst_itnb': 'dmstItnb'}
    p = {k: row.get(v) or '' for k, v in mapping.items()}
    p.update({'pageDivs': 'E1', 'searchData': '{}'})
    return p


def list_rows(session, days):
    today = now()
    params = {'date_divs': '0', 'date_from': (today-timedelta(days=days)).strftime('%Y%m%d'),
              'date_to': today.strftime('%Y%m%d'), 'numb_divs': '1'}
    rows, seen = [], set()
    for page in range(1, 101):
        params['currentPageNo'] = str(page)
        r = session.post(BASE+'/peb/bid/getAnnounceList.json', data=params,
                         headers={'X-Requested-With': 'XMLHttpRequest'}, timeout=(10, 40))
        r.raise_for_status()
        data = r.json()
        batch = data['list']
        total = int(data['totlCnt'])
        if not isinstance(batch, list):
            raise ValueError('공고 목록 응답 형식 변경')
        signature = json.dumps(batch, sort_keys=True)
        if signature in seen and batch:
            raise ValueError('페이지 반복 감지')
        seen.add(signature)
        rows.extend(batch)
        print('[PAGE]', page, len(rows), '/', total, flush=True)
        if len(rows) >= total:
            return rows
        if not batch:
            raise ValueError('목록 조회가 전체 건수보다 일찍 종료됨')
        time.sleep(0.3)
    raise ValueError('페이지 제한 초과')





def notice_basic_price_release(text):

    """공고문에 명시된 기초예비가격 공개일을 추출한다."""

    pattern = (

        r"기초\s*예비\s*가격\s*공개"

        r"(?:\s*일시|\s*일자|\s*일)?\s*[:：]\s*"

        r"['‘’]?\s*(20\d{2}|\d{2})\s*[.년/-]\s*"

        r"(\d{1,2})\s*[.월/-]\s*(\d{1,2})\s*[.일]?"

        r"(?:\s*\([월화수목금토일](?:요일)?\))?"

        r"(?:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?"

    )

    values = set()

    for match in re.finditer(pattern, text):

        year, month, day, hour, minute, second = match.groups()

        year = int(year)

        if year < 100:

            year += 2000

        dt = datetime(year, int(month), int(day))

        if hour is None:

            values.add((dt.strftime("%Y-%m-%d"), "date"))

        else:

            dt = dt.replace(

                hour=int(hour), minute=int(minute),

                second=int(second or 0)

            )

            values.add((dt.strftime("%Y-%m-%d %H:%M:%S"), "dateTime"))

    if len(values) > 1:

        raise ValueError("공고문 기초예비가격 공개일이 서로 다름")

    return next(iter(values)) if values else ("", "")



def basic_price_release(soup):
    """공식 상세화면의 명시된 기초예비가격 공개일만 사용."""
    labels = {
        "기초예비가격공개",
        "기초예비가격공개일",
        "기초예비가격공개일자",
        "기초예비가격공개일시",
    }
    values = set()
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        for index, cell in enumerate(cells[:-1]):
            label = re.sub(
                r"[\s:：]", "", cell.get_text(" ", strip=True)
            )
            if label not in labels:
                continue
            value = cells[index + 1].get_text(" ", strip=True)
            match = re.fullmatch(
                r"\s*(20\d{2})[./-]\s*(\d{1,2})[./-]\s*"
                r"(\d{1,2})\.?"
                r"(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?\s*",
                value
            )
            if not match:
                continue
            year, month, day, hour, minute, second = match.groups()
            try:
                date = datetime(int(year), int(month), int(day))
                if hour is None:
                    values.add((date.strftime("%Y-%m-%d"), "date"))
                else:
                    date = date.replace(
                        hour=int(hour), minute=int(minute),
                        second=int(second or 0)
                    )
                    values.add((
                        date.strftime("%Y-%m-%d %H:%M:%S"), "dateTime"
                    ))
            except ValueError:
                continue

    if len(values) != 1:
        return "", ""
    return next(iter(values))



def price_tab_fields(soup):

    """상세화면 표에서 원 단위 금액과 구성항목을 추출."""

    aliases = {

        "기초예비가격": ("기초예비가격",),

        "국민건강보험료": ("국민건강보험료",),

        "국민연금보험료": ("국민연금보험료",),

        "요양보험료": ("요양보험료", "노인장기요양보험료"),

        "산업안전보건관리비": ("산업안전보건관리비",),

        "퇴직공제부금": ("퇴직공제부금", "퇴직공제부금비"),

        "안전관리비": ("안전관리비",),

        "품질관리비": ("품질관리비",),

        "재료비": ("재료비",),

        "노무비": ("노무비",),

        "경비": ("경비",),

        "부가가치세": ("부가가치세",),

        "A값": ("A값", "A", "A금액"),

        "순공사원가": ("순공사원가",),

    }

    lookup = {

        alias: name

        for name, names in aliases.items()

        for alias in names

    }

    found = {}

    blanks = set()



    for tr in soup.find_all("tr"):

        cells = tr.find_all(["th", "td"], recursive=False)

        for index, cell in enumerate(cells[:-1]):

            label = re.sub(r"[\s:：]", "", cell.get_text(" ", strip=True))

            name = lookup.get(label)

            if not name:

                continue

            text = cells[index + 1].get_text(" ", strip=True)

            text = re.sub(r"\s+", "", text)

            match = re.fullmatch(r"([0-9]+(?:,[0-9]{3})*)(?:원)?", text)

            if match:

                found.setdefault(name, set()).add(

                    int(match.group(1).replace(",", ""))

                )

            elif text in ("", "-", "원", "-원"):

                blanks.add(name)



    values = {

        name: next(iter(nums))

        for name, nums in found.items() if len(nums) == 1

    }

    result = {

        "금액구성항목": values,

        "금액공란항목": sorted(blanks - set(found)),

    }

    for name in ("기초예비가격", "A값", "순공사원가"):

        result[name] = values.get(name)



    a_names = (

        "국민건강보험료", "국민연금보험료", "요양보험료",

        "산업안전보건관리비", "퇴직공제부금",

        "안전관리비", "품질관리비",

    )

    cost_names = ("재료비", "노무비", "경비", "부가가치세")

    notes = []



    for name, components in (("A값", a_names), ("순공사원가", cost_names)):

        if name in found:

            notes.append(name + ": 화면 명시값" if name in values

                         else name + ": 화면 값 충돌로 미확인")

            continue

        if all(n in values or (n in blanks and n not in found)

               for n in components):

            result[name] = sum(values.get(n, 0) for n in components)

            note = name + ": " + "+".join(components) + " 합계"

            empty = [n for n in components if n not in values]

            if empty:

                note += "; " + ",".join(empty) + " 공란은 합산 제외"

            notes.append(note)

        else:

            notes.append(name + ": 구성항목 미확인/충돌로 계산 보류")



    result["금액산출기준"] = " / ".join(notes)

    return result



def read_detail(session, row):
    params = detail_params(row)
    r = session.post(BASE+'/peb/bid/announceView.do', data=params, timeout=(10, 40))
    r.raise_for_status()
    soup = BeautifulSoup(r.content, 'html.parser')
    tables = soup.find_all('table')
    if not tables or not soup.find(id='anmtNumb'):
        raise ValueError('상세 화면 형식 확인 필요')
    if soup.find(id='anmtNumb').get('value') != row['anmtNumb']:
        raise ValueError('상세 공고번호 불일치')
    license_text = ' '.join(t.get_text(' ', strip=True) for t in tables
                            if '면허' in t.get_text())
    codes = sorted(set(re.findall(r'\[(\d{4})\]', license_text)) & set(NAMES))
    if not codes:
        return None
    regions = []
    for t in tables:
        if '지역1' in t.get_text():
            for td in t.find_all('td'):
                value = re.sub(r'\s*\[[^]]*\]', '', td.get_text(' ', strip=True)).strip()
                if value:
                    regions.append(value)
    region = '|'.join(dict.fromkeys(regions))
    attachments = []
    for t in tables:
        if '첨부파일명' in t.get_text():
            for tr in t.find_all('tr'):
                a = tr.find('a', href=True)
                if a:
                    attachments.append({'label': tr.get_text(' ', strip=True),
                                        'name': a.get_text(' ', strip=True),
                                        'url': urljoin(BASE, a['href'])})
    record = {'공고번호': row['anmtNumb'], '차수': str(row['rqstDegr']),
              '공고명': row['rpstItnm'], '발주기관': row.get('codeVld3', ''),
              '입찰마감일시': date_time(row.get('bidxEndt')),
              '참가등록마감일시': date_time(str(row.get('bidxCldt', ''))+str(row.get('bidxCltm', ''))),
              '개찰일시': date_time(str(row.get('bidxDate', ''))+str(row.get('bidxTime', ''))),
              '기초예비가격': row.get('bsicExpt'), '참가가능지역': region,
              '면허코드': codes, '면허원문': license_text,
              '추정가격': None, '공동계약': '확인필요', 'attachments': attachments,
              'detail_url': BASE+'/peb/bid/announceView.do?'+urlencode(params),
              '원문': row, 'review_reasons': []}
    price_fields = price_tab_fields(soup)

    if price_fields.get("기초예비가격") is None:

        price_fields.pop("기초예비가격", None)

    record.update(price_fields)

    record["금액출처"] = record["detail_url"]



    release, release_type = basic_price_release(soup)
    record['기초예비가격공개일시'] = release
    record['기초예비가격공개값유형'] = release_type
    record['기초예비가격공개출처'] = (
        record['detail_url'] if release else ''
    )
    notice = [a for a in attachments if '공고문안' in a['label']]
    if len(notice) != 1:
        record['review_reasons'].append('공고문 첨부 식별 필요')
        return record
    try:
        text = document_text(download(session, notice[0]['url']))
        record['공고문텍스트'] = text
        doc_release, doc_type = notice_basic_price_release(text)

        if doc_release:

            existing = record.get('기초예비가격공개일시', '')

            if existing and (

                existing[:10] != doc_release[:10]

                or (

                    record.get('기초예비가격공개값유형') == 'dateTime'

                    and doc_type == 'dateTime'

                    and existing != doc_release

                )

            ):

                record['기초예비가격공개일시'] = ''

                record['기초예비가격공개값유형'] = ''

                record['기초예비가격공개출처'] = ''

                record['review_reasons'].append(

                    '상세화면과 공고문 기초예비가격 공개일 충돌'

                )

            elif not existing or doc_type == 'dateTime':

                record['기초예비가격공개일시'] = doc_release

                record['기초예비가격공개값유형'] = doc_type

                record['기초예비가격공개출처'] = notice[0]['url']

        record['추정가격'], record['공동계약'] = amounts_and_joint(text)
    except Exception as e:
        record['review_reasons'].append('공고문: '+str(e))
    return record


def assess(record, engine):
    reasons = record['review_reasons']
    region = record['참가가능지역']
    price = record['추정가격']
    if not price or price <= 0:
        reasons.append('명시된 추정가격 미확인/충돌')
    if not region:
        reasons.append('참가지역 공란: 전국 여부 확인 필요')
    if record['공동계약'] != '미허용':
        reasons.append('공동계약 허용 여부/지역/비율 확인 필요')
    deadline = record['입찰마감일시']
    if not deadline:
        reasons.append('투찰 마감 미확인')
    elif deadline <= now().strftime('%Y-%m-%d %H:%M:%S'):
        reasons.append('투찰 마감 경과')
    if not record['참가등록마감일시']:
        reasons.append('참가등록 마감 미확인')
    elif record['참가등록마감일시'] <= now().strftime('%Y-%m-%d %H:%M:%S'):
        reasons.append('참가등록 마감 경과')
    phones = []
    for code in record['면허코드']:
        # Evaluate each alternative region independently and union recipients.
        for local in region.split('|'):
            row = dict(record, 공고업종코드=code, local_region=local,
                       scope='전국' if local == '전국' else '지역')
            row['대표지역'] = local
            extras = engine['matching_additional_rules'](row)
            bypass = any(x['bypass_min_budget'] for x in extras)
            if not price or (price < 30000000 and not bypass):
                continue
            if local == '전국' and price < 1000000000:
                # Only explicit extra rules may allow a lower-price notice.
                phones.extend(engine['additional_rule_receivers'](row))
            else:
                phones.extend(engine['decide_receivers'](row))
    record['수신대상'] = list(dict.fromkeys(phones))
    if any(x in reasons for x in ('투찰 마감 경과', '참가등록 마감 경과')):

        record['status'] = 'EXPIRED'

    elif reasons:

        record['status'] = 'REVIEW'
    elif phones:
        record['status'] = 'READY_PREVIEW'
    else:
        record['status'] = 'FILTERED'
    # 국방조달 입찰개시일 기준: 기초예비가격 공개일.
    release = record.get('기초예비가격공개일시', '')
    record['시작일시'] = release
    record['입찰개시일시'] = release
    record['입찰개시기준'] = '기초예비가격 공개일'
    record['calendar_status'] = (
        'PENDING_INTEGRATION' if release
        else 'HOLD_NO_BASIC_PRICE_RELEASE'
    )


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from-probe', type=Path)
    p.add_argument('--days', type=int, default=14)
    p.add_argument('--output', type=Path, default=Path('/home/pi/bid-d2b/output'))
    p.add_argument('--rules-source', type=Path, default=Path('/home/pi/n_data/main_send.py'))
    p.add_argument('--recipients', type=Path, default=Path('/home/pi/n_data/alimtalk_recipients.json'))
    args = p.parse_args()
    if not 1 <= args.days <= 90:
        p.error('--days must be 1..90')
    engine = rules_engine(args.rules_source, args.recipients)
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})
    r = session.get(BASE+'/peb/bid/announceList.do?key=41', timeout=(10, 30))
    r.raise_for_status()
    session.headers['Referer'] = r.url
    rows = json.loads(args.from_probe.read_text(encoding='utf-8'))['rows'] if args.from_probe else list_rows(session, args.days)
    atomic_json(args.output/'raw_list.json', {'collected_at': now().isoformat(), 'rows': rows,
                                            'cached_source': str(args.from_probe or '')})
    # Latest revision wins, including a cancellation; never resurrect older notices.
    latest = {}
    for row in rows:
        key = (row.get('rqstYear'), row.get('dprtCode'), row.get('anmtNumb'))
        rank = (int(row.get('rqstDegr') or 0), str(row.get('finlChdt') or ''),
                row.get('anmtCncl') == 'Y')
        if key not in latest or rank > latest[key][0]:
            latest[key] = (rank, row)
    records, errors = [], []
    for _, row in latest.values():
        if str(row.get('lv2Divs')) != '1' or row.get('anmtCncl') == 'Y' or '취소' in str(row.get('codeVld1', '')):
            continue
        if row.get('contMthd') == 'B':
            print('[SKIP_LOGIN]', row.get('anmtNumb'), '지명경쟁: 로그인 필요', flush=True)
            continue
        try:
            record = read_detail(session, row)
            if record:
                assess(record, engine)
                records.append(record)
                print('[{}] {}-{} {} / 추정가격={} / 지역={} / 수신={} / 사유={}'.format(
                    record['status'], record['공고번호'], record['차수'], record['공고명'],
                    record['추정가격'], record['참가가능지역'], len(record['수신대상']),
                    '; '.join(record['review_reasons'])), flush=True)
        except Exception as e:
            errors.append({'bid': row.get('anmtNumb'), 'reason': str(e)})
            print('[ERROR]', row.get('anmtNumb'), str(e), flush=True)
        atomic_json(args.output/'preview.json', {'generated_at': now().isoformat(),
                    'mode': 'PREVIEW_ONLY', 'records': records, 'errors': errors})
        time.sleep(0.3)
    atomic_json(args.output/'preview.json', {'generated_at': now().isoformat(),
                'mode': 'PREVIEW_ONLY', 'records': records, 'errors': errors})
    counts = {k: sum(x['status'] == k for x in records) for k in ['READY_PREVIEW', 'REVIEW', 'FILTERED', 'EXPIRED']}
    print('[SUMMARY]', json.dumps(counts, ensure_ascii=False), 'errors=', len(errors))
    print('[OUTPUT]', args.output/'preview.json')
    print('[NO_SEND] 알림톡/캘린더 호출 없음. 자동 실행 미등록.')
    return 1 if errors else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        print('[STOP]', type(e).__name__, str(e), file=sys.stderr)
        sys.exit(1)

