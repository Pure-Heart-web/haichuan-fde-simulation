"""Offline orchestration; no autonomous agent, mail sending, CRM write, or LLM call."""
import re
import time
from datetime import datetime, timezone

from fde_platform.core.context.resolution import has_previous_order_reference, resolve_fields, resolve_identity
from fde_platform.core.generation.draft import build_draft, load_style
from fde_platform.core.ingestion import from_text
from fde_platform.core.knowledge.retrieval import infer_intents
from fde_platform.core.policy.claims import load_claim_policy
from fde_platform.domains.foreign_trade.schema import InquiryRecord
from fde_platform.pipeline import process
from fde_platform.domains.foreign_trade.recommendation.service import recommend


def run_case(case, *, root, context_provider, knowledge_index, product_components,
             observer=None, faults=()):
    faults = frozenset(faults)
    if faults - {'crm_timeout', 'knowledge_unavailable', 'product_data_unavailable', 'draft_unavailable'}:
        raise ValueError('未知故障注入类型')
    def stage(name, call, status='ok'):
        started = datetime.now(timezone.utc).isoformat()
        start_ns = time.perf_counter_ns()
        try:
            result = call()
        except Exception as exc:
            if observer:
                observer({'stage': name, 'started_at': started, 'ended_at': datetime.now(timezone.utc).isoformat(),
                          'duration_ms': round((time.perf_counter_ns()-start_ns)/1e6, 3),
                          'status': 'failed', 'error_class': type(exc).__name__})
            raise
        if observer:
            observer({'stage': name, 'started_at': started, 'ended_at': datetime.now(timezone.utc).isoformat(),
                      'duration_ms': round((time.perf_counter_ns()-start_ns)/1e6, 3),
                      'status': status, 'error_class': None})
        return result
    for field in ('id', 'text', 'sender'):
        if not case.get(field):
            raise ValueError(f'场景缺少 {field}')
    work = stage('ingestion', lambda: from_text(case['text'], source_id=case['id'], sender=case['sender'],
                     subject=case.get('subject', 'Pump inquiry')))
    extraction, inquiry = stage('extraction', lambda: process(work))
    if inquiry is None:
        inquiry = InquiryRecord(work_item_id=work.id, warnings=['stage4_extraction_failed'])
    identity = stage('customer_resolution', lambda: resolve_identity(context_provider.entities, work.sender,
                      case.get('company_name', '')))
    previous = None
    if has_previous_order_reference(work.body) and identity.status == 'resolved':
        if 'crm_timeout' in faults:
            previous = stage('order_context', lambda: None, status='degraded')
        else:
            previous = stage('order_context', lambda: context_provider.previous_order(identity.customer_id,
                             as_of=case.get('as_of', '2026-09-20')))
    else:
        stage('order_context', lambda: None, status='skipped')
    fields = stage('field_provenance', lambda: resolve_fields(inquiry, previous, work.body))
    catalog, registry, preferences = product_components
    recommendation = (stage('product_recommendation', lambda: None, status='degraded')
                      if 'product_data_unavailable' in faults else
                      stage('product_recommendation', lambda: recommend(inquiry, catalog, registry, preferences)))
    sku = next((x.value for x in fields if x.field == 'sku'), None)
    if sku is None:
        match = re.search(r'\bCP(?:80|90|100)\b', work.body, re.I)
        sku = match.group(0).upper() if match else None
    intents = infer_intents(work.body)
    knowledge = (stage('knowledge_retrieval', lambda: {intent: () for intent in intents}, status='degraded')
                 if 'knowledge_unavailable' in faults else
                 stage('knowledge_retrieval', lambda: {intent: knowledge_index.retrieve(work.body, intent=intent,
                       sku=sku, region=case.get('region', 'global'), as_of=case.get('as_of', '2026-09-20'))
                       for intent in intents}))
    draft = (stage('reply_generation', lambda: None, status='degraded')
             if 'draft_unavailable' in faults else
             stage('reply_generation', lambda: build_draft(work, inquiry, identity, previous, fields, knowledge, intents,
                    load_claim_policy(root), load_style(root), context_unavailable='crm_timeout' in faults,
                    knowledge_unavailable='knowledge_unavailable' in faults)))
    return {
        'case_id': case['id'], 'work_item': work.to_dict(), 'extraction_status': extraction.status,
        'inquiry': inquiry.to_dict(), 'identity': identity.to_dict(),
        'previous_order': previous.to_dict() if previous else None,
        'resolved_fields': [x.to_dict() for x in fields],
        'recommendation': recommendation.to_dict() if recommendation else None,
        'knowledge_evidence': {key: [x.to_dict() for x in values] for key, values in knowledge.items()},
        'draft': draft.to_dict() if draft else None, 'workflow_version': 'stage6-offline-v1',
        'degradations': sorted(faults),
    }
