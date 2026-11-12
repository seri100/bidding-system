#!/usr/bin/env python3
"""Apply a verified final application snapshot ONLY inside a marked trial SD.

Never restores fstab, systemd, cron, or original USB/NAS paths on a live host.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess

from verify_restore import restore


def guard():
    marker = json.loads(Path('/etc/n_data_recovery_trial.json').read_text())
    if marker.get('nas_writes_allowed') or not marker.get('original_usb_must_be_disconnected'):
        raise RuntimeError('Trial marker mismatch')
    for target in ('/', '/home', '/var', '/mnt/vol1'):
        source = subprocess.check_output(['findmnt', '-n', '-o', 'SOURCE', '--target', target],
                                         universal_newlines=True).strip()
        if source != '/dev/mmcblk0p2':
            raise RuntimeError('Protected path is outside the trial SD')
    subprocess.check_call(['systemctl', 'is-active', '--quiet', 'n-data-trial-isolation.service'])
    policy = subprocess.check_output(['iptables', '-S', 'OUTPUT'], universal_newlines=True)
    if not policy.startswith('-P OUTPUT DROP\n'):
        raise RuntimeError('Outbound isolation policy is not DROP')
    if Path('/proc/sys/net/ipv6/conf/all/disable_ipv6').read_text().strip() != '1':
        raise RuntimeError('IPv6 isolation is not active')
    for name in marker['masked_units']:
        if os.readlink('/etc/systemd/system/' + name) != '/dev/null':
            raise RuntimeError('Trial scheduling mask missing')


def apply(archive, key, staging):
    guard()
    restore(archive, key, staging)
    snapshot = Path(staging) / 'snapshot'
    inventory = json.loads((snapshot / 'metadata/inventory.json').read_text())
    if inventory.get('copy_failures'):
        raise RuntimeError('Final snapshot contains copy failures')
    allowed = (Path('/home/pi'), Path('/mnt/vol1'))
    user = pwd.getpwnam('pi')
    count = 0
    for item in inventory['manifest']:
        relative = Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise RuntimeError('Unsafe manifest path')
        destination = Path('/') / relative
        if not any(parent in destination.parents for parent in allowed):
            continue
        resolved = destination.resolve()
        if not any(parent in resolved.parents for parent in allowed):
            raise RuntimeError('Snapshot destination escapes isolated application storage')
        source = snapshot / relative
        if not source.is_file() or source.is_symlink():
            raise RuntimeError('Application snapshot has an invalid source')
        missing = []
        parent = destination.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for parent in reversed(missing):
            parent.mkdir(mode=0o755)
            os.chown(str(parent), user.pw_uid, user.pw_gid)
        # A trial has no database writers; remove stale sidecars before replacing
        # the consistent SQLite backup produced with the sqlite backup API.
        with source.open('rb') as stream:
            sqlite = stream.read(16) == b'SQLite format 3\x00'
        if sqlite:
            for suffix in ('-wal', '-shm', '-journal'):
                sidecar = Path(str(destination) + suffix)
                if sidecar.exists():
                    if sidecar.is_symlink():
                        raise RuntimeError('Unexpected database sidecar symlink')
                    sidecar.unlink()
        temporary = Path(str(destination) + '.trial-restore-tmp')
        if temporary.exists() or temporary.is_symlink():
            raise RuntimeError('Restore temporary path already exists')
        shutil.copy2(str(source), str(temporary))
        os.chmod(str(temporary), item['mode'])
        os.chown(str(temporary), user.pw_uid, user.pw_gid)
        with temporary.open('rb') as stream:
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(destination))
        if hashlib.sha256(destination.read_bytes()).hexdigest() != item['sha256']:
            raise RuntimeError('Applied application file hash mismatch')
        count += 1
    if not count:
        raise RuntimeError('No application files applied')
    print(json.dumps({'trial_application_files_applied': count,
                      'snapshot_at': inventory['captured_at'],
                      'system_boot_and_scheduling_overwritten': False}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--staging', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo only on the marked trial Pi')
    apply(args.archive, args.key, args.staging)
