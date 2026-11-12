#!/usr/bin/env python3
"""Read-only operational snapshot; never starts a production program."""
import ast
import datetime
import hashlib
import hmac
import json
import os
import pathlib
import re
import secrets
import shutil
import sqlite3
import subprocess
import tarfile

STAMP = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
DEST = pathlib.Path('/home/pi/operations_recovery_' + STAMP)
PUBLIC = DEST / 'public'
PRIVATE = DEST / 'private'
for p in (DEST, PUBLIC, PRIVATE):
    p.mkdir(parents=True, exist_ok=True)
    p.chmod(0o700)

def command(args):
    r = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return r.stdout

def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')

units = []
roots = set(['/home/pi/n_data'])
extra = set()
unit_texts = {}
for line in command(['systemctl', 'list-unit-files', '--no-legend', '--no-pager']).splitlines():
    parts = line.split()
    if len(parts) < 2 or not parts[0].endswith(('.timer', '.service')):
        continue
    name, state = parts[:2]
    fragment = command(['systemctl', 'show', name, '-p', 'FragmentPath', '--value']).strip()
    if not fragment.startswith('/etc/systemd/system/'):
        continue
    text = command(['systemctl', 'cat', name, '--no-pager'])
    unit_texts[name] = text
    units.append({'unit': name, 'state': state, 'fragment': fragment,
                  'active': command(['systemctl', 'is-active', name]).strip()})
active_names = {x['unit'] for x in units if x['state'] == 'enabled' or x['active'] == 'active'}
for name in list(active_names):
    if name.endswith('.timer'):
        text = unit_texts.get(name, '')
        active_names.update(re.findall(r'^Unit=(\S+)', text, re.M) or [name[:-6] + '.service'])

cron = command(['crontab', '-l'])
root_cron = command(['sudo', '-n', 'crontab', '-l'])
active_text = cron + '\n' + root_cron + '\n' + '\n'.join(unit_texts.get(n, '') for n in active_names)
for match in re.findall(r'/home/pi/[A-Za-z0-9_.\-/]+', active_text):
    parts = pathlib.Path(match).parts
    if len(parts) > 4:
        roots.add('/home/pi/' + parts[3])
    elif len(parts) == 4:
        p = pathlib.Path(match)
        (roots if p.is_dir() else extra).add(match)
for match in re.findall(r'/usr/local/(?:s?bin)/[A-Za-z0-9_.\-/]+', active_text):
    extra.add(match)
extra.update(['/etc/fstab', '/usr/local/sbin/mount_bid.sh', '/home/pi/run_bid_and_sync.sh'])

roots.discard('/home/pi/.local')
roots.discard('/home/pi/logs')
SKIP = re.compile(r'(?i)(^\.?venv|^\.local$|alligoError|archive|backup|\.bak|broken|\.pre_|\.stable|\.before|__pycache__|node_modules|^venv|^\.git|^logs$|^raw|^attachments$|^dist$|^cache$|^reports?$)')
EXT = {'.py', '.sh', '.js', '.mjs', '.cjs', '.json', '.ini', '.yaml', '.yml', '.toml', '.conf', '.env', '.txt', '.db', '.sqlite', '.sqlite3', '.pickle', '.pkl', '.xlsx'}
files = set()
missing = []
for root in sorted(roots):
    if not os.path.isdir(root):
        missing.append(root)
        continue
    for d, dirs, names in os.walk(root):
        dirs[:] = [n for n in dirs if not SKIP.search(n)]
        for n in names:
            p = pathlib.Path(d) / n
            if p.is_symlink() or SKIP.search(n):
                continue
            # Extensionless checkpoints are part of recovery state too.
            # SQLite backup() captures committed state without stale sidecars.
            if n.endswith(('-wal', '-shm', '-journal')):
                continue
            state_file = any(part in {'state', 'send_history'}
                             for part in p.relative_to(root).parts[:-1])
            if p.suffix.lower() in EXT or n.startswith('.env') or state_file:
                if p.stat().st_size < 20 * 1024 * 1024:
                    files.add(str(p))
for p in extra:
    if os.path.isfile(p):
        files.add(p)
    else:
        missing.append(p)

# NAS state and sent history are essential even though they are not source code.
nas_roots = ['/mnt/vol1/bid/n_data']
for root in sorted(roots):
    candidate = '/mnt/vol1/bid/' + pathlib.Path(root).name
    if os.path.isdir(candidate) and candidate not in nas_roots:
        nas_roots.append(candidate)
for root in nas_roots:
    for sub in ['state', 'send_history']:
        for d, dirs, names in os.walk(os.path.join(root, sub)):
            dirs[:] = [n for n in dirs if not SKIP.search(n)]
            for n in names:
                p = pathlib.Path(d) / n
                if p.is_file() and not SKIP.search(n):
                    files.add(str(p))
    if os.path.isdir(root):
        for n in os.listdir(root):
            p = pathlib.Path(root) / n
            if p.is_file() and not SKIP.search(n) and (
                p.suffix in {'.db', '.sqlite', '.sqlite3', '.pickle', '.pkl', '.json'}
                or re.search(r'(?i)(sent.*\.txt|last_run|api_key)', n)):
                files.add(str(p))

manifest = []
failures = []
for src in sorted(files):
    dst = PRIVATE / src.lstrip('/')
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(src, 'rb') as f:
            signature = f.read(16)
        if signature == b'SQLite format 3\x00':
            a = sqlite3.connect('file:' + src + '?mode=ro', uri=True, timeout=20)
            b = sqlite3.connect(str(dst))
            a.backup(b)
            assert b.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
            b.close(); a.close()
        else:
            shutil.copy2(src, str(dst))
        digest = hashlib.sha256(dst.read_bytes()).hexdigest()
        manifest.append({'source': src, 'path': src.lstrip('/'), 'sha256': digest,
                         'bytes': dst.stat().st_size, 'mode': os.stat(src).st_mode & 0o777})
    except Exception as e:
        failures.append({'path': src, 'error': type(e).__name__})

# Privileged NAS and EnvironmentFile credentials are encrypted, never published.
private_refs = ['/root/.smbcredentials-bid']
for text in unit_texts.values():
    private_refs += [v.strip().strip('\"') for v in re.findall(r'^EnvironmentFile=-?([^\n]+)', text, re.M)]
known = {x['source'] for x in manifest}
for src in sorted(set(private_refs)):
    if src in known or not src.startswith('/') or any(x in src for x in ['$', '*', ' ']):
        continue
    result = subprocess.run(['sudo', '-n', 'cat', src], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        missing.append(src)
        continue
    dst = PRIVATE / src.lstrip('/')
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(result.stdout); dst.chmod(0o600)
    manifest.append({'source': src, 'path': src.lstrip('/'), 'sha256': hashlib.sha256(result.stdout).hexdigest(), 'bytes': len(result.stdout), 'mode': 0o600})
write(PRIVATE / 'metadata/root-crontab.txt', root_cron)
write(PRIVATE / 'metadata/crontab.txt', cron)
for n, t in unit_texts.items():
    write(PRIVATE / ('metadata/systemd/' + n), t)
write(PRIVATE / 'metadata/pip-freeze.txt', command(['python3', '-m', 'pip', 'freeze']))
write(PRIVATE / 'metadata/dpkg-packages.txt', command(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\n']))
inventory = {'captured_at': STAMP, 'host': 'raspberrypi', 'os': pathlib.Path('/etc/os-release').read_text(),
             'python': command(['python3', '--version']).strip(), 'roots': sorted(roots),
             'nas_roots': nas_roots, 'units': units, 'active_units': sorted(active_names),
             'missing_paths': sorted(set(missing)), 'copy_failures': failures,
             'excluded': ['raw data', 'attachments', 'logs', 'historical backups', 'large data >20MiB except state/history'],
             'manifest': manifest}
write(PRIVATE / 'metadata/inventory.json', json.dumps(inventory, ensure_ascii=False, indent=2))

# Public source is a review snapshot. Exact originals live only in encrypted backup.
# Sensitive files never enter the public tree. Gather their values to remove literals
# duplicated in scripts before token and phone/email scans.
secret_name = re.compile(r'(?i)(credential|token|secret|password|passwd|api.?key|recipient|aligo|alligo|settings|company|companies|\.env|id_rsa|id_ed25519)')
secret_values = set()
def leaves(v):
    if isinstance(v, dict):
        for x in v.values(): leaves(x)
    elif isinstance(v, list):
        for x in v: leaves(x)
    elif isinstance(v, str) and len(v) >= 8:
        secret_values.add(v)
for item in manifest:
    p = PRIVATE / item['path']
    if secret_name.search(p.name) and p.suffix not in {'.py', '.sh', '.js', '.mjs', '.cjs'}:
        try:
            text = p.read_text(encoding='utf-8')
            try: leaves(json.loads(text))
            except Exception:
                for l in text.splitlines():
                    if '=' in l:
                        v = l.split('=', 1)[1].strip().strip('\"\'')
                        if len(v) >= 8: secret_values.add(v)
                if len(text.strip()) >= 24 and len(text.splitlines()) == 1:
                    secret_values.add(text.strip())
        except Exception: pass

phone = re.compile(r'(?<!\d)(?:\+82[- ]?10|010)[- ]?\d{3,4}[- ]?\d{4}(?!\d)')
email = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
key_pattern = re.compile(r'(?i)(?:^key$|api.?key|secret|password|passwd|pwd|user.?id|access.?token|refresh.?token|service.?key|operator|sender|phone|recipient)')
public_files = []
withheld = []
for item in manifest:
    src = item['source']; p = PRIVATE / item['path']
    if p.suffix not in {'.py', '.sh', '.js', '.mjs', '.cjs'} and p.name != 'requirements.txt':
        continue
    text = p.read_text(encoding='utf-8-sig', errors='replace')
    original = text
    for value in sorted(secret_values, key=len, reverse=True):
        text = text.replace(value, 'REDACTED_PRIVATE_VALUE')
    # Catch Python credentials hard-coded under otherwise neutral file names.
    if p.suffix == '.py':
        try:
            tree = ast.parse(text)
            spans = []
            lines = text.splitlines(True)
            offsets = [0]
            for l in lines: offsets.append(offsets[-1] + len(l))
            for node in ast.walk(tree):
                values = []
                if isinstance(node, ast.Assign):
                    label = ' '.join(getattr(t, 'id', '') for t in node.targets)
                    if key_pattern.search(label): values = [node.value]
                elif isinstance(node, ast.Dict):
                    values = [v for k, v in zip(node.keys, node.values) if isinstance(k, ast.Str) and key_pattern.search(k.s)]
                for value in values:
                    if isinstance(value, ast.Str) and len(value.s) >= 8 and not any(x in value.s for x in ['/', '$', '{', ' ', '\n']) and not value.s.startswith('REDACTED'):
                        text = text.replace(repr(value.s), repr('REDACTED_PRIVATE_VALUE'))
                        text = text.replace('"' + value.s + '"', '"REDACTED_PRIVATE_VALUE"')
        except Exception: pass
    text = phone.sub('REDACTED_PHONE', text)
    text = email.sub('redacted@example.invalid', text)
    text = re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----.*?-----END [^-]*PRIVATE KEY-----', 'REDACTED_PRIVATE_KEY', text, flags=re.S)
    # Generic assignment strings in shell/JS and high-entropy credential strings.
    text = re.sub(r'(?im)((?:api_?key|service_?key|password|passwd|secret|access_token|refresh_token)\s*[:=]\s*[\"\'])([^\"\'\n]{12,})([\"\'])', r'\1REDACTED_PRIVATE_VALUE\3', text)
    text = re.sub(r'(?<=[\"\'])[A-Za-z0-9%+/_=\-]{48,}(?=[\"\'])', 'REDACTED_LONG_LITERAL', text)
    if p.suffix == '.py':
        try: compile(text, str(p), 'exec')
        except Exception:
            withheld.append(src); continue
    target = 'source/' + item['path']
    write(PUBLIC / target, text)
    public_files.append({'source': src, 'path': target, 'redacted': text != original,
                         'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()})

safe_inventory = dict(inventory)
safe_inventory.pop('manifest')
safe_inventory['source_files'] = public_files
safe_inventory['withheld_source_files'] = withheld
safe_inventory['snapshot_kind'] = 'Sanitized review source; encrypted originals required for exact restore'
write(PUBLIC / 'inventory.json', json.dumps(safe_inventory, ensure_ascii=False, indent=2))
write(PUBLIC / 'requirements-observed.txt', (PRIVATE / 'metadata/pip-freeze.txt').read_text())
# Schedule snapshots contain only selected non-secret directives.
for name, text in unit_texts.items():
    safe = '\n'.join(l for l in text.splitlines() if l.startswith(('[', '# /', 'Description=', 'User=', 'Group=', 'WorkingDirectory=', 'ExecStart=', 'OnCalendar=', 'Unit=', 'Persistent=', 'WantedBy=', 'Type=', 'EnvironmentFile=', 'After=', 'Requires=', 'AccuracySec='))) + '\n'
    safe = phone.sub('REDACTED_PHONE', email.sub('redacted@example.invalid', safe))
    if re.search(r'(?i)(password|token|secret|api.?key)=', safe):
        safe = '\n'.join(l for l in safe.splitlines() if not re.search(r'(?i)(password|token|secret|api.?key)=', l)) + '\n'
    write(PUBLIC / ('schedules/' + name + '.reference'), safe)
write(PUBLIC / 'crontab.reference', phone.sub('REDACTED_PHONE', email.sub('redacted@example.invalid', cron)))

key_dir = pathlib.Path('/home/pi/.config/n_data-recovery')
key_dir.mkdir(parents=True, exist_ok=True); key_dir.chmod(0o700)
key = key_dir / 'backup.key'
if not key.exists():
    key.write_text(secrets.token_hex(32) + '\n'); key.chmod(0o600)
archive = DEST / 'private.tar.gz'
with tarfile.open(str(archive), 'w:gz') as t:
    t.add(str(PRIVATE), arcname='snapshot')
encrypted = DEST / ('raspberrypi_' + STAMP + '.tar.gz.enc')
subprocess.check_call(['openssl', 'enc', '-aes-256-cbc', '-salt', '-pbkdf2', '-iter', '200000', '-in', str(archive), '-out', str(encrypted), '-pass', 'file:' + str(key)])
mac = hmac.new(key.read_bytes().strip(), encrypted.read_bytes(), hashlib.sha256).hexdigest()
write(pathlib.Path(str(encrypted) + '.hmac'), mac + '\n')
write(pathlib.Path(str(encrypted) + '.sha256'), hashlib.sha256(encrypted.read_bytes()).hexdigest() + '\n')
# Verify decrypt + all archived manifest hashes without modifying live directories.
verify_tar = DEST / 'verify.tar.gz'
subprocess.check_call(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-iter', '200000', '-in', str(encrypted), '-out', str(verify_tar), '-pass', 'file:' + str(key)])
with tarfile.open(str(verify_tar), 'r:gz') as t:
    for item in manifest:
        assert hashlib.sha256(t.extractfile('snapshot/' + item['path']).read()).hexdigest() == item['sha256']
archive.unlink(); verify_tar.unlink()
shutil.rmtree(str(PRIVATE))
subprocess.check_call(['tar', '-czf', str(DEST / 'public.tar.gz'), '-C', str(PUBLIC), '.'])
print(json.dumps({'destination': str(DEST), 'sources': len(public_files), 'private_files': len(manifest), 'withheld': len(withheld), 'failures': failures, 'roots': sorted(roots), 'missing': sorted(set(missing)), 'verified': True}, ensure_ascii=True))
