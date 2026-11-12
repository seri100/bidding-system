#!/usr/bin/env python3
"""Authenticate a private filesystem archive and restore into marked staging only."""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess


def restore(archive, key, workspace, name, reapply=False):
    archive, key, workspace = Path(archive), Path(key), Path(workspace).resolve()
    if not workspace.name.startswith('n_data-trial-') or name not in ('root', 'home-var'):
        raise ValueError('A separate trial staging workspace is required')
    workspace.mkdir(parents=True, exist_ok=True)
    workspace.chmod(0o700)
    proof = workspace / 'trial-workspace.json'
    if proof.exists() and json.loads(proof.read_text()).get('purpose') != 'n_data_sd_trial':
        raise ValueError('Workspace purpose mismatch')
    mac = hmac.new(key.read_bytes().strip(), digestmod=hashlib.sha256)
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            mac.update(block)
    if not hmac.compare_digest(mac.hexdigest(), Path(str(archive) + '.hmac').read_text().strip()):
        raise ValueError('Archive authentication failed')
    destination = workspace / name
    if destination.is_symlink() or os.path.ismount(str(destination)) or (destination.exists() and any(destination.iterdir()) and not reapply):
        raise ValueError('Destination must be a new, empty directory')
    destination.mkdir(exist_ok=True)
    proof.write_text(json.dumps({'purpose': 'n_data_sd_trial', 'production_operations': False}))
    with (workspace / (name + '-restore.stderr')).open('wb') as errors:
        os.chmod(str(workspace / (name + '-restore.stderr')), 0o600)
        decrypt = subprocess.Popen(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2',
                                    '-iter', '200000', '-pass', 'file:' + str(key),
                                    '-in', str(archive)], stdout=subprocess.PIPE, stderr=errors)
        tar = subprocess.Popen(['tar', '--extract', '--gzip', '--numeric-owner', '--same-owner',
                                '--acls', '--xattrs', '--xattrs-include=*', '--listed-incremental=/dev/null',
                                '--file=-', '--directory=' + str(destination)],
                               stdin=decrypt.stdout, stdout=subprocess.DEVNULL, stderr=errors)
        decrypt.stdout.close()
        tar_code = tar.wait(); decrypt_code = decrypt.wait()
    if tar_code != 0 or decrypt_code != 0:
        raise RuntimeError('Filesystem archive restore failed; inspect private staging log')
    print('FILESYSTEM_STAGING_RESTORED name=%s authentication=passed' % name, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--name', choices=['root', 'home-var'], required=True)
    parser.add_argument('--reapply', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Use root only in the separate Linux staging environment')
    restore(args.archive, args.key, args.workspace, args.name, args.reapply)
