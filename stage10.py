#!/usr/bin/env python3
"""Stage 10: authorized package validation and a controlled synthetic shadow pilot."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from fde_platform.domains.foreign_trade.recommendation.service import load_components
from fde_platform.hardening.auth import IdentityBroker
from fde_platform.onboarding.connector import JsonlDropConnector
from fde_platform.onboarding.data_plane import ShadowDataPlane
from fde_platform.onboarding.manifest import validate_manifest
from fde_platform.onboarding.privacy import PrivacyFilter
from fde_platform.onboarding.shadow import process_shadow

DATA = ROOT / 'stages/10-customer-onboarding/data'
DEFAULT_MANIFEST = DATA / 'customer-onboarding.json'
DEFAULT_INPUT = DATA / 'shadow-input.jsonl'
AS_OF = '2026-09-23T00:00:00+08:00'
ACCOUNTS = {
    'dp-sales-lin': 'sales',
    'dp-engineer-wu': 'engineer',
    'dp-data-owner': 'data_owner',
}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_manifest(path):
    path = Path(path).resolve()
    manifest = read(path)
    validation = validate_manifest(manifest, base_dir=path.parent)
    return manifest, validation


def identity(output, tenant_id):
    broker = IdentityBroker(output / 'identity')
    path = output / 'identity/training-credentials.json'
    if not path.exists():
        credentials = {actor: secrets.token_urlsafe(16) for actor in ACCOUNTS}
        write(path, {'mode': 'local_synthetic_credentials_only', 'passwords': credentials})
        path.chmod(0o600)
    credentials = read(path)['passwords']
    for actor, role in ACCOUNTS.items():
        broker.add_account(actor, tenant_id, role, credentials[actor])
    return broker, credentials


def privacy_filter(output):
    path = output / 'privacy-hmac.key'
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(secrets.token_bytes(32))
        path.chmod(0o600)
    return PrivacyFilter(path.read_bytes())


def is_expired(event, manifest, as_of):
    return (datetime.fromisoformat(event['received_at']) +
            timedelta(days=manifest['retention_days']) <= datetime.fromisoformat(as_of))


def prepare(output, *, manifest_path=DEFAULT_MANIFEST, input_path=DEFAULT_INPUT,
            db_name='shadow.sqlite3', as_of=AS_OF):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    manifest, validation = load_manifest(manifest_path)
    # This constructor is a second, independent guard against using the teaching
    # data plane for a package marked as real customer data.
    plane = ShadowDataPlane(output / db_name, manifest)
    broker, _ = identity(output, manifest['tenant_id'])
    privacy = privacy_filter(output)
    connector = JsonlDropConnector(input_path, manifest)
    components = load_components(ROOT)
    counts = {'created': 0, 'updated': 0, 'duplicate': 0, 'rejected': 0,
              'expired_at_intake': 0}
    privacy_counts = {'email_redactions': 0, 'phone_redactions': 0,
                      'sender_pseudonymized': 0, 'company_pseudonymized': 0}
    rejected = []
    artifacts = output / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    try:
        for event in connector.records():
            try:
                sanitized, audit = privacy.sanitize(event, manifest)
                state = plane.ingest(sanitized)
                counts[state] += 1
                for key in privacy_counts:
                    privacy_counts[key] += int(audit[key])
                if state == 'duplicate':
                    continue
                if is_expired(sanitized, manifest, as_of):
                    counts['expired_at_intake'] += 1
                artifact = process_shadow(sanitized, components)
                plane.save_case(event['case_id'], event['source_id'], event['source_version'],
                    artifact['route'], artifact['assignee_id'], artifact['assignee_role'], artifact)
                write(artifacts / f"{event['case_id']}.json", artifact)
            except (ValueError, KeyError, TypeError) as exc:
                counts['rejected'] += 1
                rejected.append({'event_id': event.get('event_id', 'unknown'),
                                 'reason': str(exc)})
        before = plane.list_cases(manifest['tenant_id'], actor_id='dp-data-owner')
        summary = {'package_validation': validation, 'ingestion': counts,
                   'privacy': privacy_counts, 'rejected': rejected,
                   'shadow_cases_before_retention': len(before),
                   'routes_before_retention': _histogram(x['route'] for x in before),
                   'retention_as_of': as_of, 'db_name': db_name,
                   'identity_mode': 'local_training_identity_not_sso',
                   'connector_mode': 'read_only_jsonl_training_drop',
                   'real_customer_data_ingested': False,
                   'external_side_effects': 0}
        write(output / 'prepare-summary.json', summary)
        return summary
    finally:
        plane.close()


def _histogram(values):
    result = {}
    for value in values:
        result[value] = result.get(value, 0) + 1
    return result


def apply_scripted_reviews(output, manifest, *, db_name='shadow.sqlite3'):
    broker, credentials = identity(output, manifest['tenant_id'])
    plane = ShadowDataPlane(output / db_name, manifest)
    applied = 0
    try:
        for item in read(DATA / 'scripted-shadow-reviews.json')['reviews']:
            case = plane.get_case(manifest['tenant_id'], item['case_id'], actor_id=item['actor_id'])
            if not case or case['state'] == 'reviewed':
                continue
            token = broker.authenticate(item['actor_id'], credentials[item['actor_id']])
            claims = broker.verify(token, tenant_id=manifest['tenant_id'], role=item['actor_role'])
            plane.review(manifest['tenant_id'], item['case_id'], claims,
                         item['action'], item['reason'])
            applied += 1
        return applied
    finally:
        plane.close()


def purge(output, manifest, *, db_name='shadow.sqlite3', as_of=AS_OF):
    plane = ShadowDataPlane(output / db_name, manifest)
    try:
        result = plane.purge_expired(as_of=as_of)
        write(Path(output) / 'retention-report.json', result)
        return result
    finally:
        plane.close()


def build_report(output, manifest, validation, *, db_name='shadow.sqlite3'):
    output = Path(output)
    plane = ShadowDataPlane(output / db_name, manifest)
    try:
        cases = plane.list_cases(manifest['tenant_id'], actor_id='dp-data-owner')
        reviewed = sum(x['state'] == 'reviewed' for x in cases)
        side_effects = sum(len(x['artifact']['external_side_effects']) for x in cases)
        prep = read(output / 'prepare-summary.json')
        retention = read(output / 'retention-report.json') if (output / 'retention-report.json').exists() else {
            'purged_event_ids': [], 'purged_case_ids': []}
        report = {
            'status': 'SYNTHETIC_CUSTOMER_PACKAGE_READY',
            'package_validation': validation,
            'ingestion': prep['ingestion'], 'privacy': prep['privacy'],
            'shadow': {'cases_before_retention': prep['shadow_cases_before_retention'],
                'cases_after_retention': len(cases), 'reviewed': reviewed,
                'pending_review': len(cases) - reviewed,
                'routes': _histogram(x['route'] for x in cases),
                'external_side_effects': side_effects},
            'retention': {'purged_event_count': len(retention['purged_event_ids']),
                'purged_case_count': len(retention.get('purged_case_ids', [])),
                **retention},
            'reuse': {'shared_core': ['WorkItem', 'extraction_pipeline', 'InquiryRecord',
                'product_search', 'rule_engine', 'recommendation_contract'],
                'customer_specific': ['authorization_manifest', 'connector_mapping',
                'privacy_policy', 'scope', 'review_assignment'],
                'measured_delivery_time_saved': None},
            'controls': {'raw_payload_persisted': False, 'tenant_scope_enforced': True,
                'customer_facing_send_implemented': False, 'external_model_used': False,
                'real_sso_used': False, 'production_data_plane_used': False},
            'real_customer_data_ingested': False,
            'actual_pilot_users': 0,
            'real_pilot_gate': 'NOT_EVALUATED',
            'next_gate': 'customer_authorization_and_production_cutover_review'
        }
        write(output / 'stage10-report.json', report)
        (output / 'stage10-report.md').write_text(_render(report), encoding='utf-8')
        return report
    finally:
        plane.close()


def _render(report):
    return f"""# Stage 10 客户接入与 Shadow Pilot 报告

状态：`{report['status']}`；真实 Pilot Gate：`{report['real_pilot_gate']}`。

- 入站：新增 {report['ingestion']['created']}，更新 {report['ingestion']['updated']}，重复 {report['ingestion']['duplicate']}，拒绝 {report['ingestion']['rejected']}。
- 留存清理前/后案例：{report['shadow']['cases_before_retention']} / {report['shadow']['cases_after_retention']}；已审核 {report['shadow']['reviewed']}。
- 对外副作用：{report['shadow']['external_side_effects']}；真实客户数据：`false`；真实用户：0。
- 复用 Core：{', '.join(report['reuse']['shared_core'])}。

本报告只证明合成客户包的接入控制和共享契约可运行，不证明真实授权、现场成效或交付时间节省。
"""


def readiness(manifest, validation):
    real = manifest['mode'] == 'authorized_customer_data'
    checks = {
        'manifest_valid': True,
        'authorization_evidence_verified': real and bool(manifest.get('authorization_evidence')),
        'production_data_plane_declared': bool(manifest['storage_controls'].get('production_data_plane')),
        'enterprise_identity_integrated': bool(manifest.get('enterprise_identity', {}).get('approved')),
        'connector_credentials_externalized': bool(manifest.get('connector_credentials_externalized')),
        'data_processing_agreement_recorded': bool(manifest.get('data_processing_agreement', {}).get('approved')),
        'cross_border_assessment_if_needed': (not manifest['cross_border'] or
            bool(manifest.get('cross_border_assessment', {}).get('approved'))),
        'stop_and_rollback_owner_named': bool(manifest.get('pilot_operations', {}).get('stop_owner')),
    }
    return {'status': 'READY_FOR_PRODUCTION_CUTOVER_REVIEW' if all(checks.values()) else
            'NOT_READY_FOR_REAL_CUSTOMER_DATA', 'manifest': validation, 'checks': checks,
            'missing': [key for key, ok in checks.items() if not ok]}


def run_demo(output, *, check_baseline=False):
    output = Path(output)
    manifest, validation = load_manifest(DEFAULT_MANIFEST)
    db = 'shadow-demo.sqlite3'
    path = output / db
    if path.exists():
        path.unlink()
    prepare(output, db_name=db)
    applied = apply_scripted_reviews(output, manifest, db_name=db)
    retention = purge(output, manifest, db_name=db)
    report = build_report(output, manifest, validation, db_name=db)
    report['scripted_reviews_applied'] = applied
    report['readiness'] = readiness(manifest, validation)
    write(output / 'stage10-report.json', report)
    (output / 'stage10-report.md').write_text(_render(report), encoding='utf-8')
    if check_baseline:
        check_report(report)
    print(f"Stage 10：{report['status']}；Shadow 案例 {report['shadow']['cases_after_retention']}，真实数据 0，发送 0。")
    return report


def _resolve(value, dotted):
    for part in dotted.split('.'):
        value = value[part]
    return value


def check_report(report):
    baseline = read(DATA / 'regression-baseline.json')
    for path, expected in baseline.items():
        actual = _resolve(report, path)
        if actual != expected:
            raise ValueError(f'Stage 10 回归失败：{path} 期望 {expected!r}，实际 {actual!r}')
    return True


def main():
    parser = argparse.ArgumentParser(description='Stage 10 客户接入与受控 Shadow Pilot')
    parser.add_argument('command', choices=['demo', 'prepare', 'validate-package', 'login',
        'queue', 'review', 'purge', 'report', 'readiness', 'eval'])
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-10')
    parser.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--actor')
    parser.add_argument('--password')
    parser.add_argument('--token')
    parser.add_argument('--case')
    parser.add_argument('--action', choices=['accept', 'edit', 'escalate', 'reject'])
    parser.add_argument('--reason')
    parser.add_argument('--check-baseline', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        manifest, validation = load_manifest(args.manifest)
        if args.command in ('demo', 'eval'):
            run_demo(output, check_baseline=args.check_baseline or args.command == 'eval')
        elif args.command == 'validate-package':
            print(json.dumps(validation, ensure_ascii=False, indent=2))
        elif args.command == 'prepare':
            print(json.dumps(prepare(output, manifest_path=args.manifest,
                input_path=args.input), ensure_ascii=False, indent=2))
        elif args.command == 'login':
            if not args.actor or not args.password:
                parser.error('login 需要 --actor 和 --password')
            broker, _ = identity(output, manifest['tenant_id'])
            print(broker.authenticate(args.actor, args.password))
        elif args.command == 'queue':
            if not args.token:
                parser.error('queue 需要 --token')
            broker, _ = identity(output, manifest['tenant_id'])
            claims = broker.verify(args.token, tenant_id=manifest['tenant_id'])
            plane = ShadowDataPlane(output / 'shadow.sqlite3', manifest)
            try:
                rows = plane.list_cases(manifest['tenant_id'], actor_id=claims['sub'])
                print(json.dumps(rows, ensure_ascii=False, indent=2))
            finally:
                plane.close()
        elif args.command == 'review':
            if not all((args.token, args.case, args.action, args.reason)):
                parser.error('review 需要 --token --case --action --reason')
            broker, _ = identity(output, manifest['tenant_id'])
            claims = broker.verify(args.token, tenant_id=manifest['tenant_id'])
            plane = ShadowDataPlane(output / 'shadow.sqlite3', manifest)
            try:
                plane.review(manifest['tenant_id'], args.case, claims, args.action, args.reason)
            finally:
                plane.close()
            print('Shadow 审核已记录；没有创建对外发送。')
        elif args.command == 'purge':
            print(json.dumps(purge(output, manifest), ensure_ascii=False, indent=2))
        elif args.command == 'report':
            print(json.dumps(build_report(output, manifest, validation), ensure_ascii=False, indent=2))
        elif args.command == 'readiness':
            print(json.dumps(readiness(manifest, validation), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
