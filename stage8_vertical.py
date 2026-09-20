#!/usr/bin/env python3
"""Two-domain, mock-integrated FDE vertical delivery exercise."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from stage8 import seed, tenant_domains
from fde_platform.core.platform.effort import EffortLog
from fde_platform.core.platform.episode import EpisodeJournal
from fde_platform.core.platform.tenant_store import TenantStore
from fde_platform.domains.after_sales.workflow import process_service_case
from fde_platform.domains.foreign_trade.platform.adapter import bridge_haichuan
from fde_platform.integrations.mock_inbound import adapt_event, create_case_record

DATA = ROOT / 'stages/08-productization/vertical'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def inbound_events():
    return [json.loads(line) for line in (DATA / 'inbound-events.jsonl').read_text(encoding='utf-8').splitlines()
            if line.strip()]


def _journal(store, tenant_id):
    domains = tenant_domains()
    return EpisodeJournal(store.scope(tenant_id, domains[tenant_id]))


def _episode_for_case(journal, case_id):
    found = [row for row in journal.list() if row['case_id'] == case_id]
    if len(found) != 1:
        raise ValueError('当前租户下案例流程不存在或不唯一')
    return found[0]


def prepare(store, output):
    seed(store)
    first_seen, duplicate_in_fixture, newly_received = set(), 0, 0
    for event in inbound_events():
        case = adapt_event(event)
        key = (event['tenant_id'], event['domain'], event['source_type'], event['source_id'])
        if key in first_seen:
            duplicate_in_fixture += 1
        first_seen.add(key)
        journal = _journal(store, event['tenant_id'])
        episode, created = journal.receive(event)
        newly_received += int(created)
        if episode['state'] == 'received':
            case_record = create_case_record(event)
            journal.session.put('case_record', case_record.case_record_id, case_record.to_dict())
            journal.case_created(episode['episode_id'], case_record.case_record_id)
            episode = journal.get(episode['episode_id'])
        if episode['state'] != 'case_open':
            continue
        if event['domain'] == 'after_sales':
            artifact = process_service_case(case, journal.session)
        else:
            artifact = bridge_haichuan(case, journal.session, ROOT)
        journal.proposal_ready(episode['episode_id'], artifact['work_item']['id'],
                               artifact['trace']['trace_id'], artifact['review_task']['task_id'])
        folder = output / 'artifacts' / event['tenant_id']
        folder.mkdir(parents=True, exist_ok=True)
        (folder / (event['case_id'] + '.json')).write_text(
            json.dumps(artifact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'newly_received': newly_received, 'duplicate_events_in_fixture': duplicate_in_fixture}


def scripted_review_and_outcome(store):
    reviews = read_json(DATA / 'scripted-reviews.json')
    outcomes = read_json(DATA / 'outcomes.json')
    if reviews['mode'] != 'synthetic_role_play' or outcomes['mode'] != 'synthetic_outcomes_only':
        raise ValueError('只允许教学角色扮演记录')
    for item in reviews['reviews']:
        journal = _journal(store, item['tenant_id'])
        episode = _episode_for_case(journal, item['case_id'])
        if episode['state'] == 'pending_review':
            journal.record_edit(episode['episode_id'], actor_id=item['actor_id'],
                                actor_role=item['actor_role'], edited_action=item['edited_action'],
                                reason=item['reason'])
    for item in outcomes['outcomes']:
        journal = _journal(store, item['tenant_id'])
        episode = _episode_for_case(journal, item['case_id'])
        if episode['state'] == 'reviewed':
            journal.close(episode['episode_id'], item)


def report(store, output, *, duplicate_events_in_fixture=None):
    episodes = []
    for tenant_id in ('qihang-training', 'haichuan-training'):
        journal = _journal(store, tenant_id)
        for row in journal.list():
            trace = journal.session.get('trace', row['trace_id']) if row['trace_id'] else None
            recommendation = journal.session.get('recommendation', row['case_id'])
            events = journal.events(row['episode_id'])
            episodes.append({'tenant_id': tenant_id, 'domain': row['domain'],
                             'episode_id': row['episode_id'], 'case_id': row['case_id'],
                             'source_type': row['source_type'], 'source_id': row['source_id'],
                             'state': row['state'], 'work_item_id': row['work_item_id'],
                             'case_record_id': row['case_record_id'],
                             'trace_id': row['trace_id'], 'review_task_id': row['review_task_id'],
                             'outcome_id': row['outcome_id'],
                             'top_option': recommendation['options'][0]['code'] if recommendation else None,
                             'evidence_refs': recommendation['evidence_refs'] if recommendation else [],
                             'trace_versions': trace.get('versions', {}) if trace else {},
                             'events': events})
    episodes.sort(key=lambda x: x['case_id'])
    effort = EffortLog(output / 'delivery-effort.jsonl').summary()
    all_event_types = [[e['event_type'] for e in item['events']] for item in episodes]
    expected_sequence = ['inbound_received', 'case_created', 'proposal_ready',
                         'human_edited', 'outcome_recorded']
    result = {'mode': 'synthetic_vertical_replay', 'episodes': episodes,
              'shared_event_sequence': all(seq == expected_sequence for seq in all_event_types),
              'episode_count': len(episodes), 'closed_count': sum(x['state'] == 'closed' for x in episodes),
              'duplicate_events_in_fixture': duplicate_events_in_fixture if duplicate_events_in_fixture is not None
                    else len(inbound_events()) - len({(x['tenant_id'], x['source_type'], x['source_id'])
                                                       for x in inbound_events()}),
              'customer_messages_sent': 0, 'dispatches_created': 0,
              'actual_customer_cases': 0, 'human_effort': effort,
              'delivery_time_savings_proven': False,
              'real_pilot_gate': 'NOT_EVALUATED'}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'episode-report.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    rows = ['| 租户 / 案例 | 来源 → 工单/询盘 → 工作项 → Trace → 审核 → 结果 | 状态 | 证据 |',
            '|---|---|---|---|']
    for item in episodes:
        chain = ' → '.join(str(item[key] or '待完成') for key in
                           ('source_id', 'case_record_id', 'work_item_id', 'trace_id',
                            'review_task_id', 'outcome_id'))
        rows.append(f'| {item["tenant_id"]} / {item["case_id"]} | {chain} | {item["state"]} | '
                    f'{", ".join(item["evidence_refs"])} |')
    md = ('# Stage 8 纵向交付演练\n\n两条案例经相同的 `inbound_received → case_created → proposal_ready → '
          'human_edited → outcome_recorded` 事件契约。所有事件、人员和结果均为**合成角色扮演**；'
          '没有客户消息、自动派工或真实 Pilot。\n\n' + '\n'.join(rows) + '\n\n'
          f'重复输入：{result["duplicate_events_in_fixture"]} 条；完整闭环：{result["closed_count"]}/'
          f'{result["episode_count"]}。\n\n真实人工交付工时：`{effort["comparison_status"]}`。'
          '脚本重放耗时不能代表 FDE 交付时间；使用 effort-start/effort-stop 为两个 Domain '
          '分别记录 Discovery、集成、规则、审核与评估工作。\n\n'
          '仍缺真实系统接入、来源授权、正式身份权限和独立结果核实；详见本阶段演练手册。\n')
    (output / 'episode-report.md').write_text(md, encoding='utf-8')
    return result


def run_demo(output):
    store = TenantStore(output / 'platform.sqlite3', tenant_domains())
    try:
        stats = prepare(store, output)
        scripted_review_and_outcome(store)
        result = report(store, output, duplicate_events_in_fixture=stats['duplicate_events_in_fixture'])
    finally:
        store.close()
    print(f'纵向演练：闭环 {result["closed_count"]}/{result["episode_count"]}；'
          f'重复输入 {result["duplicate_events_in_fixture"]}；'
          f'人工工时 {result["human_effort"]["comparison_status"]}。')
    return 0


def check_baseline(output):
    result = read_json(output / 'episode-report.json')
    expected = read_json(DATA / 'regression-baseline.json')
    for key, value in expected['report'].items():
        if result.get(key) != value:
            raise ValueError(f'纵向演练回归失败：{key}')
    by_case = {x['case_id']: x for x in result['episodes']}
    for case_id, expected_fields in expected['episodes'].items():
        actual = by_case.get(case_id)
        if not actual or any(actual.get(key) != value for key, value in expected_fields.items()):
            raise ValueError(f'纵向演练回归失败：{case_id}')
    print('Stage 8 纵向案例合成回归通过；人工交付时间和真实 Pilot 效果未证明。')
    return 0


def main():
    parser = argparse.ArgumentParser(description='启航/海川两条纵向 FDE 案例')
    parser.add_argument('command', choices=('demo', 'prepare', 'queue', 'review', 'close',
                                             'report', 'eval', 'effort-start', 'effort-stop'))
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-08-vertical')
    parser.add_argument('--tenant', choices=('qihang-training', 'haichuan-training'))
    parser.add_argument('--case')
    parser.add_argument('--actor-id')
    parser.add_argument('--actor-role')
    parser.add_argument('--edited-action')
    parser.add_argument('--reason')
    parser.add_argument('--outcome-id')
    parser.add_argument('--domain', choices=('after_sales', 'foreign_trade'))
    parser.add_argument('--phase', choices=('discovery', 'integration', 'domain_rules', 'review_workflow', 'evaluation'))
    parser.add_argument('--actor')
    parser.add_argument('--activity')
    parser.add_argument('--activity-id')
    parser.add_argument('--check-baseline', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        if args.command == 'demo':
            code = run_demo(output)
            if code or not args.check_baseline:
                return code
            return check_baseline(output)
        if args.command == 'effort-start':
            item = EffortLog(output / 'delivery-effort.jsonl').start(
                domain=args.domain, phase=args.phase, actor=args.actor or '', activity=args.activity or '')
            print(json.dumps(item, ensure_ascii=False, indent=2))
            return 0
        if args.command == 'effort-stop':
            item = EffortLog(output / 'delivery-effort.jsonl').stop(args.activity_id)
            print(json.dumps(item, ensure_ascii=False, indent=2))
            return 0
        store = TenantStore(output / 'platform.sqlite3', tenant_domains())
        try:
            if args.command == 'prepare':
                stats = prepare(store, output)
                result = report(store, output, duplicate_events_in_fixture=stats['duplicate_events_in_fixture'])
                print(f'待审核 {result["episode_count"] - result["closed_count"]} 条；{output / "episode-report.md"}')
                return 0
            if args.command == 'queue':
                if not args.tenant:
                    parser.error('queue 需要 --tenant')
                journal = _journal(store, args.tenant)
                print(json.dumps(journal.list(), ensure_ascii=False, indent=2))
                return 0
            if args.command == 'review':
                if not all((args.tenant, args.case, args.actor_id, args.actor_role,
                            args.edited_action, args.reason)):
                    parser.error('review 需要租户、案例、人员/角色、修改内容和原因')
                journal = _journal(store, args.tenant)
                episode = _episode_for_case(journal, args.case)
                feedback = journal.record_edit(episode['episode_id'], actor_id=args.actor_id,
                    actor_role=args.actor_role, edited_action=args.edited_action, reason=args.reason)
                report(store, output)
                print(json.dumps(feedback.to_dict(), ensure_ascii=False, indent=2))
                return 0
            if args.command == 'close':
                if not all((args.tenant, args.case, args.outcome_id)):
                    parser.error('close 需要 --tenant、--case、--outcome-id')
                outcomes = read_json(DATA / 'outcomes.json')['outcomes']
                item = next((x for x in outcomes if x['outcome_id'] == args.outcome_id), None)
                if item is None:
                    raise ValueError('未知合成结果来源')
                journal = _journal(store, args.tenant)
                episode = _episode_for_case(journal, args.case)
                closed = journal.close(episode['episode_id'], item)
                report(store, output)
                print(json.dumps(closed, ensure_ascii=False, indent=2))
                return 0
            if args.command == 'report':
                result = report(store, output)
                print(f'{result["closed_count"]}/{result["episode_count"]} 条闭环；{output / "episode-report.md"}')
                return 0
            if args.command == 'eval':
                if not (output / 'episode-report.json').exists():
                    run_demo(output)
                return check_baseline(output) if args.check_baseline else 0
        finally:
            store.close()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
