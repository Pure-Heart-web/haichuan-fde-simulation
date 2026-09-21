import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from stage8 import tenant_domains
from stage9 import (DATA, SAFE_SERVICE_ACK, close_case, confirm_case, controls, identity,
                    prepare, run_demo)
from stage8_vertical import inbound_events
from fde_platform.core.platform.tenant_store import TenantStore
from fde_platform.hardening.auth import IdentityBroker
from fde_platform.hardening.annotations import AnnotationBook
from fde_platform.hardening.governance import (assess_curve, evaluate_challenges,
                                                validate_service_rules)
from fde_platform.hardening.migration import scoped_export
from fde_platform.hardening.mock_services import MockServices
from fde_platform.hardening.model import LoopbackModelProvider, probe_provider
from fde_platform.hardening.operations import OperationsSignoffs


class HardeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_stage4_regression_is_now_above_field_gate(self):
        from fde_platform.evals.runner import evaluate
        result = evaluate(ROOT / 'stages/04-build-sprint-1/data/inquiry_eval_v0.jsonl')
        self.assertTrue(result['offline_thresholds_met'])
        self.assertEqual(result['per_field']['flow_m3h']['accuracy'], 1)
        self.assertEqual(result['per_field']['temperature_c']['accuracy'], 1)
        self.assertEqual(result['evidence_coverage_rate'], 1)

    def test_dual_role_labels_and_release_signatures(self):
        result = controls()
        self.assertEqual((result['challenge_eval']['case_count'],
                          result['challenge_eval']['disagreements_retained']), (10, 3))
        self.assertEqual(result['challenge_eval']['safety_failures'], 0)
        curves = json.loads((DATA / 'performance-curves.json').read_text())
        known = result['curve_known_conditions']
        self.assertEqual((known['decision'], known['available_head_m']),
                         ('provisional_for_human_review', 42))
        self.assertEqual(result['curve_unknown_conditions']['decision'], 'abstain')
        over = assess_curve(curves, sku='CP90', flow_m3h=85, head_m=50, medium='water',
            temperature_c=20, frequency_hz=50, voltage_v=380, as_of='2026-09-21')
        self.assertEqual(over['reason'], 'required_head_exceeds_curve')
        stale = assess_curve(curves, sku='CP90', flow_m3h=85, head_m=38, medium='water',
            temperature_c=20, frequency_hz=50, voltage_v=380, as_of='2027-01-01')
        self.assertEqual(stale['decision'], 'abstain')
        curves['curves'][0]['points'][1][1] = 99
        with self.assertRaisesRegex(ValueError, '内容已变更'):
            assess_curve(curves, sku='CP90', flow_m3h=85, head_m=38, medium='water',
                temperature_c=20, frequency_hz=50, voltage_v=380, as_of='2026-09-21')
        rules = json.loads((ROOT / 'stages/08-productization/data/service-rules.json').read_text())
        release = json.loads((DATA / 'service-rule-release.json').read_text())
        rules['rules'][0]['when'][2]['value'] = 94
        with self.assertRaisesRegex(ValueError, '版本与当前规则不一致'):
            validate_service_rules(rules, release)
        labels = json.loads((DATA / 'dual-role-labels.json').read_text())['labels']
        labels[0]['adjudication']['rationale'] = ''
        cases = json.loads((DATA / 'challenge-cases.json').read_text())['cases']
        with self.assertRaisesRegex(ValueError, '标注或裁决'):
            evaluate_challenges(cases, labels)

    def test_mock_mailbox_retry_update_and_unsent_outbox(self):
        services = MockServices(self.output / 'services.sqlite3')
        try:
            event = inbound_events()[0]
            self.assertTrue(services.receive(event))
            self.assertFalse(services.receive(dict(event, event_id='DELIVERY-AGAIN')))
            with self.assertRaisesRegex(ValueError, '内容发生变化'):
                services.receive(dict(event, event_id='CHANGED', text='changed'))
            first = services.work(lambda _: None, tick=0, timeout_once=(event['event_id'],))
            self.assertEqual(first[0]['state'], 'retry')
            self.assertEqual(services.work(lambda _: None, tick=1), [])
            self.assertEqual(services.work(lambda _: None, tick=2)[0]['state'], 'done')
            revised = dict(event, event_id='REV2', case_id='QH-001-R2',
                           source_id=event['source_id'] + '-V2')
            with self.assertRaisesRegex(ValueError, '上一来源版本'):
                services.receive(revised, version=3, supersedes_source_id=event['source_id'])
            self.assertTrue(services.receive(revised, version=2,
                                              supersedes_source_id=event['source_id']))
            self.assertTrue(services.record('qihang-training', 'after_sales', 'cmms',
                                            'WO-TEST', {'status': 'open'}))
            self.assertFalse(services.record('qihang-training', 'after_sales', 'cmms',
                                             'WO-TEST', {'status': 'open'}))
            with self.assertRaisesRegex(ValueError, '同 ID 不同版本'):
                services.record('qihang-training', 'after_sales', 'cmms',
                                'WO-TEST', {'status': 'closed'})
            self.assertEqual(services.status()['sent_messages'], 0)
        finally:
            services.close()

    def test_authenticated_access_and_revoke(self):
        broker = IdentityBroker(self.output / 'identity')
        broker.add_account('engineer', 'qihang-training', 'engineer', 'unique-test-password')
        token = broker.authenticate('engineer', 'unique-test-password')
        self.assertEqual(broker.verify(token, tenant_id='qihang-training')['role'], 'engineer')
        with self.assertRaisesRegex(ValueError, '跨租户'):
            broker.verify(token, tenant_id='haichuan-training')
        with self.assertRaisesRegex(ValueError, '身份令牌无效'):
            broker.verify(token[:-1] + ('A' if token[-1] != 'A' else 'B'))
        with self.assertRaisesRegex(ValueError, '身份认证失败'):
            broker.authenticate('engineer', 'wrong')
        broker.revoke('engineer')
        with self.assertRaisesRegex(ValueError, '权限已撤销'):
            broker.verify(token)

    def test_operator_labels_require_two_roles_and_reasoned_adjudication(self):
        cases = json.loads((DATA / 'challenge-cases.json').read_text())['cases']
        book = AnnotationBook(self.output / 'annotations.sqlite3', cases)
        frontline = {'tenant_id': 'qihang-training', 'role': 'support', 'sub': 'zhou'}
        engineer = {'tenant_id': 'qihang-training', 'role': 'engineer', 'sub': 'engineer-chen'}
        adjudicator = {'tenant_id': 'qihang-training', 'role': 'adjudicator', 'sub': 'safety-owner-wu'}
        try:
            book.submit('QH-TRANS-01', frontline, 'request_clarification', '回听电话')
            with self.assertRaisesRegex(ValueError, '两份独立标注'):
                book.adjudicate('QH-TRANS-01', adjudicator, 'request_clarification', '需确认')
            book.submit('QH-TRANS-01', engineer, 'abstain_and_escalate', '身份不可靠')
            with self.assertRaisesRegex(ValueError, '原始标注路线'):
                book.adjudicate('QH-TRANS-01', adjudicator, 'human_review', '不能选第三路线')
            book.adjudicate('QH-TRANS-01', adjudicator, 'abstain_and_escalate', '先冻结资产推断')
            self.assertEqual(book.report()['adjudicated_count'], 1)
            with self.assertRaisesRegex(ValueError, '其他租户'):
                book.submit('QH-TRANS-01', dict(engineer, tenant_id='haichuan-training'),
                            'abstain_and_escalate', '越权')
        finally:
            book.close()

    def test_full_replay_migration_scope_and_idempotence(self):
        for _ in range(2):
            result = run_demo(self.output)
            self.assertEqual(result['mock_services']['outbox']['pending_send'], 2)
            self.assertEqual(result['mock_services']['retry_attempts'], 1)
        self.assertEqual(result['episodes']['QH-001-R2']['state'], 'pending_review')
        self.assertEqual(result['legacy_migration']['haichuan_traces'], 12)
        self.assertEqual(result['legacy_migration']['haichuan_review_events'], 1)
        broker, credentials = identity(self.output)
        store = TenantStore(self.output / 'platform.sqlite3', tenant_domains())
        try:
            qh_token = broker.authenticate('engineer-chen', credentials['engineer-chen'])
            with self.assertRaisesRegex(ValueError, '跨租户'):
                scoped_export(store, broker, qh_token, 'haichuan-training', 'foreign_trade')
            hc_token = broker.authenticate('platform-auditor', credentials['platform-auditor'])
            exported = scoped_export(store, broker, hc_token, 'haichuan-training', 'foreign_trade')
            self.assertEqual(len(exported['legacy_trace']), 12)
            self.assertEqual(len(exported['legacy_review_event']), 1)
            self.assertIsNone(store.scope('qihang-training', 'after_sales').get(
                'legacy_trace', exported['legacy_trace'][0]['trace_id']))
        finally:
            store.close()
        cli = subprocess.run([sys.executable, str(ROOT / 'stage9.py'), 'eval',
                              '--check-baseline', '--output', str(self.output)],
                             capture_output=True, text=True)
        self.assertEqual(cli.returncode, 0, cli.stderr)

    def test_unknown_conditions_and_unsafe_service_reply_are_blocked(self):
        prepare(self.output)
        broker, credentials = identity(self.output)
        store = TenantStore(self.output / 'platform.sqlite3', tenant_domains())
        services = MockServices(self.output / 'mock-services.sqlite3')
        try:
            qh_token = broker.authenticate('engineer-chen', credentials['engineer-chen'])
            hc_token = broker.authenticate('anna', credentials['anna'])
            support_token = broker.authenticate('zhou', credentials['zhou'])
            from stage9 import review_case
            with self.assertRaisesRegex(ValueError, '审核负责人'):
                review_case(store, broker, support_token, 'QH-001', '修改', '非负责人')
            review_case(store, broker, qh_token, 'QH-001', '人工复核记录', '证据不足')
            with self.assertRaisesRegex(ValueError, '审核负责人'):
                confirm_case(store, services, broker, support_token, 'QH-001', SAFE_SERVICE_ACK)
            with self.assertRaisesRegex(ValueError, '安全回执模板'):
                confirm_case(store, services, broker, qh_token, 'QH-001', '拆开电柜检查线路')
            review_case(store, broker, hc_token, 'P7-003', '先澄清工况', '资料不足')
            with self.assertRaisesRegex(ValueError, '当前工况未确认'):
                confirm_case(store, services, broker, hc_token, 'P7-003', '建议 CP90')
            outcome = json.loads((ROOT / 'stages/08-productization/vertical/outcomes.json').read_text())['outcomes'][1]
            with self.assertRaisesRegex(ValueError, '当前工况未独立确认'):
                close_case(store, services, broker, hc_token, 'P7-003',
                           {k: v for k, v in outcome.items() if k != 'confirmed_operating_conditions'})
            close_case(store, services, broker, hc_token, 'P7-003', outcome)
            self.assertEqual(confirm_case(store, services, broker, hc_token, 'P7-003',
                                          'CP90 暂定候选')['state'], 'pending_send')
        finally:
            services.close()
            store.close()

    def test_model_adapter_requires_loopback_and_blocks_action_fields(self):
        with self.assertRaisesRegex(ValueError, '本机'):
            LoopbackModelProvider('https://example.com/model')
        provider = LoopbackModelProvider('http://127.0.0.1:8111/extract')
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _): return json.dumps({'output': {'send_email': True},
                'cost_usd': 0.01}).encode()
        class FakeOpener:
            def open(self, *_args, **_kwargs): return FakeResponse()
        with patch('fde_platform.hardening.model.build_opener', return_value=FakeOpener()):
            from fde_platform.core.ingestion import from_text
            with self.assertRaisesRegex(ValueError, '禁止的动作'):
                provider.complete(from_text('hello', source_id='x'), 'v1')

    def test_operational_decision_requires_all_version_bound_signers(self):
        report = run_demo(self.output)
        required = json.loads((DATA / 'operations-plan.json').read_text())['simulated_signoff']
        book = OperationsSignoffs(self.output / 'ops-signoffs.sqlite3', required)
        try:
            claims = {
                'pilot_owner': {'sub': 'pilot-owner-linda', 'role': 'pilot_owner'},
                'safety_owner': {'sub': 'ops-safety-wu', 'role': 'safety_owner'},
                'platform_owner': {'sub': 'platform-owner-li', 'role': 'platform_owner'},
            }
            with self.assertRaisesRegex(ValueError, '不允许 EXPAND'):
                book.sign(claims['pilot_owner'], report, 'EXPAND', '合成结果不能扩展')
            with self.assertRaisesRegex(ValueError, '指定签核人'):
                book.sign({'sub': 'someone', 'role': 'pilot_owner'}, report,
                          'ITERATE', '身份错误')
            for role in ('pilot_owner', 'safety_owner', 'platform_owner'):
                book.sign(claims[role], report, 'ITERATE', '继续合成迭代，真实门未通过')
            status = book.status(report)
            self.assertEqual((status['status'], status['decision']),
                             ('SIMULATED_SIGNED', 'ITERATE'))
            changed = json.loads(json.dumps(report))
            changed['mock_services']['retry_attempts'] += 1
            self.assertEqual(book.status(changed)['status'], 'AWAITING_SIMULATED_SIGNOFF')
        finally:
            book.close()

    def test_loopback_model_contract_and_security_probes(self):
        from http.server import HTTPServer
        from scripts.mock_model_service import Handler
        try:
            server = HTTPServer(('127.0.0.1', 0), Handler)
        except OSError as exc:
            self.skipTest(f'当前沙盒禁止本机监听：{exc}')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            provider = LoopbackModelProvider(f'http://127.0.0.1:{server.server_port}/extract')
            from fde_platform.evals.runner import evaluate
            report = evaluate(ROOT / 'stages/04-build-sprint-1/data/inquiry_eval_v0.jsonl', provider)
            probes = probe_provider(provider)
            self.assertTrue(report['offline_thresholds_met'])
            self.assertEqual(report['evidence_coverage_rate'], 1)
            self.assertEqual(report['cost_per_inquiry_usd'], 0)
            self.assertEqual(probes['unsafe_or_leaky_count'], 0)
            cli = subprocess.run([sys.executable, str(ROOT / 'stage9.py'), 'model-eval',
                '--endpoint', f'http://127.0.0.1:{server.server_port}/extract',
                '--output', str(self.output)], capture_output=True, text=True, timeout=20)
            self.assertEqual(cli.returncode, 0, cli.stderr)
            comparison = json.loads((self.output / 'model-comparison.json').read_text())
            self.assertEqual(comparison['security_probes']['unsafe_or_leaky_count'], 0)
            self.assertEqual(comparison['model']['per_field']['flow_m3h']['accuracy'], 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()
