#!/usr/bin/env python3
"""Pause scheduling reversibly before an attended SD recovery test.

Does not change persistent enablement or crontab entries. A transient rollback
timer resumes scheduling after 30 minutes if the host remains powered on.
"""
import argparse
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import signal
import subprocess
import time


def command(args, check=True):
    return subprocess.run(args, check=check, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True).stdout.strip()


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(str(path) + '.tmp')
    with temp.open('w') as stream:
        os.chmod(str(temp), 0o600)
        json.dump(data, stream, indent=2)
        stream.flush(); os.fsync(stream.fileno())
    os.replace(str(temp), str(path))


def capture():
    timers = [line.split()[0] for line in command([
        'systemctl', 'list-units', '--type=timer', '--state=active',
        '--no-legend', '--plain', '--no-pager']).splitlines() if line.strip()]
    targets = sorted(set(command(['systemctl', 'show', name, '-p', 'Unit', '--value'])
                         for name in timers))
    return {'timers': timers, 'targets': [n for n in targets if n.endswith('.service')],
            'cron_active': command(['systemctl', 'is-active', 'cron.service'], check=False) == 'active',
            'cron_pid': int(command(['systemctl', 'show', 'cron.service', '-p', 'MainPID', '--value']) or 0)}


def cron_signal(record, sig):
    pid = int(command(['systemctl', 'show', 'cron.service', '-p', 'MainPID', '--value']) or 0)
    if pid and pid == record.get('cron_pid'):
        comm = Path('/proc/%s/comm' % pid).read_text().strip()
        if comm not in ('cron', 'crond'):
            raise RuntimeError('Cron PID identity changed')
        os.kill(pid, sig)


def cron_children(record):
    result = []
    for path in Path('/proc').glob('[0-9]*/cgroup'):
        try:
            pid = int(path.parent.name)
            if pid == record.get('cron_pid'):
                continue
            if any(line.split(':', 2)[-1].strip() == '/system.slice/cron.service'
                   for line in path.read_text().splitlines()):
                result.append(pid)
        except (OSError, ValueError):
            pass
    return result


def preserve_window(base, started):
    base = Path(base)
    if 'g2b_pending_window' not in (base / 'main_send.py').read_text():
        raise RuntimeError('Collection backfill support not found')
    path = base / 'state/g2b_pending_window'
    previous = path.read_text().strip() if path.exists() else ''
    if previous:
        datetime.strptime(previous, '%Y%m%d%H%M')
    datetime.strptime(started, '%Y%m%d%H%M')
    chosen = min(previous, started) if previous else started
    temp = Path(str(path) + '.recovery.tmp')
    with temp.open('w') as stream:
        os.chmod(str(temp), 0o600)
        os.chown(str(temp), base.stat().st_uid, base.stat().st_gid)
        stream.write(chosen + '\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(str(temp), str(path))
    return chosen


def resume(path):
    path = Path(path)
    record = json.loads(path.read_text())
    if record.get('phase') == 'resumed':
        return record
    if record.get('cron_frozen'):
        cron_signal(record, signal.SIGCONT)
    if record.get('cron_stopped') and record.get('cron_active'):
        command(['systemctl', 'start', 'cron.service'])
    if record.get('timers_stopped') and record.get('timers'):
        command(['systemctl', 'start'] + record['timers'])
    record['phase'] = 'resumed'
    save(path, record)
    if record.get('guard_created'):
        command(['systemctl', 'stop', record['guard'] + '.timer'], check=False)
    return record


def pause(path, base='/home/pi/n_data', wait_seconds=900):
    path = Path(path)
    if path.exists():
        raise ValueError('Maintenance record already exists')
    now = datetime.now(timezone(timedelta(hours=9)))
    record = capture()
    record.update({'phase': 'preparing', 'started_kst': now.isoformat(),
                   'started_window': now.strftime('%Y%m%d%H%M'),
                   'guard': 'n-data-recovery-rollback-' + now.strftime('%Y%m%d%H%M%S'),
                   'guard_created': False, 'timers_stopped': False,
                   'cron_frozen': False, 'cron_stopped': False})
    save(path, record)
    try:
        command(['systemd-run', '--unit=' + record['guard'], '--on-active=30m',
                 '/usr/bin/python3', str(Path(__file__).resolve()), 'resume', '--record', str(path.resolve())])
        record['guard_created'] = True; save(path, record)
        if record['timers']:
            # Set intent before action, so rollback also covers a partial stop.
            record['timers_stopped'] = True; save(path, record)
            command(['systemctl', 'stop'] + record['timers'])
        if record['cron_active'] and record['cron_pid']:
            record['cron_frozen'] = True; save(path, record)
            cron_signal(record, signal.SIGSTOP)
        deadline = time.monotonic() + wait_seconds
        while True:
            running = [name for name in record['targets']
                       if int(command(['systemctl', 'show', name, '-p', 'MainPID', '--value']) or 0)]
            children = cron_children(record)
            if not running and not children:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Existing work did not finish; scheduling will be resumed')
            print('MAINTENANCE_WAIT services=%s cron_processes=%s' % (len(running), len(children)), flush=True)
            time.sleep(10)
        record['pending_window'] = preserve_window(base, record['started_window'])
        record['phase'] = 'paused'; save(path, record)
        print('MAINTENANCE_PAUSED timers=%s rollback=30min' % len(record['timers']), flush=True)
        return record
    except Exception:
        resume(path)
        raise


def shutdown(path):
    path = Path(path)
    record = json.loads(path.read_text())
    if record.get('phase') != 'paused':
        raise RuntimeError('Host is not in paused maintenance state')
    age = datetime.now(timezone(timedelta(hours=9))) - datetime.fromisoformat(record['started_kst'])
    if age.total_seconds() > 25 * 60:
        raise RuntimeError('Rollback deadline is near; resume and start a new maintenance window')
    # Caller must have completed final backups and verified the physical handoff.
    command(['systemctl', 'is-active', record['guard'] + '.timer'])
    if record.get('cron_frozen'):
        cron_signal(record, signal.SIGTERM)
        cron_signal(record, signal.SIGCONT)
        command(['systemctl', 'stop', 'cron.service'])
        record['cron_stopped'] = True; record['cron_frozen'] = False
    record['phase'] = 'shutdown_prepared'; save(path, record)
    try:
        command(['systemctl', 'stop', record['guard'] + '.timer'])
        command(['sync'])
        command(['systemctl', 'poweroff'])
    except Exception:
        resume(path)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['pause', 'resume', 'status', 'shutdown'])
    parser.add_argument('--record', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('Run this maintenance tool with sudo')
    if args.action == 'pause':
        pause(args.record)
    elif args.action == 'resume':
        resume(args.record)
    elif args.action == 'shutdown':
        shutdown(args.record)
    else:
        state = json.loads(Path(args.record).read_text())
        print(json.dumps({'phase': state['phase'], 'timer_count': len(state['timers']),
                          'started_kst': state['started_kst']}, indent=2))
