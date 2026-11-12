from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pi_maintenance as maintenance


class MaintenanceSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        (self.base / 'state').mkdir()
        (self.base / 'main_send.py').write_text('# g2b_pending_window')
        self.record = self.base / 'maintenance.json'

    def tearDown(self):
        self.temp.cleanup()

    def test_earlier_collection_checkpoint_is_preserved(self):
        checkpoint = self.base / 'state/g2b_pending_window'
        checkpoint.write_text('202611120700\n')
        self.assertEqual(maintenance.preserve_window(self.base, '202611121400'), '202611120700')
        self.assertEqual(checkpoint.read_text(), '202611120700\n')

    def test_invalid_checkpoint_is_not_overwritten(self):
        checkpoint = self.base / 'state/g2b_pending_window'
        checkpoint.write_text('invalid')
        with self.assertRaises(ValueError):
            maintenance.preserve_window(self.base, '202611121400')
        self.assertEqual(checkpoint.read_text(), 'invalid')

    def test_failed_rollback_guard_does_not_stop_services(self):
        state = {'timers': ['example.timer'], 'targets': [], 'cron_active': False, 'cron_pid': 0}
        calls = []
        def command(args, check=True):
            calls.append(args)
            if args[0] == 'systemd-run':
                raise RuntimeError('fixture guard failure')
            raise AssertionError('Unexpected service mutation')
        with patch.object(maintenance, 'capture', return_value=state), patch.object(maintenance, 'command', side_effect=command):
            with self.assertRaisesRegex(RuntimeError, 'fixture guard failure'):
                maintenance.pause(self.record, base=self.base)
        self.assertEqual(len(calls), 1)

    def test_checkpoint_failure_restores_stopped_timers(self):
        state = {'timers': ['example.timer'], 'targets': [], 'cron_active': False, 'cron_pid': 0}
        calls = []
        with patch.object(maintenance, 'capture', return_value=state), patch.object(maintenance, 'command', side_effect=lambda args, check=True: calls.append(args) or ''), patch.object(maintenance, 'cron_children', return_value=[]), patch.object(maintenance, 'preserve_window', side_effect=RuntimeError('fixture checkpoint failure')):
            with self.assertRaisesRegex(RuntimeError, 'fixture checkpoint failure'):
                maintenance.pause(self.record, base=self.base)
        self.assertIn(['systemctl', 'stop', 'example.timer'], calls)
        self.assertIn(['systemctl', 'start', 'example.timer'], calls)
        self.assertEqual(json.loads(self.record.read_text())['phase'], 'resumed')

    def test_resume_is_idempotent_and_keeps_originally_inactive_cron_inactive(self):
        maintenance.save(self.record, {'phase': 'paused', 'timers': ['example.timer'], 'timers_stopped': True,
                                      'cron_active': False, 'guard_created': True, 'guard': 'fixture-guard'})
        calls = []
        with patch.object(maintenance, 'command', side_effect=lambda args, check=True: calls.append(args) or ''):
            maintenance.resume(self.record)
            maintenance.resume(self.record)
        self.assertEqual(calls, [['systemctl', 'start', 'example.timer'], ['systemctl', 'stop', 'fixture-guard.timer']])

    def test_shutdown_refuses_unpaused_host(self):
        maintenance.save(self.record, {'phase': 'resumed'})
        with patch.object(maintenance, 'command') as command:
            with self.assertRaisesRegex(RuntimeError, 'not in paused'):
                maintenance.shutdown(self.record)
            command.assert_not_called()

    def test_shutdown_refuses_near_rollback_deadline(self):
        old = datetime.now(timezone(timedelta(hours=9))) - timedelta(minutes=26)
        maintenance.save(self.record, {'phase': 'paused', 'started_kst': old.isoformat()})
        with patch.object(maintenance, 'command') as command:
            with self.assertRaisesRegex(RuntimeError, 'deadline is near'):
                maintenance.shutdown(self.record)
            command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
