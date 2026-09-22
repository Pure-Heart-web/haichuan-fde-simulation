#!/usr/bin/env python3
"""Stage 14 integration lab and authorized shadow-pilot preflight."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

import stage11
import stage13
from fde_platform.integrationlab.connectors import exercise_connectors
from fde_platform.integrationlab.evidence import (evidence_manifest, shadow_metrics,
                                                   verify_manifest)
from fde_platform.integrationlab.gates import operational_gate, real_shadow_gate
from fde_platform.integrationlab.identity import rehearse_oidc
from fde_platform.integrationlab.telemetry import LabCollector
from fde_platform.runtime.worker import DeliveryWorker, OutboxDispatcher, RecordingMockSink


DATA = ROOT / 'stages/14-integration-shadow/data'
BASELINE = DATA / 'regression-baseline.json'
CONNECTORS = DATA / 'connector-scenarios.json'
IDENTITY = DATA / 'identity-lab.json'
OBSERVATIONS = DATA / 'shadow-observations.json'
DEFAULT_EXTERNAL_EVIDENCE = DATA / 'external-evidence.example.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def refresh_delivery_report(report, store):
    metrics = store.metrics()
    refreshed = json.loads(json.dumps(report))
    refreshed['worker'].update({'done': metrics['inbox'].get('done', 0),
        'dead': metrics['inbox'].get('dead', 0),
        'attempt_count': metrics['worker_attempt_count']})
    refreshed['workflow'].update({'case_count': sum(metrics['cases'].values()),
        'reviewed': metrics['review_count'],
        'pending_review': metrics['cases'].get('pending_review', 0),
        'states': metrics['cases']})
    refreshed['delivery'].update({'outbox_count': sum(metrics['outbox'].values()),
        'states': metrics['outbox'],
        'delivery_attempt_count': metrics['delivery_attempt_count'],
        'mock_deliveries': metrics['outbox'].get('delivered', 0),
        'unapproved_deliveries': metrics['unapproved_deliveries']})
    refreshed['security'].update(store.privacy_scan())
    refreshed['runtime'].update({'incident_count': len(metrics['incidents']),
                                 'incidents': metrics['incidents']})
    return refreshed


def remediate_delivery_room(delivery_output, report):
    manifest, broker, credentials, store, service = stage11.build_runtime(
        delivery_output, db_name='delivery-room-demo.sqlite3')
    actions = []
    try:
        operator = broker.authenticate('dp-operator-zhou', credentials['dp-operator-zhou'])
        metrics = store.metrics()
        for event_id in [row['object_id'] for row in metrics['incidents']
                         if row['kind'] == 'worker_dead_letter' and row['state'] == 'open']:
            service.requeue_event(operator, event_id, 'schema mapping approved in lab')
            actions.append({'type': 'requeue_event', 'object_id': event_id})
        for message_id in [row['object_id'] for row in metrics['incidents']
                           if row['kind'] == 'outbox_dead_letter' and row['state'] == 'open']:
            service.requeue_message(operator, message_id, 'mock target restored in lab')
            actions.append({'type': 'requeue_message', 'object_id': message_id})
        recovering = sum(row['state'] == 'recovering'
                         for row in store.metrics()['incidents'])
        worker_results = DeliveryWorker(store, service.components).drain()
        for item in store.cases(manifest['tenant_id'], 'stage14-controller'):
            if item['state'] != 'pending_review':
                continue
            token = broker.authenticate(item['assignee_id'], credentials[item['assignee_id']])
            result = service.review(token, item['case_id'], 'accept',
                                    'replayed case evidence checked in integration lab')
            actions.append({'type': 'review_replayed_case', 'object_id': item['case_id']})
            if result['message_id']:
                release = broker.authenticate('dp-release-li', credentials['dp-release-li'])
                service.approve(release, result['message_id'])
                actions.append({'type': 'approve_replayed_case',
                                'object_id': result['message_id']})
        dispatch_results = OutboxDispatcher(store, RecordingMockSink()).drain()
        refreshed = refresh_delivery_report(report, store)
        return refreshed, {'status': 'REMEDIATION_COMPLETED', 'actions': actions,
            'recovering_before_replay': recovering,
            'worker_replay_results': worker_results,
            'dispatcher_replay_results': dispatch_results,
            'all_incidents_resolved': all(row['state'] == 'resolved'
                for row in refreshed['runtime']['incidents'])}
    finally:
        store.close()


def rehearse_telemetry(output):
    collector = LabCollector(Path(output) / 'collector-export.jsonl')
    events = ('connector.poll', 'inbox.accept', 'worker.complete', 'review.accept',
              'outbox.approve', 'incident.resolve')
    for index, event in enumerate(events):
        collector.export('fde.' + event, f'trace-{index}', {
            'service.name': 'fde-integration-lab', 'event.type': event,
            'outcome': 'ok', 'duration_ms': index + 0.25,
            'tenant.hash': 'e48f1a7d2c77e190',
            'body': 'person@example.test raw content must be dropped'})
    return collector.flush()


def render(report):
    before, after = report['operational_gate']['before'], report['operational_gate']['after']
    shadow = report['shadow_observation']
    return f"""# Stage 14 Integration Lab & Authorized Shadow Pilot Preflight

状态：`{report['status']}`；真实 Shadow Gate：`{report['real_shadow_gate']['status']}`。

- 运行 Gate：修复前 `{before['status']}`，死信和事故真实回放后 `{after['status']}`。
- Connector Lab：`{report['connectors']['status']}`，限流重试 {report['connectors']['rate_limit_retries']}，客户系统写入 0。
- OIDC Lab：`{report['identity_lab']['status']}`，验证 Discovery、MFA、Group Mapping、Key Rotation 和停用。
- Telemetry Lab：`{report['telemetry_lab']['status']}`，导出 {report['telemetry_lab']['span_count']} spans，删除 {report['telemetry_lab']['dropped_attribute_count']} 个未授权属性。
- 合成 Shadow：{shadow['case_count']} 案例、{shadow['user_count']} 个教学角色，真实客户用户 0，外部动作 0。
- 证据包：`{report['evidence']['status']}`，路径全部为相对路径并使用 SHA-256 绑定。

本阶段验证的是本地集成实验室。PostgreSQL 生产运行、企业 OIDC、真实 Connector、OTLP 后端、客户 UAT 和值班演练仍需外部证据，因此不声称已获得真实客户 Shadow 授权。
"""


def run_demo(output, *, check_baseline=False, external_evidence=DEFAULT_EXTERNAL_EVIDENCE):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    stage13_report = stage13.run_demo(output / 'stage13-source', check_baseline=True)
    connectors = exercise_connectors(read(CONNECTORS))
    identity_lab = rehearse_oidc(read(IDENTITY))
    telemetry_lab = rehearse_telemetry(output)
    before = operational_gate(stage13_report['delivery_room'],
                              stage13_report['model_lab'], telemetry_lab, connectors)
    delivery, remediation = remediate_delivery_room(
        output / 'stage13-source/delivery-room', stage13_report['delivery_room'])
    after = operational_gate(delivery, stage13_report['model_lab'], telemetry_lab, connectors)
    shadow = shadow_metrics(read(OBSERVATIONS))
    real_gate = real_shadow_gate(read(external_evidence))
    component_paths = []
    components = {'connector-report.json': connectors, 'identity-lab-report.json': identity_lab,
        'telemetry-lab-report.json': telemetry_lab, 'remediation-report.json': remediation,
        'shadow-observation-report.json': shadow,
        'operational-gates.json': {'before': before, 'after': after},
        'real-shadow-gate.json': real_gate}
    for name, value in components.items():
        path = output / name
        write(path, value)
        component_paths.append(path)
    manifest = evidence_manifest(output, component_paths, {
        'mode': 'synthetic_integration_lab', 'real_customer_records': False,
        'external_customer_actions': 0})
    write(output / 'evidence-manifest.json', manifest)
    evidence = {'status': 'EVIDENCE_BUNDLE_VERIFIED' if
        verify_manifest(output, manifest) else 'EVIDENCE_BUNDLE_INVALID',
        'artifact_count': len(manifest['artifacts']),
        'bundle_sha256': manifest['bundle_sha256'], 'portable_relative_paths': True}
    lab_checks = {
        'blocked_before_remediation': before['status'] == 'OPERATIONAL_GATE_BLOCKED',
        'ready_after_remediation': after['status'] == 'OPERATIONAL_GATE_READY',
        'incidents_closed_after_success': remediation['all_incidents_resolved'],
        'connectors': connectors['status'] == 'CONNECTOR_LAB_PASSED',
        'identity_lab': identity_lab['status'] == 'OIDC_LAB_PASSED',
        'telemetry_lab': telemetry_lab['status'] == 'OTLP_LAB_PIPELINE_PASSED',
        'synthetic_shadow_safe': shadow['unsafe_suggestion_count'] == 0 and
                                 shadow['external_customer_actions'] == 0,
        'evidence_bundle': evidence['status'] == 'EVIDENCE_BUNDLE_VERIFIED',
    }
    report = {'status': 'INTEGRATION_LAB_READY_FOR_AUTHORIZED_SHADOW_REVIEW'
              if all(lab_checks.values()) else 'INTEGRATION_LAB_BLOCKED',
              'operational_gate': {'before': before, 'after': after},
              'remediation': remediation, 'connectors': connectors,
              'identity_lab': identity_lab, 'telemetry_lab': telemetry_lab,
              'shadow_observation': shadow, 'evidence': evidence,
              'real_shadow_gate': real_gate, 'lab_checks': lab_checks,
              'postgres_runtime_executed': False, 'enterprise_oidc_used': False,
              'real_connectors_called': 0, 'real_otlp_backend_used': False,
              'real_customer_data_ingested': False, 'actual_customer_users': 0,
              'external_customer_actions': 0,
              'decision': 'ITERATE_BEFORE_REAL_SHADOW',
              'next_gate': 'AUTHORIZED_CUSTOMER_SHADOW_PILOT'}
    write(output / 'stage14-report.json', report)
    (output / 'stage14-report.md').write_text(render(report), encoding='utf-8')
    if check_baseline:
        check_report(report)
    print(f"Stage 14：{report['status']}；Gate {before['status']} -> {after['status']}；真实客户动作 0。")
    return report


def _resolve(value, path):
    for part in path.split('.'):
        value = value[part]
    return value


def check_report(report):
    for path, expected in read(BASELINE).items():
        actual = _resolve(report, path)
        if actual != expected:
            raise ValueError(f'Stage 14 回归失败：{path} 期望 {expected!r}，实际 {actual!r}')
    return True


def main():
    parser = argparse.ArgumentParser(description='Stage 14 集成实验室与受控 Shadow 预检')
    parser.add_argument('command', choices=('demo', 'preflight', 'verify-evidence'))
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-14')
    parser.add_argument('--external-evidence', type=Path, default=DEFAULT_EXTERNAL_EVIDENCE)
    parser.add_argument('--check-baseline', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'demo':
            run_demo(args.output.resolve(), check_baseline=args.check_baseline,
                     external_evidence=args.external_evidence)
        elif args.command == 'preflight':
            print(json.dumps(real_shadow_gate(read(args.external_evidence)),
                             ensure_ascii=False, indent=2))
        else:
            manifest = read(args.output / 'evidence-manifest.json')
            valid = verify_manifest(args.output, manifest)
            print(json.dumps({'evidence_manifest_valid': valid}, ensure_ascii=False))
            return 0 if valid else 2
        return 0
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f'Stage 14 失败：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
