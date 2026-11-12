# -*- coding: utf-8 -*-
"""Explicit notice-document evidence for the <실태조사> calendar title tag."""
import hashlib
import json
import os
import re
import time
from pathlib import Path

TAG = '<실태조사>'


def classify(text):
    compact = re.sub(r'\s+', '', text)
    terms = r'(?:실태조사|사실조사(?:\(사전단속\))?|사전단속)'
    negative = re.search(terms + r'.{0,15}(?:대상에서제외|대상이아니|대상아님|실시하지않|비대상)', compact)
    if negative:
        return False, negative.group(0)
    patterns = [
        terms + r'(?:대상공사|대상사업|대상입니다|대상임|대상에해당)',
        terms + r'(?:를|가|는|이|을)?(?:실시되는공사|실시대상|실시합니다|실시됩니다|실시하므로|실시할예정)',
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, compact):
            context = compact[max(0, match.start()-400):match.end()+50]
            if re.search(r'본공사|이공사|해당공사|개찰최고순위|입찰1순위|낙찰예정', context):
                return True, context[-450:]
    return None, ''


def marked_title(summary):
    return summary if TAG in summary else TAG + summary


def evidence(root, no, order):
    from g2b_amount_refresh import notice_document, document_text
    root = Path(root)
    files = [f for folder in sorted((root/'attachments').glob('*/*/*/'+no+'-'+order))
             for f in sorted(folder.iterdir()) if notice_document(f.name)]
    if not files:
        return {'is_inspection': None, 'source': '', 'evidence': ''}
    sig = hashlib.sha256(json.dumps([(str(f), f.stat().st_size, f.stat().st_mtime_ns)
                                   for f in files], ensure_ascii=False).encode()).hexdigest()
    cache = root/'state'/'inspection_titles'/(no+'-'+order+'.json')
    if cache.exists():
        try:
            result = json.loads(cache.read_text())
            if result.get('signature') == sig:
                return result
        except (ValueError, OSError):
            pass
    result = {'signature': sig, 'is_inspection': None, 'source': '', 'evidence': ''}
    failures = False
    # HWPX generally gives cleaner Korean than two-column PDFs.
    files.sort(key=lambda f: (f.suffix.lower() != '.hwpx', f.name))
    for f in files[:6]:
        try:
            flag, reason = classify(document_text(f))
            if flag is not None:
                result.update(is_inspection=flag, source=f.name, evidence=reason)
                break
        except Exception:
            failures = True
    # Retry extraction errors next run; an absent keyword alone is not evidence.
    if not failures or result['is_inspection'] is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        tmp = cache.with_name(cache.name+'.tmp')
        tmp.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(str(tmp), str(cache))
    return result


def title_for_message(summary, message, root=None):
    from g2b_amount_refresh import identity, field
    key = identity(message)
    if not key or field(message, '업무구분') != '공사':
        return summary
    root = root or os.environ.get('N_DATA_BASE', '/mnt/vol1/bid/n_data')
    found = evidence(root, *key)
    return marked_title(summary) if found['is_inspection'] is True else summary


def refresh_titles(events, root, service, calendar_id, log, now, only_keys=None, limit=6):
    from g2b_amount_refresh import identity, field, date
    eligible = []
    cancelled = set()
    latest = {}
    for event in events:
        key = identity(event.get('description', ''))
        if not key:
            continue
        latest[key[0]] = max(latest.get(key[0], ''), key[1])
        if '취소공고' in event.get('summary', '') or '취소공고' in event.get('description', ''):
            cancelled.add(key[0])
    for event in events:
        text = event.get('description', '')
        key = identity(text)
        if not key or key[0] in cancelled or key[1] != latest[key[0]]:
            continue
        if event.get('status') == 'cancelled' or TAG in event.get('summary', ''):
            continue
        if only_keys and '-'.join(key) not in only_keys:
            continue
        close = date(field(text, '입찰마감일시'))
        if field(text, '업무구분') != '공사' or not close or close <= now:
            continue
        eligible.append((close, event, key))
    eligible.sort(key=lambda x: (x[0], x[1]['id']))
    updated = 0
    started = time.monotonic()
    for _, event, key in eligible:
        if updated >= limit or time.monotonic()-started > 60:
            break
        try:
            found = evidence(root, *key)
            if found['is_inspection'] is not True:
                continue
            summary = marked_title(event.get('summary', ''))
            request = service.events().patch(calendarId=calendar_id, eventId=event['id'],
                                             body={'summary': summary})
            request.headers['If-Match'] = event['etag']
            saved = request.execute()
            if saved.get('summary') != summary:
                raise ValueError('title_verification_failed')
            event.update(saved)  # Keep ETag current for subsequent amount patches.
            updated += 1
            log('[INSPECTION_TITLE][UPDATED] '+ '-'.join(key))
        except Exception as exc:
            log('[INSPECTION_TITLE][RETRY] %s %s' % ('-'.join(key), type(exc).__name__))
    return updated
