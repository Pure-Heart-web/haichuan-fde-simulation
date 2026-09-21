#!/usr/bin/env python3
"""Stage 13: design-partner pilot readiness and unified operator workbench."""
import argparse
from getpass import getpass
import hashlib
import json
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

import stage11
import stage12
from fde_platform.fieldops.authorization import (validate_bundle,
                                                  validate_postgres_rls)
from fde_platform.fieldops.identity import TrainingOIDCBroker
from fde_platform.fieldops.ledger import FieldOpsLedger
from fde_platform.fieldops.observability import SafeSpanWriter, evaluate_slos
from fde_platform.fieldops.workbench import WORKBENCH_HTML, workbench_contract
from fde_platform.runtime.api import serve as serve_api
from fde_platform.runtime.worker import (DeliveryWorker, OutboxDispatcher,
                                          RecordingMockSink)


DATA = ROOT / 'stages/13-pilot-readiness/data'
BUNDLE = DATA / 'pilot-authorization-bundle.json'
SHIFT_PLAN = DATA / 'shift-plan.json'
BASELINE = DATA / 'regression-baseline.json'
POSTGRES_SQL = ROOT / 'stages/13-pilot-readiness/infra/postgresql-rls.sql'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def setup_oidc(output, bundle):
    root = Path(output) / 'identity'
    root.mkdir(parents=True, exist_ok=True)
    key_path = root / 'training-oidc.key'
    codes_path = root / 'training-oidc-codes.json'
    if not key_path.exists():
        key_path.write_bytes(secrets.token_bytes(32))
        key_path.chmod(0o600)
    if not codes_path.exists():
        write(codes_path, {'mode': 'training_oidc_codes_not_enterprise_sso',
            'codes': {actor: secrets.token_urlsafe(16) for actor in stage11.ACCOUNTS}})
        codes_path.chmod(0o600)
    broker = TrainingOIDCBroker(key_path.read_bytes(),
        issuer=bundle['identity']['issuer'], audience=bundle['identity']['audience'],
        tenant_id=bundle['tenant_id'])
    codes = read(codes_path)['codes']
    for actor, role in stage11.ACCOUNTS.items():
        broker.add_account(actor, role, codes[actor])
    return broker, codes


def rehearse_identity(output, bundle):
    broker, codes = setup_oidc(output, bundle)
    verified = 0
    for actor, role in stage11.ACCOUNTS.items():
        token = broker.authenticate(actor, codes[actor], now=1_000)
        claims = broker.verify(token, tenant_id=bundle['tenant_id'], role=role, now=1_001)
        verified += claims['sub'] == actor
    blocked = 0
    token = broker.authenticate('dp-operator-zhou', codes['dp-operator-zhou'], now=1_000)
    for check in (
        lambda: broker.verify(token, tenant_id='another-tenant', now=1_001),
        lambda: broker.verify(token, role='release_manager', now=1_001),
        lambda: broker.verify(token, now=2_000),
    ):
        try:
            check()
        except ValueError:
            blocked += 1
    fresh = broker.authenticate('dp-auditor', codes['dp-auditor'], now=2_000)
    broker.revoke(fresh)
    try:
        broker.verify(fresh, now=2_001)
    except ValueError:
        blocked += 1
    return {'mode': 'training_oidc_contract_not_enterprise_sso',
            'accounts_verified': verified, 'negative_checks_blocked': blocked,
            'issuer_checked': True, 'audience_checked': True,
            'tenant_checked': True, 'role_checked': True, 'expiry_checked': True,
            'revocation_checked': True, 'enterprise_sso_used': False}


def rehearse_operations(output, bundle):
    ledger_path = Path(output) / 'field-operations.jsonl'
    spans_path = Path(output) / 'otel-spans.jsonl'
    for path in (ledger_path, spans_path):
        if path.exists():
            path.unlink()
    ledger = FieldOpsLedger(ledger_path, bundle['tenant_id'])
    spans = SafeSpanWriter(spans_path)
    tenant_hash = hashlib.sha256(bundle['tenant_id'].encode()).hexdigest()[:16]
    plan = read(SHIFT_PLAN)
    for shift in plan['shifts']:
        for item in shift['events']:
            event = ledger.append(shift['operator'], 'operator', item['type'], item['detail'],
                                  shift_id=shift['shift_id'],
                                  incident_id=item.get('incident_id'))
            spans.write('fde.pilot.' + item['type'], {
                'tenant_hash': tenant_hash, 'shift_id': shift['shift_id'],
                'event_type': item['type'], 'outcome': 'recorded'},
                object_id=f"{shift['shift_id']}|{event['sequence']}")
    audit = plan['audit_event']
    event = ledger.append(audit['actor_id'], audit['role'], audit['type'], audit['detail'],
                          shift_id=audit['shift_id'])
    spans.write('fde.pilot.' + audit['type'], {
        'tenant_hash': tenant_hash, 'shift_id': audit['shift_id'],
        'event_type': audit['type'], 'outcome': 'recorded'},
        object_id=f"{audit['shift_id']}|{event['sequence']}")
    return ledger.summary(), spans.summary()


def render(report):
    slo = report['slo']
    delivery = report['delivery_room']
    model = report['model_lab']
    return f"""# Stage 13 Design Partner Pilot Readiness 报告

状态：`{report['status']}`；真实 Pilot Gate：`{report['real_pilot_gate']}`。

- 授权包：`{report['authorization']['status']}`；客户记录内嵌 `false`；Git 存储 `false`。
- 身份：{report['identity']['accounts_verified']} 个训练 OIDC 账户通过，{report['identity']['negative_checks_blocked']} 个负向校验被拒绝；企业 SSO `false`。
- 数据面：PostgreSQL RLS 契约 `{report['postgres']['status']}`；实际 PostgreSQL 执行 `false`。
- 工作台：{report['workbench']['actions_present']}/{report['workbench']['required_actions']} 项审核、Trace、发布和运行动作已连接。
- 班次：{report['operations']['shift_count']} 个视角，{report['operations']['handoff_count']} 次交接，{report['operations']['incident_count']} 个事故且已解决。
- Delivery Room：{delivery['workflow']['case_count']} 个案例，Mock 投递 {delivery['delivery']['mock_deliveries']}，真实投递 0。
- Model Lab：安全用例 {model['security']['correct']}/{model['security']['case_count']}，演练后路由 `{model['rollout']['active_route']}`。
- SLO：`{slo['status']}`；未批准投递 {slo['values']['unapproved_deliveries']}，持久化直接标识符 {slo['values']['persistent_direct_identifier_rows']}。
- 遥测 span {report['telemetry']['span_count']}；原始客户内容、Prompt 和模型输出均未记录。

本报告证明合成现场演练可复现。PostgreSQL DDL 只做了契约检查，OIDC 是本地 HS256 训练 issuer，遥测是 OTLP-shaped JSONL；它们不能作为企业生产环境通过证据。
"""


def run_demo(output, *, check_baseline=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    bundle = read(BUNDLE)
    authorization = validate_bundle(bundle, ROOT)
    postgres = validate_postgres_rls(POSTGRES_SQL.read_text(encoding='utf-8'))
    identity = rehearse_identity(output, bundle)
    operations, telemetry = rehearse_operations(output, bundle)
    delivery = stage11.run_demo(output / 'delivery-room', check_baseline=True)
    model = stage12.run_demo(output / 'model-lab', check_baseline=True)
    workbench = workbench_contract()
    slo = evaluate_slos(delivery, model, operations, bundle['slo_thresholds'])
    checks = {
        'authorization': authorization['status'] == 'SYNTHETIC_FIELD_BUNDLE_APPROVED',
        'postgres_contract': postgres['status'] == 'POSTGRES_RLS_CONTRACT_READY',
        'identity_contract': identity['accounts_verified'] == len(stage11.ACCOUNTS) and
                             identity['negative_checks_blocked'] == 4,
        'workbench_contract': workbench['actions_present'] == workbench['required_actions'],
        'operations': operations['all_incidents_resolved'] and operations['hash_chain_valid'],
        'telemetry': telemetry['direct_identifier_rows'] == 0,
        'slo': slo['status'] == 'SYNTHETIC_PILOT_SLOS_MET',
    }
    report = {
        'status': 'SYNTHETIC_FIELD_REHEARSAL_READY' if all(checks.values()) else
                  'SYNTHETIC_FIELD_REHEARSAL_BLOCKED',
        'authorization': authorization, 'postgres': postgres,
        'identity': identity, 'workbench': workbench,
        'operations': operations, 'telemetry': telemetry, 'slo': slo,
        'delivery_room': delivery, 'model_lab': model,
        'readiness_checks': checks,
        'production_gaps': ['authorized_customer_evidence', 'production_postgresql_migration',
            'enterprise_oidc_and_jwks', 'real_connector_sandbox', 'otlp_collector_backend',
            'customer_uat_and_on_call'],
        'real_customer_data_ingested': False,
        'external_customer_actions': 0,
        'actual_pilot_users': 0,
        'real_pilot_gate': 'NOT_EVALUATED',
        'next_gate': 'AUTHORIZED_DESIGN_PARTNER_SHADOW_REVIEW',
    }
    write(output / 'stage13-report.json', report)
    (output / 'stage13-report.md').write_text(render(report), encoding='utf-8')
    if check_baseline:
        check_report(report)
    print(f"Stage 13：{report['status']}；班次 {operations['shift_count']}，事故 {operations['incident_count']}，真实数据 0，客户动作 0。")
    return report


def _resolve(value, path):
    for part in path.split('.'):
        value = value[part]
    return value


def check_report(report):
    for path, expected in read(BASELINE).items():
        actual = _resolve(report, path)
        if actual != expected:
            raise ValueError(f'Stage 13 回归失败：{path} 期望 {expected!r}，实际 {actual!r}')
    return True


def workbench_runtime(output):
    output = Path(output)
    bundle = read(BUNDLE)
    validate_bundle(bundle, ROOT)
    db_name = 'field-workbench.sqlite3'
    if not (output / db_name).exists():
        stage11.prepare(output, db_name=db_name)
        stage11.run_worker(output, db_name=db_name)
    manifest, _, _, store, service = stage11.build_runtime(output, db_name=db_name)
    broker, codes = setup_oidc(output, bundle)
    service.broker = broker
    worker = DeliveryWorker(store, service.components)
    dispatcher = OutboxDispatcher(store, RecordingMockSink())
    return manifest, broker, codes, store, service, worker, dispatcher


def main():
    parser = argparse.ArgumentParser(description='Stage 13 现场试点准备与操作员工作台')
    parser.add_argument('command', choices=('demo', 'bundle', 'login', 'serve'))
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-13')
    parser.add_argument('--check-baseline', action='store_true')
    parser.add_argument('--actor', choices=tuple(stage11.ACCOUNTS))
    parser.add_argument('--code')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8783)
    args = parser.parse_args()
    try:
        if args.command == 'demo':
            run_demo(args.output.resolve(), check_baseline=args.check_baseline)
        elif args.command == 'bundle':
            print(json.dumps(validate_bundle(read(BUNDLE), ROOT), ensure_ascii=False, indent=2))
        elif args.command == 'login':
            if not args.actor:
                parser.error('login 需要 --actor')
            bundle = read(BUNDLE)
            broker, _ = setup_oidc(args.output.resolve(), bundle)
            code = args.code or getpass('训练 OIDC code: ')
            print(broker.authenticate(args.actor, code))
        else:
            manifest, broker, codes, store, service, worker, dispatcher = workbench_runtime(
                args.output.resolve())
            print(f"训练账户 code：{args.output.resolve() / 'identity/training-oidc-codes.json'}")
            try:
                serve_api(service, worker, dispatcher, host=args.host, port=args.port,
                          console_html=WORKBENCH_HTML)
            finally:
                store.close()
        return 0
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f'Stage 13 失败：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
