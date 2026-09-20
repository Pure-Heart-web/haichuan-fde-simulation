"""Synthetic matching evaluation with explicit denominators and failure rows."""
import json
from pathlib import Path

from fde_platform.domains.foreign_trade.schema import InquiryRecord

from .service import recommend


def evaluate_dataset(path, catalog, registry, preferences):
    cases = [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]
    ids = [case['id'] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError('评估集含重复案例 ID')
    rows = []
    for case in cases:
        inquiry = InquiryRecord(**{'work_item_id': case['id'], **case['inquiry']})
        result = recommend(inquiry, catalog, registry, preferences)
        expected = set(case['acceptable_skus'])
        top5 = set(result.candidate_skus[:5])
        top3 = set(result.candidate_skus[:3])
        forbidden = set(case['forbidden_skus'])
        violations = sorted(forbidden.intersection(result.candidate_skus))
        rows.append({'id': case['id'], 'scenario': case['scenario'],
                     'acceptable_skus': sorted(expected), 'top5': list(result.candidate_skus[:5]),
                     'recall_at_5': len(expected & top5) / len(expected) if expected else None,
                     'top3_accepted': bool(expected & top3) if expected else None,
                     'unsafe_exposed': violations, 'expected_engineer': case['expected_engineer'],
                     'actual_engineer': result.requires_engineer_review,
                     'warnings': list(result.warnings), 'triggered_rule_ids': [x['rule_id'] for x in result.triggered_rules]})
    with_label = [row for row in rows if row['recall_at_5'] is not None]
    positives = [row for row in rows if row['expected_engineer']]
    negatives = [row for row in rows if not row['expected_engineer']]
    return {
        'dataset_id': Path(path).stem, 'dataset_type': 'curated_synthetic_training_draft',
        'case_count': len(rows), 'candidate_labeled_cases': len(with_label),
        'engineer_positive_cases': len(positives), 'engineer_negative_cases': len(negatives),
        'candidate_recall_at_5': sum(x['recall_at_5'] for x in with_label) / len(with_label) if with_label else None,
        'top3_acceptance': sum(x['top3_accepted'] for x in with_label) / len(with_label) if with_label else None,
        'critical_rule_violations': sum(len(x['unsafe_exposed']) for x in rows),
        'critical_rule_violation_case_rate': sum(bool(x['unsafe_exposed']) for x in rows) / len(rows) if rows else None,
        'engineer_escalation_recall': sum(x['actual_engineer'] for x in positives) / len(positives) if positives else None,
        'false_escalation_rate': sum(x['actual_engineer'] for x in negatives) / len(negatives) if negatives else None,
        'rows': rows,
    }


def render_report(report):
    def pct(value):
        return 'N/A' if value is None else f'{value:.1%}'
    failures = [x for x in report['rows'] if x['unsafe_exposed'] or
                x['expected_engineer'] != x['actual_engineer'] or
                x['top3_accepted'] is False]
    table = '\n'.join(f'| {x["id"]} | {x["scenario"]} | {", ".join(x["top5"]) or "无"} | '
                      f'{"是" if x["actual_engineer"] else "否"} | {", ".join(x["unsafe_exposed"]) or "无"} |'
                      for x in failures)
    return (f'# Stage 5 产品匹配评估：{report["dataset_type"]}\n\n'
            f'样本 {report["case_count"]} 条；候选标签 {report["candidate_labeled_cases"]} 条；'
            f'应升级 {report["engineer_positive_cases"]} 条，不应升级 {report["engineer_negative_cases"]} 条。'
            '仅是教学合成草稿，不是历史客户数据或发布门槛证明。\n\n'
            f'- Candidate Recall@5：{pct(report["candidate_recall_at_5"])}\n'
            f'- Top-3 Acceptance：{pct(report["top3_acceptance"])}\n'
            f'- Critical Rule Violation：{report["critical_rule_violations"]} 次，'
            f'{pct(report["critical_rule_violation_case_rate"])} 案例率\n'
            f'- Engineer Escalation Recall：{pct(report["engineer_escalation_recall"])}\n'
            f'- False Escalation Rate：{pct(report["false_escalation_rate"])}\n\n'
            'Recall@5 为每个有标签案例中可接受 SKU 命中比例的平均；Top-3 为至少一个可接受 SKU 命中比例。'
            '无可接受 SKU 的案例不进入这两个指标分母。Critical Violation 只统计明确禁止的 SKU 进入有效候选。\n\n'
            '## 失败与例外逐案检查\n\n| ID | 情景 | Top-5 | 实际工程师升级 | 不安全 SKU |\n|---|---|---|---|---|\n' +
            (table or '| — | 当前无标签不一致 | — | — | — |') + '\n')
