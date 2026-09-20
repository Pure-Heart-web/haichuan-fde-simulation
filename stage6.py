#!/usr/bin/env python3
"""Stage 6 offline customer context, evidence-backed reply and human review."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from fde_platform.apps.draft_review_web import serve
from fde_platform.core.knowledge.retrieval import KnowledgeIndex
from fde_platform.domains.foreign_trade.context.provider import SimulatedContextProvider
from fde_platform.domains.foreign_trade.recommendation.service import load_components
from fde_platform.domains.foreign_trade.reply.eval import evaluate_context, evaluate_generation, evaluate_knowledge, render_report
from fde_platform.domains.foreign_trade.reply.store import DraftStore
from fde_platform.domains.foreign_trade.reply.workflow import run_case

DATA = ROOT / 'stages/06-context-knowledge-reply/data'


def components():
    return SimulatedContextProvider(ROOT), KnowledgeIndex(ROOT), load_components(ROOT)


def scenarios():
    return [json.loads(x) for x in (DATA / 'scenarios.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]


def save_eval(output, provider, index, products):
    db = output / 'drafts.sqlite3'
    store = DraftStore(db) if db.exists() else None
    try:
        report = {
            'mode': 'synthetic_training_only', 'real_data_release_gate': 'NOT_EVALUATED',
            'context': evaluate_context(DATA / 'context-eval.jsonl', provider),
            'knowledge': evaluate_knowledge(DATA / 'knowledge-eval.jsonl', index),
            'generation': evaluate_generation(DATA / 'scenarios.jsonl', DATA / 'generation-eval-labels.jsonl',
                root=ROOT, provider=provider, index=index, products=products, review_store=store),
        }
    finally:
        if store:
            store.close()
    output.mkdir(parents=True, exist_ok=True)
    (output / 'stage6-eval.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'stage6-eval.md').write_text(render_report(report), encoding='utf-8')
    print(f'Stage 6 合成评估：Context {report["context"]["case_count"]}、Knowledge {report["knowledge"]["case_count"]}、Reply {report["generation"]["case_count"]}；{output / "stage6-eval.md"}')
    return report


def check_baseline(report):
    baseline = json.loads((DATA / 'regression-baseline.json').read_text(encoding='utf-8'))
    if baseline['mode'] != 'synthetic_regression_only':
        raise ValueError('Stage 6 基线模式无效')
    for section, count in baseline['case_counts'].items():
        if report[section]['case_count'] != count:
            print(f'合成回归失败：{section} 案例数变化', file=sys.stderr)
            return 4
    for direction in ('minimums', 'maximums'):
        for key, bound in baseline[direction].items():
            section, metric = key.split('.', 1)
            actual = report[section].get(metric)
            if actual is None or (direction == 'minimums' and actual < bound) or (
                    direction == 'maximums' and actual > bound):
                print(f'合成回归失败：{key}={actual}，{direction} 要求 {bound}', file=sys.stderr)
                return 4
    return 0


def run_demo(output):
    provider, index, products = components()
    output.mkdir(parents=True, exist_ok=True)
    folder = output / 'drafts'
    folder.mkdir(exist_ok=True)
    store = DraftStore(output / 'drafts.sqlite3')
    try:
        created, stale = 0, []
        for case in scenarios():
            artifact = run_case(case, root=ROOT, context_provider=provider,
                                knowledge_index=index, product_components=products)
            (folder / (case['id'] + '.json')).write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            existing = store.get(case['id'])
            if existing is not None and existing['artifact'] != artifact:
                stale.append(case['id'])
            created += store.save(artifact)
        queued = len(store.list_items())
        gaps = len(store.gaps())
    finally:
        store.close()
    report = save_eval(output, provider, index, products)
    status = {'status': 'TRAINING_DEMO_ONLY', 'draft_queue_count': queued, 'new_drafts': created,
              'stale_queue_case_ids': stale,
              'knowledge_gap_count': gaps, 'synthetic_context_cases': report['context']['case_count'],
              'synthetic_knowledge_cases': report['knowledge']['case_count'],
              'synthetic_reply_cases': report['generation']['case_count'],
              'real_customer_cases': 0, 'real_data_release_gate': 'NOT_EVALUATED',
              'sent_messages': 0}
    (output / 'sprint-status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'草稿队列 {queued} 条，本次新增 {created} 条；知识缺口 {gaps} 条。没有发送邮件。')
    if stale:
        print(f'已有队列中的 {len(stale)} 条草稿版本与当前代码不同，原审核记录未覆盖；可用 --output 指定新目录复现。')
    return 0


def main():
    parser = argparse.ArgumentParser(description='海川 Stage 6 客户上下文、知识和证据化回复教学切片')
    parser.add_argument('command', choices=['demo', 'eval', 'draft', 'review'])
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-06')
    parser.add_argument('--case', help='从 scenarios.jsonl 选择案例 ID')
    parser.add_argument('--input', type=Path, help='单条场景 JSON（id、sender、text 必填）')
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--check-baseline', action='store_true', help='对冻结的合成数据执行回归门槛')
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        if args.command == 'review':
            serve(output / 'drafts.sqlite3', args.port)
            return 0
        if args.command == 'demo':
            return run_demo(output)
        provider, index, products = components()
        if args.command == 'eval':
            report = save_eval(output, provider, index, products)
            return check_baseline(report) if args.check_baseline else 0
        if bool(args.case) == bool(args.input):
            parser.error('draft 必须二选一提供 --case 或 --input')
        if args.case:
            case = next((x for x in scenarios() if x['id'] == args.case), None)
            if case is None:
                raise ValueError('案例 ID 不存在')
        else:
            case = json.loads(args.input.read_text(encoding='utf-8'))
        artifact = run_case(case, root=ROOT, context_provider=provider,
                            knowledge_index=index, product_components=products)
        print(json.dumps(artifact, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
