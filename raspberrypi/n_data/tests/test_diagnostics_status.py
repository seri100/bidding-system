import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from test_joint_region import joint, row, normalize, KEY, Process

SPEC = importlib.util.spec_from_file_location('queue_status', Path(__file__).resolve().parents[1] / 'joint_region_status.py')
status = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(status)


class DiagnosticsTests(unittest.TestCase):
    def test_failure_stage_and_type_persist(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(joint.subprocess, 'Popen', Process):
            Process.output = json.dumps({KEY: {'ok': False, 'error': 'TimeoutException', 'stage': 'detail_read'}})
            logs = []
            self.assertEqual(joint.enrich_rows([row()], directory, normalize, logs.append), [])
            entry = json.loads((Path(directory) / 'g2b_joint_region_v1.json').read_text())['pending'][KEY]
            self.assertEqual((entry['last_error'], entry['last_stage']), ('TimeoutException', 'detail_read'))
            self.assertTrue(any('stage=detail_read' in line for line in logs))

    def test_timeout_uses_last_phase_and_kills_only_worker_group(self):
        process = Mock(pid=12345, returncode=-9)
        process.communicate.side_effect = [subprocess.TimeoutExpired('mock', 240), ('', '[G2B][PHASE] detail_read\n')]
        with tempfile.TemporaryDirectory() as directory, patch.object(joint.subprocess, 'Popen', return_value=process), patch.object(joint.os, 'killpg') as kill:
            joint.enrich_rows([row()], directory, normalize, lambda s: None)
            kill.assert_called_once_with(12345, signal.SIGKILL)
            entry = json.loads((Path(directory) / 'g2b_joint_region_v1.json').read_text())['pending'][KEY]
            self.assertEqual((entry['last_error'], entry['last_stage']), ('TimeoutExpired', 'detail_read'))

    def test_diagnostic_values_are_controlled(self):
        self.assertEqual(joint.last_worker_stage('[G2B][PHASE] home\n[G2B][PHASE] arbitrary_value\n'), 'home')
        with tempfile.TemporaryDirectory() as directory, patch.object(joint.subprocess, 'Popen', Process):
            Process.output = json.dumps({KEY: {'ok': False, 'error': 'PRIVATE MESSAGE', 'stage': 'PRIVATE MESSAGE'}})
            joint.enrich_rows([row()], directory, normalize, lambda s: None)
            entry = json.loads((Path(directory) / 'g2b_joint_region_v1.json').read_text())['pending'][KEY]
            self.assertEqual((entry['last_error'], entry['last_stage']), ('UnknownError', 'unknown'))

    def worker_modules(self, factory):
        selenium = types.ModuleType('selenium')
        webdriver = types.ModuleType('selenium.webdriver')
        chrome = types.ModuleType('selenium.webdriver.chrome')
        service = types.ModuleType('selenium.webdriver.chrome.service')
        webdriver.ChromeOptions = lambda: types.SimpleNamespace(add_argument=lambda value: None)
        webdriver.Chrome = factory
        service.Service = lambda executable: executable
        selenium.webdriver = webdriver
        return {'selenium': selenium, 'selenium.webdriver': webdriver,
                'selenium.webdriver.chrome': chrome, 'selenium.webdriver.chrome.service': service}

    def test_browser_start_failure_is_structured(self):
        factory = Mock(side_effect=RuntimeError('PRIVATE_MARKER'))
        output = io.StringIO()
        with patch.dict(sys.modules, self.worker_modules(factory)), patch.dict(os.environ, {'G2B_CHROMIUM': '/mock/browser', 'G2B_CHROMEDRIVER': '/mock/driver'}), patch.object(sys, 'stderr', output):
            result = joint.worker([(KEY.rsplit('-', 1)[0], '000')])
        self.assertEqual(result[KEY], {'ok': False, 'error': 'RuntimeError', 'stage': 'browser_start'})
        self.assertNotIn('PRIVATE_MARKER', output.getvalue())

    def test_lookup_failure_keeps_phase_without_exception_message(self):
        driver = Mock()
        def fail(*args):
            joint.lookup_phase(driver, 'detail_read')
            raise TimeoutError('PRIVATE_MARKER')
        output = io.StringIO()
        with patch.dict(sys.modules, self.worker_modules(Mock(return_value=driver))), patch.dict(os.environ, {'G2B_CHROMIUM': '/mock/browser', 'G2B_CHROMEDRIVER': '/mock/driver'}), patch.object(joint, 'fetch_detail', side_effect=fail), patch.object(sys, 'stderr', output):
            result = joint.worker([(KEY.rsplit('-', 1)[0], '000')])
        self.assertEqual(result[KEY], {'ok': False, 'error': 'TimeoutError', 'stage': 'detail_read'})
        driver.quit.assert_called_once_with()
        self.assertNotIn('PRIVATE_MARKER', output.getvalue())


class StatusTests(unittest.TestCase):
    def test_legacy_pending_warns_without_exposing_snapshot(self):
        now = 2000000000
        state = {'cache': {'one': {'at': now-10}}, 'pending': {KEY: {
            'created': now-7200, 'last_try': now-120, 'attempts': 3, 'row': {'private': 'PRIVATE_MARKER'}}}}
        result = status.summarize(state, now=now)
        self.assertEqual(result['status'], 'attention')
        self.assertEqual(result['pending'][0]['warnings'], ['attempts', 'age'])
        self.assertEqual(result['pending'][0]['last_stage'], 'unknown')
        self.assertEqual(result['cache_within_6h'], 1)
        self.assertNotIn('PRIVATE_MARKER', json.dumps(result))

    def test_current_empty_state_is_ok(self):
        result = status.summarize({'cache': {}, 'pending': {}})
        self.assertEqual((result['status'], result['pending_count']), ('ok', 0))

    def test_corrupt_and_missing_state_are_not_reported_as_ok(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            self.assertEqual(status.inspect(path)['status'], 'missing')
            path.write_text('{bad')
            self.assertEqual(status.inspect(path)['status'], 'invalid')
            path.write_text(json.dumps({'pending': {KEY: {'created': 0}}}))
            self.assertEqual(status.inspect(path)['status'], 'invalid')

    def test_status_does_not_change_state_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'state.json'
            path.write_text('{"cache": {}, "pending": {}}')
            before = (path.read_bytes(), path.stat().st_mtime_ns)
            self.assertEqual(status.inspect(path)['status'], 'ok')
            self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_invalid_cache_and_nan_timestamps_are_rejected(self):
        with self.assertRaises(ValueError):
            status.summarize({'cache': {'one': None}})
        with self.assertRaises(ValueError):
            status.summarize({'pending': {KEY: {'created': float('nan'), 'attempts': 0}}})


if __name__ == '__main__':
    unittest.main()
