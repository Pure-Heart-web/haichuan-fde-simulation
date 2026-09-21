#!/usr/bin/env python3
"""Stage 11 production-shaped local Delivery Room and operations exercise."""
import argparse
import json
from pathlib import Path
import secrets
import sqlite3
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from fde_platform.domains.foreign_trade.recommendation.service import load_components
from fde_platform.hardening.auth import IdentityBroker
from fde_platform.onboarding.connector import JsonlDropConnector
from fde_platform.onboarding.manifest import validate_manifest
from fde_platform.runtime.api import serve
from fde_platform.runtime.service import DeliveryRoomService
from fde_platform.runtime.store import RuntimeStore
from fde_platform.runtime.worker import (DeliveryWorker, LocalHttpSink,
    OutboxDispatcher, RecordingMockSink, fetch_local_mock_token)

DATA = ROOT / 'stages/11-delivery-room/data'
MANIFEST = ROOT / 'stages/10-customer-onboarding/data/customer-onboarding.json'
EVENTS = DATA / 'pilot-events.jsonl'
PLAN = DATA / 'runtime-plan.json'
BASELINE = DATA / 'regression-baseline.json'
ACCOUNTS = {
    'dp-sales-lin': 'sales',
    'dp-engineer-wu': 'engineer',
    'dp-release-li': 'release_manager',
    'dp-operator-zhou': 'operator',
    'dp-auditor': 'auditor',
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def identity(output, tenant_id):
    broker = IdentityBroker(output / 'identity')
    path = output / 'identity/training-credentials.json'
    if not path.exists():
        write(path, {'mode': 'local_synthetic_credentials_only',
                     'passwords': {actor: secrets.token_urlsafe(16) for actor in ACCOUNTS}})
        path.chmod(0o600)
    credentials = read(path)['passwords']
    for actor, role in ACCOUNTS.items():
        broker.add_account(actor, tenant_id, role, credentials[actor])
    return broker, credentials


def secret(output, filename, size=32):
    path = output / filename
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_urlsafe(size) + '\n')
        path.chmod(0o600)
    return path.read_text().strip()


def build_runtime(output, *, db_name='delivery-room.sqlite3'):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    manifest = read(MANIFEST)
    validate_manifest(manifest, base_dir=MANIFEST.parent)
    broker, credentials = identity(output, manifest['tenant_id'])
    service_token = secret(output, 'connector-service.token')
    privacy_hex = secret(output, 'privacy-hmac.hex', size=48)
    privacy_key = bytes.fromhex(privacy_hex[:64]) if all(c in '0123456789abcdef' for c in privacy_hex[:64]) else None
    if privacy_key is None or len(privacy_key) < 32:
        privacy_path = output / 'privacy-hmac.hex'
        privacy_path.write_text(secrets.token_hex(32) + '\n')
        privacy_path.chmod(0o600)
        privacy_key = bytes.fromhex(privacy_path.read_text().strip())
    store = RuntimeStore(output / db_name, manifest['tenant_id'], manifest['domain'])
    components = load_components(ROOT)
    service = DeliveryRoomService(store, manifest, broker, components, privacy_key,
                                  service_token=service_token)
    return manifest, broker, credentials, store, service


def prepare(output, *, db_name='delivery-room.sqlite3', events_path=EVENTS):
    manifest, broker, credentials, store, service = build_runtime(output, db_name=db_name)
    counts = {'total_received': 0, 'created': 0, 'updated': 0, 'duplicate': 0,
              'rejected': 0}
    rejected = []
    try:
        token = secret(Path(output), 'connector-service.token')
        for raw in JsonlDropConnector(events_path, manifest).records():
            counts['total_received'] += 1
            try:
                result = service.accept(raw, token)
                counts[result['state']] += 1
            except (ValueError, KeyError, TypeError) as exc:
                counts['rejected'] += 1
                rejected.append({'event_id': raw.get('event_id'), 'reason': str(exc)})
        result = {'intake': counts, 'rejected': rejected,
                  'mode': 'synthetic_production_shaped_runtime'}
        write(Path(output) / 'intake-report.json', result)
        return result
    finally:
        store.close()


def run_worker(output, *, db_name='delivery-room.sqlite3'):
    plan = read(PLAN)
    manifest, broker, credentials, store, service = build_runtime(output, db_name=db_name)
    try:
        recovered = store.recover_leases(0)
        worker = DeliveryWorker(store, service.components,
            fault_plan=plan['worker']['faults'])
        results = worker.drain()
        report = {'lease_recoveries': recovered, 'results': results,
                  'done': sum(x['state'] == 'done' for x in results),
                  'dead': sum(x['state'] == 'dead' for x in results),
                  'retry_events': sum(x['state'] == 'retry' for x in results)}
        write(Path(output) / 'worker-report.json', report)
        return report
    finally:
        store.close()


def apply_roleplay_reviews(output, *, db_name='delivery-room.sqlite3'):
    manifest, broker, credentials, store, service = build_runtime(output, db_name=db_name)
    results = []
    try:
        cases = store.cases(manifest['tenant_id'], 'roleplay-controller')
        for item in cases:
            actor = item['assignee_id']
            token = broker.authenticate(actor, credentials[actor])
            if item['route'] == 'quarantine':
                action, reason = 'reject', '提示注入案例保持隔离，不生成投递'
            elif item['route'] == 'request_clarification':
                action, reason = 'escalate', '关键信息缺失，转人工澄清且不生成投递'
            else:
                action, reason = 'accept', '模拟审核已核对字段证据、规则和候选边界'
            results.append(service.review(token, item['case_id'], action, reason))
        write(Path(output) / 'roleplay-reviews.json',
              {'mode': 'synthetic_roleplay', 'reviews': results})
        return results
    finally:
        store.close()


def approve_all(output, *, db_name='delivery-room.sqlite3'):
    manifest, broker, credentials, store, service = build_runtime(output, db_name=db_name)
    try:
        token = broker.authenticate('dp-release-li', credentials['dp-release-li'])
        pending = [x for x in store.outbox() if x['state'] == 'pending_approval']
        for item in pending:
            service.approve(token, item['message_id'])
        return len(pending)
    finally:
        store.close()


def dispatch_demo(output, *, db_name='delivery-room.sqlite3'):
    manifest, broker, credentials, store, service = build_runtime(output, db_name=db_name)
    try:
        ready = [x for x in store.outbox() if x['state'] == 'ready']
        faults = {}
        if ready:
            faults[ready[0]['message_id']] = 'retry_once'
        if len(ready) > 1:
            faults[ready[-1]['message_id']] = 'permanent_failure'
        sink = RecordingMockSink(faults)
        results = OutboxDispatcher(store, sink).drain()
        report = {'sink_mode': sink.mode, 'results': results,
                  'mock_deliveries': len(sink.deliveries),
                  'real_customer_deliveries': 0,
                  'faults': faults}
        write(Path(output) / 'dispatch-report.json', report)
        return report
    finally:
        store.close()


def build_report(output, *, db_name='delivery-room.sqlite3', durable_restart=False,
                 cross_tenant_access_allowed=0):
    output = Path(output)
    manifest, broker, credentials, store, service = build_runtime(output, db_name=db_name)
    try:
        intake = read(output / 'intake-report.json')['intake']
        worker = read(output / 'worker-report.json')
        dispatch = read(output / 'dispatch-report.json')
        metrics = store.metrics()
        privacy = store.privacy_scan()
        pending = metrics['cases'].get('pending_review', 0)
        report = {
            'status': 'SYNTHETIC_DELIVERY_ROOM_READY',
            'intake': intake,
            'worker': {'done': metrics['inbox'].get('done', 0),
                'dead': metrics['inbox'].get('dead', 0),
                'retry_events': worker['retry_events'],
                'attempt_count': metrics['worker_attempt_count'],
                'lease_recoveries': worker['lease_recoveries']},
            'workflow': {'case_count': sum(metrics['cases'].values()),
                'reviewed': metrics['review_count'], 'pending_review': pending,
                'states': metrics['cases']},
            'delivery': {'outbox_count': sum(metrics['outbox'].values()),
                'states': metrics['outbox'],
                'delivery_attempt_count': metrics['delivery_attempt_count'],
                'mock_deliveries': dispatch['mock_deliveries'],
                'real_customer_deliveries': 0,
                'unapproved_deliveries': metrics['unapproved_deliveries'],
                'sink_mode': dispatch['sink_mode']},
            'security': {'cross_tenant_access_allowed': cross_tenant_access_allowed,
                **privacy, 'enterprise_sso_used': False},
            'runtime': {'schema_version': metrics['schema_version'],
                'durable_restart_verified': durable_restart,
                'storage': 'sqlite_training_reference',
                'api': 'authenticated_local_http',
                'incident_count': len(metrics['incidents']),
                'incidents': metrics['incidents']},
            'pilot': {'synthetic_cases': 36, 'synthetic_shifts': 5,
                'actual_users': 0, 'actual_elapsed_days': 0,
                'observed_customer_value': None},
            'real_customer_data_ingested': False,
            'real_pilot_gate': 'NOT_EVALUATED',
            'production_cutover_gate': 'NOT_READY'
        }
        write(output / 'stage11-report.json', report)
        (output / 'stage11-report.md').write_text(render(report), encoding='utf-8')
        return report
    finally:
        store.close()


def render(report):
    return f"""# Stage 11 Production-like Delivery Room 报告

状态：`{report['status']}`；真实 Pilot Gate：`{report['real_pilot_gate']}`。

- 入站 {report['intake']['total_received']}：新增 {report['intake']['created']}、更新 {report['intake']['updated']}、重复 {report['intake']['duplicate']}。
- Worker：完成 {report['worker']['done']}、死信 {report['worker']['dead']}、重试事件 {report['worker']['retry_events']}。
- 工作流：案例 {report['workflow']['case_count']}、审核记录 {report['workflow']['reviewed']}、待审核 {report['workflow']['pending_review']}。
- Outbox：{report['delivery']['outbox_count']} 条；Mock 投递 {report['delivery']['mock_deliveries']}；真实客户投递 0；未批准投递 {report['delivery']['unapproved_deliveries']}。
- 安全：跨租户成功 0；持久化直接标识符 {report['security']['rows_with_direct_identifier']}；事故 {report['runtime']['incident_count']}。

这是 SQLite、本地签名身份与 Mock Sink 组成的生产形态教学运行时。它验证服务边界、恢复、重试、双人发布和审计，不构成生产 PostgreSQL、企业 SSO 或客户现场 Pilot。
"""


def run_demo(output, *, check_baseline=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    db_name = 'delivery-room-demo.sqlite3'
    db = output / db_name
    if db.exists():
        db.unlink()
    prepare(output, db_name=db_name)
    worker = run_worker(output, db_name=db_name)
    apply_roleplay_reviews(output, db_name=db_name)
    approve_all(output, db_name=db_name)
    dispatch_demo(output, db_name=db_name)
    manifest, broker, credentials, store, service = build_runtime(output, db_name=db_name)
    before = store.metrics()
    cross_allowed = 0
    try:
        try:
            store.cases('another-tenant', 'intruder')
            cross_allowed += 1
        except ValueError:
            pass
    finally:
        store.close()
    reopened = RuntimeStore(db, manifest['tenant_id'], manifest['domain'])
    try:
        durable = reopened.metrics()['inbox'] == before['inbox'] and bool(before['inbox'])
    finally:
        reopened.close()
    report = build_report(output, db_name=db_name, durable_restart=durable,
                          cross_tenant_access_allowed=cross_allowed)
    if check_baseline:
        check_report(report)
    print(f"Stage 11：{report['status']}；案例 {report['workflow']['case_count']}，Mock 投递 {report['delivery']['mock_deliveries']}，真实投递 0。")
    return report


def _resolve(value, path):
    for part in path.split('.'):
        value = value[part]
    return value


def check_report(report):
    for path, expected in read(BASELINE).items():
        actual = _resolve(report, path)
        if actual != expected:
            raise ValueError(f'Stage 11 回归失败：{path} 期望 {expected!r}，实际 {actual!r}')
    return True


def main():
    parser = argparse.ArgumentParser(description='Stage 11 Production-like Delivery Room')
    parser.add_argument('command', choices=['demo', 'eval', 'prepare', 'work', 'login',
        'queue', 'review', 'approve', 'requeue-event', 'requeue-message', 'dispatch',
        'trace', 'dashboard', 'serve'])
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-11')
    parser.add_argument('--events', type=Path, default=EVENTS)
    parser.add_argument('--actor')
    parser.add_argument('--password')
    parser.add_argument('--token')
    parser.add_argument('--case')
    parser.add_argument('--action', choices=['accept', 'edit', 'escalate', 'reject'])
    parser.add_argument('--reason')
    parser.add_argument('--message')
    parser.add_argument('--event')
    parser.add_argument('--sink', default='http://127.0.0.1:8782/deliveries')
    parser.add_argument('--oauth', default='http://127.0.0.1:8782/oauth/token')
    parser.add_argument('--client-secret', default='stage11-local-secret')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8781)
    parser.add_argument('--check-baseline', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        if args.command in ('demo', 'eval'):
            run_demo(output, check_baseline=args.check_baseline or args.command == 'eval')
            return 0
        if args.command == 'prepare':
            print(json.dumps(prepare(output, events_path=args.events), ensure_ascii=False, indent=2))
            return 0
        if args.command == 'work':
            print(json.dumps(run_worker(output), ensure_ascii=False, indent=2))
            return 0
        manifest, broker, credentials, store, service = build_runtime(output)
        try:
            if args.command == 'login':
                if not args.actor or not args.password:
                    parser.error('login 需要 --actor 与 --password')
                print(broker.authenticate(args.actor, args.password))
            elif args.command == 'queue':
                if not args.token:
                    parser.error('queue 需要 --token')
                print(json.dumps(service.cases(args.token), ensure_ascii=False, indent=2))
            elif args.command == 'review':
                if not all((args.token, args.case, args.action, args.reason)):
                    parser.error('review 需要 --token --case --action --reason')
                print(json.dumps(service.review(args.token, args.case, args.action, args.reason),
                                 ensure_ascii=False, indent=2))
            elif args.command == 'approve':
                if not args.token or not args.message:
                    parser.error('approve 需要 --token 与 --message')
                service.approve(args.token, args.message)
                print(json.dumps({'message_id': args.message, 'state': 'ready'},
                                 ensure_ascii=False))
            elif args.command == 'requeue-event':
                if not all((args.token, args.event, args.reason)):
                    parser.error('requeue-event 需要 --token --event --reason')
                service.requeue_event(args.token, args.event, args.reason)
                print(json.dumps({'event_id': args.event, 'state': 'retry'}, ensure_ascii=False))
            elif args.command == 'requeue-message':
                if not all((args.token, args.message, args.reason)):
                    parser.error('requeue-message 需要 --token --message --reason')
                service.requeue_message(args.token, args.message, args.reason)
                print(json.dumps({'message_id': args.message, 'state': 'retry'}, ensure_ascii=False))
            elif args.command == 'dispatch':
                token = fetch_local_mock_token(args.oauth, args.client_secret)
                sink = LocalHttpSink(args.sink, token)
                print(json.dumps({'results': OutboxDispatcher(store, sink).drain()},
                                 ensure_ascii=False, indent=2))
            elif args.command == 'trace':
                if not args.token or not args.case:
                    parser.error('trace 需要 --token 与 --case')
                print(json.dumps(service.trace(args.token, args.case), ensure_ascii=False, indent=2))
            elif args.command == 'dashboard':
                if not args.token:
                    parser.error('dashboard 需要 --token')
                service.claims(args.token)
                print(json.dumps(store.metrics(), ensure_ascii=False, indent=2))
            elif args.command == 'serve':
                plan = read(PLAN)
                worker = DeliveryWorker(store, service.components,
                    fault_plan=plan['worker']['faults'])
                token = fetch_local_mock_token(args.oauth, args.client_secret)
                dispatcher = OutboxDispatcher(store, LocalHttpSink(args.sink, token))
                serve(service, worker, dispatcher, host=args.host, port=args.port)
        finally:
            try:
                store.close()
            except sqlite3.ProgrammingError:
                pass
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError,
            RuntimeError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
