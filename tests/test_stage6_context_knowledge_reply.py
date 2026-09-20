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
from fde_platform.core.context.resolution import resolve_fields, resolve_identity
from fde_platform.core.generation.draft import GeneratedClaim
from fde_platform.core.knowledge.retrieval import KnowledgeIndex
from fde_platform.core.policy.claims import ClaimPolicyError, load_claim_policy, validate_claims
from fde_platform.domains.foreign_trade.context.provider import ContextError, SimulatedContextProvider
from fde_platform.domains.foreign_trade.recommendation.service import load_components
from fde_platform.domains.foreign_trade.reply.eval import evaluate_context, evaluate_generation, evaluate_knowledge
from fde_platform.domains.foreign_trade.reply.store import DraftStore
from fde_platform.domains.foreign_trade.reply.workflow import run_case
from fde_platform.domains.foreign_trade.schema import InquiryRecord

DATA = ROOT / 'stages/06-context-knowledge-reply/data'


class StageSixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provider = SimulatedContextProvider(ROOT)
        cls.index = KnowledgeIndex(ROOT)
        cls.products = load_components(ROOT)
        cls.cases = {x['id']: x for x in (json.loads(line) for line in
                     (DATA / 'scenarios.jsonl').read_text(encoding='utf-8').splitlines())}

    def run_case(self, case_id):
        return run_case(self.cases[case_id], root=ROOT, context_provider=self.provider,
                        knowledge_index=self.index, product_components=self.products)

    def test_identity_exact_precedence_and_no_cross_customer_context(self):
        exact = resolve_identity(self.provider.entities, 'john@abcmarine.example', 'ABC Marine')
        self.assertEqual((exact.status, exact.customer_id, exact.method),
                         ('resolved', 'CUST-DEMO-001', 'exact_contact'))
        header = resolve_identity(self.provider.entities, 'John <john@abcmarine.example>', '')
        self.assertEqual(header.customer_id, 'CUST-DEMO-001')
        ambiguous = resolve_identity(self.provider.entities, 'unknown@unrelated.example', 'ABC Marine')
        self.assertEqual(ambiguous.status, 'needs_confirmation')
        self.assertIsNone(ambiguous.customer_id)
        conflict = resolve_identity(self.provider.entities, 'john@abcmarine.example', 'ABC Marine Equipment Ltd')
        self.assertEqual(conflict.status, 'needs_confirmation')
        self.assertIsNone(self.run_case('S6-003')['previous_order'])
        self.assertIsNone(self.run_case('S6-010')['previous_order'])

    def test_previous_order_contract_filters_cancelled_other_family_and_future(self):
        current = self.provider.previous_order('CUST-DEMO-001')
        self.assertEqual(current.source_id, 'S6-ORD-002')
        self.assertEqual(current.data['sku'], 'CP90')
        old = self.provider.previous_order('CUST-DEMO-001', as_of='2025-01-01')
        self.assertEqual(old.source_id, 'S6-ORD-001')
        self.provider.orders.append({**self.provider.orders[0], 'order_id': 'S6-ORD-TIE'})
        try:
            with self.assertRaisesRegex(ContextError, '同日多笔'):
                self.provider.previous_order('CUST-DEMO-001', as_of='2025-01-01')
        finally:
            self.provider.orders.pop()

    def test_historical_values_never_override_explicit_current(self):
        inquiry = InquiryRecord(work_item_id='W1', voltage_v=400, frequency_hz=60)
        prior = self.provider.previous_order('CUST-DEMO-001')
        fields = {x.field: x for x in resolve_fields(inquiry, prior, 'Same as last order.')}
        self.assertEqual((fields['voltage_v'].value, fields['voltage_v'].source_type), (400, 'explicit_current'))
        self.assertEqual((fields['sku'].value, fields['sku'].source_type), ('CP90', 'historical_reference'))
        self.assertEqual(inquiry.voltage_v, 400)
        without_reference = resolve_fields(InquiryRecord(work_item_id='W2'), prior, 'Need a pump.')
        self.assertFalse(without_reference)

    def test_knowledge_governance_filters_before_rank(self):
        warranty = self.index.retrieve('What is the warranty?', intent='warranty')
        self.assertEqual([x.document_id for x in warranty], ['WARRANTY-2026'])
        self.assertEqual(warranty[0].fact_value, '12 months from shipment')
        self.assertFalse(self.index.retrieve('Warranty?', intent='warranty', as_of='2025-01-01'))
        self.assertEqual(self.index.retrieve('CE CP90?', intent='ce', sku='CP90', region='EU')[0].document_id,
                         'CE-CP90-EU-2026')
        self.assertFalse(self.index.retrieve('CE CP80?', intent='ce', sku='CP80', region='EU'))
        self.assertFalse(self.index.retrieve('CE CP90?', intent='ce', sku='CP90', region='US'))
        self.assertFalse(self.index.retrieve('ATEX CP90?', intent='atex', sku='CP90', region='EU'))

    def test_claim_policy_rejects_unsupported_commitments(self):
        policy = load_claim_policy(ROOT)
        for claim in [GeneratedClaim('price', 'Our final price is $100.'),
                      GeneratedClaim('specific_delivery', 'We will ship in 4 weeks.'),
                      GeneratedClaim('warranty', '24 months from shipment.'),
                      GeneratedClaim('typical_lead_time', 'Delivery in 4 weeks.', ('LEADTIME-2026:LT26-1',)),
                      GeneratedClaim('final_product', 'CP90 is the final model.', ('SRC-TECH',)),
                      GeneratedClaim('final_product', 'CP90 is the final model.', ('SRC-TECH',), 'fake-approval')]:
            with self.subTest(claim=claim.claim_type), self.assertRaises(ClaimPolicyError):
                validate_claims([claim], {'LEADTIME-2026:LT26-1', 'SRC-TECH'}, policy)

    def test_reply_provenance_abstention_and_human_review_boundary(self):
        normal = self.run_case('S6-001')
        body = normal['draft']['body']
        self.assertIn('12 months from shipment', body)
        self.assertIn('selected CP90 EU configurations', body)
        self.assertIn('Please confirm whether the previous 380V', body)
        self.assertNotIn('24 months', body)
        self.assertTrue(normal['draft']['requires_review'])
        self.assertFalse(normal['draft']['sent'])
        self.assertEqual(normal['previous_order']['source_id'], 'S6-ORD-002')
        self.assertEqual(normal['knowledge_evidence']['warranty'][0]['document_id'], 'WARRANTY-2026')
        atex = self.run_case('S6-005')
        self.assertEqual([x['intent'] for x in atex['draft']['knowledge_gaps']], ['atex'])
        self.assertEqual(atex['draft']['knowledge_gaps'][0]['query'], 'atex for CP90')
        self.assertNotIn('ATEX documentation is available', atex['draft']['body'])
        self.assertIn('verify the ATEX information', atex['draft']['body'])
        lead = self.run_case('S6-006')['draft']['body']
        self.assertIn('subject to production confirmation', lead)
        self.assertIn('formal quotation once the required configuration is confirmed', lead)
        self.assertNotIn('final price is', lead)
        changed = run_case({'id': 'CHANGE', 'sender': 'john@abcmarine.example',
                            'text': 'Same as previous order. Need 30 pcs CP100 centrifugal pump.'},
                           root=ROOT, context_provider=self.provider, knowledge_index=self.index,
                           product_components=self.products)
        self.assertIn('You specified CP100 now; the previous order used CP90', changed['draft']['body'])

    def test_store_review_feedback_and_immutable_original(self):
        normal = self.run_case('S6-001')
        ambiguous = self.run_case('S6-003')
        atex = self.run_case('S6-005')
        outdoor = self.run_case('S6-008')
        with tempfile.TemporaryDirectory() as tmp:
            store = DraftStore(Path(tmp) / 'drafts.sqlite3')
            for artifact in (normal, ambiguous, atex, outdoor):
                self.assertTrue(store.save(artifact))
            self.assertFalse(store.save(normal))
            with self.assertRaisesRegex(ValueError, '身份未确认'):
                store.review('S6-003', 'approve', 'Linda', 'sales')
            with self.assertRaisesRegex(ValueError, '工程师'):
                store.review('S6-008', 'approve', 'Linda', 'sales')
            store.review('S6-001', 'approve', 'Linda', 'sales')
            store.review('S6-001', 'minor_edit', 'Linda', 'sales', edited_body='Dear John, revised text.')
            with self.assertRaisesRegex(ValueError, '未重新验证'):
                store.review('S6-001', 'approve', 'Linda', 'sales')
            self.assertEqual(store.get('S6-001')['artifact']['draft']['body'], normal['draft']['body'])
            self.assertEqual([x['action'] for x in store.reviews('S6-001')], ['approve', 'minor_edit'])
            self.assertEqual(store.gaps('S6-005')[0]['status'], 'open')
            store.confirm_gap('S6-005', 'atex', 'Quality', 'Only EX config under review')
            self.assertEqual(store.gaps('S6-005')[0]['status'], 'pending_governance')
            self.assertEqual(store.gaps('S6-005')[0]['human_answer'], 'Only EX config under review')
            self.assertFalse(self.index.retrieve('ATEX?', intent='atex', sku='CP90', region='EU'))
            feedback_eval = evaluate_generation(DATA / 'scenarios.jsonl', DATA / 'generation-eval-labels.jsonl',
                root=ROOT, provider=self.provider, index=self.index, products=self.products, review_store=store)
            self.assertEqual(feedback_eval['draft_acceptance_rate'], 1)
            self.assertEqual(feedback_eval['human_edit_rate'], 0.5)
            store.close()

    def test_eval_denominators_and_cli(self):
        context = evaluate_context(DATA / 'context-eval.jsonl', self.provider)
        knowledge = evaluate_knowledge(DATA / 'knowledge-eval.jsonl', self.index)
        generation = evaluate_generation(DATA / 'scenarios.jsonl', DATA / 'generation-eval-labels.jsonl',
            root=ROOT, provider=self.provider, index=self.index, products=self.products)
        self.assertEqual((context['case_count'], knowledge['case_count'], generation['case_count']), (12, 50, 10))
        self.assertEqual(knowledge['outdated_document_retrieval_rate'], 0)
        self.assertEqual(generation['unsupported_claim_rate'], 0)
        self.assertIsNone(generation['draft_acceptance_rate'])
        with tempfile.TemporaryDirectory() as tmp:
            proc = subprocess.run([sys.executable, str(ROOT / 'stage6.py'), 'demo', '--output', tmp],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            status = json.loads((Path(tmp) / 'sprint-status.json').read_text())
            self.assertEqual((status['draft_queue_count'], status['knowledge_gap_count']), (10, 2))
            self.assertEqual(status['sent_messages'], 0)

    def test_review_page_get_post(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DraftStore(Path(tmp) / 'drafts.sqlite3')
            store.save(self.run_case('S6-005'))
            store.close()
            proc = subprocess.Popen([sys.executable, str(ROOT / 'stage6.py'), 'review',
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
                url = f'http://127.0.0.1:{found.group(1)}/item/S6-005'
                html = urlopen(url, timeout=5).read().decode()
                self.assertIn('知识缺口', html)
                token = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
                data = {'csrf': token, 'kind': 'gap', 'intent': 'atex', 'owner': 'Quality',
                        'human_answer': 'Needs controlled document'}
                urlopen(Request(url, data=urlencode(data).encode()), timeout=5)
                data = {'csrf': token, 'kind': 'review', 'action': 'escalate', 'reviewer': 'Linda',
                        'reviewer_role': 'sales', 'comment': '确认 ATEX 文件'}
                urlopen(Request(url, data=urlencode(data).encode()), timeout=5)
            finally:
                proc.terminate()
                proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()
            store = DraftStore(Path(tmp) / 'drafts.sqlite3')
            self.assertEqual(store.gaps('S6-005')[0]['status'], 'pending_governance')
            self.assertEqual(store.reviews('S6-005')[0]['action'], 'escalate')
            store.close()


if __name__ == '__main__':
    unittest.main()
