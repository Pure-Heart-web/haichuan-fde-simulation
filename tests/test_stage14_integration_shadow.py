import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from stage14 import (CONNECTORS, DEFAULT_EXTERNAL_EVIDENCE, IDENTITY,
                     OBSERVATIONS, check_report, read, run_demo)
from fde_platform.integrationlab.connectors import (ReadOnlyConnectorSandbox,
                                                     exercise_connectors)
from fde_platform.integrationlab.evidence import (evidence_manifest, shadow_metrics,
                                                   verify_manifest)
from fde_platform.integrationlab.gates import real_shadow_gate
from fde_platform.integrationlab.identity import RotatingLabOIDC, rehearse_oidc
from fde_platform.integrationlab.telemetry import LabCollector


class IntegrationShadowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_real_shadow_gate_requires_every_external_evidence_item(self):
        evidence = read(DEFAULT_EXTERNAL_EVIDENCE)
        blocked = real_shadow_gate(evidence)
        self.assertEqual(blocked['status'], 'AUTHORIZED_SHADOW_NOT_READY')
        self.assertEqual(len(blocked['missing_evidence']), 8)
        complete = {key: True for key in blocked['missing_evidence']}
        complete.update({'mode': 'authorized_customer_shadow',
                         'customer_writes_enabled': False,
                         'git_contains_customer_records': False})
        self.assertEqual(real_shadow_gate(complete)['status'], 'AUTHORIZED_SHADOW_READY')
        complete['customer_writes_enabled'] = True
        self.assertIn('safe_shadow_boundary',
                      real_shadow_gate(complete)['missing_evidence'])

    def test_connector_lab_resumes_rate_limit_and_blocks_write_drift_and_revoke(self):
        report = exercise_connectors(read(CONNECTORS))
        self.assertEqual(report['status'], 'CONNECTOR_LAB_PASSED')
        self.assertEqual(report['rate_limit_retries'], 2)
        self.assertEqual(report['duplicate_events'], 2)
        self.assertEqual(report['customer_writes'], 0)
        connector = ReadOnlyConnectorSandbox('test', [{'event_id': 'E',
            'source_id': 'S', 'source_version': 1, 'case_id': 'C',
            'received_at': 'now', 'subject': 's', 'body': 'b', 'kind': 'mail'}])
        with self.assertRaisesRegex(PermissionError, 'read_only'):
            connector.write({})
        broken = read(CONNECTORS)
        broken['connectors'][0]['records'][-1]['source_version'] = 3
        with self.assertRaisesRegex(ValueError, 'version_gap'):
            exercise_connectors(broken)

    def test_oidc_lab_checks_discovery_rotation_mfa_mapping_and_disable(self):
        report = rehearse_oidc(read(IDENTITY))
        self.assertTrue(report['key_rotation_verified'])
        self.assertEqual(report['disable_checks_blocked'], 2)
        self.assertFalse(report['enterprise_oidc_used'])
        provider = RotatingLabOIDC('https://lab.invalid/test', 'aud', 'tenant',
            {'engineers': 'engineer'}, {'a': b'a' * 32, 'b': b'b' * 32})
        token = provider.issue('actor', 'engineers')
        provider.rotate('b')
        self.assertEqual(provider.verify(token)['role'], 'engineer')
        provider.disable_group('engineers')
        with self.assertRaises(ValueError):
            provider.verify(token)

    def test_collector_drops_content_and_direct_identifier_attributes(self):
        collector = LabCollector(self.output / 'spans.jsonl')
        row = collector.export('test', 'trace', {'service.name': 'fde',
            'event.type': 'review', 'outcome': 'person@example.test',
            'body': 'raw content'})
        self.assertEqual(row['attributes'], {'service.name': 'fde',
                                             'event.type': 'review'})
        report = collector.flush()
        self.assertEqual(report['dropped_attribute_count'], 2)
        self.assertFalse(report['raw_content_exported'])
        self.assertNotIn('person@example.test', (self.output / 'spans.jsonl').read_text())

    def test_evidence_manifest_is_portable_and_detects_tampering(self):
        one = self.output / 'one.json'
        two = self.output / 'nested/two.json'
        one.write_text('{}')
        two.parent.mkdir()
        two.write_text('{"safe":true}')
        manifest = evidence_manifest(self.output, [one, two], {'mode': 'test'})
        self.assertTrue(verify_manifest(self.output, manifest))
        self.assertEqual([x['path'] for x in manifest['artifacts']],
                         ['nested/two.json', 'one.json'])
        two.write_text('{"safe":false}')
        self.assertFalse(verify_manifest(self.output, manifest))

    def test_shadow_metrics_keep_synthetic_and_actual_users_separate(self):
        report = shadow_metrics(read(OBSERVATIONS))
        self.assertEqual(report['case_count'], 12)
        self.assertEqual(report['user_count'], 3)
        self.assertEqual(report['actions'], {'accept': 6, 'edit': 3,
                                             'escalate': 2, 'abstain': 1})
        self.assertEqual(report['actual_customer_users'], 0)

    def test_infra_contract_uses_loopback_set_local_and_content_deletion(self):
        infra = ROOT / 'stages/14-integration-shadow/infra'
        compose = (infra / 'docker-compose.integration.yml').read_text()
        rls = (infra / 'postgres-session-rls.sql').read_text()
        collector = (infra / 'otel-collector.example.yaml').read_text()
        self.assertIn('127.0.0.1:55433:5432', compose)
        self.assertGreaterEqual(rls.count('SET LOCAL app.tenant_id'), 2)
        self.assertIn('pooled session leaked tenant-a rows', rls)
        for key in ('prompt', 'body', 'content', 'model.output', 'tool.arguments'):
            self.assertIn('key: ' + key, collector)
        self.assertIn('endpoint: 127.0.0.1:4317', collector)

    def test_full_demo_blocks_then_recovers_from_runtime_facts(self):
        report = run_demo(self.output, check_baseline=True)
        self.assertTrue(check_report(report))
        self.assertEqual(report['operational_gate']['before']['status'],
                         'OPERATIONAL_GATE_BLOCKED')
        self.assertEqual(report['operational_gate']['after']['status'],
                         'OPERATIONAL_GATE_READY')
        self.assertTrue(report['remediation']['all_incidents_resolved'])
        self.assertEqual(report['real_shadow_gate']['status'],
                         'AUTHORIZED_SHADOW_NOT_READY')
        self.assertFalse(report['real_customer_data_ingested'])
        manifest = read(self.output / 'evidence-manifest.json')
        self.assertTrue(verify_manifest(self.output, manifest))
        self.assertFalse(any(Path(x['path']).is_absolute() for x in manifest['artifacts']))

    def test_cli_demo_and_evidence_verification(self):
        result = subprocess.run([sys.executable, str(ROOT / 'stage14.py'), 'demo',
            '--output', str(self.output), '--check-baseline'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('真实客户动作 0', result.stdout)
        verify = subprocess.run([sys.executable, str(ROOT / 'stage14.py'),
            'verify-evidence', '--output', str(self.output)], capture_output=True, text=True)
        self.assertEqual(verify.returncode, 0, verify.stderr)
        self.assertIn('true', verify.stdout)


if __name__ == '__main__':
    unittest.main()
