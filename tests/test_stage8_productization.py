import json
from pathlib import Path
import re
import select
import subprocess
import sys
import tempfile
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from stage8 import cases, seed, tenant_domains
from fde_platform.core.ingestion import from_text
from fde_platform.core.platform.contracts import ContextRequest, EntityRef
from fde_platform.core.platform.runtime import ScopedKnowledgeIndex, evaluate_rules
from fde_platform.core.platform.tenant_store import TenantStore
from fde_platform.domains.after_sales.context import AssetContextProvider
from fde_platform.domains.after_sales.diagnosis import ALLOWED_ACTIONS, ALLOWED_FIELDS, diagnose
from fde_platform.domains.after_sales.extraction import extract_service_case
from fde_platform.domains.after_sales.workflow import process_service_case


class StageEightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = TenantStore(Path(self.temp.name) / 'platform.sqlite3', tenant_domains())
        seed(self.store)
        self.qh = self.store.scope('qihang-training', 'after_sales')
        self.hc = self.store.scope('haichuan-training', 'foreign_trade')
        self.cases = {x['id']: x for x in cases()}

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_tenant_scope_precedes_retrieval_and_review(self):
        qh_docs = ScopedKnowledgeIndex(self.qh).retrieve(intent='e37', as_of='2026-09-21', model='QH-75', role='engineer')
        self.assertEqual([x['document_id'] for x in qh_docs], ['QH-E37-2026'])
        self.assertEqual(ScopedKnowledgeIndex(self.hc).retrieve(
            intent='e37', as_of='2026-09-21', model='QH-75', role='engineer'), ())
        self.assertIsNone(self.qh.get('knowledge', 'HC-WARRANTY-SIM'))
        with self.assertRaisesRegex(ValueError, '范围不匹配'):
            self.qh.put('knowledge', 'LEAK', {'tenant_id': 'haichuan-training'})
        with self.assertRaisesRegex(ValueError, 'Domain 不匹配'):
            self.store.scope('qihang-training', 'foreign_trade')
        artifact = process_service_case(self.cases['QH-001'], self.qh)
        self.assertIsNone(self.hc.get('trace', artifact['trace']['trace_id']))
        self.assertIsNone(self.hc.get('review_task', artifact['review_task']['task_id']))
        with self.assertRaisesRegex(ValueError, '当前租户'):
            self.hc.review(artifact['review_task']['task_id'], 'engineer-chen', 'engineer', 'resolve', '核对')
        with self.assertRaisesRegex(ValueError, '跨租户'):
            AssetContextProvider(self.qh).get_context(
                EntityRef('haichuan-training', 'foreign_trade', 'asset', 'QH7519238'),
                ContextRequest('maintenance_history', '2026-09-21'))

    def test_context_changes_domain_ranking_without_core_change(self):
        case = self.cases['QH-001']
        work = from_text(case['text'], source_id=case['id'], tenant_id='qihang-training',
                         domain='after_sales', source_type='ticket')
        extraction, service = extract_service_case(work)
        self.assertEqual(extraction.status, 'extracted')
        self.assertEqual((service.serial_number, service.error_code, service.current_pressure_bar),
                         ('QH7519238', 'E37', 5.0))
        context = AssetContextProvider(self.qh).get_context(
            EntityRef('qihang-training', 'after_sales', 'asset', service.serial_number),
            ContextRequest('maintenance_history', case['as_of']))
        old, _, _ = diagnose(service, context, self.qh, as_of=case['as_of'], use_context=False)
        new, _, provenance = diagnose(service, context, self.qh, as_of=case['as_of'])
        self.assertEqual(old.options[0].code, 'inspect_intake_condition')
        self.assertEqual(new.options[0].code, 'review_maintenance_work_order')
        self.assertTrue(provenance['recent_maintenance_used'])
        self.assertEqual(context[0].source_id, 'WO-QH-110')

    def test_safety_rules_and_human_review(self):
        critical = process_service_case(self.cases['QH-002'], self.qh)
        self.assertEqual(critical['recommendation']['risk_level'], 'critical')
        self.assertIn('SERVICE_E37_003', [x['rule_id'] for x in critical['rule_hits']])
        self.assertEqual(critical['review_task']['assignee_role'], 'engineer')
        with self.assertRaisesRegex(ValueError, '安全阻断'):
            self.qh.review('QH-002-REVIEW', 'engineer-chen', 'engineer', 'approve')
        with self.assertRaisesRegex(ValueError, '无权'):
            self.qh.review('QH-002-REVIEW', 'zhou', 'support', 'resolve', '已看')
        self.qh.review('QH-002-REVIEW', 'engineer-chen', 'engineer', 'resolve', '需按安全 SOP 线下复核')
        self.assertEqual(self.qh.feedback('QH-002-REVIEW')[0]['action'], 'resolve')
        with self.assertRaisesRegex(ValueError, '已有审核'):
            self.qh.review('QH-002-REVIEW', 'engineer-chen', 'engineer', 'resolve', '重复')
        low = process_service_case(self.cases['QH-003'], self.qh)
        self.assertEqual(low['review_task']['assignee_role'], 'support')
        self.qh.review('QH-003-REVIEW', 'zhou', 'support', 'approve')
        self.assertEqual(len(self.qh.feedback('QH-003-REVIEW')), 1)

    def test_missing_asset_and_rule_allowlist(self):
        unknown = process_service_case(self.cases['QH-004'], self.qh)
        self.assertEqual(unknown['recommendation']['options'][0]['code'], 'verify_asset_identity')
        self.assertFalse(unknown['provenance']['asset_known'])
        bad_rule = {'id': 'BAD', 'status': 'active', 'effective_date': '2026-01-01',
                    'source_ids': ['SIM'], 'severity': 'high',
                    'when': [{'field': 'customer.discount', 'op': 'equals', 'value': 1}],
                    'actions': ['engineer_review']}
        with self.assertRaisesRegex(ValueError, '未批准字段'):
            evaluate_rules({}, [bad_rule], allowed_fields=ALLOWED_FIELDS,
                           allowed_actions=ALLOWED_ACTIONS, as_of='2026-09-21')

    def test_cli_fresh_output_regression_and_idempotence(self):
        output = Path(self.temp.name) / 'cli'
        for _ in range(2):
            run = subprocess.run([sys.executable, str(ROOT / 'stage8.py'), 'demo', '--output', str(output)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
        check = subprocess.run([sys.executable, str(ROOT / 'stage8.py'), 'eval', '--check-baseline',
                                '--output', str(output)], capture_output=True, text=True)
        self.assertEqual(check.returncode, 0, check.stderr)
        status = json.loads((output / 'platform-status.json').read_text())
        self.assertEqual((status['qihang_cases'], status['haichuan_bridge_cases'], status['real_pilot_users']),
                         (10, 1, 0))
        report = json.loads((output / 'stage8-eval.json').read_text())
        self.assertEqual((report['field_correct'], report['top1_correct'], report['unsafe_auto_guidance_count']),
                         (50, 10, 0))
        wrong_tenant = subprocess.run([sys.executable, str(ROOT / 'stage8.py'), 'trace', '--case', 'QH-001',
                                       '--tenant', 'haichuan-training', '--output', str(output)],
                                      capture_output=True, text=True)
        self.assertEqual(wrong_tenant.returncode, 2)

    def test_service_review_page_is_domain_specific_and_scoped(self):
        process_service_case(self.cases['QH-001'], self.qh)
        process_service_case(self.cases['QH-003'], self.qh)
        proc = subprocess.Popen([sys.executable, str(ROOT / 'stage8.py'), 'review',
                                 '--output', self.temp.name, '--port', '0'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            ready, _, _ = select.select([proc.stdout], [], [], 5)
            self.assertTrue(ready, '售后页面未启动')
            line = proc.stdout.readline()
            if line.startswith('Stage 8：'):
                line = proc.stdout.readline()
            found = re.search(r':(\d+)/', line)
            if not found and proc.poll() is not None:
                stderr = proc.stderr.read()
                if 'Operation not permitted' in stderr:
                    self.skipTest('当前沙盒禁止本地监听')
                self.fail(stderr or '页面启动失败')
            self.assertIsNotNone(found, line)
            base = f'http://127.0.0.1:{found.group(1)}'
            engineer = base + '/item/QH-001-REVIEW?user=engineer-chen'
            html = urlopen(engineer, timeout=5).read().decode()
            self.assertIn('最近维修', html)
            self.assertIn('WO-QH-110', html)
            self.assertNotIn('Reply Draft', html)
            with self.assertRaises(HTTPError) as denied:
                urlopen(base + '/item/QH-001-REVIEW?user=zhou', timeout=5)
            self.assertEqual(denied.exception.code, 404)
            token = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
            data = urlencode({'csrf': token, 'action': 'resolve', 'reason': '按 SOP 线下核查'}).encode()
            urlopen(Request(engineer, data=data), timeout=5)
        finally:
            proc.terminate()
            proc.wait(timeout=5)
            proc.stdout.close()
            proc.stderr.close()
        self.assertEqual(self.qh.feedback('QH-001-REVIEW')[0]['action'], 'resolve')


if __name__ == '__main__':
    unittest.main()
