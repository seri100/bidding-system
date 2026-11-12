#!/usr/bin/env python3
"""Validate an isolated recovery trial on the actual Pi, without sending data."""
import argparse
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess


def run(args):
    return subprocess.check_output(args, universal_newlines=True, stderr=subprocess.DEVNULL).strip()


def verify():
    marker = json.loads(Path('/etc/n_data_recovery_trial.json').read_text())
    if marker.get('nas_writes_allowed') or not marker.get('original_usb_must_be_disconnected'):
        raise RuntimeError('Trial marker failed')
    mounts = {target: run(['findmnt', '-n', '-o', 'SOURCE', '--target', target])
              for target in ('/', '/home', '/var', '/mnt/vol1')}
    if any(source != '/dev/mmcblk0p2' for source in mounts.values()):
        raise RuntimeError('A protected path is outside the trial SD')
    mounted = run(['findmnt', '-rn', '-o', 'SOURCE,FSTYPE'])
    if any(line.split()[0].startswith('/dev/sd') or line.split()[-1] in ('cifs', 'nfs', 'nfs4')
           for line in mounted.splitlines()):
        raise RuntimeError('External storage is mounted')
    if run(['systemctl', 'is-active', 'n-data-trial-isolation.service']) != 'active':
        raise RuntimeError('Trial isolation service is inactive')
    rules = run(['iptables', '-S', 'OUTPUT']).splitlines()
    expected = {'-P OUTPUT DROP', '-A OUTPUT -o lo -j ACCEPT',
                '-A OUTPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT',
                '-A OUTPUT -p udp -m udp --sport 68 --dport 67 -j ACCEPT'}
    if set(rules) != expected:
        raise RuntimeError('Outbound firewall differs from trial policy')
    for key in ('all', 'default'):
        if Path('/proc/sys/net/ipv6/conf/%s/disable_ipv6' % key).read_text().strip() != '1':
            raise RuntimeError('IPv6 is not disabled')
    for name in marker['masked_units']:
        if os.readlink('/etc/systemd/system/' + name) != '/dev/null':
            raise RuntimeError('An expected unit is not masked')
    timers = run(['systemctl', 'list-units', '--type=timer', '--state=active',
                  '--no-legend', '--plain', '--no-pager'])
    if timers:
        raise RuntimeError('An automatic timer is active')
    base = Path('/home/pi/n_data')
    required = ['main_send.py', 'error_alert_monitor.py', 'g2b_api02.py',
                'g2b_amount_refresh.py', 'g2b_joint_region.py', 'g2b_cancel_sync.py',
                'modules/calendar_sync.py', 'kakao_send_tb0485.py']
    for name in required:
        compile((base / name).read_bytes(), name, 'exec')
    dependencies = ['requests', 'pandas', 'bs4', 'openpyxl', 'googleapiclient.discovery',
                    'google.oauth2.credentials']
    run(['runuser', '-u', 'pi', '--', 'python3', '-c',
         'import importlib; [importlib.import_module(n) for n in ' + repr(dependencies) + ']'])
    databases = set()
    for directory in (base, Path('/mnt/vol1/bid/n_data')):
        for pattern in ('*.sqlite', '*.sqlite3', '*.db'):
            databases.update(directory.rglob(pattern))
    databases = sorted(databases)
    checked = 0
    for path in databases:
        # Immutable read-only mode cannot create WAL/journal files.
        connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1', uri=True)
        try:
            if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise RuntimeError('A restored SQLite database failed integrity checking')
            checked += 1
        finally:
            connection.close()
    if not checked:
        raise RuntimeError('No restored SQLite database was found')
    for directory in ('/home/pi/n_data/state', '/mnt/vol1/bid/n_data/state'):
        probe = ('import os,tempfile; f=tempfile.TemporaryFile(dir=' + repr(directory)
                 + '); f.write(b\"trial\"); f.flush(); os.fsync(f.fileno()); f.close()')
        run(['runuser', '-u', 'pi', '--', 'python3', '-c', probe])
    return {'physical_pi_boot': 'passed', 'architecture': platform.machine(),
            'python': platform.python_version(), 'storage_isolation': 'passed',
            'firewall': 'passed', 'masked_units': len(marker['masked_units']),
            'automatic_timers': 0, 'python_files_compiled': len(required),
            'dependencies_imported': dependencies, 'sqlite_checked': checked,
            'pi_state_write_probes': 2,
            'production_sends_executed': False, 'nas_connected': False,
            'original_boot_restoration_pending': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run with sudo on the marked trial Pi')
    report = verify()
    Path(args.output).write_text(json.dumps(report, indent=2))
    print(json.dumps(report), flush=True)
