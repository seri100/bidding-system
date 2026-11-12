# -*- coding: utf-8 -*-
"""Late-published G2B amounts. Python 3.7; no messaging or event creation.

Existing calendar events are the durable work queue, including notices outside
the collection window. Only amount fields and our own status block are patched.
"""
import datetime as dt
import html
import json
import os
import re
import struct
import subprocess
import time
import zipfile
import zlib
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from xml.etree import ElementTree as ET

KST = dt.timezone(dt.timedelta(hours=9))
LABELS = ('기초금액', '순공사원가', 'A값')
BASE = 'https://apis.data.go.kr/1230000/ad/BidPublicInfoService/'
COMPONENTS = ('mrfnHealthInsrprm', 'npnInsrprm', 'odsnLngtrmrcprInsrprm',
              'rtrfundNon', 'sftyMngcst', 'sftyChckMngcst', 'qltyMngcst')
BLOCK_START, BLOCK_END = '[금액 재확인]', '[/금액 재확인]'


def integer(value):
    text = str(value if value is not None else '').strip().replace(',', '')
    if not re.fullmatch(r'\d+(?:\.0+)?', text):
        return None
    return int(text.split('.')[0])


def date(value):
    text = str(value or '').strip()
    if not text:
        return None
    try:
        value = dt.datetime.fromisoformat(text.replace('/', '-').replace('Z', '+00:00'))
        return value.replace(tzinfo=KST) if value.tzinfo is None else value.astimezone(KST)
    except ValueError:
        return None


def plain(text):
    text = re.sub(r'<(?:br\b[^>]*|/p|/div|/tr)>', '\n', str(text), flags=re.I)
    return html.unescape(re.sub(r'<[^>]+>', '', text)).replace('\xa0', ' ')


def field(text, label):
    text = re.sub(r'(?<=원)(?=(?:A값|참가지역)\s*[:：])', ' ', plain(text))
    labels = ('공고명', '입찰서접수개시일시', '입찰마감일시', '업무구분',
              '기초금액', '순공사원가', 'A값', '참가지역', '공동도급지역',
              '공고번호', '발주기관', '업종', '낙찰방법', '상세URL',
              '확인시각', '출처')
    # __BASIS_FIELD_BOUNDARY_V2__

    labels = labels + (

        '협정마감일시', '입찰서접수마감일시',

        '추정가격', '추정금액',

    )

    boundary = '|'.join(re.escape(k) for k in labels)
    m = re.search(r'(?<!\S)' + re.escape(label) + r'\s*[:：]\s*(.*?)'
                  + r'(?=\s+(?:' + boundary + r')\s*[:：]|\s*\[금액 재확인\]|$)',
                  text, re.S)
    value = m.group(1).strip() if m else ''

    # 업무구분 아래의 사용자 메모를 업무구분에 포함하지 않는다.

    if label == '업무구분' and value:

        value = value.splitlines()[0].strip()

    return value


def identity(text):
    m = re.fullmatch(r'(R\d{2}[A-Z]{2}\d+|\d{11})\s*-\s*(\d{1,3})', field(text, '공고번호'))
    return (m.group(1), m.group(2).zfill(3)) if m else None


def message_amounts(text):
    out = {}
    for label in LABELS:
        m = re.fullmatch(r'([\d,]+)\s*(?:원)?', field(text, label))
        if m:
            out[label] = integer(m.group(1))
    return out


def complete(amounts):
    return all(k in amounts and amounts[k] is not None and
               (amounts[k] > 0 or k == 'A값') for k in LABELS)


def exact_item(items, bid_no, bid_ord):
    matched = [r for r in items if str(r.get('bidNtceNo', '')).strip() == bid_no
               and str(r.get('bidNtceOrd', '')).strip().isdigit()
               and str(r.get('bidNtceOrd', '')).strip().zfill(3) == bid_ord]
    if not matched:
        return {}
    # Multiple classification rows must not be silently mixed.
    if len(matched) > 1 and len({json.dumps(r, sort_keys=True) for r in matched}) > 1:
        raise ValueError('ambiguous_classifications')
    return matched[0]


def api_amounts(detail):
    out, sources = {}, {}
    aliases = {'기초금액': ('bssamt', 'bsisAmount'),
               '순공사원가': ('bssAmtPurcnstcst', 'bssamtPurcnstcst'),
               'A값': ('AValue', 'aValue', 'avalue', 'aAmt')}
    for label, keys in aliases.items():
        for key in keys:
            n = integer(detail.get(key))
            if n is not None and (n > 0 or label == 'A값'):
                out[label], sources[label] = n, '공사기초금액 API/' + key
                break
    # Only sum the seven explicitly published A components when applicability
    # is Y and every required field exists. Never treat missing as zero.
    if 'A값' not in out and detail.get('bidPrceCalclAYn') == 'Y':
        keys = COMPONENTS
        values = [integer(detail.get(k)) for k in keys]
        quality_flag = detail.get('qltyMngcstAObjYn')
        if quality_flag in ('Y', 'N') and all(v is not None for v in values):
            if quality_flag == 'N':
                values[-1] = 0
            out['A값'] = sum(values)
            sources['A값'] = '공사기초금액 API/공개된 A 적용항목 합계'
    return out, sources


def document_amounts(text):
    """Read explicit money labels and explicitly printed A total tables.

    Reject percentages, formulas and multiple conflicting candidate amounts.
    """
    candidates = {k: set() for k in LABELS}
    labels = {'기초금액': r'(?:예비가격\s*)?기초\s*금액',
              '순공사원가': r'(?:기초금액\s*중\s*)?순\s*공사\s*원가',
              'A값': r'A\s*값'}
    for key, pattern in labels.items():
        for m in re.finditer(pattern + r'\s*(?:[:：=]|은|는)?\s*(?:금\s*)?([\d,]{4,})\s*원', text, re.I):
            n = integer(m.group(1))
            if n and n >= 1000:
                candidates[key].add(n)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        # Some notices print five applicable components, others seven. Read
        # the printed total, never synthesize a total omitted by the notice.
        context = '\n'.join(lines[max(0, i-10):i+1])
        compact = re.sub(r'\s+', '', context)
        if not (re.search(r'A값', compact, re.I) and all(w in compact for w in
                ('국민건강', '국민연금', '요양보험', '퇴직공제', '보건관리'))):
            continue
        for row in lines[i+1:i+5]:
            nums = re.findall(r'(?<![\d.])(?:\d{1,3}(?:,\d{3})+|0)(?![\d.%])', row)
            # This checks a printed total rather than synthesizing an absent A.
            explicit_total = bool(re.search(r'(?:합계|소계|계)\(?A값\)?', compact, re.I))
            if len(nums) == 8 or (explicit_total and len(nums) in (6, 7)):
                vals = [integer(x) for x in nums]
                if vals[0] > 0 and vals[0] == sum(vals[1:]):
                    candidates['A값'].add(vals[0])
                elif vals[-1] > 0 and vals[-1] == sum(vals[:-1]):
                    candidates['A값'].add(vals[-1])
    return {k: next(iter(v)) for k, v in candidates.items() if len(v) == 1}


def document_text(path):
    path = Path(path)
    if path.stat().st_size > 25 * 1024 * 1024:
        raise ValueError('document_too_large')
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        return subprocess.check_output(['pdftotext', '-layout', str(path), '-'],
                                       stderr=subprocess.DEVNULL, timeout=20).decode('utf-8', 'replace')
    if suffix in ('.hwpx', '.docx'):
        with zipfile.ZipFile(str(path)) as z:
            names = [n for n in z.namelist() if re.fullmatch(r'Contents/section\d+\.xml', n)
                     or n == 'word/document.xml']
            if sum(z.getinfo(n).file_size for n in names) > 30 * 1024 * 1024:
                raise ValueError('expanded_document_too_large')
            parts = []
            for n in sorted(names):
                root = ET.fromstring(z.read(n))
                for e in root.iter():
                    if e.tag.rsplit('}', 1)[-1] == 'p':
                        parts.append(''.join(e.itertext()))
                    if e.tag.rsplit('}', 1)[-1] == 'tr':
                        cells = [c for c in e if c.tag.rsplit('}', 1)[-1] == 'tc']
                        parts.append(' | '.join(''.join(c.itertext()) for c in cells))
            return '\n'.join(parts)
    if suffix == '.hwp':
        import olefile
        with olefile.OleFileIO(str(path)) as ole:
            header = ole.openstream('FileHeader').read()
            compressed = bool(header[36] & 1)
            parts = []
            for entry in sorted(ole.listdir()):
                if len(entry) != 2 or entry[0] != 'BodyText' or not entry[1].startswith('Section'):
                    continue
                data = ole.openstream(entry).read()
                if compressed:
                    dec = zlib.decompressobj(-15)
                    data = dec.decompress(data, 30 * 1024 * 1024)
                    if not dec.eof:
                        raise ValueError('expanded_document_too_large')
                pos = 0
                while pos + 4 <= len(data):
                    head = struct.unpack_from('<I', data, pos)[0]
                    tag, size = head & 1023, head >> 20
                    pos += 4
                    if size == 4095:
                        size = struct.unpack_from('<I', data, pos)[0]
                        pos += 4
                    if tag == 67:
                        parts.append(data[pos:pos+size].decode('utf-16le', 'replace'))
                    pos += size
            return '\n'.join(parts)
    return ''


def notice_document(name):
    return Path(name).suffix.lower() in ('.pdf', '.hwpx', '.hwp', '.docx') and any(
        word in name for word in ('공고', '입찰설명', '견적제출', '견적 제출'))


def read_documents(raw, root, bid_no, bid_ord, log=lambda x: None):
    """Use only exact-notice archive files and notice-specific official URLs."""
    folder_candidates = sorted((Path(root) / 'attachments').glob('*/*/*/' + bid_no + '-' + bid_ord))
    files = [p for folder in folder_candidates for p in sorted(folder.iterdir()) if notice_document(p.name)]
    candidates = {}
    for i in range(1, 21):
        name = str(raw.get('ntceSpecFileNm%d' % i) or '')
        url = str(raw.get('ntceSpecDocUrl%d' % i) or '')
        if notice_document(name) and url:
            candidates[name] = url
    # Prefer the archived original. If absent, download only identified notice docs.
    existing_names = {p.name for p in files}
    missing = [(n, u) for n, u in candidates.items() if n not in existing_names]
    if missing:
        import requests
        day = date(raw.get('bidNtceDt'))
        if day:
            folder = Path(root) / 'attachments' / ('%04d년' % day.year) / ('%02d월' % day.month) / ('%02d일' % day.day) / (bid_no + '-' + bid_ord)
            folder.mkdir(parents=True, exist_ok=True)
            for name, url in missing[:3]:
                u, q = urlparse(url), parse_qs(urlparse(url).query)
                if u.scheme != 'https' or u.hostname not in ('www.g2b.go.kr', 'g2b.go.kr'):
                    continue
                if q.get('bidPbancNo') != [bid_no] or q.get('bidPbancOrd') != [bid_ord]:
                    continue
                name = re.sub(r'[\\/<>:"|?*\x00]', '_', name)[:220]
                target = folder / name
                part = target.with_name(target.name + '.amount-part')
                try:
                    with requests.get(url, timeout=(8, 20), stream=True) as response:
                        response.raise_for_status()
                        if urlparse(response.url).hostname not in ('www.g2b.go.kr', 'g2b.go.kr'):
                            raise ValueError('unexpected_redirect')
                        size = 0
                        with part.open('wb') as h:
                            for chunk in response.iter_content(65536):
                                size += len(chunk)
                                if size > 25 * 1024 * 1024:
                                    raise ValueError('document_too_large')
                                h.write(chunk)
                    os.replace(str(part), str(target))
                    files.append(target)
                except Exception as e:
                    log('[BASIS_REFRESH][DOC_ERROR] %s-%s %s' % (bid_no, bid_ord, type(e).__name__))
                    if part.exists():
                        part.unlink()
    values, sources, conflicts = {}, {}, set()
    for path in files[:6]:
        try:
            extracted = document_amounts(document_text(path))
            for label, amount in extracted.items():
                if label in values and values[label] != amount:
                    conflicts.add(label)
                values[label], sources[label] = amount, '공고문/' + path.name
        except Exception as e:
            log('[BASIS_REFRESH][DOC_ERROR] %s-%s %s' % (bid_no, bid_ord, type(e).__name__))
    for label in conflicts:
        values.pop(label, None)
        sources.pop(label, None)
    return values, sources


def resolve(detail, raw, root, bid_no, bid_ord, log=lambda x: None):
    amounts, sources = api_amounts(detail)
    if not complete(amounts):
        docs, doc_sources = read_documents(raw, root, bid_no, bid_ord, log)
        for label, n in docs.items():
            if label not in amounts:
                amounts[label], sources[label] = n, doc_sources[label]
    return amounts, sources


def enrich_row(row, detail, root, log=lambda x: None):
    no, order = str(row.get('공고번호') or ''), str(row.get('차수') or '000').zfill(3)
    if not re.fullmatch(r'R\d{2}[A-Z]{2}\d+|\d{11}', no):
        return row
    raw = row.get('원문') if isinstance(row.get('원문'), dict) else {}
    if detail and exact_item([detail], no, order) != detail:
        detail = {}
    amounts, sources = resolve(detail, raw, root, no, order, log)
    # A list budget or an unverified previous value must never survive here.
    row['기초금액'] = amounts.get('기초금액', 0)
    for k, v in amounts.items():
        row[k] = v
    row['_basis_amount_sources'] = sources
    return row


def update_description(original, amounts, sources, pending, stamp):
    result = original
    separator = '<br>' if re.search(r'<br\b', original, re.I) else '\n'
    for label in LABELS:
        value = ('%s원' % format(amounts[label], ',')) if label in amounts else '미공개/확인 필요'
        pattern = (r'(' + re.escape(label) + r'\s*[:：]\s*)'
                   r'(?:[\d,]+[ \t]*원?|미공개/확인 필요|미확인|미공개)')
        hits = list(re.finditer(pattern, result))
        if len(hits) > 1:
            raise ValueError('ambiguous_amount_labels')
        if hits:
            result = re.sub(pattern, lambda m: m.group(1) + value, result, count=1)
        else:
            result += separator + label + ' : ' + value
    result = re.sub(r'\[금액 재확인\][\s\S]*?\[/금액 재확인\]', '', result).rstrip()
    source_text = '; '.join('%s=%s' % (k, sources[k]) for k in LABELS if k in sources)
    status = '미공개/확인 필요: ' + ', '.join(k for k in LABELS if k not in amounts) if pending else '금액 확인 완료'
    block = [BLOCK_START, status, '확인시각 : ' + stamp, '출처 : ' + source_text, BLOCK_END]
    return result + separator + separator.join(html.escape(x) if separator == '<br>' else x for x in block)


def list_events(service, calendar_id, now):
    start = (now - dt.timedelta(days=60)).replace(hour=0, minute=0, second=0, microsecond=0)
    end = now + dt.timedelta(days=120)
    token = None
    events = []
    while True:
        result = service.events().list(calendarId=calendar_id, timeMin=start.isoformat(),
                                       timeMax=end.isoformat(), singleEvents=True,
                                       maxResults=250, pageToken=token).execute()
        events.extend(result.get('items', []))
        token = result.get('nextPageToken')
        if not token:
            return events


def run(api_key, request_items, root, service, calendar_id, log=lambda x: None,
        now=None, dry_run=False, limit=6, only_keys=None, target_filter=None):
    """No event creation, messaging, date changes, reminders or attendee writes."""
    now = now or dt.datetime.now(KST)
    if target_filter is None:
        raise ValueError('target_filter_required')
    state_path = Path(root) / 'state' / 'basis_refresh.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'events': {}}
    entries = state['events']
    scanned = list_events(service, calendar_id, now)
    # Inspection title tagging also runs for notices with complete amounts.
    if not dry_run:
        from g2b_inspection import refresh_titles
        refresh_titles(scanned, root, service, calendar_id, log, now, only_keys=only_keys)
    cancelled = set()
    latest_order = {}
    for event in scanned:
        key = identity(event.get('description', ''))
        if key:
            latest_order[key[0]] = max(latest_order.get(key[0], ''), key[1])
        if key and ('취소공고' in plain(event.get('description', '')) or '취소공고' in event.get('summary', '')):
            cancelled.add(key[0])
    candidates, excluded, future, scope_excluded = [], 0, 0, 0
    for event in scanned:
        text = event.get('description', '')
        ident = identity(text)
        if not ident or event.get('status') == 'cancelled' or ident[0] in cancelled:
            continue
        if ident[1] != latest_order[ident[0]]:
            continue
        if field(text, '업무구분') != '공사' or '[입찰개시]' not in plain(text):
            continue
        key = '-'.join(ident)
        if only_keys and key not in only_keys:
            continue
        begin = date(field(text, '입찰서접수개시일시'))
        close = date(field(text, '입찰마감일시'))
        if not begin or not close or close <= now:
            continue
        event_begin = date(event.get('start', {}).get('dateTime'))
        if not event_begin or event_begin != begin:
            log('[BASIS_REFRESH][SKIP_DATE_MISMATCH] ' + key)
            continue
        # The requested trigger is the opening DATE, including evening openings.
        previous = entries.get(event['id'], {})
        last = date(previous.get('last_attempt'))
        if (previous.get('status') == 'excluded_industry' and last
                and last.date() == now.date()):
            scope_excluded += 1
            continue
        # Only today's successful API verification can defer a complete event.
        verified = previous.get('sources', {})
        if (previous.get('status') == 'complete' and last
                and last.date() == now.date()
                and previous.get('amounts') == message_amounts(text)
                and all(str(verified.get(k, '')).startswith('공사기초금액 API/')
                        for k in LABELS)):
            excluded += 1
            continue
        if last and (now-last).total_seconds() < 850:
            continue
        candidates.append((previous.get('last_attempt', ''), begin, event, ident))
    # Today's opening notices take priority over older unresolved notices.
    candidates.sort(key=lambda x: (x[1].date() != now.date(), x[0], x[1], x[2]['id']))
    stats = {'scanned': len(scanned), 'excluded_complete': excluded, 'future_pending': future,
             'due': len(candidates), 'attempted': 0, 'updated': 0, 'resolved': 0, 'errors': 0,
             'excluded_industry': scope_excluded, 'unknown_industry': 0,
             'dry_run': dry_run, 'results': []}
    started = time.monotonic()
    for _, begin, event, (no, order) in candidates[:limit]:
        if time.monotonic()-started > 150:
            break
        key, eid = no + '-' + order, event['id']
        stats['attempted'] += 1
        entry = {'key': key, 'last_attempt': now.isoformat(), 'status': 'pending'}
        try:
            params = {'serviceKey': api_key, 'pageNo': 1, 'numOfRows': 100,
                      'inqryDiv': 2, 'bidNtceNo': no, 'bidNtceOrd': order, 'type': 'json'}
            raw = exact_item(request_items(BASE+'getBidPblancListInfoCnstwk', params, timeout=20), no, order)
            if not raw:
                raise ValueError('notice_identity_not_found')
            if '취소' in str(raw.get('ntceKindNm', '')):
                entry['status'] = 'cancelled'
                entries[eid] = entry
                continue
            decision, reason = target_filter(raw)
            if decision not in ('target', 'excluded', 'unknown'):
                raise ValueError('invalid_target_filter_result')
            if decision != 'target':
                entry.update(status='excluded_industry' if decision == 'excluded'
                             else 'pending_industry', reason=reason)
                stats['excluded_industry' if decision == 'excluded' else 'unknown_industry'] += 1
                entries[eid] = entry
                log('[BASIS_REFRESH][%s] %s reason=%s' % (
                    entry['status'].upper(), key, reason))
                continue
            if date(raw.get('bidBeginDt')) != begin or date(raw.get('bidClseDt')) != date(field(event['description'], '입찰마감일시')):
                raise ValueError('notice_schedule_changed')
            detail = exact_item(request_items(BASE+'getBidPblancListInfoCnstwkBsisAmount', params, timeout=20), no, order)
            values, sources = resolve(detail, raw, root, no, order, log)
            # Keep previously disclosed amounts if the API/document omitted them.
            old = message_amounts(event['description'])
            merged = dict(values)
            pending = not complete(merged)
            stamp = now.strftime('%Y-%m-%d %H:%M KST')
            description = update_description(event['description'], merged, sources, pending, stamp)
            if description != event['description']:
                if not dry_run:
                    # ETag guards against overwriting a simultaneous manual note.
                    req = service.events().patch(calendarId=calendar_id, eventId=eid,
                                                  body={'description': description})
                    req.headers['If-Match'] = event['etag']
                    saved = req.execute()
                    if saved.get('description') != description:
                        raise ValueError('calendar_verification_failed')
                stats['updated'] += 1
            if not pending:
                stats['resolved'] += 1
            entry.update(status='pending' if pending else 'complete', amounts=merged, sources=sources,
                         basis_open_dt=detail.get('bssamtOpenDt', ''), notice_dt=raw.get('bidNtceDt', ''))
            stats['results'].append({'key': key, 'amounts': merged, 'status': entry['status']})
            log('[BASIS_REFRESH][%s] %s base=%s pure=%s A=%s' % (
                'DRY_RUN' if dry_run else entry['status'].upper(), key,
                merged.get(LABELS[0]), merged.get(LABELS[1]), merged.get(LABELS[2])))
        except Exception as exc:
            stats['errors'] += 1
            entry.update(status='retry', error=type(exc).__name__ + ':' + str(exc)[:100]
                         if isinstance(exc, ValueError) else type(exc).__name__)
            log('[BASIS_REFRESH][RETRY] %s %s' % (key, entry['error']))
        entries[eid] = entry
    if not dry_run:
        # State contains only public notice identity, amounts and retry status.
        keep = {e['id'] for e in scanned}
        state['events'] = {k: v for k, v in entries.items() if k in keep}
        state['last_run'] = now.isoformat()
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = state_path.with_name(state_path.name + '.tmp')
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(str(tmp), str(state_path))
    log('[BASIS_REFRESH][SUMMARY] ' + json.dumps({k: v for k, v in stats.items() if k != 'results'}, sort_keys=True))
    return stats
