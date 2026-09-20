#!/usr/bin/env python3
"""Run the Sprint 1 demo, eval, single-item ingestion, or local review UI."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from fde_platform.apps.review_web import serve
from fde_platform.core.ingestion import from_eml, from_text
from fde_platform.core.observability import log_extraction
from fde_platform.core.store import Store
from fde_platform.evals.runner import evaluate, render_report
from fde_platform.pipeline import process

DATA = ROOT / 'stages/04-build-sprint-1/data/inquiry_eval_v0.jsonl'
STAGE3 = ROOT / 'stages/03-data-boundary/data'


def save_eval(output, *, check_baseline=False):
    output.mkdir(parents=True, exist_ok=True)
    report = evaluate(DATA)
    (output / 'eval-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'eval-report.md').write_text(render_report(report), encoding='utf-8')
    print(f'合成评估：{report["case_count"]} 条，字段微平均 {report["critical_field_accuracy"]:.1%}；报告 {output / "eval-report.md"}')
    if check_baseline:
        baseline = json.loads((ROOT / 'stages/04-build-sprint-1/data/regression-baseline.json').read_text(encoding='utf-8'))
        if baseline['engine'] != report['engine'] or baseline['dataset_id'] != 'stage4-100-synthetic-v0':
            print('回归基线与当前评估配置不一致', file=sys.stderr)
            return 4
        if report['critical_field_accuracy'] < baseline['critical_field_accuracy'] - baseline['allowed_drop']:
            print('回归检查失败：关键字段准确率低于允许范围', file=sys.stderr)
            return 4
        for field, original in baseline['per_field_accuracy'].items():
            if report['per_field'][field]['accuracy'] < original - baseline['allowed_drop']:
                print(f'回归检查失败：{field} 准确率低于允许范围', file=sys.stderr)
                return 4
        if report['parse_failure_rate'] > baseline['parse_failure_rate']:
            print('回归检查失败：解析失败率升高', file=sys.stderr)
            return 4
    return 0


def save_work(work, output, store):
    if store.get_item(work.id) is not None:
        return False
    result, record = process(work)
    store.save_extraction(work, result, record)
    log_extraction(output / 'telemetry.jsonl', work, result, record)
    return True


def run_demo(output, *, check_baseline=False):
    output.mkdir(parents=True, exist_ok=True)
    store = Store(output / 'review.sqlite3')
    try:
        golden = json.loads((STAGE3 / 'golden.json').read_text(encoding='utf-8'))
        created = 0
        for case in golden['cases']:
            work = from_eml(STAGE3 / case['inquiry_path'], source_id=case['id'])
            created += save_work(work, output, store)
        queued = len(store.list_items())
    finally:
        store.close()
    print(f'审核队列已有 {queued} 条合成询盘，本次新增 {created} 条。')
    eval_code = save_eval(output, check_baseline=check_baseline)
    report = json.loads((output / 'eval-report.json').read_text(encoding='utf-8'))
    status = 'DEMO_READY_NEEDS_EXTRACTION_WORK' if not report['offline_thresholds_met'] else 'DEMO_READY_FOR_REAL_DATA_REVIEW'
    audit = {'status': status, 'review_queue_count': queued, 'synthetic_eval_cases': report['case_count'],
             'offline_thresholds_met': report['offline_thresholds_met'],
             'real_data_release_gate': 'NOT_EVALUATED',
             'unmet_fields': [field for field, item in report['per_field'].items() if item['accuracy'] < .95]}
    (output / 'sprint-status.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (output / 'sprint-status.md').write_text('# Sprint 1 教学状态\n\n' +
        f'状态：`{status}`。已入队 {queued} 条 Stage 3 合成邮件，合成评估 {report["case_count"]} 条。\n\n' +
        f'未达每字段 95% 的字段：{", ".join(audit["unmet_fields"]) or "无"}。真实数据 Release Gate 未评估。\n', encoding='utf-8')
    print(f'Sprint 1 状态：{status}')
    return eval_code


def main():
    parser = argparse.ArgumentParser(description='海川 Sprint 1 本地教学切片')
    parser.add_argument('command', choices=['demo', 'eval', 'review', 'process'])
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-04')
    parser.add_argument('--eml', type=Path)
    parser.add_argument('--text')
    parser.add_argument('--source-id', default='manual')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--check-baseline', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        if args.command == 'eval':
            return save_eval(output, check_baseline=args.check_baseline)
        if args.command == 'review':
            serve(output / 'review.sqlite3', port=args.port)
            return 0
        if args.command == 'demo':
            return run_demo(output, check_baseline=args.check_baseline)
        store = Store(output / 'review.sqlite3')
        try:
            if bool(args.eml) == (args.text is not None):
                parser.error('process 必须二选一提供 --eml 或 --text')
            work = from_eml(args.eml, source_id=args.source_id) if args.eml else from_text(args.text, source_id=args.source_id)
            created = save_work(work, output, store)
            print(f'{"已入队" if created else "已存在"}：{work.id}；打开 python3 stage4.py review 进行人工审核。')
            return 0
        finally:
            store.close()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
