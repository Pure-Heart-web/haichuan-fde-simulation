#!/usr/bin/env python3
"""Stage 8: offline two-tenant productization and Qihang after-sales replay."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from fde_platform.apps.service_review_web import serve
from fde_platform.core.ingestion import from_text
from fde_platform.core.platform.contracts import ContextRequest, EntityRef
from fde_platform.core.platform.runtime import ScopedKnowledgeIndex
from fde_platform.core.platform.tenant_store import TenantStore
from fde_platform.domains.after_sales.context import AssetContextProvider
from fde_platform.domains.after_sales.diagnosis import diagnose
from fde_platform.domains.after_sales.extraction import extract_service_case
from fde_platform.domains.after_sales.workflow import process_service_case
from fde_platform.domains.foreign_trade.platform.adapter import bridge_haichuan

DATA = ROOT / 'stages/08-productization/data'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def config():
    item = read_json(DATA / 'tenant-config.json')
    if (item['mode'] != 'synthetic_training_only' or item['auto_customer_guidance'] or
        item['auto_dispatch'] or item['real_pilot_gate'] != 'NOT_EVALUATED'):
        raise ValueError('Stage 8 只能在不指导客户、不派工的模拟模式运行')
    return item


def tenant_domains():
    return {x['tenant_id']: x['domain'] for x in config()['tenants']}


def cases():
    return [json.loads(line) for line in (DATA / 'service-cases.jsonl').read_text(encoding='utf-8').splitlines()
            if line.strip()]


def seed(store):
    assets = read_json(DATA / 'assets.json')
    knowledge = read_json(DATA / 'knowledge.json')
    rules = read_json(DATA / 'service-rules.json')
    if any(x['mode'] != 'synthetic_training_only' for x in (assets, knowledge, rules)):
        raise ValueError('只允许合成数据包')
    qh = store.scope('qihang-training', 'after_sales')
    for row in assets['assets']:
        qh.put('context', row['serial_number'], {'tenant_id': qh.tenant_id, 'domain': qh.domain,
             'source_version': assets['version'], **row})
    for doc in knowledge['documents']:
        store.scope(doc['tenant_id'], doc['domain']).put('knowledge', doc['document_id'], doc)
    for rule in rules['rules']:
        qh.put('rule', rule['id'], {'tenant_id': qh.tenant_id, 'domain': qh.domain,
                                  'registry_version': rules['version'], **rule})


def evaluate(artifacts, haichuan, qh):
    field_names = ('device_model', 'serial_number', 'error_code', 'current_pressure_bar',
                   'recent_maintenance')
    field_correct = field_total = top_correct = risk_correct = routing_correct = unsafe = 0
    failures = []
    for case in cases():
        result = artifacts[case['id']]
        service = result['service_case']
        expected = case['expected']
        extracted = {**service, 'recent_maintenance': service['recent_maintenance_reported']}
        for name in field_names:
            field_total += 1
            if extracted[name] == expected[name]:
                field_correct += 1
            else:
                failures.append({'case_id': case['id'], 'field': name,
                                 'expected': expected[name], 'actual': extracted[name]})
        rec, task = result['recommendation'], result['review_task']
        top = rec['options'][0]['code']
        top_correct += top == expected['top_option']
        risk_correct += rec['risk_level'] == expected['risk_level']
        routing_correct += task['assignee_role'] == expected['reviewer_role']
        unsafe += int(rec['risk_level'] in ('high', 'critical') and not task['payload']['blocking_risk'])
        if top != expected['top_option'] or rec['risk_level'] != expected['risk_level']:
            failures.append({'case_id': case['id'], 'expected_top': expected['top_option'],
                             'actual_top': top, 'expected_risk': expected['risk_level'],
                             'actual_risk': rec['risk_level']})
    tenant_scope_ok = (not any(x['document_id'].startswith('HC-') for x in qh.list('knowledge')) and
                       not any(x['document_id'].startswith('QH-') for x in haichuan.list('knowledge')) and
                       qh.get('trace', haichuan.list('trace')[0]['trace_id']) is None and
                       haichuan.get('trace', qh.list('trace')[0]['trace_id']) is None)
    return {'mode': 'synthetic_cross_domain_regression', 'case_count': len(artifacts),
            'field_correct': field_correct, 'field_total': field_total,
            'field_accuracy': field_correct / field_total, 'top1_correct': top_correct,
            'risk_correct': risk_correct, 'review_routing_correct': routing_correct,
            'unsafe_auto_guidance_count': unsafe, 'tenant_scope_ok': tenant_scope_ok,
            'real_pilot_gate': 'NOT_EVALUATED', 'failures': failures,
            'observed_api_cost_usd': 0.0}


def render_eval(report):
    return (f'# Stage 8 双客户合成评估\n\n售后案例 {report["case_count"]} 条；'
            f'字段 {report["field_correct"]}/{report["field_total"]}；'
            f'Top-1 {report["top1_correct"]}/{report["case_count"]}；'
            f'风险 {report["risk_correct"]}/{report["case_count"]}；'
            f'审核路由 {report["review_routing_correct"]}/{report["case_count"]}。\n\n'
            f'跨租户作用域检查：{report["tenant_scope_ok"]}；自动高风险指导：'
            f'{report["unsafe_auto_guidance_count"]}；离线 API 成本：$0。\n\n'
            '**这些只验证教学样本；没有真实启航用户、授权资产源、现场维修结果或生产安全批准。** '
            '真实 Pilot Gate：`NOT_EVALUATED`。\n')


def save_incident(output, qh):
    case = next(x for x in cases() if x['id'] == 'QH-001')
    work = from_text(case['text'], source_id=case['id'], tenant_id=qh.tenant_id,
                     domain=qh.domain, source_type=case['source_type'])
    _, service = extract_service_case(work)
    context = AssetContextProvider(qh).get_context(
        EntityRef(qh.tenant_id, qh.domain, 'asset', service.serial_number),
        ContextRequest('maintenance_history', case['as_of']))
    before, _, _ = diagnose(service, context, qh, as_of=case['as_of'], use_context=False)
    after, _, provenance = diagnose(service, context, qh, as_of=case['as_of'], use_context=True)
    report = {'incident_id': 'INC-SIM-008-01', 'mode': 'synthetic_shadow_replay',
              'case_id': case['id'], 'legacy_top': before.options[0].code,
              'corrected_top': after.options[0].code,
              'root_cause': 'retrieved_recent_maintenance_not_used_in_domain_ranking',
              'asset_context_source_ids': [x.source_id for x in context],
              'recent_maintenance_used_after': provenance['recent_maintenance_used'],
              'fix_location': 'after_sales/diagnosis.py',
              'core_abstraction_deferred': 'context_aware_decision_inputs',
              'actual_incident': False}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'shadow-incident.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'shadow-incident.md').write_text(
        '# 启航 Shadow 故障重放\n\nQH-001 的旧排序先给 `' + report['legacy_top'] +
        '`；同一抽取、知识和资产历史下，使用“昨日保养”决策输入后先给 `' +
        report['corrected_top'] + '`。历史来源：`' + ', '.join(report['asset_context_source_ids']) +
        '`。这是合成故障，不是实际派工或现场事故；先保留在售后 Domain，等待更多客户验证后再抽到 Core。\n',
        encoding='utf-8')
    return report


def run_demo(output):
    output.mkdir(parents=True, exist_ok=True)
    store = TenantStore(output / 'platform.sqlite3', tenant_domains())
    try:
        seed(store)
        qh = store.scope('qihang-training', 'after_sales')
        hc = store.scope('haichuan-training', 'foreign_trade')
        artifacts = {}
        folder = output / 'service-artifacts'
        folder.mkdir(exist_ok=True)
        for case in cases():
            artifact = process_service_case(case, qh)
            artifacts[case['id']] = artifact
            (folder / (case['id'] + '.json')).write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        source_case = next(item for item in (
            json.loads(line) for line in
            (ROOT / 'stages/07-pilot-operations/data/pilot-scenarios.jsonl').read_text(encoding='utf-8').splitlines()
            if line.strip()) if item['id'] == 'P7-001')
        bridge = bridge_haichuan(source_case, hc, ROOT)
        (output / 'haichuan-bridge.json').write_text(json.dumps(bridge, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        eval_report = evaluate(artifacts, hc, qh)
        (output / 'stage8-eval.json').write_text(json.dumps(eval_report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (output / 'stage8-eval.md').write_text(render_eval(eval_report), encoding='utf-8')
        incident = save_incident(output, qh)
        status = {'status': 'SYNTHETIC_TWO_TENANT_REPLAY_READY', 'qihang_cases': len(artifacts),
                  'haichuan_bridge_cases': 1, 'qihang_review_tasks': len(qh.list('review_task')),
                  'tenant_scope_ok': eval_report['tenant_scope_ok'],
                  'shadow_failure_replayed': incident['legacy_top'] != incident['corrected_top'],
                  'real_pilot_users': 0, 'real_pilot_gate': 'NOT_EVALUATED',
                  'customer_guidance_sent': 0, 'dispatches_created': 0}
        (output / 'platform-status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    finally:
        store.close()
    print(f'Stage 8：启航 {status["qihang_cases"]} 条售后案例、海川 {status["haichuan_bridge_cases"]} 条适配；'
          f'租户隔离 {status["tenant_scope_ok"]}；真实 Pilot 未评估。')
    return 0


def check_baseline(output):
    expected = read_json(DATA / 'regression-baseline.json')
    status = read_json(output / 'platform-status.json')
    report = read_json(output / 'stage8-eval.json')
    incident = read_json(output / 'shadow-incident.json')
    for key, value in expected['status'].items():
        if status.get(key) != value:
            raise ValueError(f'Stage 8 状态回归失败：{key}')
    for key, value in expected['eval'].items():
        if report.get(key) != value:
            raise ValueError(f'Stage 8 评估回归失败：{key}')
    if (incident['legacy_top'], incident['corrected_top']) != ('inspect_intake_condition', 'review_maintenance_work_order'):
        raise ValueError('近期保养排序故障未正确重放')
    print('Stage 8 合成双租户回归通过；真实 Pilot Gate 未评估。')
    return 0


def main():
    parser = argparse.ArgumentParser(description='Stage 8 双客户产品化离线演练')
    parser.add_argument('command', choices=('demo', 'eval', 'review', 'trace', 'incident'))
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-08')
    parser.add_argument('--tenant', choices=('qihang-training', 'haichuan-training'), default='qihang-training')
    parser.add_argument('--case')
    parser.add_argument('--port', type=int, default=8769)
    parser.add_argument('--check-baseline', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        if args.command == 'demo':
            return run_demo(output)
        if not (output / 'platform-status.json').exists():
            run_demo(output)
        if args.command == 'eval':
            if args.check_baseline:
                return check_baseline(output)
            print((output / 'stage8-eval.md').read_text(encoding='utf-8'))
            return 0
        if args.command == 'review':
            serve(output / 'platform.sqlite3', tenant_domains(), config()['qihang_reviewers'], args.port)
            return 0
        if args.command == 'incident':
            print((output / 'shadow-incident.md').read_text())
            return 0
        if not args.case:
            parser.error('trace 需要 --case')
        store = TenantStore(output / 'platform.sqlite3', tenant_domains())
        try:
            scope = store.scope(args.tenant, tenant_domains()[args.tenant])
            trace = next((x for x in scope.list('trace') if x['case_id'] == args.case), None)
            if trace is None:
                raise ValueError('当前租户找不到该 Trace')
            print(json.dumps(trace, ensure_ascii=False, indent=2))
        finally:
            store.close()
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
