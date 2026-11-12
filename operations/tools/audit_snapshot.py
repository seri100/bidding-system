#!/usr/bin/env python3
"""Conservatively redact public review snapshots; never run on live sources."""
import argparse
import ast
import hashlib
import io
import json
import math
from pathlib import Path
import re
import tokenize

SENSITIVE = re.compile(r'(?i)(^key$|api.?key|service.?key|secret|password|passwd|pwd|(?:^|_)pass$|(?:^|_)user$|login|access.?token|refresh.?token|user.?id|operator|sender|phone|recipient)')
REFERENCE = re.compile(r'(?i)(file|path|url|name|pattern|field|label|column)$')


def suspicious(value):
    if len(value) < 25 or any(c.isspace() for c in value) or value.startswith(('http', '/', '.', 'REDACTED')):
        return False
    if not re.fullmatch(r'[A-Za-z0-9%+/_=\-]+', value) or not re.search(r'\d', value):
        return False
    entropy = -sum((value.count(c) / len(value)) * math.log2(value.count(c) / len(value)) for c in set(value))
    return entropy >= 3.7


def clean_python(text):
    tree = ast.parse(text)
    values = set()
    for node in ast.walk(tree):
        candidates = []
        if isinstance(node, ast.Assign):
            labels = [getattr(n, 'id', '') for n in node.targets]
            if any(SENSITIVE.search(n) and not REFERENCE.search(n) for n in labels):
                candidates = [node.value]
        elif isinstance(node, ast.Dict):
            candidates = [v for k, v in zip(node.keys, node.values) if isinstance(k, ast.Str) and SENSITIVE.search(k.s) and not REFERENCE.search(k.s)]
        for value in candidates:
            if isinstance(value, ast.Str) and value.s and not value.s.startswith(('/', '.', 'http', 'REDACTED')):
                values.add(value.s)
        if isinstance(node, ast.Str) and suspicious(node.s):
            values.add(node.s)
    output = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.STRING:
            try:
                value = ast.literal_eval(token.string)
            except Exception:
                value = None
            if isinstance(value, str) and value in values:
                token = token._replace(string=repr('REDACTED_PRIVATE_VALUE'))
        output.append(token)
    result = tokenize.untokenize(output)
    compile(result, '<public-snapshot>', 'exec')
    return result


def audit(root):
    changed = 0
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix not in {'.py', '.sh', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.reference'}:
            continue
        text = path.read_text(encoding='utf-8-sig')
        result = text
        if path.suffix == '.py':
            result = clean_python(result)
        else:
            result = re.sub(r'(?im)((?:\bkey|api_?key|service_?key|password|passwd|pwd|pass|user|username|secret|access_token|refresh_token|user_?id)\s*[:=]\s*[\"\'])([^\"\'\n]+)([\"\'])', r'\1REDACTED_PRIVATE_VALUE\3', result)
        result = re.sub(r'([A-Za-z][A-Za-z0-9+.-]*://)[^\s\"\'@/]+@', r'\1REDACTED_PRIVATE_VALUE@', result)
        result = re.sub(r'(?i)([?&](?:serviceKey|api_key|token|password)=)[^&\s\"\']+', r'\1REDACTED_PRIVATE_VALUE', result)
        if result != text:
            path.write_text(result, encoding='utf-8')
            changed += 1
    inventory_path = root / 'inventory.json'
    inventory = json.loads(inventory_path.read_text(encoding='utf-8'))
    for item in inventory.get('source_files', inventory.get('files', [])):
        data = (root / item['path']).read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        item['redacted'] = item.get('redacted', False) or sha != item['sha256']
        item['sha256'] = sha
    inventory['public_audit'] = 'Known config values, credential assignments, token-like literals, private keys, phone numbers, emails and credential URL parameters removed. Review snapshot; not a deployable secret configuration.'
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding='utf-8')
    print('PUBLIC_AUDIT additional_redacted_files=%s' % changed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot_directory', type=Path)
    audit(parser.parse_args().snapshot_directory)
