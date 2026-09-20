#!/usr/bin/env python3
"""Stage 5 offline recommendation, evaluation, and local human review."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from fde_platform.apps.recommendation_web import serve
from fde_platform.core.store import Store
from fde_platform.domains.foreign_trade.recommendation.eval import evaluate_dataset, render_report
from fde_platform.domains.foreign_trade.recommendation.service import load_components, recommend
from fde_platform.domains.foreign_trade.recommendation.store import RecommendationStore
from fde_platform.domains.foreign_trade.schema import InquiryRecord

DATA = ROOT / 'stages/05-product-recommendation/data/matching-golden-draft.jsonl'


def save_eval(output, catalog, registry, preferences):
    report = evaluate_dataset(DATA, catalog, registry, preferences)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'matching-eval.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'matching-eval.md').write_text(render_report(report), encoding='utf-8')
    print(f'合成匹配评估：{report["case_count"]} 条；详见 {output / "matching-eval.md"}')
    return report


def run_demo(output):
    catalog, registry, preferences = load_components(ROOT)
    output.mkdir(parents=True, exist_ok=True)
    store = RecommendationStore(output / 'recommendations.sqlite3')
    try:
        created = 0
        for line in DATA.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            case = json.loads(line)
            inquiry = InquiryRecord(**{'work_item_id': case['id'], **case['inquiry']})
            created += store.save(inquiry, recommend(inquiry, catalog, registry, preferences), 'synthetic_golden_draft')
        count = len(store.list_items())
    finally:
        store.close()
    report = save_eval(output, catalog, registry, preferences)
    status = {'status': 'TRAINING_DEMO_ONLY', 'review_queue_count': count, 'new_items': created,
              'synthetic_eval_cases': report['case_count'], 'real_historical_cases': 0,
              'actual_performance_curves_available': False, 'real_data_release_gate': 'NOT_EVALUATED'}
    (output / 'sprint-status.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Stage 5 队列 {count} 条，本次新增 {created} 条；真实数据 Release Gate 未评估。')
    return 0


def import_stage4(output, stage4_db):
    catalog, registry, preferences = load_components(ROOT)
    old = Store(stage4_db)
    new = RecommendationStore(output / 'recommendations.sqlite3')
    created = skipped = 0
    try:
        for row in old.list_items():
            events = old.reviews(row['id'])
            if not events or events[-1]['action'] == 'reject':
                skipped += 1
                continue
            latest = events[-1]
            record = latest['corrected_record'] if latest['action'] == 'edit' else latest['model_record']
            if record is None:
                skipped += 1
                continue
            inquiry = InquiryRecord(**record)
            created += new.save(inquiry, recommend(inquiry, catalog, registry, preferences), 'stage4_human_review')
    finally:
        old.close()
        new.close()
    print(f'导入已审核 Stage 4 记录 {created} 条；跳过未审核/拒绝 {skipped} 条。')
    return 0


def main():
    parser = argparse.ArgumentParser(description='海川 Stage 5 产品候选教学切片')
    parser.add_argument('command', choices=['demo', 'eval', 'recommend', 'from-stage4', 'review'])
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-05')
    parser.add_argument('--inquiry', type=Path, help='InquiryRecord JSON 文件')
    parser.add_argument('--stage4-db', type=Path, default=ROOT / 'outputs/stage-04/review.sqlite3')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        if args.command == 'demo':
            return run_demo(output)
        if args.command == 'review':
            serve(output / 'recommendations.sqlite3', args.port)
            return 0
        if args.command == 'from-stage4':
            if not args.stage4_db.exists():
                raise ValueError('Stage 4 审核数据库不存在；先运行 Stage 4 并完成人工审核')
            return import_stage4(output, args.stage4_db)
        catalog, registry, preferences = load_components(ROOT)
        if args.command == 'eval':
            save_eval(output, catalog, registry, preferences)
            return 0
        if args.inquiry is None:
            parser.error('recommend 必须提供 --inquiry JSON 文件')
        inquiry = InquiryRecord(**json.loads(args.inquiry.read_text(encoding='utf-8')))
        print(json.dumps(recommend(inquiry, catalog, registry, preferences).to_dict(), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
