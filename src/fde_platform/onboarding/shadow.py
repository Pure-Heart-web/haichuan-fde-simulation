"""Reuse the shared extraction/recommendation core behind a shadow-only route."""
from fde_platform.core.ingestion import from_text
from fde_platform.pipeline import process
from fde_platform.domains.foreign_trade.recommendation.service import recommend

from .privacy import detect_untrusted_instruction


def process_shadow(event, components):
    """Build a review artifact; never create a customer-facing message or action."""
    base = {
        'case_id': event['case_id'], 'source_id': event['source_id'],
        'source_version': event['source_version'], 'contact_ref': event['contact_ref'],
        'customer_ref': event['customer_ref'], 'shadow_only': True,
        'external_side_effects': [],
    }
    if detect_untrusted_instruction(event['body']):
        return {**base, 'route': 'quarantine', 'assignee_id': 'dp-engineer-wu',
                'assignee_role': 'engineer', 'reason': 'untrusted_instruction_detected',
                'extraction': None, 'inquiry': None, 'recommendation': None}
    work = from_text(event['body'], source_id=event['source_id'],
        tenant_id=event['tenant_id'], sender=event['contact_ref'],
        subject=event.get('subject', ''), received_at=event['received_at'],
        domain=event['domain'], source_type='authorized_jsonl_drop')
    result, inquiry = process(work)
    if inquiry is None:
        return {**base, 'route': 'engineer_review', 'assignee_id': 'dp-engineer-wu',
                'assignee_role': 'engineer', 'reason': 'extraction_failed',
                'extraction': result.to_dict(), 'inquiry': None, 'recommendation': None}
    recommendation = recommend(inquiry, *components)
    if any(field in recommendation.missing_information for field in
           ('flow_m3h', 'head_m', 'product_type_confirmation', 'medium_detail')):
        route, assignee, role, reason = ('request_clarification', 'dp-sales-lin',
                                         'sales', 'critical_information_missing')
    elif recommendation.requires_engineer_review:
        route, assignee, role, reason = ('engineer_review', 'dp-engineer-wu',
                                         'engineer', 'domain_rule_or_candidate_risk')
    else:
        route, assignee, role, reason = ('sales_review', 'dp-sales-lin',
                                         'sales', 'standard_scope_candidate')
    return {**base, 'route': route, 'assignee_id': assignee,
            'assignee_role': role, 'reason': reason,
            'extraction': result.to_dict(), 'inquiry': inquiry.to_dict(),
            'recommendation': recommendation.to_dict()}
