"""Sanitized stage traces; no raw email, draft body, price or discount fields."""
import hashlib
import json
from datetime import datetime, timezone

from fde_platform.pipeline import MODEL_VERSION, PROMPT_VERSION


def _hash(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]


def trace_id(case_id):
    return 'trace_' + _hash('stage7-offline-v1|' + case_id)


def build_trace(case, mode, artifact, spans, versions, *, owner):
    tid = trace_id(case['id'])
    recommendation = artifact.get('recommendation') or {}
    evidence = artifact.get('knowledge_evidence') or {}
    draft = artifact.get('draft') or {}
    metadata = {
        'ingestion': {'work_item_id': artifact['work_item']['id']},
        'extraction': {'status': artifact['extraction_status'], 'model': MODEL_VERSION,
                       'prompt_version': PROMPT_VERSION, 'token_usage': 0, 'api_cost_usd': 0},
        'customer_resolution': {'status': artifact['identity']['status'], 'method': artifact['identity']['method'],
                                'customer_ref': _hash(artifact['identity']['customer_id']) if artifact['identity']['customer_id'] else None},
        'order_context': {'source_id': artifact['previous_order']['source_id'] if artifact['previous_order'] else None,
                          'source_version': versions['order_data_version']},
        'field_provenance': {'source_types': sorted(set(x['source_type'] for x in artifact['resolved_fields']))},
        'product_recommendation': {'candidate_ids': recommendation.get('candidate_skus', []),
            'candidate_scores': [{'sku': x['sku'], 'score': x['score']} for x in recommendation.get('candidates', [])],
            'rules_triggered': [x['rule_id'] for x in recommendation.get('triggered_rules', [])],
            'rule_version': recommendation.get('rule_registry_version'),
            'ranking_version': recommendation.get('ranking_version')},
        'knowledge_retrieval': {'intents': sorted(evidence),
            'documents': [{'intent': key, 'document_id': x['document_id'], 'chunk_id': x['chunk_id'],
                           'score': x['relevance_score']} for key, xs in evidence.items() for x in xs],
            'filters': {'region': case.get('region', 'global'), 'sku': next((x['value'] for x in artifact['resolved_fields'] if x['field'] == 'sku'), None)}},
        'reply_generation': {'claim_types': [x['claim_type'] for x in draft.get('claims', [])],
                             'evidence_refs': sorted({r for x in draft.get('claims', []) for r in x['source_refs']}),
                             'style_version': draft.get('style_version'),
                             'claim_policy_version': draft.get('claim_policy_version'),
                             'draft_status': draft.get('status')},
    }
    clean_spans = []
    previous_ref = 'input:' + _hash(case['id'] + '|' + case['text'])
    for span in spans:
        record = dict(span)
        stage = record['stage']
        record['input_reference'] = previous_ref
        record['version'] = versions.get(stage + '_version', versions['workflow_version'])
        record['metadata'] = metadata.get(stage, {})
        record['output_reference'] = None if record['status'] == 'failed' else 'output:' + _hash(
            json.dumps({'stage': stage, 'metadata': record['metadata']}, sort_keys=True, ensure_ascii=False))
        if record['output_reference']:
            previous_ref = record['output_reference']
        clean_spans.append(record)
    elapsed = sum(x['duration_ms'] for x in clean_spans)
    return {
        'trace_id': tid, 'case_id': case['id'], 'owner': owner, 'mode': mode,
        'status': 'degraded' if artifact.get('degradations') else 'completed',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'input_digest': _hash(case['text']), 'workflow_version': versions['workflow_version'],
        'versions': versions, 'degradations': artifact.get('degradations', []),
        'total_offline_latency_ms': round(elapsed, 3),
        'observed_api_cost_usd': 0.0, 'spans': clean_spans,
        'raw_email_saved_in_trace': False,
    }
