# -*- coding: utf-8 -*-
import json
import tempfile
import unittest
import types
from pathlib import Path
from unittest.mock import patch
import fire_share_auto as app

TEXT = '''1.3. 공사명 : 시험 소방공사 1.4. 공사현장 : 대구광역시
1.8. 업종별 추정금액 및 업종별 금액
일반소방시설공사업(기계) 600,000,000원(60%) 600,000,000원(60%)
일반소방시설공사업(전기) 400,000,000원(40%) 400,000,000원(40%)
1.9. 평가대상 업종 기계 100% 2. 입찰 및 계약방식
3.1. 일반소방시설공사업(기계 및 전기) 또는 전문소방시설공사업.
본 공사는 지역의무공동도급이 적용되는 공사로서 대구광역시에 본점을 둔
지역업체의 시공참여비율이 전체 공사금액의 49% 이상이어야 합니다.
3.2. 다른 사항 5. 공동계약
5.1. 공동이행방식, 분담이행방식, 공동이행방식과 분담이행방식이 혼합된 방식이 가능합니다.
최소지분율은 10% 이상 6. 현장설명'''
COMPANIES = dict(records=[dict(지역='대구',상호='=BAD()',주소='대구시 시험로 1',
                    면허종류='공사업- 일반(전기)',대표자='대표',전화번호='053-123-4567',
                    최초면허취득일='2020-01-02',등록번호='01',협회관리번호='C-1',출처='https://example.test')],
                 controls=[],fetched_at='2026-11-17',fetched_epoch=0)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.state=self.root/'state'
        self.data=self.root/'data'
        self.output=self.root/'output'
        self.output.mkdir()
        self.key='R26BK01834905-000'
        self.folder=self.data/'attachments'/'2026년'/'11월'/'17일'/self.key
        self.folder.mkdir(parents=True)
        self.doc=self.folder/'공사입찰.hwpx'
        self.doc.write_text(TEXT)
        self.row=dict(공고번호='R26BK01834905',차수='000',공고명='시험 소방공사',
                      시공경험배점한도=True,첨부파일폴더=str(self.folder))

    def tearDown(self):
        self.tmp.cleanup()

    def queue(self):
        app.enqueue(self.row,state_dir=self.state,logger=lambda s:None)
        return self.state/'queue'/(self.key+'.json')

    def process(self,path,ledger,err=''):
        with patch.object(app,'matching_documents',return_value=[(self.doc,TEXT)]), \
             patch.object(app,'company_data',return_value=(COMPANIES,err)):
            return app.process_job(path,self.data,self.output,self.state,ledger)

    def test_unreadable_discovery_is_visible_then_cleared_after_repair(self):
        modules={'g2b_amount_refresh':types.SimpleNamespace(document_text=lambda p:TEXT,notice_document=lambda n:True),
                 'g2b_score_cap':types.SimpleNamespace(has_score_cap=lambda t:True)}
        ledger={}
        with patch.dict('sys.modules',modules):
            with patch.object(modules['g2b_amount_refresh'],'document_text',side_effect=ValueError('broken_source')):
                app.discover(self.data,self.state,ledger,days=100000)
            self.assertIn(str(self.doc),ledger['document_errors'])
            app.discover(self.data,self.state,ledger,days=100000)
        self.assertNotIn(str(self.doc),ledger['document_errors'])
        self.assertTrue((self.state/'queue'/(self.key+'.json')).exists())

    def test_non_fire_discovery_is_not_an_error_or_job(self):
        modules={'g2b_amount_refresh':types.SimpleNamespace(document_text=lambda p:'1.3. 공사명: 건축공사 1.4. 현장',notice_document=lambda n:True),
                 'g2b_score_cap':types.SimpleNamespace(has_score_cap=lambda t:True)}
        ledger={}
        with patch.dict('sys.modules',modules):
            app.discover(self.data,self.state,ledger,days=100000)
        self.assertFalse(ledger.get('document_errors'))
        self.assertFalse(list((self.state/'queue').glob('*.json')))

    def test_bad_extra_attachment_does_not_block_valid_source(self):
        good=self.folder/'공사입찰설명서.hwpx';good.write_text(TEXT)
        def extract(p):
            if p==self.doc:raise ValueError('unreadable_extra')
            return TEXT
        modules={'g2b_amount_refresh':types.SimpleNamespace(document_text=extract,notice_document=lambda n:True),
                 'g2b_score_cap':types.SimpleNamespace(has_score_cap=lambda t:True)}
        with patch.dict('sys.modules',modules):
            matches=app.matching_documents([self.folder])
        self.assertEqual([p for p,t in matches],[good])

    def test_explicit_conditions_and_two_bases(self):
        d=app.parse_notice(TEXT,self.key)
        self.assertEqual(d['regions'],['대구'])
        self.assertEqual(d['required'],.49)
        self.assertEqual(d['mixed'],'허용')
        self.assertEqual(d['minimum'],.1)
        self.assertEqual(len(d['basis']),2)
        self.assertEqual(d['evaluation'],'평가대상업종기계100%')
        self.assertFalse(d['issues'])

    def test_fire_industry_even_if_title_omits_fire_word(self):
        text=TEXT.replace('시험 소방공사','스프링클러 설치공사')
        d=app.parse_notice(text,self.key,{'공고업종코드':'0040'})
        self.assertEqual(d['regions'],['대구'])

    def test_explicit_other_bid_document_rejected(self):
        with self.assertRaises(ValueError):
            app.parse_notice('R26BK99999999-000 '+TEXT,self.key)

    def test_missing_ratio_never_becomes_zero(self):
        d=app.parse_notice(TEXT.replace('49%','미공개'),self.key)
        self.assertIsNone(d['required'])
        self.assertTrue(d['issues'])

    def test_bad_percentage_rejected(self):
        d=app.parse_notice(TEXT.replace('(40%)','(45%)'),self.key)
        self.assertEqual(d['basis'],[])
        self.assertTrue(d['issues'])

    def test_office_address_does_not_define_region(self):
        text='서울특별시 서초구 서울지방조달청 '+TEXT
        self.assertEqual(app.parse_notice(text,self.key)['regions'],['대구'])

    def test_unknown_region_has_review_folder(self):
        text=TEXT.replace('대구광역시','미정')
        self.assertEqual(app.parse_notice(text,self.key)['regions'],['_확인필요'])

    def test_mixed_prohibition_overrides_both_words(self):
        t=TEXT.replace('혼합된 방식이 가능합니다','혼합된 방식이 가능하나 혼합방식은 불허')
        self.assertEqual(app.parse_notice(t,self.key)['mixed'],'불허')

    def test_evaluation_100_not_used_as_division(self):
        d=app.parse_notice(TEXT,self.key)
        self.assertEqual(d['basis'][0]['기계비율'],.6)

    def test_queue_is_idempotent_and_excludes_phones(self):
        self.row['수신번호']='secret'
        self.assertTrue(app.enqueue(self.row,state_dir=self.state,logger=lambda s:None))
        self.assertFalse(app.enqueue(self.row,state_dir=self.state,logger=lambda s:None))
        q=app.read_json(self.state/'queue'/(self.key+'.json'))
        self.assertNotIn('수신번호',q)

    def test_new_revision_is_new_job(self):
        self.queue()
        self.row['차수']='001'
        self.queue()
        self.assertEqual(len(list((self.state/'queue').glob('*.json'))),2)

    def test_non_fire_and_not_score_cap_not_queued(self):
        self.row['공고명']='건축공사'
        self.assertFalse(app.enqueue(self.row,state_dir=self.state))
        self.row['공고명']='소방공사'
        self.row['시공경험배점한도']=False
        self.assertFalse(app.enqueue(self.row,state_dir=self.state))

    def test_complete_source_preferred_over_incomplete_attachment(self):
        good=self.folder/'공사입찰설명서.hwpx';good.write_text(TEXT)
        self.row['_score_cap_source']=self.doc.name
        path=self.queue();ledger={}
        with patch.object(app,'matching_documents',return_value=[(self.doc,TEXT.replace('1.8.','9.8.')),(good,TEXT)]), \
             patch.object(app,'company_data',return_value=(COMPANIES,'')):
            result=app.process_job(path,self.data,self.output,self.state,ledger)
        self.assertEqual(result,'complete')

    def test_conflicting_complete_sources_require_review(self):
        other=self.folder/'변경공고.hwpx';other.write_text(TEXT)
        changed=TEXT.replace('(60%)','(55%)').replace('(40%)','(45%)')
        path=self.queue();ledger={}
        with patch.object(app,'matching_documents',return_value=[(self.doc,TEXT),(other,changed)]), \
             patch.object(app,'company_data',return_value=(COMPANIES,'')):
            result=app.process_job(path,self.data,self.output,self.state,ledger)
        self.assertEqual(result,'review_needed')
        self.assertTrue(ledger['jobs'][self.key]['issues'])

    def test_success_and_repeat(self):
        ledger={}
        path=self.queue()
        self.assertEqual(self.process(path,ledger),'complete')
        self.assertEqual(self.process(path,ledger),'skipped')
        self.assertEqual(ledger['jobs'][self.key]['attempts'],1)
        self.assertTrue((self.output/'대구').exists())

    def test_same_order_document_change_rebuilds(self):
        ledger={};path=self.queue()
        self.process(path,ledger)
        digest=ledger['jobs'][self.key]['digest']
        self.doc.write_text(TEXT+'\n수정')
        self.assertEqual(self.process(path,ledger),'complete')
        self.assertNotEqual(ledger['jobs'][self.key]['digest'],digest)

    def test_removed_output_regenerated(self):
        ledger={};path=self.queue();self.process(path,ledger)
        Path(ledger['jobs'][self.key]['files'][0]).unlink()
        self.assertEqual(self.process(path,ledger),'complete')

    def test_company_failure_keeps_retry_status_and_previous_list(self):
        ledger={};path=self.queue()
        self.assertEqual(self.process(path,ledger,'stale cache; retry'),'retry')
        self.assertTrue(path.exists())
        self.assertEqual(ledger['jobs'][self.key]['status'],'retry')
        self.assertTrue(ledger['jobs'][self.key]['files'])
        self.assertEqual(self.process(path,ledger,'stale cache; retry'),'deferred')
        ledger['jobs'][self.key]['next_retry']=0
        self.assertEqual(self.process(path,ledger),'complete')

    def test_excel_source_strings_not_formulas_and_dates_typed(self):
        from openpyxl import load_workbook
        ledger={};self.process(self.queue(),ledger)
        wb=load_workbook(ledger['jobs'][self.key]['files'][0])
        self.assertNotEqual(wb['업체목록']['B2'].data_type,'f')
        self.assertEqual(wb['업체목록']['G2'].value.year,2020)
        self.assertEqual(wb['분담비율']['G2'].value,'=D2-F2')

    def test_old_file_preserved_on_replace_error(self):
        p=self.output/'old.xlsx';p.write_bytes(b'original')
        d=app.parse_notice(TEXT,self.key)
        with patch.object(app.os,'replace',side_effect=PermissionError('open in Excel')):
            with self.assertRaises(PermissionError):
                app.write_workbook(p,d,COMPANIES,'',self.doc)
        self.assertEqual(p.read_bytes(),b'original')
        self.assertFalse(list(self.output.glob('.fire_share_*.xlsx')))

    def test_nas_unmounted_preserves_queue(self):
        p=self.queue()
        args=type('Args',(),dict(state=str(self.state),nas_mount='/fake',data_root=str(self.data),output=str(self.output)))()
        with patch.object(app.os.path,'ismount',return_value=False):
            self.assertEqual(app.run(args),75)
        self.assertTrue(p.exists())
        self.assertFalse(list(self.output.iterdir()))

    def test_cache_success_zero_not_failure(self):
        empty=dict(records=[],controls=[],fetched_at='today',fetched_epoch=1)
        with patch.object(app,'fetch_companies',return_value=empty):
            value,error=app.company_data('대구',self.state)
        self.assertFalse(error)
        self.assertEqual(value['records'],[])

    def test_unmapped_geography_never_fetches_global_directory(self):
        with self.assertRaises(ValueError):
            app.fetch_companies('_확인필요')

    def test_snapshot_path_cannot_escape_archive(self):
        self.row['첨부파일폴더']=str(self.root)
        self.assertEqual(app.source_folders(self.data,self.key,self.row),[self.folder])


if __name__=='__main__':
    unittest.main()
