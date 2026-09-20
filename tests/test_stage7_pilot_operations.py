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
from fde_platform.core.knowledge.retrieval import KnowledgeIndex
from fde_platform.core.pilot.data_release import analyze_latency_incident, incident_report, validate_product_candidate
from fde_platform.core.pilot.metrics import dashboard, load_events
from fde_platform.core.pilot.store import PilotStore
from fde_platform.domains.foreign_trade.context.provider import SimulatedContextProvider
from fde_platform.domains.foreign_trade.pilot.orchestration import classify_scope, review_tasks, simulate_case
from fde_platform.domains.foreign_trade.recommendation.service import load_components

DATA = ROOT / 'stages/07-pilot-operations/data'


class StageSevenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider = SimulatedContextProvider(ROOT)
        cls.index = KnowledgeIndex(ROOT)
        cls.products = load_components(ROOT)
        cls.cases = {x['id']: x for x in (json.loads(line) for line in
                     (DATA / 'pilot-scenarios.jsonl').read_text(encoding='utf-8').splitlines())}

    def simulate(self, case_id):
        return simulate_case(self.cases[case_id], root=ROOT, provider=self.provider,
                             index=self.index, products=self.products)

    def test_scope_shadow_hidden_and_fault_degradation(self):
        self.assertEqual([x for x in self.cases if classify_scope(self.cases[x])[0] == 'shadow'],
                         ['P7-006', 'P7-007', 'P7-008'])
        shadow_artifact, shadow_trace = self.simulate('P7-007')
        self.assertEqual(shadow_trace['mode'], 'shadow')
        self.assertEqual(review_tasks(self.cases['P7-007'], shadow_artifact, shadow_trace), ())
        crm, _ = self.simulate('P7-009')
        self.assertIsNone(crm['previous_order'])
        self.assertIn('temporarily unavailable', crm['draft']['body'])
        knowledge, _ = self.simulate('P7-010')
        self.assertFalse(knowledge['knowledge_evidence']['warranty'])
        self.assertNotIn('12 months', knowledge['draft']['body'])
        self.assertEqual(knowledge['draft']['knowledge_gaps'][0]['reason'], 'knowledge_service_unavailable')
        product, _ = self.simulate('P7-011')
        self.assertIsNone(product['recommendation'])
        reply, _ = self.simulate('P7-012')
        self.assertIsNone(reply['draft'])
        self.assertTrue(review_tasks(self.cases['P7-012'], reply, self.simulate('P7-012')[1])[0].payload['manual_fallback'])

    def test_trace_has_versions_decisions_and_no_raw_email(self):
        artifact, trace = self.simulate('P7-003')
        self.assertEqual(trace['case_id'], 'P7-003')
        self.assertEqual(trace['versions']['rule_registry_version'], 'pump-rules-sim-v1')
        self.assertIn('product_data_version', trace['versions'])
        self.assertEqual([x['stage'] for x in trace['spans']], [
            'ingestion', 'extraction', 'customer_resolution', 'order_context',
            'field_provenance', 'product_recommendation', 'knowledge_retrieval', 'reply_generation'])
        self.assertTrue(all(x['started_at'] and x['ended_at'] and x['input_reference'] for x in trace['spans']))
        self.assertEqual(trace['spans'][1]['metadata']['token_usage'], 0)
        self.assertIn('WARRANTY-2026', [x['document_id'] for x in trace['spans'][6]['metadata']['documents']])
        serialized = json.dumps(trace, ensure_ascii=False)
        self.assertNotIn(self.cases['P7-003']['text'], serialized)
        self.assertNotIn('Special_Discount', serialized)
        self.assertFalse(trace['raw_email_saved_in_trace'])
        self.assertTrue(artifact['draft']['requires_review'])

    def test_role_review_prerequisite_override_and_trace_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PilotStore(Path(tmp) / 'pilot.sqlite3')
            artifact, trace = self.simulate('P7-002')
            store.save_trace(trace)
            for task in review_tasks(self.cases['P7-002'], artifact, trace):
                store.save_task(task)
            with self.assertRaisesRegex(ValueError, '前置审核'):
                store.review('P7-002-SALES', 'mike', 'sales', 'approve')
            with self.assertRaisesRegex(ValueError, '无权'):
                store.review('P7-002-ENG', 'linda', 'sales', 'resolve')
            with self.assertRaisesRegex(ValueError, '原因分类'):
                store.review('P7-002-ENG', 'chen', 'engineer', 'override', '排序不合理')
            store.review('P7-002-ENG', 'chen', 'engineer', 'override', '排序不合理', 'bad_ranking')
            store.review('P7-002-SALES', 'mike', 'sales', 'approve')
            with self.assertRaisesRegex(ValueError, '已处理'):
                store.review('P7-002-SALES', 'mike', 'sales', 'approve')
            self.assertEqual([x['action'] for x in store.get_trace('P7-002')['human_review_events']],
                             ['override', 'approve'])
            self.assertEqual(len(store.list_tasks(actor_id='linda', role='sales')), 0)
            self.assertEqual(len(store.list_tasks(actor_id='mike', role='sales')), 1)
            shadow, shadow_trace = self.simulate('P7-007')
            store.save_trace(shadow_trace)
            from fde_platform.core.pilot.models import ReviewTask
            fake = ReviewTask('BAD', 'P7-007', shadow_trace['trace_id'], 'sales_draft', 'low',
                              'sales', 'mike', {}, {})
            with self.assertRaisesRegex(ValueError, 'Shadow'):
                store.save_task(fake)
            manual, manual_trace = self.simulate('P7-012')
            store.save_trace(manual_trace)
            for task in review_tasks(self.cases['P7-012'], manual, manual_trace):
                store.save_task(task)
            with self.assertRaisesRegex(ValueError, '无可验证草稿'):
                store.review('P7-012-SALES', 'linda', 'sales', 'approve')
            store.close()

    def test_data_release_and_latency_incident(self):
        mapping = ROOT / 'stages/05-product-recommendation/data/material-mapping.json'
        baseline = DATA / 'product-v12.json'
        bad = validate_product_candidate(mapping, baseline, DATA / 'product-v13-bad.json')
        fixed = validate_product_candidate(mapping, baseline, DATA / 'product-v13-fixed.json')
        self.assertEqual(bad['status'], 'BLOCKED')
        self.assertIn('unmapped_material:CP90:Stainless Steel 316', bad['problems'])
        self.assertEqual(fixed['status'], 'READY_FOR_SIMULATED_APPROVAL')
        incident = incident_report(bad, fixed)
        self.assertEqual(incident['classification'], 'data_contract_canonicalization')
        self.assertFalse(incident['published'])
        latency = analyze_latency_incident(json.loads((DATA / 'latency-incident.json').read_text()))
        self.assertEqual((latency['classification'], latency['dominant_stage']),
                         ('context_integration_bottleneck', 'crm_context'))
        self.assertFalse(latency['model_change_indicated'])

    def test_dashboard_segments_and_no_real_pilot_claim(self):
        events = load_events(DATA / 'pilot-events.jsonl')
        self.assertEqual(len(events), 180)
        config = json.loads((DATA / 'pilot-config.json').read_text())
        baseline = json.loads((DATA / 'baseline.json').read_text())
        report = dashboard(events, baseline, config['users'])
        self.assertEqual(report['real_pilot_release_gate'], 'NOT_EVALUATED')
        self.assertEqual(report['pilot_decision'], 'ITERATE_SIMULATION_ONLY')
        self.assertEqual(report['eligible_complex_cases'], 90)
        users = {x['segment']: x for x in report['segments']['user_id']}
        self.assertLess(users['linda']['eligible_complex_adoption'], users['mike']['eligible_complex_adoption'])
        weeks = {x['segment']: x for x in report['segments']['week']}
        self.assertLess(weeks[1]['eligible_complex_adoption'], weeks[2]['eligible_complex_adoption'])
        self.assertIsNone(report['ai']['engineer_escalation_recall'])
        self.assertEqual(report['system']['observed_api_cost_per_attempt_usd'], 0)

    def test_cli_demo_and_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run([sys.executable, str(ROOT / 'stage7.py'), 'demo', '--output', tmp],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            status = json.loads((Path(tmp) / 'pilot-status.json').read_text())
            self.assertEqual((status['trace_count'], status['shadow_case_count'], status['visible_review_tasks']),
                             (12, 3, 13))
            check = subprocess.run([sys.executable, str(ROOT / 'stage7.py'), 'eval', '--output', tmp,
                                    '--check-baseline'], capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stderr)
            trace = subprocess.run([sys.executable, str(ROOT / 'stage7.py'), 'trace', '--output', tmp,
                                    '--case', 'P7-003'], capture_output=True, text=True)
            self.assertEqual(trace.returncode, 0, trace.stderr)
            self.assertEqual(json.loads(trace.stdout)['mode'], 'pilot')

    def test_review_page_role_scope_and_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = PilotStore(Path(tmp) / 'pilot.sqlite3')
            artifact, trace = self.simulate('P7-001')
            store.save_trace(trace)
            for task in review_tasks(self.cases['P7-001'], artifact, trace):
                store.save_task(task)
            store.close()
            proc = subprocess.Popen([sys.executable, str(ROOT / 'stage7.py'), 'review',
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
                        self.skipTest('当前沙盒禁止本地监听；普通本机/CI 可运行 HTTP 测试')
                    self.fail(stderr or '审核服务启动失败')
                self.assertIsNotNone(found, line)
                base = f'http://127.0.0.1:{found.group(1)}'
                linda = base + '/item/P7-001-SALES?user=linda'
                html = urlopen(linda, timeout=5).read().decode()
                self.assertIn('草稿', html)
                self.assertIn('候选', html)
                token = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
                try:
                    urlopen(base + '/item/P7-001-SALES?user=anna', timeout=5)
                    self.fail('其他销售不应看到 Linda 的任务')
                except Exception as exc:
                    self.assertIn('404', str(exc))
                data = {'csrf': token, 'action': 'approve', 'comment': ''}
                urlopen(Request(linda, data=urlencode(data).encode()), timeout=5)
            finally:
                proc.terminate()
                proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()
            store = PilotStore(Path(tmp) / 'pilot.sqlite3')
            self.assertEqual(store.get_task('P7-001-SALES')['status'], 'completed')
            store.close()


if __name__ == '__main__':
    unittest.main()
