#!/usr/bin/env python3
"""Build a regular SD image file from authenticated staging, without device mounts."""
import argparse
import gzip
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess

from isolate_trial_root import prepare, validate_tree


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            sha.update(block)
    return sha.hexdigest()


def build(workspace, prefix, key):
    workspace, prefix, key = Path(workspace).resolve(), Path(prefix), Path(key)
    root = validate_tree(workspace)
    home_var = workspace / 'home-var'
    if not (root / 'etc/fstab').is_file() or not (home_var / 'home/pi/n_data/main_send.py').is_file():
        raise ValueError('Both authenticated filesystem staging trees are required')
    for name in ['home', 'var']:
        source, destination = home_var / name, root / name
        if source.is_symlink() or destination.is_symlink():
            raise ValueError('Filesystem roots must be real staging directories')
        destination.mkdir(exist_ok=True)
        subprocess.check_call(['rsync', '-aHAX', '--numeric-ids', '--delete', str(source) + '/', str(destination) + '/'])
    isolation = prepare(workspace)
    subprocess.check_call(['sh', '-n', str(root / 'usr/local/sbin/n-data-trial-isolation')])
    layout = json.loads(Path(str(prefix) + '.layout.json').read_text())
    mac = hmac.new(key.read_bytes().strip(), digestmod=hashlib.sha256)
    with prefix.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            mac.update(block)
    if not hmac.compare_digest(mac.hexdigest(), Path(str(prefix) + '.hmac').read_text().strip()):
        raise ValueError('Boot prefix authentication failed')
    image = workspace / 'trial.img'
    if image.exists():
        raise ValueError('Trial image already exists')
    process = subprocess.Popen(['openssl', 'enc', '-d', '-aes-256-cbc', '-pbkdf2', '-iter', '200000',
                                '-pass', 'file:' + str(key), '-in', str(prefix)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    prefix_sha = hashlib.sha256(); count = 0
    with image.open('xb') as output:
        image.chmod(0o600)
        with gzip.GzipFile(fileobj=process.stdout, mode='rb') as source:
            for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
                output.write(block); prefix_sha.update(block); count += len(block)
    process.stdout.close(); process.stderr.read(); process.wait()
    if process.returncode or count != layout['prefix_bytes'] or prefix_sha.hexdigest() != layout['prefix_sha256']:
        raise ValueError('Boot prefix content verification failed')
    with image.open('r+b') as output:
        mbr = output.read(512)
        start, sectors = struct.unpack_from('<II', mbr, 446 + 16 + 8)
        if start * 512 != count or sectors * 512 != layout['root_partition_bytes']:
            raise ValueError('MBR and partition layout mismatch')
        disk_bytes = layout['disk_bytes']
        if not count + sectors * 512 <= disk_bytes <= 64 * 1024 ** 3:
            raise ValueError('Unexpected original image size')
        output.truncate(disk_bytes)
    filesystem = workspace / 'rootfs.ext4'
    if filesystem.exists():
        raise ValueError('Filesystem image already exists')
    with filesystem.open('xb') as output:
        output.truncate(layout['root_partition_bytes'])
    filesystem.chmod(0o600)
    features = ['none'] + layout['root_filesystem_features']
    command = ['mke2fs', '-q', '-F', '-t', 'ext4', '-O', ','.join(features),
               '-b', str(layout['root_block_size']), '-N', str(layout['root_inode_count']),
               '-I', '256', '-m', '1', '-U', layout['root_filesystem_uuid'], '-L', 'rootfs',
               '-E', 'lazy_itable_init=0,lazy_journal_init=0', '-d', str(root), str(filesystem)]
    with (workspace / 'image-build.stderr').open('wb') as errors:
        subprocess.check_call(command, stderr=errors)
        subprocess.check_call(['e2fsck', '-f', '-n', str(filesystem)], stdout=errors, stderr=errors)
    marker_text = subprocess.check_output(['debugfs', '-R', 'cat /etc/n_data_recovery_trial.json', str(filesystem)],
                                          stderr=subprocess.DEVNULL, universal_newlines=True)
    marker = json.loads(marker_text)
    if marker['nas_writes_allowed'] or not marker['original_usb_must_be_disconnected']:
        raise ValueError('Trial isolation marker mismatch')
    with image.open('r+b') as output, filesystem.open('rb') as source:
        output.seek(layout['prefix_bytes'])
        shutil.copyfileobj(source, output, 8 * 1024 * 1024)
        output.flush(); os.fsync(output.fileno())
    report = {'trial_image_only': True, 'image_bytes': image.stat().st_size,
              'image_sha256': digest(image), 'filesystem_check': 'passed',
              'boot_prefix_verified': True, 'isolation_marker_verified': True,
              'original_usb_must_be_disconnected': True, 'nas_writes_allowed': False,
              'outbound_new_connections_allowed': False,
              'masked_unit_count': len(isolation['masked_units']),
              'physical_boot_test_pending': True,
              'image_method': 'authenticated filesystem restore plus original boot prefix; no device attachment'}
    Path(str(image) + '.ready.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True)
    parser.add_argument('--boot-prefix', required=True)
    parser.add_argument('--key', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run as root in the separate staging environment')
    build(args.workspace, args.boot_prefix, args.key)
