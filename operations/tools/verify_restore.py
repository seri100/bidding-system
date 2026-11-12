#!/usr/bin/env python3
"""Authenticate an encrypted recovery archive and extract to an empty staging folder.

Never writes production paths, installs services or sends notifications.
"""
import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tarfile
import tempfile


def restore(archive, key, destination):
    archive, key, destination = Path(archive), Path(key), Path(destination)
    expected = Path(str(archive) + '.hmac').read_text().strip()
    mac = hmac.new(key.read_bytes().strip(), digestmod=hashlib.sha256)
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            mac.update(block)
    if not hmac.compare_digest(mac.hexdigest(), expected):
        raise ValueError('Authentication failed: wrong key or modified archive')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Destination must be empty')
    destination.mkdir(parents=True, exist_ok=True)
    destination.chmod(0o700)
    with tempfile.TemporaryDirectory(prefix='n_data_restore_') as temp:
        plain = Path(temp) / 'verified.tar.gz'
        subprocess.check_call(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2',
                               '-iter', '200000', '-in', str(archive), '-out', str(plain),
                               '-pass', 'file:' + str(key)])
        with tarfile.open(str(plain), 'r:gz') as tar:
            members = tar.getmembers()
            for member in members:
                target = (destination / member.name).resolve()
                if destination.resolve() not in target.parents and target != destination.resolve():
                    raise ValueError('Unsafe archive path')
                if not member.isfile() and not member.isdir():
                    raise ValueError('Links and special files are not accepted')
            tar.extractall(str(destination), members=members)
    pi_manifest = destination / 'snapshot/metadata/inventory.json'
    pc_manifests = list(destination.glob('pc-*/manifest.json'))
    pc_manifest = pc_manifests[0] if len(pc_manifests) == 1 else destination / 'missing-manifest'
    if pi_manifest.exists():
        inventory = json.loads(pi_manifest.read_text())
        base, files = destination / 'snapshot', inventory['manifest']
    elif pc_manifest.exists():
        inventory = json.loads(pc_manifest.read_text(encoding='utf-8'))
        base, files = pc_manifest.parent, inventory['files']
    else:
        raise ValueError('Missing manifest')
    sqlite_count = 0
    for item in files:
        file = base / item['path']
        if hashlib.sha256(file.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError('File verification failed: ' + item['path'])
        with file.open('rb') as stream:
            signature = stream.read(16)
        if signature == b'SQLite format 3\x00':
            connection = sqlite3.connect('file:' + str(file) + '?mode=ro', uri=True)
            try:
                if connection.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('SQLite integrity failure')
                sqlite_count += 1
            finally:
                connection.close()
    print('VERIFIED files=%s sqlite=%s staging=%s' % (len(files), sqlite_count, destination))
    return len(files)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    restore(args.archive, args.key, args.destination)
