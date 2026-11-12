#!/usr/bin/env python3
"""Read the original Pi SD boot prefix only; never opens a source for writing."""
from datetime import datetime
import gzip
import hashlib
import hmac
import json
import os
from pathlib import Path
import struct
import subprocess


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    source = Path('/dev/mmcblk0')
    if os.geteuid() != 0 or not source.exists():
        raise RuntimeError('Run read-only capture on the original Pi with sudo')
    root_source = subprocess.check_output(['findmnt', '-n', '-o', 'SOURCE', '--target', '/'], universal_newlines=True).strip()
    if os.path.realpath(root_source) != '/dev/mmcblk0p2':
        raise RuntimeError('Unexpected original boot/root device')
    with source.open('rb', buffering=0) as stream:
        mbr = stream.read(512)
    if mbr[510:512] != b'\x55\xaa' or mbr[446 + 16 + 4] != 0x83:
        raise RuntimeError('Unexpected Pi MBR/root partition')
    root_sector, root_sectors = struct.unpack_from('<II', mbr, 446 + 16 + 8)
    prefix_bytes, root_bytes = root_sector * 512, root_sectors * 512
    if not 16 * 1024 * 1024 <= prefix_bytes <= 1024 * 1024 * 1024:
        raise RuntimeError('Unexpected boot prefix length')
    info = subprocess.check_output(['dumpe2fs', '-h', '/dev/mmcblk0p2'], stderr=subprocess.DEVNULL, universal_newlines=True)
    fields = dict(line.split(':', 1) for line in info.splitlines() if ':' in line)
    features = [x for x in fields['Filesystem features'].split() if x != 'needs_recovery']
    destination = Path(args.destination)
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / ('boot-prefix-' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.bin.gz.enc')
    key = Path('/home/pi/.config/n_data-recovery/backup.key')
    process = subprocess.Popen(['openssl', 'enc', '-aes-256-cbc', '-salt', '-pbkdf2', '-iter', '200000',
                                '-pass', 'file:' + str(key), '-out', str(output)],
                               stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    sha = hashlib.sha256()
    with source.open('rb', buffering=0) as stream:
        with gzip.GzipFile(fileobj=process.stdin, mode='wb', compresslevel=1, mtime=0) as zipped:
            remaining = prefix_bytes
            while remaining:
                block = stream.read(min(4 * 1024 * 1024, remaining))
                if not block:
                    raise RuntimeError('Source read ended before boot prefix')
                sha.update(block); zipped.write(block); remaining -= len(block)
    process.stdin.close()
    error = process.stderr.read(); process.wait()
    if process.returncode:
        raise RuntimeError('Boot prefix encryption failed')
    verify = subprocess.Popen(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-iter', '200000',
                               '-pass', 'file:' + str(key), '-in', str(output)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    restored_sha = hashlib.sha256(); restored_bytes = 0
    with gzip.GzipFile(fileobj=verify.stdout, mode='rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            restored_sha.update(block); restored_bytes += len(block)
    verify.stdout.close(); verify.stderr.read(); verify.wait()
    if verify.returncode or restored_bytes != prefix_bytes or restored_sha.digest() != sha.digest():
        raise RuntimeError('Boot prefix decryption verification failed')
    mac = hmac.new(key.read_bytes().strip(), digestmod=hashlib.sha256)
    cipher_sha = hashlib.sha256()
    with output.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            mac.update(block); cipher_sha.update(block)
    Path(str(output) + '.hmac').write_text(mac.hexdigest() + '\n')
    Path(str(output) + '.sha256').write_text(cipher_sha.hexdigest() + '\n')
    layout = {'source_opened_read_only': True, 'boot_prefix_verified': True,
              'prefix_bytes': prefix_bytes, 'prefix_sha256': sha.hexdigest(),
              'root_partition_bytes': root_bytes,
              'disk_bytes': int(Path('/sys/block/mmcblk0/size').read_text()) * 512,
              'root_filesystem_uuid': fields['Filesystem UUID'].strip(),
              'root_filesystem_features': features,
              'root_block_size': int(fields['Block size']),
              'root_inode_count': int(fields['Inode count'])}
    Path(str(output) + '.layout.json').write_text(json.dumps(layout, indent=2))
    print(json.dumps({'file': output.name, 'boot_prefix_verified': True, 'bytes': prefix_bytes}))


if __name__ == '__main__':
    main()
