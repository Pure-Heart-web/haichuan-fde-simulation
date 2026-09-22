import io
import json
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

from scripts.build_stage11_dataset import records
from stage11 import (build_runtime, prepare, read, run_demo, run_worker)
from fde_platform.runtime.api import handler_for
from fde_platform.runtime.store import RuntimeStore
from fde_platform.runtime.worker import (DeliveryWorker, LocalHttpSink,
    OutboxDispatcher, RecordingMockSink)


class DeliveryRoomTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_dataset_has_cases_updates_duplicates_and_risks(self):
        events = records()
        self.assertEqual(len(events), 46)
        self.assertEqual(len({x['case_id'] for x in events}), 36)
        self.assertEqual(sum(x['source_version'] == 2 for x in events), 4)
        event_ids = [x['event_id'] for x in events]
        self.assertEqual(len(event_ids) - len(set(event_ids)), 6)
        self.assertEqual(sum('Ignore previous' in x['body'] for x in events), 4)

    def test_durable_ingest_changed_event_version_and_lease_recovery(self):
        manifest, broker, credentials, store, service = build_runtime(self.output)
        try:
            token = (self.output / 'connector-service.token').read_text().strip()
            raw = records()[0]
            self.assertEqual(service.accept(raw, token)['state'], 'created')
            self.assertEqual(service.accept(raw, token)['state'], 'duplicate')
            with self.assertRaisesRegex(ValueError, '内容发生变化'):
                service.accept(dict(raw, body=raw['body'] + ' changed'), token)
            with self.assertRaisesRegex(ValueError, '期望 2'):
                service.accept(dict(raw, event_id='jump', source_version=3), token)
            claimed = store.claim_job('crashed-worker', 0)
            self.assertEqual(claimed['event_id'], raw['event_id'])
        finally:
            store.close()
        reopened = RuntimeStore(self.output / 'delivery-room.sqlite3',
                                manifest['tenant_id'], manifest['domain'])
        try:
            self.assertEqual(reopened.recover_leases(3), 1)
            self.assertEqual(reopened.claim_job('replacement-worker', 3)['attempt_count'], 2)
        finally:
            reopened.close()

    def test_review_assignment_and_two_person_outbox(self):
        prepare(self.output)
        run_worker(self.output)
        manifest, broker, credentials, store, service = build_runtime(self.output)
        try:
            case = store.cases(manifest['tenant_id'], 'controller')[0]
            sales = broker.authenticate('dp-sales-lin', credentials['dp-sales-lin'])
            engineer = broker.authenticate('dp-engineer-wu', credentials['dp-engineer-wu'])
            assignee_token = engineer if case['assignee_role'] == 'engineer' else sales
            wrong_token = sales if case['assignee_role'] == 'engineer' else engineer
            with self.assertRaisesRegex(ValueError, '负责人'):
                service.review(wrong_token, case['case_id'], 'accept', 'wrong reviewer')
            with self.assertRaisesRegex(ValueError, '直接邮箱'):
                service.review(assignee_token, case['case_id'], 'accept',
                               'contact person@example.test')
            reviewed = service.review(assignee_token, case['case_id'], 'accept', 'evidence checked')
            self.assertIsNotNone(reviewed['message_id'])
            sink = RecordingMockSink()
            self.assertIsNone(OutboxDispatcher(store, sink).once(0))
            self.assertEqual(len(sink.deliveries), 0)
            with self.assertRaisesRegex(ValueError, 'Release Manager'):
                service.approve(assignee_token, reviewed['message_id'])
            release = broker.authenticate('dp-release-li', credentials['dp-release-li'])
            self.assertTrue(service.approve(release, reviewed['message_id']))
            result = OutboxDispatcher(store, sink).once(0)
            self.assertEqual(result['state'], 'delivered')
            self.assertEqual(len(sink.deliveries), 1)
            self.assertEqual(store.metrics()['unapproved_deliveries'], 0)
        finally:
            store.close()

    def test_local_http_sink_restricts_endpoint_and_carries_idempotency(self):
        with self.assertRaisesRegex(ValueError, '本机'):
            LocalHttpSink('https://example.com/deliveries', 'token')

        captured = {}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def read(self, _): return b'{"mock_delivery":true,"status":"accepted"}'
        class Opener:
            def open(self, request, timeout):
                captured['authorization'] = request.get_header('Authorization')
                captured['idempotency'] = request.get_header('Idempotency-key')
                return Response()
        sink = LocalHttpSink('http://127.0.0.1:9999/deliveries', 'local-token', Opener())
        result = sink.deliver({'idempotency_key': 'KEY-1', 'payload': {'safe': True}})
        self.assertTrue(result['mock_delivery'])
        self.assertEqual(captured, {'authorization': 'Bearer local-token',
                                    'idempotency': 'KEY-1'})

    def test_privacy_scan_parses_json_before_scanning_numeric_telemetry(self):
        store = RuntimeStore(self.output / 'typed-scan.sqlite3', 'tenant-a', 'foreign_trade')
        event = {'tenant_id': 'tenant-a', 'domain': 'foreign_trade', 'event_id': 'E1',
            'source_id': 'S1', 'source_version': 1, 'case_id': 'C1',
            'contact_ref': 'CONTACT-safe', 'customer_ref': 'CUSTOMER-safe',
            'subject': 'safe', 'body': 'safe', 'received_at': '2026-09-22T00:00:00Z'}
        try:
            store.accept(event)
            store.claim_job('worker', 0)
            store.complete_job('E1', {'route': 'sales_review', 'assignee_id': 'sales-1',
                'assignee_role': 'sales', 'latency_ms': 13800001234.125,
                'external_side_effects': []})
            self.assertEqual(store.privacy_scan()['rows_with_direct_identifier'], 0)
        finally:
            store.close()

    def test_full_demo_metrics_privacy_and_restart(self):
        report = run_demo(self.output, check_baseline=True)
        self.assertEqual(report['intake']['total_received'], 46)
        self.assertEqual(report['workflow']['case_count'], 35)
        self.assertEqual(report['workflow']['reviewed'], 35)
        self.assertEqual(report['delivery']['states'], {'dead': 1, 'delivered': 26})
        self.assertEqual(report['delivery']['real_customer_deliveries'], 0)
        self.assertEqual(report['security']['rows_with_direct_identifier'], 0)
        self.assertTrue(report['runtime']['durable_restart_verified'])
        self.assertEqual(report['runtime']['incident_count'], 2)
        self.assertEqual(report['real_pilot_gate'], 'NOT_EVALUATED')
        markers = (b'operator1@example.test', b'Design Partner Alpha')
        for path in self.output.rglob('*'):
            if path.is_file():
                for marker in markers:
                    self.assertNotIn(marker, path.read_bytes(), f'PII leak in {path}')

    def test_dead_letter_replay_requires_operator_and_preserves_approval(self):
        run_demo(self.output)
        manifest, broker, credentials, store, service = build_runtime(
            self.output, db_name='delivery-room-demo.sqlite3')
        try:
            engineer = broker.authenticate('dp-engineer-wu', credentials['dp-engineer-wu'])
            operator = broker.authenticate('dp-operator-zhou', credentials['dp-operator-zhou'])
            with self.assertRaisesRegex(ValueError, '运行操作权限'):
                service.requeue_event(engineer, 'DR-E017-V1', 'mapping fixed')
            self.assertTrue(service.requeue_event(operator, 'DR-E017-V1', 'mapping v2 approved'))
            dead_message = next(x['message_id'] for x in store.outbox() if x['state'] == 'dead')
            self.assertTrue(service.requeue_message(operator, dead_message,
                                                    'target reconciled and available'))
            self.assertTrue(all(x['state'] == 'recovering'
                                for x in store.metrics()['incidents']))
            DeliveryWorker(store, service.components).drain()
            OutboxDispatcher(store, RecordingMockSink()).drain()
            metrics = store.metrics()
            self.assertEqual(metrics['inbox'].get('dead', 0), 0)
            self.assertEqual(metrics['outbox'].get('dead', 0), 0)
            self.assertTrue(all(x['state'] == 'resolved' for x in metrics['incidents']))
        finally:
            store.close()

    def test_http_api_health_auth_and_queue(self):
        prepare(self.output)
        run_worker(self.output)
        manifest, broker, credentials, store, service = build_runtime(self.output)
        worker = DeliveryWorker(store, service.components)
        dispatcher = OutboxDispatcher(store, RecordingMockSink())
        from http.server import ThreadingHTTPServer
        try:
            server = ThreadingHTTPServer(('127.0.0.1', 0),
                                         handler_for(service, worker, dispatcher))
        except OSError as exc:
            store.close()
            self.skipTest(f'当前沙盒禁止本机监听：{exc}')
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            self.assertEqual(json.load(urlopen(base + '/health'))['status'], 'ok')
            with self.assertRaises(HTTPError) as denied:
                urlopen(base + '/v1/cases')
            self.assertEqual(denied.exception.code, 403)
            token = broker.authenticate('dp-auditor', credentials['dp-auditor'])
            request = Request(base + '/v1/cases', headers={'Authorization': 'Bearer ' + token})
            self.assertEqual(len(json.load(urlopen(request))['cases']), 35)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)
            store.close()

    def test_cli_eval(self):
        result = subprocess.run([sys.executable, str(ROOT / 'stage11.py'), 'eval',
            '--output', str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('真实投递 0', result.stdout)


if __name__ == '__main__':
    unittest.main()
