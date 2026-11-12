# -*- coding: utf-8 -*-
"""Detect the explicit construction-experience full-score condition."""
import html
import re
import unicodedata
from pathlib import Path
from g2b_amount_refresh import document_text, notice_document

def has_score_cap(text):
    text = unicodedata.normalize('NFKC', html.unescape(str(text or '')))
    text = re.sub(r'<[^>]*>', '', text)
    text = re.sub(r'[\x00-\x1f\x7f\s]+', '', text)
    return bool(re.search(
        r'시공경험(?:은|에대해서는|에대하여는|에대한평가는)'
        r'배점한도(?:를|을)?적용(?:하고|하며|합니다)[,，.。·ㆍ]*'
        r'경영상태(?:는|에대해서는|에대하여는)?평가(?:합니다|함|하며|하고|한다)',
        text))

def enrich_score_cap(row, root, log=lambda text: None):
    if row.get('_score_cap_checked'):
        return row
    no = str(row.get('공고번호') or '')
    order = str(row.get('차수') or '000').zfill(3)
    if not re.fullmatch(r'R\d{2}[A-Z]{2}\d+|\d{11}', no) or not re.fullmatch(r'\d{3}', order):
        return row
    row['시공경험배점한도'] = False
    folders = sorted((Path(root) / 'attachments').glob('*/*/*/' + no + '-' + order))
    errors = False
    for folder in folders:
        for path in sorted(folder.iterdir()):
            if not path.is_file() or not notice_document(path.name):
                continue
            try:
                if has_score_cap(document_text(path)):
                    row['시공경험배점한도'] = True
                    row['_score_cap_source'] = path.name
                    row['_score_cap_checked'] = True
                    log('[SCORE_CAP][MATCH] %s-%s source=%s' % (no, order, path.name))
                    return row
            except Exception as exc:
                errors = True
                log('[SCORE_CAP][DOC_ERROR] %s-%s %s' % (no, order, type(exc).__name__))
    row['_score_cap_checked'] = bool(folders) and not errors
    return row
