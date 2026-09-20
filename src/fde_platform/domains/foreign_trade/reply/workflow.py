"""Offline orchestration; no autonomous agent, mail sending, CRM write, or LLM call."""
import re

from fde_platform.core.context.resolution import has_previous_order_reference, resolve_fields, resolve_identity
from fde_platform.core.generation.draft import build_draft, load_style
from fde_platform.core.ingestion import from_text
from fde_platform.core.knowledge.retrieval import infer_intents
from fde_platform.core.policy.claims import load_claim_policy
from fde_platform.domains.foreign_trade.schema import InquiryRecord
from fde_platform.pipeline import process
from fde_platform.domains.foreign_trade.recommendation.service import recommend


def run_case(case, *, root, context_provider, knowledge_index, product_components):
    for field in ('id', 'text', 'sender'):
        if not case.get(field):
            raise ValueError(f'场景缺少 {field}')
    work = from_text(case['text'], source_id=case['id'], sender=case['sender'],
                     subject=case.get('subject', 'Pump inquiry'))
    extraction, inquiry = process(work)
    if inquiry is None:
        inquiry = InquiryRecord(work_item_id=work.id, warnings=['stage4_extraction_failed'])
    identity = resolve_identity(context_provider.entities, work.sender, case.get('company_name', ''))
    previous = None
    if has_previous_order_reference(work.body) and identity.status == 'resolved':
        previous = context_provider.previous_order(identity.customer_id, as_of=case.get('as_of', '2026-09-20'))
    fields = resolve_fields(inquiry, previous, work.body)
    catalog, registry, preferences = product_components
    recommendation = recommend(inquiry, catalog, registry, preferences)
    sku = next((x.value for x in fields if x.field == 'sku'), None)
    if sku is None:
        match = re.search(r'\bCP(?:80|90|100)\b', work.body, re.I)
        sku = match.group(0).upper() if match else None
    intents = infer_intents(work.body)
    knowledge = {intent: knowledge_index.retrieve(work.body, intent=intent, sku=sku,
                 region=case.get('region', 'global'), as_of=case.get('as_of', '2026-09-20'))
                 for intent in intents}
    draft = build_draft(work, inquiry, identity, previous, fields, knowledge, intents,
                        load_claim_policy(root), load_style(root))
    return {
        'case_id': case['id'], 'work_item': work.to_dict(), 'extraction_status': extraction.status,
        'inquiry': inquiry.to_dict(), 'identity': identity.to_dict(),
        'previous_order': previous.to_dict() if previous else None,
        'resolved_fields': [x.to_dict() for x in fields],
        'recommendation': recommendation.to_dict(),
        'knowledge_evidence': {key: [x.to_dict() for x in values] for key, values in knowledge.items()},
        'draft': draft.to_dict(), 'workflow_version': 'stage6-offline-v1',
    }
