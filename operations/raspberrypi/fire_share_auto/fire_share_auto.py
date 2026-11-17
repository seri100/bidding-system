# -*- coding: utf-8 -*-
"""Durable fire score-cap exports. Python 3.7 compatible; no messaging calls."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

VERSION = '1.0.2'
KST = dt.timezone(dt.timedelta(hours=9))
DEFAULT_STATE = Path('/home/pi/n_data/state/fire_share_auto')
REGIONS = {'서울': ['01'], '부산': ['02'], '대구': ['03'], '인천': ['04'],
           '광주': ['05'], '대전': ['06'], '울산': ['07'], '경기': ['08', '09'],
           '강원': ['10'], '충북': ['11'], '충남': ['12'], '전북': ['13'],
           '전남': ['14'], '경북': ['15'], '경남': ['16'], '제주': ['17'], '세종': ['18']}
ALIASES = {'서울특별시': '서울', '부산광역시': '부산', '대구광역시': '대구',
           '인천광역시': '인천', '광주광역시': '광주', '대전광역시': '대전',
           '울산광역시': '울산', '경기도': '경기', '강원특별자치도': '강원',
           '강원도': '강원', '충청북도': '충북', '충청남도': '충남',
           '전북특별자치도': '전북', '전라북도': '전북', '전라남도': '전남',
           '경상북도': '경북', '경상남도': '경남', '제주특별자치도': '제주',
           '제주도': '제주', '세종특별자치시': '세종'}
KEY = re.compile(r'^(?:R\d{2}[A-Z]{2}\d+|\d{11})-\d{3}$')
BASE = 'https://www.ekffa.or.kr/fe/member/'
FIELDS = ('공고번호', '차수', '공고명', '게시일시', '입찰마감일시', '협정마감일시',
          '발주기관', '공고업종코드', '공고업종명', '첨부파일폴더', '_score_cap_source')


def now():
    return dt.datetime.now(KST).isoformat(timespec='seconds')


def log(message):
    print('[%s] [FIRE_SHARE] %s' % (now(), message), flush=True)


def compact(text):
    return re.sub(r'[\s|\x00-\x1f]+', '', text)


def read_json(path, default=None):
    if not Path(path).exists():
        return {} if default is None else default
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def enqueue(row, root=None, logger=log, state_dir=None):
    """Small local-only queue write; whitelist never includes recipient secrets."""
    if row.get('시공경험배점한도') is not True:
        return False
    no = str(row.get('공고번호') or '')
    order = str(row.get('차수') or '000').zfill(3)
    key = no + '-' + order
    if not KEY.fullmatch(key):
        return False
    if '소방' not in str(row.get('공고명', '')) and '소방' not in str(row.get('공고업종명', '')) and not any(
            x in str(row.get('공고업종코드', '')) for x in ('0038', '0039', '0040')):
        return False
    payload = {k: str(row[k]) for k in FIELDS if row.get(k) is not None}
    payload.update({'공고번호': no, '차수': order, '시공경험배점한도': True})
    path = Path(state_dir or os.environ.get('FIRE_SHARE_STATE', str(DEFAULT_STATE))) / 'queue' / (key + '.json')
    if path.exists() and read_json(path) == payload:
        return False
    atomic_json(path, payload)
    logger('[FIRE_SHARE][QUEUED] ' + key)
    return True


def segment(text, start, end):
    m = re.search(start + r'(.*?)' + end, text, re.S)
    return m.group(1) if m else ''


def parse_notice(text, key, row=None):
    """Extract explicit notice clauses, never infer missing permissions/ratios."""
    if not KEY.fullmatch(key):
        raise ValueError('invalid_notice_key')
    row = row or {}
    t = compact(text)
    identities=set(re.findall(r'R\d{2}[A-Z]{2}\d+',t))
    if identities and key.rsplit('-',1)[0] not in identities:
        raise ValueError('notice_source_identity_mismatch')
    title = segment(t, r'1\.3\.공사명[:：]?', r'1\.4\.') or str(row.get('공고명', ''))
    if not title:
        m = re.search(r'공사명[:：](.+?)(?:수요기관|개찰일시|1\.4\.)', t)
        title = m.group(1).strip('○ㆍ') if m else ''
    # Keep the displayed title's original spacing when the source supplies it.
    raw_title = str(row.get('공고명') or '')
    if raw_title and compact(raw_title) == compact(title):
        title = raw_title
    else:
        for m in re.finditer(r'공\s*사\s*명\s*[:：]\s*([^\n\r]+)', text):
            candidate = re.split(r'수\s*요\s*기\s*관|개\s*찰\s*일\s*시|1\.4\.|[○ㆍ]', m.group(1))[0].strip()
            if compact(candidate) == compact(title):
                title = candidate
                break
    fire_industry = any(x in str(row.get('공고업종코드','')) for x in ('0038','0039','0040'))
    if not title or ('소방' not in title and not fire_industry and not re.search(r'주공종[:：]?(?:일반|전문)소방',t)):
        raise ValueError('not_fire_notice')
    qualification = segment(t, r'3\.1\.', r'3\.2\.')
    contract_match = re.search(r'([45])\.공동계약', t)
    contract = ''
    if contract_match:
        i = contract_match.start()
        end = re.search(r'%d\.현장' % (int(contract_match.group(1)) + 1), t[contract_match.end():])
        contract = t[i:contract_match.end() + end.start()] if end else t[i:i+5000]
    issues = []
    region_clause = qualification + contract
    # Geography comes from eligibility/mandatory participation, never office address.
    mandatory = re.findall(r'시공참여비율이전체공사금액의(\d+(?:\.\d+)?)%이상', region_clause)
    mandatory = sorted(set(float(n) / 100 for n in mandatory))
    mandatory_mode = '지역의무공동도급이적용' in region_clause
    restricted = '둔자이어야' in qualification or '소재한' in qualification
    candidates = set()
    if mandatory_mode:
        clauses = re.findall(r'지역의무공동도급이적용되는공사로서(.{0,90})', region_clause)
    elif restricted:
        clauses = re.findall(r'계속하여(.{0,50}?)둔자이어야', qualification)
    else:
        clauses = []
    for clause in clauses:
        for name, short in ALIASES.items():
            if name in clause:
                candidates.add(short)
    regions = sorted(candidates)
    if not regions:
        regions = ['_확인필요']
        issues.append('참가자격 조항의 적용 지역 확인 필요')
    if len(regions) > 1:
        issues.append('복수지역 조항: 지역별 의무비율을 원문에서 별도 확인')
    required = mandatory[0] if len(mandatory) == 1 and len(regions)==1 else None
    if mandatory_mode and required is None:
        issues.append('지역의무 참여비율 확인 필요')
    mode = '지역의무' if mandatory_mode else ('지역제한' if restricted else '확인 필요')
    if mode == '확인 필요':
        issues.append('지역제한/지역의무 적용 방식 확인 필요')
    both = re.search(r'공동이행방식(?:또는|,|및)분담이행방식', contract)
    common = '허용' if both else '확인 필요'
    split = '허용' if both else '확인 필요'
    if re.search(r'공동이행방식(?:만|으로만)', contract):
        common, split = '허용', '불허'
    mixed = '불허' if re.search(r'혼합방식.{0,35}(?:불허|허용하지않)', contract) else (
        '허용' if re.search(r'혼합된방식이가능|혼합방식(?:을|도|이)?허용', contract) else '명시 없음(확인 필요)')
    if common == '확인 필요' or split == '확인 필요':
        issues.append('공동이행/분담이행 허용 방식 확인 필요')
    min_match = re.search(r'최소지분율[이가은는]?(\d+(?:\.\d+)?)%이상', contract)
    minimum = float(min_match.group(1))/100 if min_match else None
    rep = '기계분야' if re.search(r'대표자는기계분야', contract) else (
        '주공종 출자비율이 가장 많은 자' if '주공종의출자비율이가장많은자' in contract else
        '원문 공동계약 조항 참조')
    table = segment(t, r'1\.8\.', r'1\.9\.')
    basis = []
    vals = {}
    for kind in ('기계', '전기'):
        m = re.search(r'일반소방시설공사업\(' + kind + r'\)(.*?)(?=일반소방시설공사업\(|$)', table)
        pairs = re.findall(r'([\d,]+)원\((\d+(?:\.\d+)?)%\)', m.group(1)) if m else []
        vals[kind] = [(int(a.replace(',', '')), float(p)/100) for a, p in pairs[:2]]
    for i, label in enumerate(('추정금액(도급자관급 포함)', '추정가격+부가세(도급분)')):
        if len(vals['기계']) <= i or len(vals['전기']) <= i:
            issues.append(label + ' 기계/전기 비율 확인 필요')
            continue
        ma, mp = vals['기계'][i]
        ea, ep = vals['전기'][i]
        if ma <= 0 or ea <= 0 or not 0 <= mp <= 1 or not 0 <= ep <= 1 or abs(mp+ep-1) > .002:
            issues.append(label + ' 비율/금액 검증 실패')
            continue
        basis.append({'기준': label, '기계금액': ma, '전기금액': ea, '기계비율': mp, '전기비율': ep})
    eval_clause = segment(t, r'1\.9\.', r'2\.입찰')
    url = 'https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=%s&bidPbancOrd=%s' % tuple(key.rsplit('-', 1))
    return dict(key=key, title=title, regions=regions, mode=mode, required=required,
                common=common, split=split, mixed=mixed, minimum=minimum,
                representative=rep, basis=basis, issues=issues, source=url,
                qualification=qualification, contract=contract, table=table,
                evaluation=eval_clause, checked_at=now(), metadata=row)


def get_html(session, endpoint, params):
    from bs4 import BeautifulSoup
    response = session.get(BASE + endpoint, params=params, timeout=(10, 30))
    response.raise_for_status()
    response.encoding = response.apparent_encoding or 'utf-8'
    return BeautifulSoup(response.text, 'html.parser'), response.url


def fetch_companies(region):
    if region not in REGIONS:
        raise ValueError('unmapped_region')
    import requests
    records, controls = [], []
    with requests.Session() as session:
        session.headers['User-Agent'] = 'n_data-fire-share/1.0 (public member directory)'
        for code in REGIONS[region]:
            for license_code, license_name in (('3', '일반(기계)'), ('2', '일반(전기)')):
                listed, count, page = [], None, 1
                while True:
                    params = dict(upKindcode='10', _m='41', commId=code, licenseDiv=license_code, currentPage=page)
                    soup, list_url = get_html(session, 'NR_listCompany.do', params)
                    node = soup.select_one('.board-count')
                    match = re.search(r'([\d,]+)\s*건', node.get_text() if node else '')
                    if not match:
                        raise ValueError('directory_count_missing')
                    current_count = int(match.group(1).replace(',', ''))
                    if count is None:
                        count = current_count
                    elif count != current_count:
                        raise ValueError('directory_changed_during_pagination')
                    links = soup.select('a[href^="javascript:COMPANY.view"]')
                    for a in links:
                        identity = re.search(r"view\('([\w-]+)'", a['href'])
                        if not identity:
                            raise ValueError('company_identity_missing')
                        cols = [td.get_text(' ', strip=True) for td in a.find_parent('tr').find_all('td')]
                        if len(cols) < 6 or cols[5] != license_name:
                            raise ValueError('company_license_filter_mismatch')
                        listed.append((identity.group(1), cols))
                    if len(listed) >= count:
                        break
                    if not links or page >= 1000:
                        raise ValueError('directory_pagination_incomplete')
                    page += 1
                    time.sleep(.1)
                if len(listed) != count or len({k for k, c in listed}) != count:
                    raise ValueError('directory_count_or_duplicate_mismatch')
                controls.append(dict(지역=region, 지역코드=code, 면허=license_name, 검색건수=count,
                                     수집건수=len(listed), 출처=list_url))
                for identity, cols in listed:
                    soup, url = get_html(session, 'NR_viewCompany.do', dict(upKindcode='10', _m='41', compManageNo=identity))
                    detail = {}
                    for th in soup.select('th'):
                        td = th.find_next_sibling('td')
                        if td:
                            detail[th.get_text(' ', strip=True)] = td.get_text(' ', strip=True)
                    if compact(detail.get('상호', '')) != compact(cols[1]):
                        raise ValueError('detail_identity_mismatch')
                    if license_name not in detail.get('등록분야', ''):
                        raise ValueError('detail_license_mismatch')
                    records.append(dict(지역=region, 상호=detail.get('상호', cols[1]),
                                        주소=detail.get('주소') or cols[3], 면허종류=detail.get('등록분야') or cols[5],
                                        대표자=detail.get('대표자') or cols[2], 전화번호=detail.get('전화번호') or cols[4],
                                        최초면허취득일=detail.get('최초면허취득일') or '',
                                        등록번호=detail.get('등록번호') or '', 협회관리번호=identity, 출처=url))
                    time.sleep(.08)
    return dict(records=records, controls=controls, fetched_at=now(), fetched_epoch=time.time())


def company_data(region, state, max_age=86400):
    path = state / 'company_cache' / (region + '.json')
    cached = read_json(path)
    if cached and time.time() - cached.get('fetched_epoch', 0) < max_age:
        return cached, ''
    try:
        current = fetch_companies(region)
        atomic_json(path, current)
        return current, ''
    except Exception as exc:
        if cached:
            return cached, '조회 실패: 이전 성공 목록(%s) 사용, 재시도 대기 / %s' % (cached.get('fetched_at'), type(exc).__name__)
        return dict(records=[], controls=[], fetched_at='미조회'), '업체조회 실패: %s, 재시도 대기' % type(exc).__name__


def excel_value(value):
    # Public source fields must never become Excel formulas.
    if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def add_sheet(wb, name, headers, rows, widths):
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.worksheet.table import Table, TableStyleInfo
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    ws.append(headers)
    for row in rows:
        ws.append([excel_value(v) for v in row])
    for cell in ws[1]:
        cell.font = Font(name='맑은 고딕', color='FFFFFF', bold=True, size=10)
        cell.fill = PatternFill('solid', fgColor='263F60')
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[1].height = 32
    from openpyxl.utils import get_column_letter
    for i, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width
    for row in ws.iter_rows(min_row=2):
        height = 30
        for cell in row:
            cell.font = Font(name='맑은 고딕', size=10)
            cell.alignment = Alignment(vertical='center', wrap_text=True)
            if isinstance(cell.value, str):
                width = widths[cell.column-1]
                height = max(height, min(400, (len(cell.value)//max(12, int(width/1.4))+1)*16))
        ws.row_dimensions[row[0].row].height = height
    if rows:
        table = Table(displayName='ExportTable%d' % len(wb.worksheets), ref=ws.dimensions)
        table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=True)
        ws.add_table(table)
    ws.freeze_panes = 'A2'
    return ws


def write_workbook(path, review, companies, fetch_error, source_path):
    from openpyxl import Workbook, load_workbook
    wb = Workbook()
    wb.remove(wb.active)
    req = review['required']
    summary = [
        ('공고번호·차수', review['key']), ('공고명', review['title']),
        ('대상지역', ', '.join(review['regions'])), ('지역 적용', review['mode']),
        ('지역 의무참여비율', req if req is not None else ('해당 없음(지역제한)' if review['mode']=='지역제한' else '확인 필요')),
        ('공동이행', review['common']), ('분담이행', review['split']), ('혼합방식', review['mixed']),
        ('최소참여지분율', review['minimum'] if review['minimum'] is not None else '원문 확인 필요'),
        ('대표자 조건', review['representative']), ('배점한도', '시공경험 배점한도 적용, 경영상태 평가'),
        ('원문 검토상태', '확인 필요: ' + ' / '.join(review['issues']) if review['issues'] else '주요 조건 추출 완료'),
        ('업체조회 상태', fetch_error or ('협회 회원사 조회 %d건' % len(companies['records']))),
        ('업체조회 시각', companies['fetched_at']), ('정리 시각', review['checked_at']),
        ('업체 조회범위', '협회 회원사 공개조회. 일반(기계)·일반(전기) 면허. 0건은 지역 전체 등록업체 부재를 의미하지 않음.'),
        ('등록일 기준', '최초면허취득일(협회 공개 항목명). 주소 전입일과 다름.'),
    ]
    for label in ('게시일시', '입찰마감일시', '협정마감일시'):
        if review['metadata'].get(label):
            summary.append((label, review['metadata'][label]))
    ws = add_sheet(wb, '공고검토', ['항목', '내용'], summary, [30, 110])
    for row in ws.iter_rows(min_row=2):
        if isinstance(row[1].value, float):
            row[1].number_format = '0.0%'
    rows = []
    for b in review['basis']:
        rows.append([b['기준'], b['기계금액'], b['전기금액'], b['기계비율'], b['전기비율'], req,
                     None, None])
    ratios = add_sheet(wb, '분담비율', ['금액·비율 기준', '기계금액(원)', '전기금액(원)', '기계비율', '전기비율',
                                      '지역의무비율', '기계비율−의무비율', '전기비율−의무비율'], rows,
                       [37, 23, 23, 18, 18, 22, 27, 27])
    for r in range(2, len(rows)+2):
        for c in (2, 3):
            ratios.cell(r,c).number_format = '#,##0'
        for c in range(4,9):
            ratios.cell(r,c).number_format = '0.0%'
        if req is not None:
            ratios.cell(r,7, '=D%d-F%d' % (r,r))
            ratios.cell(r,8, '=E%d-F%d' % (r,r))
        else:
            for c in (6,7,8):
                ratios.cell(r,c,'해당 없음' if review['mode']=='지역제한' else '확인 필요')
    remarks = [
        ('비율 기준', '원문 1.8의 공종비율. 관급 포함 추정금액과 도급금액(추정가격+부가세)을 구분. 적격심사 평가비율은 별도 원문 확인.'),
        ('비율 차이 해석', '해당 공종 전부를 지역업체에 분담할 때의 단순 수치 비교. 실제 구성원의 면허·지역·최소지분·대표자 조건을 함께 검토.'),
    ]
    for b in review['basis']:
        if req is not None:
            for kind in ('기계','전기'):
                enough = b[kind+'비율'] >= req
                remarks.append((b['기준']+' / '+kind,
                    '전체 공종비율이 지역의무비율 이상' if enough else
                    '이 공종만 지역업체에 전부 분담하면 지역의무비율 미달. 혼합방식 허용 여부와 추가 지역지분 구성 검토 필요.'))
    if review['mixed']=='불허':
        remarks.append(('혼합방식', '공동+분담 혼합으로 부족 지역지분을 보완할 수 없음. 공고에서 허용한 방식으로 구성 검토.'))
    remarks += [('참가자격 원문',review['qualification']), ('공동계약 원문',review['contract']),
                ('공종금액 원문',review['table']), ('적격심사 평가비율 원문',review['evaluation']),
                ('공고 URL',review['source']), ('원문파일',str(source_path))]
    add_sheet(wb,'원문근거',['항목','내용'],remarks,[37,150])
    headers = ['지역','상호','주소','면허종류','대표자','전화번호','등록일(최초면허취득일)',
               '등록번호','협회관리번호','협회 상세 URL']
    cols = ['지역','상호','주소','면허종류','대표자','전화번호','최초면허취득일','등록번호','협회관리번호','출처']
    firms = []
    for record in companies['records']:
        values = [record.get(c, '') for c in cols]
        try:
            values[6] = dt.datetime.strptime(values[6],'%Y-%m-%d')
        except (ValueError, TypeError):
            values[6] = values[6] or '협회 미표시'
        firms.append(values)
    firms_ws = add_sheet(wb,'업체목록',headers,firms,[10,34,67,28,25,24,31,25,25,90])
    for r in range(2,len(firms)+2):
        firms_ws.cell(r,7).number_format = 'yyyy-mm-dd'
    add_sheet(wb,'조회현황',['지역','협회지역코드','면허','검색건수','수집건수','출처'],
              [[c.get(k,'') for k in ('지역','지역코드','면허','검색건수','수집건수','출처')]
               for c in companies['controls']], [12,22,24,18,18,100])
    # Atomic replace: a locked/open workbook is left intact and job stays pending.
    path = Path(path)
    fd, temp = tempfile.mkstemp(prefix='.fire_share_',suffix='.xlsx',dir=str(path.parent))
    os.close(fd)
    try:
        wb.save(temp)
        check = load_workbook(temp, read_only=True)
        if check.sheetnames != ['공고검토','분담비율','원문근거','업체목록','조회현황']:
            raise ValueError('saved_workbook_structure')
        if sum(bool(r[1]) for r in check['업체목록'].iter_rows(min_row=2,values_only=True)) != len(firms):
            raise ValueError('saved_company_count')
        check.close()
        os.replace(temp,str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def source_folders(data_root, key, row):
    folders = []
    # Only archive descendants can be exported, never arbitrary row paths.
    root = (data_root/'attachments').resolve()
    raw = row.get('첨부파일폴더')
    if raw:
        p = Path(raw).resolve()
        if p.name==key and root in p.parents and p.is_dir():
            folders.append(p)
    for p in (data_root/'attachments').glob('*/*/*/'+key):
        if p not in folders:
            folders.append(p)
    return folders


def matching_documents(folders):
    from g2b_amount_refresh import document_text, notice_document
    from g2b_score_cap import has_score_cap
    docs=[]
    for folder in folders:
        for p in sorted(folder.iterdir()):
            if p.is_file() and notice_document(p.name):
                try:
                    text=document_text(p)
                    if has_score_cap(text):
                        docs.append((p,text))
                except Exception as exc:
                    log('DOC_SOURCE_RETRY %s %s' % (folder.name,type(exc).__name__))
    return docs


def discover(data_root, state, ledger, days=30, limit=80):
    from g2b_amount_refresh import document_text, notice_document
    from g2b_score_cap import has_score_cap
    examined=0
    cutoff=dt.datetime.now(KST).date()-dt.timedelta(days=days)
    for folder in sorted((data_root/'attachments').glob('*/*/*/*'), reverse=True):
        if not folder.is_dir() or not KEY.fullmatch(folder.name):
            continue
        try:
            year,month,day = folder.parts[-4:-1]
            date=dt.date(int(re.sub(r'\D','',year)),int(re.sub(r'\D','',month)),int(re.sub(r'\D','',day)))
        except ValueError:
            continue
        if date<cutoff:
            continue
        for p in sorted(folder.iterdir()):
            if not p.is_file() or not notice_document(p.name):
                continue
            stat=p.stat()
            signature='%d:%d' % (stat.st_mtime_ns,stat.st_size)
            if ledger.setdefault('documents',{}).get(str(p))==signature:
                continue
            if examined>=limit:
                return
            examined+=1
            try:
                text=document_text(p)
                if has_score_cap(text):
                    no,order=folder.name.rsplit('-',1)
                    existing=read_json(state/'queue'/(folder.name+'.json'))
                    title=parse_notice(text,folder.name,existing)['title']
                    row={'공고번호':no,'차수':order,'공고명':title,'공고업종명':'소방시설공사업',
                         '시공경험배점한도':True,'첨부파일폴더':str(folder),'_score_cap_source':p.name}
                    q=state/'queue'/(folder.name+'.json')
                    # Discovery must not discard richer data already captured by the hook.
                    old=read_json(q)
                    for k,v in old.items():
                        if k not in ('첨부파일폴더','_score_cap_source'):
                            row[k]=v
                    enqueue(row,logger=log,state_dir=state)
                ledger['documents'][str(p)]=signature
                ledger.setdefault('document_errors',{}).pop(str(p),None)
            except ValueError as exc:
                if str(exc)=='not_fire_notice':
                    ledger['documents'][str(p)]=signature
                    ledger.setdefault('document_errors',{}).pop(str(p),None)
                else:
                    ledger.setdefault('document_errors',{})[str(p)]=dict(key=folder.name,error=str(exc)[:160],checked_at=now())
                    log('DISCOVERY_RETRY %s %s' % (folder.name,type(exc).__name__))
            except Exception as exc:
                ledger.setdefault('document_errors',{})[str(p)]=dict(key=folder.name,error=type(exc).__name__,checked_at=now())
                log('DISCOVERY_RETRY %s %s' % (folder.name,type(exc).__name__))


def process_job(queue_path, data_root, output, state, ledger, force=False):
    row=read_json(queue_path)
    key=queue_path.stem
    folders=source_folders(data_root,key,row)
    if not folders:
        raise ValueError('attachments_missing')
    # Byte digest detects same-order corrections, not just new revision numbers.
    h=hashlib.sha256(VERSION.encode())
    h.update(json.dumps(row,sort_keys=True,ensure_ascii=False).encode('utf-8'))
    for f in folders:
        for p in sorted(f.iterdir()):
            if p.is_file():
                h.update(p.name.encode('utf-8'))
                with p.open('rb') as handle:
                    for chunk in iter(lambda:handle.read(1024*1024),b''):
                        h.update(chunk)
    digest=h.hexdigest()
    previous=ledger.setdefault('jobs',{}).get(key,{})
    if not force and previous.get('digest')==digest:
        if previous.get('status')=='complete' and all(Path(p).exists() for p in previous.get('files',[])):
            return 'skipped'
        if previous.get('status')!='complete' and previous.get('next_retry',0)>time.time():
            return 'deferred'
    docs=matching_documents(folders)
    if not docs:
        raise ValueError('score_cap_source_missing')
    preferred=row.get('_score_cap_source')
    candidates=[]
    for p,text in docs:
        try:
            parsed=parse_notice(text,key,row)
            candidates.append((p,parsed))
        except ValueError:
            continue
    if not candidates:
        raise ValueError('no_usable_fire_notice_source')
    candidates.sort(key=lambda item:(len(item[1]['issues']),-len(item[1]['basis']),item[0].name!=preferred))
    source,review=candidates[0]
    complete=[r for p,r in candidates if not r['issues']]
    signatures={json.dumps({k:r[k] for k in ('regions','mode','required','common','split','mixed','basis')},sort_keys=True,ensure_ascii=False) for r in complete}
    if len(signatures)>1:
        review['issues'].append('복수 원문 사이 조건·비율 상이: 최신 공고 원문 확인 필요')
    paths=[]
    retry=[]
    company_counts=[]
    for region in review['regions']:
        if region in REGIONS:
            companies,error=company_data(region,state)
        else:
            companies,error=dict(records=[],controls=[],fetched_at='미조회'),'지역 확인 후 업체조회 필요'
        if error:
            retry.append(error)
        company_counts.append(len(companies['records']))
        target=output/region/key
        target.mkdir(parents=True,exist_ok=True)
        original=target/'원문'
        original.mkdir(exist_ok=True)
        for f in folders:
            for p in f.iterdir():
                if p.is_file():
                    destination=original/p.name
                    if not destination.exists() or hashlib.sha256(destination.read_bytes()).digest()!=hashlib.sha256(p.read_bytes()).digest():
                        shutil.copy2(str(p),str(destination))
        final=target/(key+'_소방분담.xlsx')
        write_workbook(final,review,companies,error,original/source.name)
        atomic_json(target/'검토정보.json',dict(version=VERSION,review=review,company_status=error or '성공',
                                              company_count=len(companies['records']),digest=digest))
        paths.append(str(final))
    status='retry' if retry else ('review_needed' if review['issues'] else 'complete')
    attempts=previous.get('attempts',0)+1
    ledger['jobs'][key]=dict(digest=digest,status=status,attempts=attempts,files=paths,
                             checked_at=now(),issues=review['issues'],errors=retry,
                             next_retry=time.time()+min(3600,300*2**min(attempts-1,4)))
    log('SAVED %s status=%s companies=%s regions=%s' % (key,status,
         ','.join(str(n) for n in company_counts),
         ','.join(review['regions'])))
    return status


def run(args):
    state=Path(args.state)
    state.mkdir(parents=True,exist_ok=True)
    with (state/'worker.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            log('SKIP worker already active')
            return 0
        if not os.path.ismount(args.nas_mount):
            log('RETRY NAS not mounted; queue retained')
            return 75
        data_root=Path(args.data_root)
        output=Path(args.output)
        if not (data_root/'attachments').is_dir() or not output.is_dir():
            log('RETRY expected NAS paths unavailable; queue retained')
            return 75
        ledger_path=state/'ledger.json'
        ledger=read_json(ledger_path)
        if not args.queue_only:
            discover(data_root,state,ledger,days=args.days)
        atomic_json(ledger_path,ledger)
        counts={}
        queue=state/'queue'
        queue.mkdir(exist_ok=True)
        for p in sorted(queue.glob('*.json')):
            if args.only and p.stem!=args.only:
                continue
            if not KEY.fullmatch(p.stem):
                continue
            try:
                result=process_job(p,data_root,output,state,ledger,force=args.force)
            except Exception as exc:
                previous=ledger.setdefault('jobs',{}).get(p.stem,{})
                previous.update(status='retry',error=type(exc).__name__+': '+str(exc)[:180],checked_at=now())
                ledger['jobs'][p.stem]=previous
                result='retry'
                log('RETRY %s %s' % (p.stem,type(exc).__name__))
            counts[result]=counts.get(result,0)+1
            atomic_json(ledger_path,ledger)
        status=dict(last_run=now(),version=VERSION,counts=counts,queue=str(queue),output=str(output),
                    pending=[k for k,v in ledger.get('jobs',{}).items() if v.get('status')!='complete'],
                    discovery_pending=ledger.get('document_errors',{}))
        atomic_json(state/'status.json',status)
        atomic_json(output/'자동정리_실행상태.json',status)
        log('END '+json.dumps(counts,ensure_ascii=False))
        return 0


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--state',default=str(DEFAULT_STATE))
    p.add_argument('--data-root',default='/mnt/vol1/bid/n_data')
    p.add_argument('--output',default='/mnt/vol1/소방분담')
    p.add_argument('--nas-mount',default='/mnt/vol1')
    p.add_argument('--days',type=int,default=30)
    p.add_argument('--only')
    p.add_argument('--force',action='store_true')
    p.add_argument('--queue-only',action='store_true')
    return run(p.parse_args())


if __name__=='__main__':
    sys.exit(main())
