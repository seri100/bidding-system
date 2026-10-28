"""Read-only joint-region queue summary. No browser, network, sender or state writes."""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys
import time


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def summarize(state, now=None, warn_attempts=3, warn_age_minutes=60):
    now = time.time() if now is None else now
    if not isinstance(state, dict) or not all(isinstance(state.get(k, {}), dict) for k in ('cache', 'pending')):
        raise ValueError('invalid state structure')
    pending = []
    for key, entry in state.get('pending', {}).items():
        if not isinstance(key, str) or not re.fullmatch(r'R\d{2}BK\d+-\d{3}', key) or not isinstance(entry, dict):
            raise ValueError('invalid pending entry')
        attempts, created, last_try = entry.get('attempts', 0), entry.get('created'), entry.get('last_try', 0)
        if (not isinstance(attempts, int) or isinstance(attempts, bool) or attempts < 0
                or not number(created) or created <= 0 or not number(last_try) or last_try < 0):
            raise ValueError('invalid pending counters/times')
        age = max(0, (now - created) / 60)
        warnings = []
        if attempts >= warn_attempts:
            warnings.append('attempts')
        if age >= warn_age_minutes:
            warnings.append('age')
        raw_row = entry.get('row') or {}
        deadline = raw_row.get('입찰마감일시', '') if isinstance(raw_row, dict) else ''
        try:
            if deadline and datetime.fromisoformat(str(deadline).replace('/', '-')).timestamp() <= now:
                warnings.append('deadline_passed')
        except (ValueError, OverflowError, OSError):
            pass
        # Only controlled class/phase names are exposed, never row snapshots or exception messages.
        error = str(entry.get('last_error') or '')
        stage = str(entry.get('last_stage') or 'unknown')
        error = error if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', error) else ''
        stage = stage if re.fullmatch(r'[a-z_]{1,40}', stage) else 'unknown'
        pending.append({'bid': key, 'attempts': attempts, 'age_minutes': round(age, 1),
                        'last_try_minutes': round(max(0, (now-last_try)/60), 1) if last_try else None,
                        'last_error': error, 'last_stage': stage, 'warnings': warnings})
    fresh = 0
    for entry in state.get('cache', {}).values():
        if not isinstance(entry, dict) or not number(entry.get('at')):
            raise ValueError('invalid cache entry')
        if 0 <= now - entry['at'] < 21600:
            fresh += 1
    pending.sort(key=lambda item: (-item['age_minutes'], item['bid']))
    return {'schema_version': 1, 'checked_at': datetime.fromtimestamp(now).astimezone().isoformat(timespec='seconds'),
            'status': 'attention' if any(item['warnings'] for item in pending) else 'ok',
            'cache_count': len(state.get('cache', {})), 'cache_within_6h': fresh,
            'pending_count': len(pending), 'pending': pending}


def inspect(path, **kwargs):
    try:
        state = json.loads(Path(path).read_text(encoding='utf-8'))
        return summarize(state, **kwargs)
    except FileNotFoundError:
        return {'status': 'missing', 'error': 'state_not_initialized'}
    except (ValueError, TypeError):
        return {'status': 'invalid', 'error': 'invalid_state'}
    except OSError:
        return {'status': 'error', 'error': 'state_unreadable'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-file', default='/mnt/vol1/bid/n_data/state/g2b_joint_region_v1.json')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--warn-attempts', type=int, default=3)
    parser.add_argument('--warn-age-minutes', type=float, default=60)
    args = parser.parse_args()
    if args.warn_attempts < 1 or not math.isfinite(args.warn_age_minutes) or args.warn_age_minutes <= 0:
        parser.error('warning thresholds must be positive')
    result = inspect(args.state_file, warn_attempts=args.warn_attempts, warn_age_minutes=args.warn_age_minutes)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif result['status'] in ('ok', 'attention'):
        print('공동도급지역 점검: %s / 대기 %d건 / 캐시 %d건 (6시간 이내 %d건)' %
              (result['status'], result['pending_count'], result['cache_count'], result['cache_within_6h']))
        for item in result['pending']:
            print('%s: 시도 %d회, 대기 %.1f분, 단계=%s, 오류=%s, 주의=%s' %
                  (item['bid'], item['attempts'], item['age_minutes'], item['last_stage'],
                   item['last_error'] or '미기록', ','.join(item['warnings']) or '-'))
    else:
        print('공동도급지역 점검 불가: ' + result['error'])
    return 0 if result['status'] == 'ok' else 1 if result['status'] == 'attention' else 2


if __name__ == '__main__':
    sys.exit(main())
