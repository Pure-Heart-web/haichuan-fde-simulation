"""Explicit simulated rollout: in-scope review tasks; out-of-scope shadow only."""
import json
import re
from pathlib import Path

from fde_platform.core.pilot.models import ReviewTask
from fde_platform.core.pilot.trace import build_trace
from fde_platform.domains.foreign_trade.reply.workflow import run_case


def classify_scope(case):
    text = case['text'].casefold()
    if re.search(r'\b(submersible|diaphragm|gear) pump\b', text):
        return 'shadow', 'unsupported_product_family'
    if re.search(r'\bchemical\b|\bATEX\b', case['text'], re.I):
        return 'shadow', 'chemical_service_out_of_pilot_scope'
    if re.search(r'\b(?:8[0-9]|9[0-9]|1[0-9][0-9])\s*°?\s*c\b', text):
        return 'shadow', 'extreme_temperature_out_of_pilot_scope'
    if not re.search(r'\bcentrifugal pump\b', text):
        return 'shadow', 'unsupported_product_family'
    return 'pilot', None


def versions(root, provider, index, product_components):
    root = Path(root)
    manifest = json.loads((root / 'stages/03-data-boundary/data/manifest.json').read_text(encoding='utf-8'))
    tech = next(x for x in manifest['sources'] if x['id'] == 'SRC-TECH')
    extension = json.loads((root / 'stages/05-product-recommendation/data/technical-extensions.json').read_text(encoding='utf-8'))
    catalog, registry, preferences = product_components
    return {'workflow_version': 'stage7-offline-pilot-v1',
            'ingestion_version': 'stage4-ingestion-v1', 'extraction_version': 'stage4-regex-baseline-v1',
            'customer_resolution_version': 'stage6-identity-v1',
            'order_context_version': provider.version, 'order_data_version': provider.version,
            'product_recommendation_version': 'stage5-recommend-v1',
            'product_data_version': tech['version'] + '|' + extension['source_version'],
            'material_mapping_version': catalog.mapping_version,
            'rule_registry_version': registry['registry_version'],
            'ranking_version': preferences['version'],
            'knowledge_retrieval_version': index.dataset_id,
            'reply_generation_version': 'stage6-template-v1'}


def simulate_case(case, *, root, provider, index, products):
    mode, reason = classify_scope(case)
    if case.get('scope') != mode or (mode == 'shadow' and case.get('shadow_reason') != reason):
        raise ValueError(f'{case["id"]} 的试点范围标注与规则不一致')
    spans = []
    faults = (case['fault'],) if case.get('fault') else ()
    artifact = run_case(case, root=root, context_provider=provider, knowledge_index=index,
                        product_components=products, observer=spans.append, faults=faults)
    trace = build_trace(case, mode, artifact, spans, versions(root, provider, index, products), owner=case['owner'])
    trace['scope_reason'] = reason
    return artifact, trace


def review_tasks(case, artifact, trace):
    if trace['mode'] == 'shadow':
        return ()
    recommendation = artifact['recommendation'] or {}
    draft = artifact['draft'] or {}
    candidates = list(recommendation.get('candidate_skus') or [])
    explicit_sku = next((x['value'] for x in artifact['resolved_fields']
                         if x['field'] == 'sku' and x['source_type'] == 'explicit_current'), None)
    sku_conflict = bool(explicit_sku and explicit_sku not in candidates)
    engineer = (recommendation.get('requires_engineer_review', False) or
                draft.get('required_reviewer') == 'engineer' or
                'product_data_unavailable' in artifact['degradations'] or sku_conflict)
    warnings = list(recommendation.get('warnings') or []) + list(artifact['degradations'])
    if sku_conflict:
        warnings.append('explicit_sku_not_in_eligible_candidates')
    evidence = {'trace_id': trace['trace_id'],
                'rule_ids': [x['rule_id'] for x in recommendation.get('triggered_rules', [])],
                'knowledge_source_ids': [x['document_id'] for xs in artifact['knowledge_evidence'].values() for x in xs],
                'product_data_version': trace['versions']['product_data_version'],
                'rule_version': trace['versions']['rule_registry_version']}
    tasks = []
    prerequisite = None
    if engineer:
        prerequisite = f'{case["id"]}-ENG'
        tasks.append(ReviewTask(prerequisite, case['id'], trace['trace_id'], 'engineer_review', 'high',
                    'engineer', 'chen',
                    {'candidate_skus': candidates, 'requested_sku': explicit_sku,
                     'missing_information': recommendation.get('missing_information', []),
                     'warnings': warnings,
                     'question': '确认候选、工况与触发规则；若数据缺失请标记并解释。'},
                    evidence))
    tasks.append(ReviewTask(f'{case["id"]}-SALES', case['id'], trace['trace_id'], 'sales_draft',
                 'medium' if engineer or artifact['degradations'] else 'low', 'sales', case['owner'],
                 {'draft_subject': draft.get('subject'), 'draft_body': draft.get('body'),
                  'draft_status': draft.get('status', 'manual_workflow_required'),
                  'candidate_skus': candidates, 'warnings': warnings,
                  'manual_fallback': 'draft_unavailable' in artifact['degradations'],
                  'note': '批准仅记录教学审核，不发送邮件或确认最终型号。'},
                 evidence, prerequisite))
    return tuple(tasks)
