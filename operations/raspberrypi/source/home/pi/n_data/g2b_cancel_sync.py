# -*- coding: utf-8 -*-
"""Synchronize cancellation to tracked notices without erasing user notes."""
import html
import json
import os
import re
from pathlib import Path

START, END = '[취소공고 동기화]', '[/취소공고 동기화]'


def notice_id(text):
    text = html.unescape(re.sub(r'<[^>]+>', ' ', str(text)))
    match = re.search(r'공고번호\s*[:：]\s*(R\d{2}[A-Z]{2}\d+|\d{11})\s*-\s*(\d{1,3})(?!\d)', text)
    return (match.group(1), match.group(2).zfill(3)) if match else None


def is_cancel_message(text):
    return '[취소공고]' in str(text) or START in str(text)


def cancel_body(event, no, order):
    summary = event.get('summary', '')
    if '[취소공고]' not in summary:
        summary = '[취소공고] ' + summary
    description = event.get('description', '')
    # Repeated calls do not create duplicate blocks or discard original notes.
    marker = '취소공고번호 : %s - %s' % (no, order)
    if marker not in html.unescape(description):
        description = re.sub(re.escape(START) + r'[\s\S]*?' + re.escape(END), '', description).rstrip()
        block = ('%s\n취소공고번호 : %s - %s\n상태 : 취소공고 확인\n'
                 '취소공고URL : https://www.g2b.go.kr/link/PNPE027_01/single/'
                 '?bidPbancNo=%s&bidPbancOrd=%s\n%s') % (START, no, order, no, order, END)
        if re.search(r'<(?:p|div|br)\b', description, re.I):
            description += '<br><br>' + html.escape(block).replace('\n', '<br>')
        else:
            description += '\n\n' + block
    return {'summary': summary, 'description': description}


def sync_cancel_message(service, calendar_id, message, log=lambda x: None):
    ident = notice_id(message)
    if not ident or not is_cancel_message(message):
        raise ValueError('invalid_cancel_identity')
    no, order = ident
    token, candidates = None, []
    while True:
        result = service.events().list(calendarId=calendar_id, q=no,
            singleEvents=True, maxResults=100, pageToken=token).execute()
        for event in result.get('items', []):
            found = notice_id(event.get('description', ''))
            if (event.get('status') != 'cancelled' and found and found[0] == no
                    and int(found[1]) <= int(order)):
                candidates.append(event['id'])
        token = result.get('nextPageToken')
        if not token:
            break
    changed = 0
    for eid in dict.fromkeys(candidates):
        # Read immediately before patching; an ETag protects manual edits.
        event = service.events().get(calendarId=calendar_id, eventId=eid).execute()
        found = notice_id(event.get('description', ''))
        if not found or found[0] != no or int(found[1]) > int(order):
            continue
        body = cancel_body(event, no, order)
        if all(event.get(k, '') == v for k, v in body.items()):
            continue
        if not event.get('etag'):
            raise ValueError('missing_event_etag')
        request = service.events().patch(calendarId=calendar_id, eventId=eid, body=body)
        request.headers['If-Match'] = event['etag']
        saved = request.execute()
        if any(saved.get(k) != v for k, v in body.items()):
            raise ValueError('cancel_verification_failed')
        changed += 1
    status = 'cancel_updated' if changed else ('cancel_already_synced' if candidates else 'cancel_not_tracked')
    log('[GCAL_CANCEL][%s] %s-%s matched=%d updated=%d' % (status.upper(), no, order, len(candidates), changed))
    return status, '', candidates[0] if candidates else ''


def sync_pending_messages(messages, root, service_factory, calendar_id, log=lambda x: None, only_bid=''):
    path = Path(root) / 'state' / 'gcal_cancel_pending.json'
    pending = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    for message in messages:
        ident = notice_id(message)
        if not ident or not is_cancel_message(message):
            raise ValueError('invalid_cancel_message')
        pending['-'.join(ident)] = message
    if not pending:
        return
    def save():
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + '.tmp')
        temp.write_text(json.dumps(pending, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(str(temp), str(path))
    save()  # Keep the retry queue even if authentication/network fails below.
    service = service_factory()
    for key in list(pending):
        if only_bid and key.rsplit('-', 1)[0] != only_bid:
            continue
        try:
            sync_cancel_message(service, calendar_id, pending[key], log)
            pending.pop(key)
            save()
        except Exception as exc:
            log('[GCAL_CANCEL][RETRY] %s %s' % (key, type(exc).__name__))
