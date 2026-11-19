import copy
from datetime import datetime, timedelta
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('joint', Path(__file__).resolve().parents[1] / 'g2b_joint_region.py')
joint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(joint)
BID = 'R26BK01789188'
KEY = BID + '-000'


def row():
    return {'공고번호': BID, '차수': '000', '공동도급지역': '', '공동도급비율': '49',
            '입찰마감일시': (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S'),
            '원문': {'bidNtceNo': BID, 'bidNtceOrd': '000', 'rgnDutyJntcontrctRt': '49', 'rgnDutyJntcontrctYn': 'Y'}}


def normalize(raw):
    return {'원문': raw, '공동도급지역': raw.get('jntcontrctDutyRgnNm1', ''),
            '공동도급비율': raw.get('rgnDutyJntcontrctRt', '')}


def detail(region='경상남도'):
    return joint.parse_detail(BID, '000', KEY, '해당', '[' + region + ']', '49')


class Process:
    returncode = 0
    output = ''

    def __init__(self, *args, **kwargs):
        pass

    def communicate(self, *args, **kwargs):
        return self.output, ''


class JointRegionTests(unittest.TestCase):
    def test_exact_identity_and_multiple_regions(self):
        parsed = joint.parse_detail(BID, '000', BID + ' - 000', '해당', '[서울특별시][경기도]', '49%')
        self.assertEqual(parsed['regions'], ['서울특별시', '경기도'])
        self.assertEqual(parsed['ratio'], '49')
        self.assertEqual(joint.parse_detail(BID, '000', KEY, '해당없음', '', '')['regions'], [])

    def test_rejects_wrong_notice_missing_and_conflicting_values(self):
        for shown, duty, region, ratio in [
            (BID + '-001', '해당', '[경상남도]', '49'),
            ('R26BK01788813-000', '해당', '[경상남도]', '49'),
            (KEY, '해당', '', '49'),
            (KEY, '해당없음', '[경상남도]', '49'),
            (KEY, '해당', '[경상남도]', '101')]:
            with self.subTest(shown=shown, duty=duty, ratio=ratio), self.assertRaises(ValueError):
                joint.parse_detail(BID, '000', shown, duty, region, ratio)

    def test_eligibility_and_site_regions_do_not_supply_joint_region(self):
        candidate = row()
        candidate['공동도급비율'] = ''
        candidate['참가제한지역'] = '충청북도'
        candidate['공사현장지역'] = '경상남도'
        candidate['원문'].update(rgnDutyJntcontrctYn='N', rgnDutyJntcontrctRt='', prtcptPsblRgnNm='충청북도')
        self.assertFalse(joint.needs_lookup(candidate))
        candidate['원문']['rgnDutyJntcontrctYn'] = 'Y'
        self.assertTrue(joint.needs_lookup(candidate))

    def test_failure_persists_and_recovers_outside_collection_window(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(joint.subprocess, 'Popen', Process):
            Process.output = json.dumps({KEY: {'ok': False, 'error': 'TimeoutException'}})
            self.assertEqual(joint.enrich_rows([row()], directory, normalize, lambda s: None), [])
            saved = json.loads((Path(directory) / 'g2b_joint_region_v1.json').read_text())
            self.assertEqual(saved['pending'][KEY]['attempts'], 1)
            Process.output = json.dumps({KEY: {'ok': True, 'data': detail()}})
            resumed = joint.enrich_rows([], directory, normalize, lambda s: None)
            self.assertEqual(resumed[0]['공동도급지역'], '경상남도')
            self.assertFalse(json.loads((Path(directory) / 'g2b_joint_region_v1.json').read_text())['pending'])

    def test_cache_reuse_and_changed_notice_invalidates_cache(self):
        candidate = row()
        with tempfile.TemporaryDirectory() as directory:
            Process.output = json.dumps({KEY: {'ok': True, 'data': detail()}})
            with patch.object(joint.subprocess, 'Popen', Process):
                joint.enrich_rows([copy.deepcopy(candidate)], directory, normalize, lambda s: None)
            with patch.object(joint.subprocess, 'Popen', side_effect=AssertionError('unexpected browser')):
                cached = joint.enrich_rows([copy.deepcopy(candidate)], directory, normalize, lambda s: None)
            self.assertEqual(cached[0]['공동도급지역'], '경상남도')
            candidate['원문']['chgDt'] = 'changed'
            Process.output = json.dumps({KEY: {'ok': True, 'data': detail('서울특별시')}})
            with patch.object(joint.subprocess, 'Popen', Process):
                refreshed = joint.enrich_rows([candidate], directory, normalize, lambda s: None)
            self.assertEqual(refreshed[0]['공동도급지역'], '서울특별시')

    def test_cancellation_clears_pending_without_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            Process.output = json.dumps({KEY: {'ok': False, 'error': 'TimeoutException'}})
            with patch.object(joint.subprocess, 'Popen', Process):
                joint.enrich_rows([row()], directory, normalize, lambda s: None)
            with patch.object(joint.subprocess, 'Popen', side_effect=AssertionError('unexpected browser')):
                result = joint.enrich_rows([row()], directory, normalize, lambda s: None, cancelled=lambda r: True)
            self.assertEqual(len(result), 1)
            self.assertFalse(json.loads((Path(directory) / 'g2b_joint_region_v1.json').read_text())['pending'])


if __name__ == '__main__':
    unittest.main()
