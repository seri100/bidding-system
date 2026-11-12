#!/usr/bin/env python3
"""Repeatable offline recovery checks on Linux/WSL; no production execution."""
import argparse
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3

from verify_restore import restore


def drill(archive_root, key_file, destination):
    if os.name != 'posix':
        raise RuntimeError('Use Linux or WSL: the Pi archive contains Linux filenames')
    archive_root, destination = Path(archive_root), Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Drill destination must be empty')
    destination.mkdir(parents=True, exist_ok=True)
    destination.chmod(0o700)
    report = {
        'time_kst': datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'environment': {'os': platform.system(), 'architecture': platform.machine(),
                        'python': platform.python_version()},
        'scope': 'Offline archive restore, Python compilation and SQLite/SQL checks',
        'archives': [],
        'not_tested': ['new hardware boot', 'Pi ARM runtime/dependency installation',
                       'NAS remount on a replacement device', 'production scheduling',
                       'SMS/Kakao sends', 'Google Calendar writes', 'Cloudflare redeploy'],
    }
    for prefix, target in [('raspberrypi_', 'pi'), ('pc-originals-', 'pc')]:
        archives = sorted(archive_root.glob(prefix + '*.enc'))
        if len(archives) != 1:
            raise ValueError('Provide exactly one archive of each type in archive_root')
        archive = archives[0]
        count = restore(archive, key_file, destination / target)
        report['archives'].append({'name': archive.name, 'verified_files': count,
                                   'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                                   'authentication': 'passed'})
    snapshot = destination / 'pi/snapshot'
    inventory = json.loads((snapshot / 'metadata/inventory.json').read_text(encoding='utf-8'))
    n_data = snapshot / 'home/pi/n_data'
    required = ['main_send.py', 'error_alert_monitor.py', 'g2b_api02.py',
                'g2b_amount_refresh.py', 'g2b_joint_region.py', 'g2b_cancel_sync.py',
                'modules/calendar_sync.py', 'kakao_send_tb0485.py']
    compile_result = []
    for name in required:
        path = n_data / name
        compile(path.read_bytes(), name, 'exec')
        compile_result.append(name)
    report['n_data_compile_passed'] = compile_result
    report['original_missing_paths'] = inventory.get('missing_paths', [])
    report['private_restore_components'] = {
        'nas_credential_file': (snapshot / 'root/.smbcredentials-bid').is_file(),
        'pi_crontab': (snapshot / 'metadata/crontab.txt').is_file(),
        'root_crontab': (snapshot / 'metadata/root-crontab.txt').is_file(),
        'systemd_directory': (snapshot / 'metadata/systemd').is_dir(),
        'recipient_configuration': (n_data / 'alimtalk_recipients.json').is_file(),
        'nas_sent_keys': (snapshot / 'mnt/vol1/bid/n_data/sent_keys.txt').is_file(),
    }
    sql_files = list((destination / 'pc').rglob('dashboard-d1*.sql'))
    if len(sql_files) != 1:
        raise ValueError('Expected exactly one dashboard SQL export')
    connection = sqlite3.connect(':memory:')
    try:
        connection.executescript(sql_files[0].read_text(encoding='utf-8-sig'))
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        report['d1_sql'] = {
            'integrity': 'ok',
            'table_count': connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0],
            'gcal_bid_count': connection.execute('SELECT COUNT(*) FROM gcal_bids').fetchone()[0],
        }
    finally:
        connection.close()
    (destination / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-root', required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--destination', required=True)
    args = parser.parse_args()
    drill(args.archive_root, args.key, args.destination)
