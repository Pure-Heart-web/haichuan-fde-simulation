"""Staged product-data validation; returns a review decision, never publishes."""
import json
import math
from pathlib import Path


def validate_product_candidate(mapping_path, baseline_path, candidate_path):
    mapping = json.loads(Path(mapping_path).read_text(encoding='utf-8'))
    baseline = json.loads(Path(baseline_path).read_text(encoding='utf-8'))
    candidate = json.loads(Path(candidate_path).read_text(encoding='utf-8'))
    aliases = {key.casefold(): value for key, value in mapping['aliases'].items()}
    problems, changes = [], []
    if baseline['status'] != 'approved_in_simulation' or candidate['status'] != 'candidate':
        problems.append('invalid_release_state')
    before = {p['sku']: p for p in baseline['products']}
    seen = set()
    for row in candidate['products']:
        sku = row.get('sku')
        if not sku or sku in seen:
            problems.append(f'duplicate_or_missing_sku:{sku}')
            continue
        seen.add(sku)
        material = row.get('material')
        canonical = aliases.get(material.casefold()) if isinstance(material, str) else None
        if canonical is None:
            problems.append(f'unmapped_material:{sku}:{material}')
        for low, high in (('flow_min', 'flow_max'),):
            a, b = row.get(low), row.get(high)
            if not (type(a) in (int, float) and type(b) in (int, float) and
                    math.isfinite(a) and math.isfinite(b) and 0 < a < b):
                problems.append(f'invalid_range:{sku}')
        old = before.get(sku)
        if old is None:
            changes.append({'sku': sku, 'change': 'added'})
        elif row != old:
            changes.append({'sku': sku, 'change': 'modified', 'fields':
                            sorted(key for key in set(old) | set(row) if old.get(key) != row.get(key))})
    for sku in before.keys() - seen:
        problems.append(f'missing_existing_sku:{sku}')
    return {'baseline_version': baseline['version'], 'candidate_version': candidate['version'],
            'material_mapping_version': mapping['version'], 'changes': changes,
            'problems': problems, 'status': 'BLOCKED' if problems else 'READY_FOR_SIMULATED_APPROVAL',
            'published': False}


def incident_report(bad_result, fixed_result):
    if bad_result['status'] != 'BLOCKED' or not any(x.startswith('unmapped_material:') for x in bad_result['problems']):
        raise ValueError('故障样本必须复现材质规范化问题')
    return {'incident_id': 'INC-SIM-001', 'mode': 'synthetic_replay',
            'classification': 'data_contract_canonicalization',
            'symptom': 'CP90 候选因未映射材质被隔离，推荐覆盖下降',
            'affected_skus': ['CP90'], 'detection': 'staged_data_release_gate',
            'immediate_mitigation': f'保留/回滚到 {bad_result["baseline_version"]}；禁止候选数据覆盖权威源',
            'root_cause': bad_result['problems'],
            'permanent_fix': '材质别名映射与数据质量校验、差异审查、离线评估、技术负责人签核后再发布',
            'fixed_candidate_status': fixed_result['status'],
            'actual_production_incident': False, 'published': False}


def analyze_latency_incident(event):
    if event.get('mode') != 'synthetic_incident_replay':
        raise ValueError('只接受合成延迟故障')
    stages = event['stage_durations_ms']
    if sum(stages.values()) != event['during_p95_ms']:
        raise ValueError('延迟分解与 P95 不一致')
    bottleneck = max(stages, key=stages.get)
    return {'incident_id': event['incident_id'], 'classification':
            'context_integration_bottleneck' if bottleneck == 'crm_context' else 'other_bottleneck',
            'p95_before_ms': event['before_p95_ms'], 'p95_during_ms': event['during_p95_ms'],
            'dominant_stage': bottleneck, 'dominant_stage_ms': stages[bottleneck],
            'immediate_mitigation': 'CRM 超时、有限重试与缓存；历史上下文不可用时继续但要求人工核实',
            'model_change_indicated': False, 'actual_production_incident': False}
