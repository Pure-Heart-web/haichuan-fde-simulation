#!/usr/bin/env python3
"""Stage 7 controlled-pilot simulation: trace, review, dashboard and incident replay."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from fde_platform.apps.pilot_review_web import serve
from fde_platform.core.knowledge.retrieval import KnowledgeIndex
from fde_platform.core.pilot.data_release import analyze_latency_incident, incident_report, validate_product_candidate
from fde_platform.core.pilot.metrics import dashboard, load_events, render_dashboard
from fde_platform.core.pilot.store import PilotStore
from fde_platform.domains.foreign_trade.context.provider import SimulatedContextProvider
from fde_platform.domains.foreign_trade.pilot.orchestration import review_tasks, simulate_case
from fde_platform.domains.foreign_trade.recommendation.service import load_components

DATA = ROOT / 'stages/07-pilot-operations/data'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def scenarios():
    return [json.loads(x) for x in (DATA / 'pilot-scenarios.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]


def load_config():
    config = read_json(DATA / 'pilot-config.json')
    if config['mode'] != 'simulation_only' or config['scope']['auto_send'] or config['scope']['auto_quote']:
        raise ValueError('Pilot 配置不得启用真实发送或自动报价')
    return config


def save_dashboard(output, store):
    config = load_config()
    events = load_events(DATA / 'pilot-events.jsonl')
    report = dashboard(events, read_json(DATA / 'baseline.json'), config['users'], store)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'pilot-dashboard.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'pilot-dashboard.md').write_text(render_dashboard(report), encoding='utf-8')
    print(f'合成 Pilot 仪表盘：{report["case_count"]} 条、{report["duration_business_days"]} 个工作日；{output / "pilot-dashboard.md"}')
    return report


def save_incident(output):
    mapping = ROOT / 'stages/05-product-recommendation/data/material-mapping.json'
    baseline = DATA / 'product-v12.json'
    bad = validate_product_candidate(mapping, baseline, DATA / 'product-v13-bad.json')
    fixed = validate_product_candidate(mapping, baseline, DATA / 'product-v13-fixed.json')
    incident = incident_report(bad, fixed)
    latency = analyze_latency_incident(read_json(DATA / 'latency-incident.json'))
    result = {'bad_release_gate': bad, 'fixed_release_gate': fixed,
              'product_incident': incident, 'latency_incident': latency}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'product-incident.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'product-incident.md').write_text(
        '# Stage 7 产品数据故障注入\n\n'
        f'坏版本 `{bad["candidate_version"]}`：`{bad["status"]}`；原因：{", ".join(bad["problems"])}。\n\n'
        f'修复候选 `{fixed["candidate_version"]}`：`{fixed["status"]}`，仍需模拟审批，未发布。\n\n'
        f'分类：`{incident["classification"]}`。止损：{incident["immediate_mitigation"]}。'
        f'长期修复：{incident["permanent_fix"]}。\n\n这是教学故障重放，不是生产事故。\n', encoding='utf-8')
    (output / 'latency-incident.md').write_text(
        '# Stage 7 延迟故障注入\n\n'
        f'合成 P95 从 {latency["p95_before_ms"]} ms 升至 {latency["p95_during_ms"]} ms；'
        f'主耗时是 `{latency["dominant_stage"]}`（{latency["dominant_stage_ms"]} ms）。'
        f'分类：`{latency["classification"]}`。短期处理：{latency["immediate_mitigation"]}。'
        '更换模型不是这次故障的直接修复。\n\n这不是实际生产事故。\n', encoding='utf-8')
    print(f'数据发布门：坏版本 {bad["status"]}，修复候选 {fixed["status"]}；没有执行发布。')
    return result


def run_demo(output):
    config = load_config()
    provider, index, products = SimulatedContextProvider(ROOT), KnowledgeIndex(ROOT), load_components(ROOT)
    output.mkdir(parents=True, exist_ok=True)
    store = PilotStore(output / 'pilot.sqlite3')
    try:
        new_traces = new_tasks = shadow = 0
        for case in scenarios():
            artifact, trace = simulate_case(case, root=ROOT, provider=provider, index=index, products=products)
            mode = trace['mode']
            folder = output / ('shadow-artifacts' if mode == 'shadow' else 'pilot-artifacts')
            folder.mkdir(exist_ok=True)
            (folder / (case['id'] + '.json')).write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            new_traces += store.save_trace(trace)
            shadow += int(mode == 'shadow')
            for task in review_tasks(case, artifact, trace):
                new_tasks += store.save_task(task)
        trace_count = len(store.list_traces())
        task_count = len(store.list_tasks(actor_id='admin', role='admin'))
        dashboard_report = save_dashboard(output, store)
    finally:
        store.close()
    incident = save_incident(output)
    status = {'status': 'TRAINING_REPLAY_READY', 'trace_count': trace_count, 'new_traces': new_traces,
              'visible_review_tasks': task_count, 'new_review_tasks': new_tasks,
              'shadow_case_count': shadow, 'synthetic_activity_events': dashboard_report['case_count'],
              'bad_data_release_status': incident['bad_release_gate']['status'],
              'actual_pilot_users': 0, 'real_pilot_release_gate': 'NOT_EVALUATED',
              'sent_messages': 0, 'published_product_versions': 0}
    (output / 'pilot-status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Trace {trace_count} 条、可见审核任务 {task_count} 条、隐藏 Shadow {shadow} 条；没有发送或发布。')
    return 0


def check_baseline(output):
    baseline = read_json(DATA / 'regression-baseline.json')
    status = read_json(output / 'pilot-status.json')
    report = read_json(output / 'pilot-dashboard.json')
    incident = read_json(output / 'product-incident.json')
    for key, value in baseline['status_expected'].items():
        if status.get(key) != value:
            print(f'Stage 7 合成回归失败：{key}={status.get(key)}，预期 {value}', file=sys.stderr)
            return 4
    for key, value in baseline['dashboard_expected'].items():
        if report.get(key) != value:
            print(f'Stage 7 合成回归失败：{key}', file=sys.stderr)
            return 4
    if incident['bad_release_gate']['status'] != 'BLOCKED' or incident['fixed_release_gate']['status'] != 'READY_FOR_SIMULATED_APPROVAL':
        print('Stage 7 合成回归失败：产品数据发布门', file=sys.stderr)
        return 4
    store = PilotStore(output / 'pilot.sqlite3')
    try:
        if any(x['case_id'] in baseline['shadow_case_ids'] for x in store.list_tasks(actor_id='admin', role='admin')):
            print('Stage 7 合成回归失败：Shadow 进入可见审核队列', file=sys.stderr)
            return 4
    finally:
        store.close()
    return 0


def main():
    parser = argparse.ArgumentParser(description='海川 Stage 7 离线 Pilot 运营模拟')
    parser.add_argument('command', choices=['demo', 'dashboard', 'review', 'trace', 'incident', 'eval'])
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-07')
    parser.add_argument('--case', help='trace 命令的案例 ID')
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--check-baseline', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        if args.command == 'demo':
            return run_demo(output)
        if args.command == 'review':
            serve(output / 'pilot.sqlite3', load_config()['users'], args.port)
            return 0
        if args.command == 'incident':
            save_incident(output)
            return 0
        if args.command == 'eval':
            if not (output / 'pilot-status.json').exists():
                run_demo(output)
            if args.check_baseline:
                code = check_baseline(output)
                if not code:
                    print('Stage 7 合成回归通过；真实 Pilot Gate 未评估。')
                return code
            print('Stage 7 教学产物已存在；使用 --check-baseline 验证回归。')
            return 0
        store = PilotStore(output / 'pilot.sqlite3')
        try:
            if args.command == 'dashboard':
                save_dashboard(output, store)
                return 0
            if not args.case:
                parser.error('trace 必须提供 --case')
            trace = store.get_trace(args.case)
            if trace is None:
                raise ValueError('Trace 不存在；先运行 demo')
            print(json.dumps(trace, ensure_ascii=False, indent=2))
            return 0
        finally:
            store.close()
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
