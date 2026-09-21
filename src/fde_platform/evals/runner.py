"""Offline field-level eval on labeled synthetic examples."""
import json
import math
import statistics
import time
from dataclasses import replace
from pathlib import Path

from ..core.ingestion import from_text, html_to_text
from ..pipeline import process

CRITICAL_FIELDS = ('product_type', 'quantity', 'flow_m3h', 'head_m', 'medium_category',
                   'temperature_c', 'voltage_v', 'frequency_hz', 'destination_port')


def equal(a, b):
    if isinstance(a, (int, float)) and not isinstance(a, bool) and isinstance(b, (int, float)) and not isinstance(b, bool):
        return math.isclose(a, b, rel_tol=0, abs_tol=.03)
    return a == b


def percentile(values, p):
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)


def evaluate(dataset_path, provider=None):
    lines = Path(dataset_path).read_text(encoding='utf-8').splitlines()
    cases = [json.loads(line) for line in lines if line.strip()]
    if not cases:
        raise ValueError('评估集为空')
    per_field = {field: {'correct': 0, 'total': 0, 'present_correct': 0, 'present_total': 0,
                         'absent_correct': 0, 'absent_total': 0} for field in CRITICAL_FIELDS}
    failures, latencies = [], []
    parse_failures = 0
    attachment_cases = 0
    evidence_present = evidence_total = 0
    for case in cases:
        if case.get('mode') != 'simulation' or set(case.get('expected', {})) != set(CRITICAL_FIELDS):
            raise ValueError(f'{case.get("id")} 标签或模式无效')
        body = html_to_text(case['body']) if case.get('format') == 'html' else case['body']
        work = from_text(body, source_id=case['id'])
        if case.get('attachments'):
            work = replace(work, attachments=case['attachments'])
            attachment_cases += 1
        started = time.perf_counter()
        result, record = process(work, provider)
        latencies.append((time.perf_counter() - started) * 1000)
        if result.status == 'failed':
            parse_failures += 1
        actual = record.to_dict() if record else {}
        for field in CRITICAL_FIELDS:
            if actual.get(field) is not None:
                evidence_total += 1
                evidence_key = 'medium_description' if field == 'medium_category' else field
                if evidence_key in actual.get('evidence', {}):
                    evidence_present += 1
        for field in CRITICAL_FIELDS:
            expected, predicted = case['expected'][field], actual.get(field)
            stats = per_field[field]
            stats['total'] += 1
            bucket = 'absent' if expected is None else 'present'
            stats[bucket + '_total'] += 1
            if equal(predicted, expected):
                stats['correct'] += 1
                stats[bucket + '_correct'] += 1
            else:
                taxonomy = ('schema_or_parse' if result.status == 'failed' else
                            'normalization_or_unit_parsing' if case['group'] == 'unit_conversion' else
                            'unsupported_attachment' if case.get('attachments') else
                            'semantic_or_coverage')
                failures.append({'id': case['id'], 'group': case['group'], 'field': field,
                                 'expected': expected, 'actual': predicted, 'taxonomy': taxonomy})
        if case.get('expected_missing'):
            missing = set(actual.get('missing_fields', []))
            if not set(case['expected_missing']) <= missing:
                failures.append({'id': case['id'], 'group': case['group'], 'field': 'missing_fields',
                                 'expected': case['expected_missing'], 'actual': sorted(missing),
                                 'taxonomy': 'attachment_or_missing_policy'})
    total = sum(x['total'] for x in per_field.values())
    correct = sum(x['correct'] for x in per_field.values())
    present_total = sum(x['present_total'] for x in per_field.values())
    present_correct = sum(x['present_correct'] for x in per_field.values())
    absent_total = sum(x['absent_total'] for x in per_field.values())
    absent_correct = sum(x['absent_correct'] for x in per_field.values())
    return {
        'dataset': str(dataset_path), 'mode': 'simulation',
        'engine': getattr(provider, 'model_version', 'regex-baseline-v2'),
        'case_count': len(cases), 'field_count': total,
        'critical_field_accuracy': correct / total,
        'present_field_accuracy': present_correct / present_total if present_total else None,
        'absent_field_accuracy': absent_correct / absent_total if absent_total else None,
        'parse_failure_rate': parse_failures / len(cases),
        'attachment_cases': attachment_cases, 'attachment_content_processed': False,
        'evidence_coverage_rate': evidence_present / evidence_total if evidence_total else None,
        'p95_latency_ms_local': percentile(latencies, .95),
        'median_latency_ms_local': statistics.median(latencies),
        'cost_per_inquiry_usd': (getattr(provider, 'total_cost_usd', None) / len(cases)
                                 if provider is not None and getattr(provider, 'total_cost_usd', None) is not None
                                 else 0.0 if provider is None else None),
        'per_field': {key: {**stats,
                            'accuracy': stats['correct'] / stats['total'],
                            'present_accuracy': stats['present_correct'] / stats['present_total'] if stats['present_total'] else None,
                            'absent_accuracy': stats['absent_correct'] / stats['absent_total'] if stats['absent_total'] else None}
                      for key, stats in per_field.items()},
        'failures': failures,
        'failure_counts': {category: sum(x['taxonomy'] == category for x in failures)
                           for category in sorted({x['taxonomy'] for x in failures})},
        'offline_thresholds': {'each_critical_field_accuracy_min': .95, 'parse_failure_rate_max_exclusive': .02},
        'offline_thresholds_met': all(x['correct'] / x['total'] >= .95 for x in per_field.values()) and parse_failures / len(cases) < .02,
        'release_status': 'NOT_EVALUATED_ON_REAL_DATA',
    }


def render_report(report):
    rows = ['| 字段 | 正确/总数 | 准确率 | 非空准确率 | 空值准确率 |', '|---|---:|---:|---:|---:|']
    def percent(value):
        return 'n/a' if value is None else f'{value:.1%}'
    for field, stats in report['per_field'].items():
        rows.append(f'| {field} | {stats["correct"]}/{stats["total"]} | {percent(stats["accuracy"])} | {percent(stats["present_accuracy"])} | {percent(stats["absent_accuracy"])} |')
    head = ['# Sprint 1 离线评估 · 合成样本', '',
            f'引擎：`{report["engine"]}`；案例数：{report["case_count"]}；关键字段比较数：{report["field_count"]}。', '',
            f'字段微平均准确率：**{percent(report["critical_field_accuracy"])}**；非空字段：{percent(report["present_field_accuracy"])}；空值字段：{percent(report["absent_field_accuracy"])}。',
            f'解析失败率：{percent(report["parse_failure_rate"])}；本机 P95 处理耗时：{report["p95_latency_ms_local"]:.2f} ms；单案外部模型费用：{report["cost_per_inquiry_usd"] if report["cost_per_inquiry_usd"] is not None else "未提供"} USD。', '',
            '本报告不包含真实销售样本、人工复核时间或 LLM 性能。模板生成的合成集可用于回归练习，不能据此判定 Pilot Release Gate。', '',
            '## 字段结果', '']
    tail = ['', '## 错误分类', ''] + [f'- {k}: {v}' for k, v in report['failure_counts'].items()]
    tail += ['', '## 前 20 个差异', '', '| 案例 | 组别 | 字段 | 期望 | 实际 | 分类 |', '|---|---|---|---|---|---|']
    for item in report['failures'][:20]:
        tail.append('| ' + ' | '.join(str(item[k]).replace('|', '\\|') for k in ('id', 'group', 'field', 'expected', 'actual', 'taxonomy')) + ' |')
    tail += ['', '## 释放条件', '', f'合成离线阈值（每个关键字段 ≥95%，解析失败 <2%）：{"满足" if report["offline_thresholds_met"] else "未满足"}；真实数据 Release Gate：**未评估**。']
    return '\n'.join(head + rows + tail) + '\n'
