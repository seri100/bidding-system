#!/usr/bin/env python3
"""Encrypted online /home + /var pre-copy. Not a final/offline system image."""
import argparse
from datetime import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import time


def run(destination, mode="home-var"):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    private = Path('/home/pi/.config/n_data-recovery')
    key = private / 'backup.key'
    if not key.is_file():
        raise RuntimeError('Recovery key missing')
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name = mode + '-precopy-' + stamp
    sources = ['home', 'var'] if mode == 'home-var' else ['.', 'boot']
    output = destination / (name + '.tar.gz.enc')
    snapshot = private / (name + '.snar')
    log_path = private / (name + '.stderr')
    started = time.monotonic()
    with log_path.open('wb') as errors:
        tar = subprocess.Popen([
            'sudo', '-n', 'nice', '-n', '15', 'ionice', '-c', '3', '/bin/tar',
            '--one-file-system', '--acls', '--xattrs', '--numeric-owner',
            '--listed-incremental=' + str(snapshot),
            '--exclude=home/pi/.config/n_data-recovery',
            '-I', 'gzip -1', '-cf', '-', '-C', '/',
        ] + sources, stdout=subprocess.PIPE, stderr=errors)
        crypt = subprocess.Popen([
            'openssl', 'enc', '-aes-256-cbc', '-salt', '-pbkdf2', '-iter', '200000',
            '-pass', 'file:' + str(key), '-out', str(output),
        ], stdin=tar.stdout, stderr=errors)
        tar.stdout.close()
        crypt_code = crypt.wait()
        tar_code = tar.wait()
    if crypt_code != 0 or tar_code not in (0, 1):
        raise RuntimeError('Pre-copy failed; inspect private log')
    subprocess.check_call(['sudo', '-n', 'chown', '%s:%s' % (os.getuid(), os.getgid()), str(snapshot)])
    mac = hmac.new(key.read_bytes().strip(), digestmod=hashlib.sha256)
    sha = hashlib.sha256()
    with output.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            mac.update(block); sha.update(block)
    Path(str(output) + '.hmac').write_text(mac.hexdigest() + '\n')
    Path(str(output) + '.sha256').write_text(sha.hexdigest() + '\n')
    with log_path.open('ab') as errors:
        decrypt = subprocess.Popen([
            'openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-iter', '200000',
            '-pass', 'file:' + str(key), '-in', str(output),
        ], stdout=subprocess.PIPE, stderr=errors)
        listing = subprocess.Popen(['/bin/tar', '-tzf', '-'], stdin=decrypt.stdout,
                                   stdout=subprocess.PIPE, stderr=errors)
        decrypt.stdout.close()
        names, _ = listing.communicate()
        decrypt_code = decrypt.wait()
    if listing.returncode != 0 or decrypt_code != 0:
        raise RuntimeError('Pre-copy decrypt/gzip/tar verification failed')
    result = {
        'file': output.name, 'phase': 'online_pre_copy_only',
        'source_roots': (['/home', '/var'] if mode == 'home-var' else ['root filesystem only', '/boot']), 'encrypted_bytes': output.stat().st_size,
        'archive_entries': len(names.splitlines()), 'tar_exit': tar_code,
        'live_files_may_have_changed': True,
        'decryption_and_archive_check': 'passed',
        'final_quiesced_backup_required': True,
        'snapshot_metadata_private': True,
        'elapsed_seconds': int(time.monotonic() - started),
    }
    Path(str(output) + '.report.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--mode', choices=['home-var', 'root-boot'], default='home-var')
    args = parser.parse_args()
    run(args.destination, args.mode)
