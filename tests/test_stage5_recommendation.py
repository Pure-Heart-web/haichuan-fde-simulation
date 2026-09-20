import json
from pathlib import Path
import re
import select
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fde_platform.core.rules.engine import RuleError, evaluate, validate_registry
from fde_platform.core.ingestion import from_text
from fde_platform.core.store import Store
from fde_platform.domains.foreign_trade.products.catalog import load_catalog
from fde_platform.domains.foreign_trade.products.search import search
from fde_platform.domains.foreign_trade.recommendation.eval import evaluate_dataset
from fde_platform.domains.foreign_trade.recommendation.service import load_components, recommend
from fde_platform.domains.foreign_trade.recommendation.store import RecommendationStore
from fde_platform.domains.foreign_trade.schema import InquiryRecord
from fde_platform.pipeline import process
from stage5 import import_stage4


class StageFiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog, cls.registry, cls.preferences = load_components(ROOT)

    def inquiry(self, **values):
        return InquiryRecord(work_item_id='test', product_type='centrifugal_pump',
                             medium_category='water', flow_m3h=85, head_m=38, **values)

    def result(self, inquiry):
        return recommend(inquiry, self.catalog, self.registry, self.preferences)

    def test_authoritative_catalog_and_quarantine(self):
        products = {x.sku: x for x in self.catalog.products}
        self.assertEqual(products['CP90'].flow_min_m3h, 80)
        self.assertEqual(products['CP90'].head_max_m, 42)
        self.assertEqual(products['CP90'].source_id, 'SRC-TECH')
        self.assertEqual(products['CP85-CI'].material, 'CAST_IRON')
        self.assertEqual(products['CP85-CI'].source_id, 'ST5-SUPP')
        self.assertEqual([x['sku'] for x in self.catalog.quarantined], ['CPX-UNK'])

    def test_search_boundaries_and_retired(self):
        found = search(InquiryRecord(work_item_id='b', product_type='centrifugal_pump',
                                     flow_m3h=70, head_m=32), self.catalog)
        self.assertEqual([p.sku for p in found.eligible], ['CP80'])
        self.assertIn('CP70-OLD', [x['sku'] for x in found.rejected])

    def test_seawater_excludes_cast_iron_and_records_rule_evidence(self):
        inquiry = InquiryRecord(work_item_id='sea', product_type='centrifugal_pump',
                                flow_m3h=88, head_m=38, medium_category='seawater')
        result = self.result(inquiry)
        self.assertNotIn('CP85-CI', result.candidate_skus)
        self.assertIn('CP85-CI', [x['sku'] for x in result.rejected_candidates])
        self.assertIn('PUMP_MATERIAL_001', [x['rule_id'] for x in result.triggered_rules])
        self.assertEqual(result.required_reviewer, 'engineer')
        self.assertEqual(result.candidates[0]['evidence']['source_id'], 'SRC-TECH')

    def test_high_temperature_rule_fires_without_candidate(self):
        inquiry = InquiryRecord(work_item_id='hot', product_type='centrifugal_pump',
                                flow_m3h=85, head_m=38, medium_category='water', temperature_c=90)
        result = self.result(inquiry)
        self.assertFalse(result.candidate_skus)
        self.assertIn('HIGH_TEMP_001', [x['rule_id'] for x in result.triggered_rules])
        self.assertTrue(result.requires_engineer_review)

    def test_candidate_rule_inactive_and_clean_case_sales(self):
        inquiry = InquiryRecord(work_item_id='clean', product_type='centrifugal_pump',
                                flow_m3h=75, head_m=35, medium_category='water')
        result = self.result(inquiry)
        self.assertEqual(result.candidate_skus, ('CP80',))
        self.assertFalse(result.requires_engineer_review)
        self.assertNotIn('CURVE_EDGE_001', [x['rule_id'] for x in result.triggered_rules])
        self.assertTrue(result.human_review_required)
        self.assertEqual(result.provisional_top_sku, 'CP80')

    def test_missing_medium_and_generic_pump_not_silently_matched(self):
        missing = InquiryRecord(work_item_id='missing', product_type='centrifugal_pump',
                                flow_m3h=85, head_m=38)
        result = self.result(missing)
        self.assertIn('MEDIUM_UNKNOWN_001', [x['rule_id'] for x in result.triggered_rules])
        self.assertTrue(result.requires_engineer_review)
        generic = InquiryRecord(work_item_id='generic', product_type='pump',
                                flow_m3h=85, head_m=38, medium_category='water')
        self.assertFalse(self.result(generic).candidate_skus)
        other = InquiryRecord(work_item_id='other', product_type='centrifugal_pump',
                              flow_m3h=85, head_m=38, medium_category='oil')
        self.assertTrue(self.result(other).requires_engineer_review)
        invalid = InquiryRecord(work_item_id='invalid', product_type='centrifugal_pump',
                                flow_m3h=float('nan'), head_m=38, medium_category='water')
        with self.assertRaisesRegex(ValueError, '有限数值'):
            self.result(invalid)

    def test_rule_dsl_rejects_executable_field(self):
        registry = json.loads(json.dumps(self.registry))
        registry['rules'][0]['when'][0]['field'] = '__import__("os")'
        with self.assertRaises(RuleError):
            validate_registry(registry)

    def test_review_events_and_role_boundary(self):
        inquiry = InquiryRecord(work_item_id='review', product_type='centrifugal_pump',
                                flow_m3h=88, head_m=38, medium_category='seawater')
        result = self.result(inquiry)
        with tempfile.TemporaryDirectory() as tmp:
            store = RecommendationStore(Path(tmp) / 'reviews.sqlite3')
            self.assertTrue(store.save(inquiry, result, 'test'))
            self.assertFalse(store.save(inquiry, result, 'test'))
            with self.assertRaisesRegex(ValueError, '工程师'):
                store.review('review', 'approve', 'Linda', 'sales', result.provisional_top_sku)
            with self.assertRaisesRegex(ValueError, '候选'):
                store.review('review', 'approve', 'Chen', 'engineer', 'CP85-CI')
            store.review('review', 'escalate', 'Linda', 'sales', reason='确认海水工况')
            store.review('review', 'approve', 'Chen', 'engineer', result.provisional_top_sku)
            self.assertEqual([x['action'] for x in store.reviews('review')], ['escalate', 'approve'])
            self.assertEqual(store.get_item('review')['result']['provisional_top_sku'], result.provisional_top_sku)
            store.close()

    def test_eval_denominators_and_cli(self):
        path = ROOT / 'stages/05-product-recommendation/data/matching-golden-draft.jsonl'
        report = evaluate_dataset(path, self.catalog, self.registry, self.preferences)
        self.assertEqual(report['case_count'], 24)
        self.assertEqual(report['candidate_labeled_cases'], 18)
        self.assertEqual(report['critical_rule_violations'], 0)
        self.assertLess(report['false_escalation_rate'], 0.5)
        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run([sys.executable, str(ROOT / 'stage5.py'), 'demo', '--output', tmp],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads((Path(tmp) / 'sprint-status.json').read_text())['review_queue_count'], 24)

    def test_stage4_human_review_handoff_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'stage4.sqlite3'
            old = Store(db)
            for key in ('approved', 'unreviewed', 'rejected'):
                work = from_text(f'Need centrifugal pump for seawater. Flow 88 m3/h, Head 38m. Ref {key}.', source_id=key)
                extracted, record = process(work)
                old.save_extraction(work, extracted, record)
                if key != 'unreviewed':
                    old.review(work.id, 'approve' if key == 'approved' else 'reject', 'Linda', None)
            old.close()
            self.assertEqual(import_stage4(Path(tmp) / 'stage5', db), 0)
            new = RecommendationStore(Path(tmp) / 'stage5/recommendations.sqlite3')
            self.assertEqual(len(new.list_items()), 1)
            self.assertEqual(new.list_items()[0]['origin'], 'stage4_human_review')
            new.close()

    def test_review_page_get_post_and_role_rejection(self):
        inquiry = InquiryRecord(work_item_id='WEB-SEA', product_type='centrifugal_pump',
                                flow_m3h=88, head_m=38, medium_category='seawater')
        with tempfile.TemporaryDirectory() as tmp:
            store = RecommendationStore(Path(tmp) / 'recommendations.sqlite3')
            store.save(inquiry, self.result(inquiry), 'test')
            store.close()
            proc = subprocess.Popen([sys.executable, str(ROOT / 'stage5.py'), 'review',
                                     '--output', tmp, '--port', '0'], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            try:
                ready, _, _ = select.select([proc.stdout], [], [], 5)
                self.assertTrue(ready, '审核服务未启动')
                line = proc.stdout.readline()
                found = re.search(r':(\d+)/', line)
                if not found and proc.poll() is not None:
                    stderr = proc.stderr.read()
                    if 'Operation not permitted' in stderr:
                        self.skipTest('当前沙盒禁止本地监听；在普通本机/CI 环境可运行 HTTP 测试')
                    self.fail(stderr or '审核服务启动失败')
                self.assertIsNotNone(found, line)
                url = f'http://127.0.0.1:{found.group(1)}/item/WEB-SEA'
                html = urlopen(url, timeout=5).read().decode()
                self.assertIn('CP85-CI', html)
                token = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
                base = {'csrf': token, 'reviewer': 'Linda', 'reviewer_role': 'sales',
                        'action': 'approve', 'chosen_sku': 'CP90'}
                try:
                    urlopen(Request(url, data=urlencode(base).encode()), timeout=5)
                    self.fail('sales 不得批准海水工程师任务')
                except Exception as exc:
                    self.assertIn('400', str(exc))
                base.update(action='escalate', reason='请工程师确认材质')
                urlopen(Request(url, data=urlencode(base).encode()), timeout=5)
            finally:
                proc.terminate()
                proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()
            store = RecommendationStore(Path(tmp) / 'recommendations.sqlite3')
            self.assertEqual(store.reviews('WEB-SEA')[0]['action'], 'escalate')
            store.close()


if __name__ == '__main__':
    unittest.main()
