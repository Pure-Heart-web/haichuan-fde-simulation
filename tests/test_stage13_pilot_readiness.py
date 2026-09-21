import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from stage13 import (BUNDLE, POSTGRES_SQL, check_report, read, run_demo,
                     workbench_runtime)
from fde_platform.fieldops.authorization import (controlled, digest,
                                                  validate_bundle,
                                                  validate_postgres_rls)
from fde_platform.fieldops.identity import TrainingOIDCBroker
from fde_platform.fieldops.ledger import FieldOpsLedger
from fde_platform.fieldops.observability import SafeSpanWriter
from fde_platform.fieldops.workbench import WORKBENCH_HTML, workbench_contract
from fde_platform.runtime.api import handler_for


class PilotReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.bundle = read(BUNDLE)

    def tearDown(self):
        self.temp.cleanup()

    def test_authorization_bundle_is_hash_bound_and_external_mount_only(self):
        result = validate_bundle(self.bundle, ROOT)
        self.assertEqual(result['status'], 'SYNTHETIC_FIELD_BUNDLE_APPROVED')
        changed = json.loads(json.dumps(self.bundle))
        changed['data_boundary']['git_storage_allowed'] = True
        signature = digest(controlled(changed))
        for item in changed['approvals']:
            item['content_sha256'] = signature
        with self.assertRaisesRegex(ValueError, '外置挂载'):
            validate_bundle(changed, ROOT)
        changed = json.loads(json.dumps(self.bundle))
        changed['operations']['stop_owner'] = 'somebody-else'
        with self.assertRaisesRegex(ValueError, '签核同一授权包'):
            validate_bundle(changed, ROOT)

    def test_postgres_contract_requires_enable_force_and_policy_per_table(self):
        sql = POSTGRES_SQL.read_text()
        report = validate_postgres_rls(sql)
        self.assertEqual(report['status'], 'POSTGRES_RLS_CONTRACT_READY')
        self.assertFalse(report['runtime_executed_against_postgres'])
        broken = sql.replace('ALTER TABLE outbox FORCE ROW LEVEL SECURITY;', '')
        blocked = validate_postgres_rls(broken)
        self.assertEqual(blocked['status'], 'POSTGRES_RLS_CONTRACT_BLOCKED')
        self.assertFalse(blocked['checks']['outbox_rls_forced'])
        compose = (ROOT / 'stages/13-pilot-readiness/infra/docker-compose.postgres.yml').read_text()
        script = (ROOT / 'stages/13-pilot-readiness/infra/verify-rls.sh').read_text()
        self.assertIn('127.0.0.1:55432:5432', compose)
        self.assertIn('cross-tenant insert unexpectedly succeeded', script)

    def test_training_oidc_checks_issuer_audience_tenant_role_expiry_and_revoke(self):
        broker = TrainingOIDCBroker(b'x' * 32,
            issuer='https://training.invalid/test', audience='workbench',
            tenant_id='tenant-a', ttl_seconds=60)
        broker.add_account('actor', 'operator', 'training-code-123')
        token = broker.authenticate('actor', 'training-code-123', now=100)
        claims = broker.verify(token, tenant_id='tenant-a', role='operator', now=101)
        self.assertEqual(claims['sub'], 'actor')
        for kwargs in ({'tenant_id': 'tenant-b', 'now': 101},
                       {'role': 'auditor', 'now': 101}, {'now': 161}):
            with self.assertRaises(ValueError):
                broker.verify(token, **kwargs)
        broker.revoke(token)
        with self.assertRaises(ValueError):
            broker.verify(token, now=102)

    def test_field_ledger_enforces_roles_and_detects_tamper(self):
        path = self.output / 'ledger.jsonl'
        ledger = FieldOpsLedger(path, 'tenant-a')
        with self.assertRaisesRegex(ValueError, '角色'):
            ledger.append('sales', 'sales', 'baseline_restored', 'bad role',
                          shift_id='S1')
        ledger.append('operator', 'operator', 'shift_start', 'start', shift_id='S1')
        ledger.append('operator', 'operator', 'shift_end', 'end', shift_id='S1')
        self.assertTrue(ledger.summary()['hash_chain_valid'])
        rows = path.read_text().splitlines()
        changed = json.loads(rows[0])
        changed['detail'] = 'tampered'
        rows[0] = json.dumps(changed)
        path.write_text('\n'.join(rows) + '\n')
        with self.assertRaisesRegex(ValueError, '事件链损坏'):
            ledger.events()

    def test_safe_spans_reject_content_and_direct_identifiers(self):
        writer = SafeSpanWriter(self.output / 'spans.jsonl')
        writer.write('fde.pilot.shift_start', {'tenant_hash': '55dfc7c4',
            'shift_id': 'S1', 'event_type': 'shift_start', 'outcome': 'recorded'},
            object_id='CASE-1')
        with self.assertRaisesRegex(ValueError, '未授权'):
            writer.write('bad', {'prompt': 'raw customer body'}, object_id='CASE-2')
        with self.assertRaisesRegex(ValueError, '直接标识'):
            writer.write('bad', {'outcome': 'person@example.test'}, object_id='CASE-3')
        summary = writer.summary()
        self.assertEqual(summary['span_count'], 1)
        self.assertFalse(summary['raw_customer_content_logged'])

    def test_workbench_connects_all_required_human_actions(self):
        report = workbench_contract()
        self.assertEqual(report['actions_present'], report['required_actions'])
        self.assertIn('Stage 13', WORKBENCH_HTML)
        self.assertIn('browser_memory_only', report['token_storage'])
        self.assertEqual(report['customer_delivery_target'], 'local_mock_only')

    def test_full_demo_matches_baseline_and_preserves_real_world_boundary(self):
        report = run_demo(self.output, check_baseline=True)
        self.assertTrue(check_report(report))
        self.assertEqual(report['status'], 'SYNTHETIC_FIELD_REHEARSAL_READY')
        self.assertFalse(report['postgres']['runtime_executed_against_postgres'])
        self.assertFalse(report['identity']['enterprise_sso_used'])
        self.assertEqual(report['external_customer_actions'], 0)
        self.assertFalse(report['real_customer_data_ingested'])
        self.assertEqual(report['actual_pilot_users'], 0)
        self.assertEqual(report['model_lab']['rollout']['active_route'], 'baseline')
        spans = (self.output / 'otel-spans.jsonl').read_text()
        self.assertNotIn('person@example.test', spans)
        self.assertNotIn('SIM-SECRET-CANARY', spans)

    def test_workbench_http_requires_oidc_and_returns_role_scoped_queue(self):
        manifest, broker, codes, store, service, worker, dispatcher = workbench_runtime(
            self.output)
        try:
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(
                service, worker, dispatcher, console_html=WORKBENCH_HTML))
        except OSError as exc:
            store.close()
            self.skipTest(f'当前沙盒禁止本机监听：{exc}')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            self.assertIn('Stage 13', urlopen(base + '/').read().decode())
            with self.assertRaises(HTTPError):
                urlopen(base + '/v1/cases')
            token = broker.authenticate('dp-auditor', codes['dp-auditor'])
            request = Request(base + '/v1/cases',
                              headers={'Authorization': 'Bearer ' + token})
            self.assertEqual(len(json.load(urlopen(request))['cases']), 35)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            store.close()

    def test_cli_demo(self):
        result = subprocess.run([sys.executable, str(ROOT / 'stage13.py'), 'demo',
            '--output', str(self.output), '--check-baseline'],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('真实数据 0，客户动作 0', result.stdout)


if __name__ == '__main__':
    unittest.main()
