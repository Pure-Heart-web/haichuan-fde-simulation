#!/usr/bin/env python3
"""Synthetic delivery hardening: fixtures, services, identity, governance and ops."""
import argparse
from getpass import getpass
import json
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from stage7 import run_demo as run_stage7
from stage8 import seed, tenant_domains
from stage8_vertical import inbound_events, prepare_event
from fde_platform.core.platform.episode import EpisodeJournal
from fde_platform.core.platform.tenant_store import TenantStore
from fde_platform.evals.runner import evaluate
from fde_platform.hardening.auth import IdentityBroker
from fde_platform.hardening.annotations import AnnotationBook
from fde_platform.hardening.governance import assess_curve, evaluate_challenges, validate_service_rules
from fde_platform.hardening.migration import migrate_stage7, scoped_export
from fde_platform.hardening.mock_services import MockServices
from fde_platform.hardening.model import LoopbackModelProvider, probe_provider
from fde_platform.hardening.operations import OperationsSignoffs

DATA = ROOT / 'stages/09-hardening/data'
VERTICAL = ROOT / 'stages/08-productization/vertical'
ACCOUNTS = {'engineer-chen': ('qihang-training', 'engineer'),
            'zhou': ('qihang-training', 'support'),
            'safety-owner-wu': ('qihang-training', 'adjudicator'),
            'anna': ('haichuan-training', 'sales'),
            'mike': ('haichuan-training', 'engineer'),
            'product-owner-li': ('haichuan-training', 'adjudicator'),
            'platform-auditor': ('haichuan-training', 'auditor'),
            'pilot-owner-linda': ('haichuan-training', 'pilot_owner'),
            'platform-owner-li': ('haichuan-training', 'platform_owner'),
            'ops-safety-wu': ('qihang-training', 'safety_owner')}
SAFE_SERVICE_ACK = '已收到故障信息，工程师将按工单现场复核；此处不提供远程维修步骤。'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def identity(output):
    broker = IdentityBroker(output / 'identity')
    path = output / 'identity' / 'training-credentials.json'
    if not path.exists():
        credentials = {actor: secrets.token_urlsafe(16) for actor in ACCOUNTS}
        write(path, {'mode': 'local_synthetic_credentials_only', 'passwords': credentials})
        path.chmod(0o600)
    passwords = read(path)['passwords']
    for actor, (tenant, role) in ACCOUNTS.items():
        broker.add_account(actor, tenant, role, passwords[actor])
    return broker, passwords


def journal(store, tenant_id):
    return EpisodeJournal(store.scope(tenant_id, tenant_domains()[tenant_id]))


def episode_for_case(store, tenant_id, case_id):
    matches = [x for x in journal(store, tenant_id).list() if x['case_id'] == case_id]
    if len(matches) != 1:
        raise ValueError('当前租户案例不存在或不唯一')
    return matches[0]


def require_assignee(store, episode, claims):
    task = journal(store, claims['tenant_id']).session.get('review_task', episode['review_task_id'])
    if (not task or task['assignee_id'] != claims['sub'] or
        task['assignee_role'] != claims['role']):
        raise ValueError('当前身份不是该任务的审核负责人')
    return task


def deliver(store, services, output, event):
    if event['domain'] == 'after_sales':
        source_ref, source_kind = 'WO-QH-110', 'cmms'
    else:
        source_ref, source_kind = 'S6-ORD-002', 'crm'
    if not services.get_record(event['tenant_id'], event['domain'], source_kind, source_ref):
        raise ValueError(f'模拟 {source_kind.upper()} 来源暂不可用：{source_ref}')
    prepare_event(store, output, event)
    episode = episode_for_case(store, event['tenant_id'], event['case_id'])
    recommendation = journal(store, event['tenant_id']).session.get('recommendation', event['case_id'])
    if source_ref not in recommendation['evidence_refs']:
        raise ValueError('建议未携带已查询的外部来源证据')
    kind = 'ticket' if event['domain'] == 'after_sales' else 'sales_inquiry'
    services.record(event['tenant_id'], event['domain'], kind, episode['case_record_id'],
                    {'case_id': event['case_id'], 'source_id': event['source_id'],
                     'mode': 'mock_service', 'status': 'open'})


def prepare(output):
    controls()  # Release signatures must validate before any mock input is processed.
    broker, credentials = identity(output)
    store = TenantStore(output / 'platform.sqlite3', tenant_domains())
    services = MockServices(output / 'mock-services.sqlite3')
    try:
        seed(store)
        maintenance = read(ROOT / 'stages/08-productization/data/assets.json')['assets'][0]['maintenance'][0]
        services.record('qihang-training', 'after_sales', 'cmms', maintenance['work_order_id'], maintenance)
        services.record('haichuan-training', 'foreign_trade', 'crm', 'S6-ORD-002',
                        {'source_id': 'S6-ORD-002', 'mode': 'synthetic_previous_order_reference'})
        events = inbound_events()
        received = [services.receive(item) for item in events[:2]]
        redelivery = dict(events[0], event_id='SIM-CALL-QH-001-REDELIVERY')
        duplicate_accepted = services.receive(redelivery)
        first = services.work(lambda x: deliver(store, services, output, x),
                              tick=0, timeout_once=('SIM-MAIL-P7-003',))
        second = services.work(lambda x: deliver(store, services, output, x), tick=2)
        return {'new_inputs': sum(received), 'duplicate_accepted': duplicate_accepted,
                'first_poll': first, 'retry_poll': second,
                'service_status': services.status()}
    finally:
        services.close()
        store.close()


def controls():
    challenges = evaluate_challenges(read(DATA / 'challenge-cases.json')['cases'],
                                     read(DATA / 'dual-role-labels.json')['labels'])
    safety = validate_service_rules(read(ROOT / 'stages/08-productization/data/service-rules.json'),
                                    read(DATA / 'service-rule-release.json'))
    curves = read(DATA / 'performance-curves.json')
    curve_known = assess_curve(curves, sku='CP90', flow_m3h=85, head_m=38, medium='water',
                               temperature_c=20, frequency_hz=50, voltage_v=380, as_of='2026-09-21')
    curve_unknown = assess_curve(curves, sku='CP90', flow_m3h=85, head_m=38, medium='water',
                                 temperature_c=None, frequency_hz=None, voltage_v=None, as_of='2026-09-21')
    return {'challenge_eval': challenges, 'service_safety_release': safety,
            'curve_known_conditions': curve_known, 'curve_unknown_conditions': curve_unknown,
            'safety_threshold_95c_is_training_only': True}


def review_case(store, broker, token, case_id, edited_action, reason):
    claims = broker.verify(token)
    episode = episode_for_case(store, claims['tenant_id'], case_id)
    require_assignee(store, episode, claims)
    if episode['state'] == 'pending_review':
        journal(store, claims['tenant_id']).record_edit(episode['episode_id'],
            actor_id=claims['sub'], actor_role=claims['role'],
            edited_action=edited_action, reason=reason)
    return episode_for_case(store, claims['tenant_id'], case_id)


def confirm_case(store, services, broker, token, case_id, content):
    claims = broker.verify(token)
    episode = episode_for_case(store, claims['tenant_id'], case_id)
    require_assignee(store, episode, claims)
    if episode['domain'] == 'after_sales' and content != SAFE_SERVICE_ACK:
        raise ValueError('售后待发送区只允许安全回执模板，不能输出远程维修步骤')
    if episode['domain'] == 'foreign_trade' and 'CP90' in content:
        outcome = services.get_record(claims['tenant_id'], episode['domain'],
                                      'crm', 'SIM-CRM-P7-003-CONFIRM')
        if not outcome or outcome['case_id'] != case_id:
            raise ValueError('当前工况未确认；不能把产品候选放入待发送区')
        conditions = outcome['confirmed_operating_conditions']
        assessment = assess_curve(read(DATA / 'performance-curves.json'),
            **conditions, as_of=outcome['recorded_at'][:10])
        if assessment['decision'] != 'provisional_for_human_review':
            raise ValueError('性能曲线不支持当前工况；必须升级')
    return dict(services.confirm_to_outbox(episode, claims, content))


def close_case(store, services, broker, token, case_id, outcome):
    claims = broker.verify(token)
    if outcome['observed_by'] != claims['sub']:
        raise ValueError('结果记录人必须是已认证的观察人')
    episode = episode_for_case(store, claims['tenant_id'], case_id)
    require_assignee(store, episode, claims)
    if episode['domain'] == 'foreign_trade':
        conditions = outcome.get('confirmed_operating_conditions')
        if not conditions:
            raise ValueError('客户当前工况未独立确认')
        assessment = assess_curve(read(DATA / 'performance-curves.json'),
            **conditions, as_of=outcome['recorded_at'][:10])
        if assessment['decision'] != 'provisional_for_human_review':
            raise ValueError('经确认工况未通过模拟性能曲线门')
    kind = 'cmms' if episode['domain'] == 'after_sales' else 'crm'
    # The external observation is its own source of truth. Persist it before linking it
    # into the workflow so a local journal failure can be retried without inventing data.
    services.record(claims['tenant_id'], episode['domain'], kind, outcome['outcome_id'], outcome)
    if episode['state'] == 'reviewed':
        journal(store, claims['tenant_id']).close(episode['episode_id'], outcome)
    episode = episode_for_case(store, claims['tenant_id'], case_id)
    return episode


def replay_humans(output):
    broker, credentials = identity(output)
    store = TenantStore(output / 'platform.sqlite3', tenant_domains())
    services = MockServices(output / 'mock-services.sqlite3')
    try:
        reviews = read(VERTICAL / 'scripted-reviews.json')['reviews']
        outcomes = {x['case_id']: x for x in read(VERTICAL / 'outcomes.json')['outcomes']}
        for item in reviews:
            token = broker.authenticate(item['actor_id'], credentials[item['actor_id']])
            episode = review_case(store, broker, token, item['case_id'],
                                  item['edited_action'], item['reason'])
            close_case(store, services, broker, token, item['case_id'], outcomes[item['case_id']])
            content = (SAFE_SERVICE_ACK
                if item['domain'] == 'after_sales' else
                'CP90 仅为暂定候选，须由销售和工程师最终确认；请复核适用文件。')
            confirm_case(store, services, broker, token, item['case_id'], content)
        updated = dict(inbound_events()[0], event_id='SIM-CALL-QH-001-V2',
                       case_id='QH-001-R2', source_id='CALL-QH-20260921-001-V2',
                       received_at='2026-09-22T09:00:00+08:00', as_of='2026-09-22',
                       text='Corrected transcript: QH-75 serial QH7519238, E37, pressure 5 bar, abnormal noise. Recheck yesterday maintenance.')
        services.receive(updated, version=2, supersedes_source_id=inbound_events()[0]['source_id'])
        services.work(lambda x: deliver(store, services, output, x), tick=3)
        return services.status()
    finally:
        services.close()
        store.close()


def migrate(output):
    legacy = output / 'legacy-stage-07'
    run_stage7(legacy)
    from fde_platform.core.pilot.store import PilotStore
    old = PilotStore(legacy / 'pilot.sqlite3')
    try:
        if not old.events():
            task = next(x for x in old.list_tasks(actor_id='admin', role='admin')
                        if not x['prerequisite_task_id'])
            action = 'edit' if task['type'] == 'sales_draft' else 'resolve'
            old.review(task['task_id'], task['assignee_id'], task['assignee_role'],
                       action, '模拟迁移前审核记录')
    finally:
        old.close()
    store = TenantStore(output / 'platform.sqlite3', tenant_domains())
    try:
        result = migrate_stage7(legacy / 'pilot.sqlite3',
                                store.scope('haichuan-training', 'foreign_trade'))
    finally:
        store.close()
    return result


def make_report(output):
    store = TenantStore(output / 'platform.sqlite3', tenant_domains())
    services = MockServices(output / 'mock-services.sqlite3')
    try:
        episodes = [x for tenant in tenant_domains() for x in journal(store, tenant).list()]
        by_case = {x['case_id']: x for x in episodes}
        controls_report = controls()
        service = services.status()
        operations_plan = read(DATA / 'operations-plan.json')
        legacy_dashboard = read(output / 'legacy-stage-07/pilot-dashboard.json') if (
            output / 'legacy-stage-07/pilot-dashboard.json').exists() else None
        closed = sum(x['state'] == 'closed' for x in episodes)
        reviewed = sum(x['state'] in ('reviewed', 'closed') for x in episodes)
        hard_stop = (controls_report['challenge_eval']['safety_failures'] > 0 or
                     service['sent_messages'] > 0 or
                     controls_report['service_safety_release']['status'] != 'SIMULATED_APPROVED')
        report = {'mode': 'synthetic_hardening_replay', 'stage4': {
            'offline_thresholds_met': evaluate(ROOT / 'stages/04-build-sprint-1/data/inquiry_eval_v0.jsonl')['offline_thresholds_met']},
            'episodes': {case: {'state': row['state'], 'tenant_id': row['tenant_id'],
                'event_types': [x['event_type'] for x in journal(store, row['tenant_id']).events(row['episode_id'])]}
                for case, row in by_case.items()},
            'mock_services': service, 'controls': controls_report,
            'legacy_migration': {'haichuan_traces': len(store.scope('haichuan-training', 'foreign_trade').list('legacy_trace')),
                                 'haichuan_review_events': len(store.scope('haichuan-training', 'foreign_trade').list('legacy_review_event'))},
            'model_comparison': ('SYNTHETIC_ENDPOINT_EVALUATED'
                if (output / 'model-comparison.json').exists() else 'NOT_RUN_NO_ENDPOINT'),
            'actual_pilot_users': 0,
            'operator_annotation_status': ('AVAILABLE_SEPARATELY' if
                (output / 'annotations.sqlite3').exists() else 'NOT_STARTED'),
            'operations': {'baseline_version': operations_plan['version'],
                'metric_definitions': operations_plan['metric_definitions'],
                'simulated_reviewed_cases': reviewed, 'simulated_human_edits': reviewed,
                'simulated_case_count': len(episodes), 'simulated_closed_cases': closed,
                'real_adoption': None, 'real_expert_minutes': None, 'real_error_rate': None,
                'dependency_retry_attempts': service['retry_attempts'],
                'dependency_incident': {'kind': 'mock_mailbox_timeout', 'status': 'recovered_after_retry',
                                        'owner': 'sim-platform-oncall', 'actual_incident': False},
                'paid_model_cost_usd': 0.0, 'actual_integration_cost': None,
                'stage7_synthetic_adoption_rate': legacy_dashboard['product']['eligible_complex_adoption_rate']
                    if legacy_dashboard else None,
                'stop_triggered': hard_stop,
                'required_simulated_signers': operations_plan['simulated_signoff'],
                'simulated_signoffs_recorded': [],
                'real_signoffs': []},
            'pilot_decision': 'STOP_IN_SIMULATION' if hard_stop else 'ITERATE_IN_SIMULATION',
            'pilot_decision_status': 'RECOMMENDATION_AWAITING_SIGNOFF',
            'real_pilot_gate': 'NOT_EVALUATED',
            'real_safety_approval': False, 'real_product_approval': False,
            'stop_conditions': operations_plan['stop_if'],
            'on_call': {'simulated_owner': 'sim-platform-oncall', 'rollback': 'disable_mock_worker_and_revert_fixture_version',
                        'actual_on_call': False}}
        signoff_path = output / 'ops-signoffs.sqlite3'
        if signoff_path.exists():
            signoffs = OperationsSignoffs(signoff_path, operations_plan['simulated_signoff'])
            try:
                status = signoffs.status(report)
            finally:
                signoffs.close()
            report['operations']['simulated_signoffs_recorded'] = status['current_signoffs']
            report['pilot_decision_status'] = status['status']
        write(output / 'hardening-report.json', report)
        (output / 'hardening-report.md').write_text(
            '# Stage 9 交付强化演练\n\n'
            f'Stage 4 合成字段门槛：{report["stage4"]["offline_thresholds_met"]}；'
            f'挑战案例：{controls_report["challenge_eval"]["correct"]}/{controls_report["challenge_eval"]["case_count"]}；'
            f'保留分歧：{controls_report["challenge_eval"]["disagreements_retained"]}。\n\n'
            f'完整闭环：{sum(x["state"] == "closed" for x in episodes)}；'
            f'更新待审：{sum(x["state"] == "pending_review" for x in episodes)}；'
            f'模拟重试：{service["retry_attempts"]}；待发送：{service["outbox"].get("pending_send", 0)}；'
            '实际发送：0。\n\n'
            '性能曲线和售后规则仅有合成审批。模型端点未配置，真实身份、人工标注与 Pilot 均未验证；'
            '决策仅为 ITERATE_IN_SIMULATION。详见 stages/09-hardening/README.md。\n', encoding='utf-8')
        return report
    finally:
        services.close()
        store.close()


def run_demo(output):
    prep = prepare(output)
    replay_humans(output)
    migration = migrate(output)
    result = make_report(output)
    print(f'Stage 9 合成强化：闭环 {sum(x["state"] == "closed" for x in result["episodes"].values())}；'
          f'更新待审 1；重试 {result["mock_services"]["retry_attempts"]}；'
          f'待发送 {result["mock_services"]["outbox"].get("pending_send", 0)}；'
          f'旧队列迁移 {migration["traces"]} Trace。')
    return result


def check_baseline(report):
    expected = read(DATA / 'regression-baseline.json')
    for key, value in expected.items():
        actual = report
        for part in key.split('.'):
            actual = actual[part]
        if actual != value:
            raise ValueError(f'Stage 9 合成回归失败：{key}={actual!r}')
    print('Stage 9 合成强化回归通过；真实试点、真人标注和模型端点仍未验证。')


def main():
    parser = argparse.ArgumentParser(description='Stage 9 双 Domain 交付强化演练')
    parser.add_argument('command', choices=('demo', 'prepare', 'login', 'queue', 'review',
        'confirm', 'close', 'report', 'eval', 'model-eval', 'migrate', 'export-legacy',
        'label', 'adjudicate', 'labels-report', 'ops-signoff', 'ops-status'))
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-09')
    parser.add_argument('--check-baseline', action='store_true')
    parser.add_argument('--actor')
    parser.add_argument('--token-file', type=Path)
    parser.add_argument('--case')
    parser.add_argument('--edited-action')
    parser.add_argument('--reason')
    parser.add_argument('--content')
    parser.add_argument('--outcome-id')
    parser.add_argument('--endpoint')
    parser.add_argument('--tenant')
    parser.add_argument('--route')
    parser.add_argument('--decision', choices=('STOP', 'ITERATE', 'EXPAND'))
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        if args.command == 'demo':
            result = run_demo(output)
            if args.check_baseline:
                check_baseline(result)
            return 0
        if args.command == 'prepare':
            print(json.dumps(prepare(output), ensure_ascii=False, indent=2))
            return 0
        if args.command == 'migrate':
            print(json.dumps(migrate(output), ensure_ascii=False, indent=2))
            return 0
        if args.command == 'model-eval':
            if not args.endpoint:
                parser.error('model-eval 需要 --endpoint 本机模型服务地址')
            baseline = evaluate(ROOT / 'stages/04-build-sprint-1/data/inquiry_eval_v0.jsonl')
            provider = LoopbackModelProvider(args.endpoint)
            model = evaluate(ROOT / 'stages/04-build-sprint-1/data/inquiry_eval_v0.jsonl', provider)
            security = probe_provider(provider)
            result = {'mode': 'synthetic_eval_only', 'baseline': baseline, 'model': model,
                      'security_probes': security,
                      'not_independent_real_world_evidence': True}
            write(output / 'model-comparison.json', result)
            print(output / 'model-comparison.json')
            return 0
        broker, _ = identity(output)
        if args.command == 'login':
            if args.actor not in ACCOUNTS:
                parser.error('login 需要 --actor 指定已预置的模拟身份')
            token = broker.authenticate(args.actor, getpass('本地演练密码: '))
            path = output / 'identity' / (args.actor + '.token')
            path.write_text(token + '\n')
            path.chmod(0o600)
            print(path)
            return 0
        if args.command == 'report':
            result = make_report(output)
            print(output / 'hardening-report.md')
            return 0
        if args.command == 'eval':
            result = read(output / 'hardening-report.json') if (output / 'hardening-report.json').exists() else run_demo(output)
            if args.check_baseline:
                check_baseline(result)
            return 0
        if not args.token_file:
            parser.error('访问队列、审核或导出需要 --token-file')
        token = args.token_file.read_text().strip()
        claims = broker.verify(token)
        if args.command in ('ops-signoff', 'ops-status'):
            result = read(output / 'hardening-report.json')
            book = OperationsSignoffs(output / 'ops-signoffs.sqlite3',
                read(DATA / 'operations-plan.json')['simulated_signoff'])
            try:
                if args.command == 'ops-signoff':
                    if not all((args.decision, args.reason)):
                        parser.error('ops-signoff 需要 --decision 与 --reason')
                    answer = book.sign(claims, result, args.decision, args.reason)
                else:
                    if claims['role'] not in ('pilot_owner', 'safety_owner', 'platform_owner', 'auditor'):
                        raise ValueError('当前身份不能查看运营签核')
                    answer = book.status(result)
                print(json.dumps(answer, ensure_ascii=False, indent=2))
                return 0
            finally:
                book.close()
        if args.command in ('label', 'adjudicate', 'labels-report'):
            book = AnnotationBook(output / 'annotations.sqlite3',
                                  read(DATA / 'challenge-cases.json')['cases'])
            try:
                if args.command == 'label':
                    if not all((args.case, args.route, args.reason)):
                        parser.error('label 需要 --case、--route、--reason')
                    result = book.submit(args.case, claims, args.route, args.reason)
                elif args.command == 'adjudicate':
                    if not all((args.case, args.route, args.reason)):
                        parser.error('adjudicate 需要 --case、--route、--reason')
                    result = book.adjudicate(args.case, claims, args.route, args.reason)
                else:
                    result = book.report()
                    owner_prefix = 'QH-' if claims['tenant_id'] == 'qihang-training' else 'HC-'
                    result['adjudications'] = [x for x in result['adjudications']
                                               if x['case_id'].startswith(owner_prefix)]
                    adjudicated = {x['case_id'] for x in result['adjudications']}
                    result['labels'] = [x for x in result['labels']
                        if x['case_id'].startswith(owner_prefix) and
                        (x['actor_id'] == claims['sub'] or x['case_id'] in adjudicated or
                         claims['role'] == 'adjudicator')]
                    result['label_count'] = len(result['labels'])
                    result['adjudicated_count'] = len(result['adjudications'])
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            finally:
                book.close()
        store = TenantStore(output / 'platform.sqlite3', tenant_domains())
        services = MockServices(output / 'mock-services.sqlite3')
        try:
            if args.command == 'queue':
                scope = journal(store, claims['tenant_id'])
                rows = [row for row in scope.list() if claims['role'] == 'auditor' or
                        (task := scope.session.get('review_task', row['review_task_id'])) and
                        task['assignee_id'] == claims['sub'] and task['assignee_role'] == claims['role']]
                print(json.dumps(rows, ensure_ascii=False, indent=2))
            elif args.command == 'export-legacy':
                tenant = args.tenant or claims['tenant_id']
                exported = scoped_export(store, broker, token, tenant, tenant_domains()[tenant])
                path = output / 'exports' / tenant / 'legacy-stage7.json'
                write(path, exported)
                print(path)
            elif args.command == 'review':
                if not all((args.case, args.edited_action, args.reason)):
                    parser.error('review 需要 --case、--edited-action、--reason')
                print(json.dumps(review_case(store, broker, token, args.case,
                    args.edited_action, args.reason), ensure_ascii=False, indent=2))
            elif args.command == 'confirm':
                if not all((args.case, args.content)):
                    parser.error('confirm 需要 --case、--content')
                print(json.dumps(confirm_case(store, services, broker, token,
                    args.case, args.content), ensure_ascii=False, indent=2))
            elif args.command == 'close':
                if not all((args.case, args.outcome_id)):
                    parser.error('close 需要 --case、--outcome-id')
                outcome = next((x for x in read(VERTICAL / 'outcomes.json')['outcomes']
                    if x['outcome_id'] == args.outcome_id), None)
                if not outcome:
                    raise ValueError('结果 ID 不在合成来源清单')
                print(json.dumps(close_case(store, services, broker, token,
                    args.case, outcome), ensure_ascii=False, indent=2))
        finally:
            services.close()
            store.close()
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
