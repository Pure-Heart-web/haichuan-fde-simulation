"""Segmented synthetic pilot dashboard; never labels simulated events as live telemetry."""
import json
import statistics
from collections import Counter
from pathlib import Path


def load_events(path):
    events = [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]
    ids = [x['id'] for x in events]
    if len(ids) != len(set(ids)) or not events or any(x.get('data_classification') != 'synthetic_training_event' for x in events):
        raise ValueError('试点事件 ID 重复、为空或不是教学合成数据')
    return events


def _rate(rows, numerator):
    return sum(numerator(x) for x in rows) / len(rows) if rows else None


def _segment(events, field):
    result = []
    for value in sorted({x[field] for x in events}):
        xs = [x for x in events if x[field] == value]
        complex_eligible = [x for x in xs if x['eligible'] and x['complexity'] == 'complex']
        result.append({'segment': value, 'cases': len(xs),
                       'eligible_complex_cases': len(complex_eligible),
                       'eligible_complex_adoption': _rate(complex_eligible, lambda x: x['assisted']),
                       'assisted_rate': _rate([x for x in xs if x['eligible']], lambda x: x['assisted'])})
    return result


def dashboard(events, baseline, users, task_store=None):
    if baseline['mode'] != 'hypothetical_pre_pilot_baseline':
        raise ValueError('前测基线必须明确是假设')
    if len(events) != 180 or len({x['date'] for x in events}) != 10:
        raise ValueError('教学试点集预期为 10 个工作日、180 条事件')
    eligible = [x for x in events if x['eligible']]
    complex_eligible = [x for x in eligible if x['complexity'] == 'complex']
    attempted = [x for x in events if x['attempted']]
    assisted = [x for x in events if x['assisted']]
    reviewed = [x for x in assisted if x['review_outcome'] != 'none']
    top3 = [x for x in assisted if x['top3_accepted'] is not None]
    daily = []
    for day in sorted({x['date'] for x in events}):
        rows = [x for x in events if x['date'] == day]
        ec = [x for x in rows if x['eligible'] and x['complexity'] == 'complex']
        daily.append({'date': day, 'inquiries': len(rows), 'daily_active_users':
                      len({x['user_id'] for x in rows if x['assisted']}),
                      'assisted': sum(x['assisted'] for x in rows),
                      'eligible_complex_adoption': _rate(ec, lambda x: x['assisted']),
                      'average_context_switches_on_attempts':
                      statistics.mean(x['context_switches'] for x in rows if x['attempted'])
                      if any(x['attempted'] for x in rows) else None})
    expected_processing = [baseline['processing_minutes'][x['experience']][x['complexity']] for x in eligible]
    expected_response = [baseline['first_response_minutes'][x['experience']][x['complexity']] for x in eligible]
    latencies = sorted(x['latency_ms'] for x in attempted if x['latency_ms'] is not None)
    p95 = latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)] if latencies else None
    overrides = [x for x in task_store.events() if x['action'] == 'override'] if task_store else []
    failure_categories = Counter(x['failure_category'] for x in events if x['failure_category'])
    for x in overrides:
        failure_categories['override:' + x['override_category']] += 1
    return {
      'mode': 'synthetic_pilot_replay', 'real_pilot_release_gate': 'NOT_EVALUATED',
      'pilot_decision': 'ITERATE_SIMULATION_ONLY', 'duration_business_days': 10,
      'users': [x['user_id'] for x in users if x['role'] == 'sales'],
      'case_count': len(events), 'eligible_cases': len(eligible),
      'eligible_complex_cases': len(complex_eligible),
      'business': {
        'median_processing_minutes': statistics.median(x['processing_minutes'] for x in eligible),
        'hypothetical_baseline_median_processing_minutes': statistics.median(expected_processing),
        'median_first_response_minutes': statistics.median(x['first_response_minutes'] for x in eligible),
        'hypothetical_baseline_median_first_response_minutes': statistics.median(expected_response),
        'engineer_consultations_per_day': sum(x['engineer_consulted'] for x in events) / 10,
        'hypothetical_baseline_engineer_consultations_per_day': baseline['engineer_consultations_per_day']},
      'product': {
        'average_daily_active_users': statistics.mean(x['daily_active_users'] for x in daily),
        'ai_assisted_inquiry_rate': _rate(eligible, lambda x: x['assisted']),
        'eligible_complex_adoption_rate': _rate(complex_eligible, lambda x: x['assisted']),
        'draft_accept_or_minor_edit_rate': _rate(reviewed, lambda x: x['review_outcome'] in ('accept', 'minor_edit')),
        'abandonment_rate': _rate(attempted, lambda x: x['abandoned'])},
      'ai': {
        'extraction_correction_rate': _rate(assisted, lambda x: x['extraction_corrected']),
        'top3_product_acceptance': _rate(top3, lambda x: x['top3_accepted']),
        'critical_rule_violations': sum(x['critical_rule_violation'] for x in events),
        'engineer_escalation_recall': None, 'unsupported_claim_rate': None,
        'unavailable_reason': 'no independent live pilot labels'},
      'system': {
        'success_rate': _rate(attempted, lambda x: x['system_success']),
        'p95_latency_ms': p95, 'integration_error_rate': _rate(attempted, lambda x: x['integration_error']),
        'observed_api_cost_per_attempt_usd': sum(x['api_cost_usd_observed'] for x in attempted) / len(attempted)
          if attempted else None, 'cost_scope': 'offline baseline with no paid model calls'},
      'daily': daily,
      'segments': {field: _segment(events, field) for field in ('user_id', 'experience', 'complexity', 'customer_type', 'week')},
      'failure_distribution': dict(sorted(failure_categories.items())),
      'shadow_cases_visible_to_sales': 0,
    }


def render_dashboard(report):
    p, b, s = report['product'], report['business'], report['system']
    def pct(x): return 'N/A' if x is None else f'{x:.1%}'
    users = '\n'.join(f'| {x["segment"]} | {x["eligible_complex_cases"]} | {pct(x["eligible_complex_adoption"])} |'
                      for x in report['segments']['user_id'])
    weeks = '\n'.join(f'| {x["segment"]} | {x["eligible_complex_cases"]} | {pct(x["eligible_complex_adoption"])} |'
                      for x in report['segments']['week'])
    return (f'# Stage 7 合成 Pilot 仪表盘\n\n{report["case_count"]} 条虚构事件，10 个工作日。'
            f'**没有真实用户试点、业务改善或生产部署。** 决策：`{report["pilot_decision"]}`。\n\n'
            f'- 标准复杂询盘采用率：{pct(p["eligible_complex_adoption_rate"])}（分母 {report["eligible_complex_cases"]}）\n'
            f'- 全部合格询盘辅助率：{pct(p["ai_assisted_inquiry_rate"])}\n'
            f'- 草稿接受/小修改：{pct(p["draft_accept_or_minor_edit_rate"])}；放弃率：{pct(p["abandonment_rate"])}\n'
            f'- 合成处理时间中位数：{b["median_processing_minutes"]} 分；假设前测同样本组合：{b["hypothetical_baseline_median_processing_minutes"]} 分\n'
            f'- 合成首次响应中位数：{b["median_first_response_minutes"]} 分；假设前测：{b["hypothetical_baseline_median_first_response_minutes"]} 分\n'
            f'- 系统成功率：{pct(s["success_rate"])}；合成 P95：{s["p95_latency_ms"]} ms；实测 API 成本：$0（离线无付费调用）\n'
            '- 工程师升级召回、Pilot 无证据主张率：N/A（缺独立真人标注）\n\n'
            '## 按销售分段\n\n| 用户 | 合格复杂询盘 | 采用率 |\n|---|---:|---:|\n' + users +
            '\n\n## 按周分段\n\n| 周 | 合格复杂询盘 | 采用率 |\n|---|---:|---:|\n' + weeks +
            '\n\n以上时间与采用变化是脚本生成的假设，不构成因果效果证明。逐日、角色、经验和客户类型数据见 `pilot-dashboard.json`。\n')
