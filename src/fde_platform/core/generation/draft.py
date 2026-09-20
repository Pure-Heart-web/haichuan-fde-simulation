"""Structured content first, wording second. This offline baseline uses no LLM."""
import json
from dataclasses import asdict, dataclass
from email.utils import parseaddr
from pathlib import Path

from fde_platform.core.policy.claims import validate_claims


@dataclass(frozen=True)
class GeneratedClaim:
    claim_type: str
    text: str
    source_refs: tuple[str, ...] = ()
    approval_ref: str | None = None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ReplyDraft:
    work_item_id: str
    subject: str
    body: str
    claims: tuple[GeneratedClaim, ...]
    content_plan: tuple[str, ...]
    knowledge_gaps: tuple[dict, ...]
    status: str
    required_reviewer: str
    requires_review: bool
    style_version: str
    claim_policy_version: str
    sent: bool = False

    def to_dict(self):
        return asdict(self)


def load_style(root):
    path = Path(root) / 'tenants/haichuan/reply-style.json'
    style = json.loads(path.read_text(encoding='utf-8'))
    if style['status'] != 'training_only' or style['tone'] != 'concise_professional':
        raise ValueError('不支持的回复风格')
    return style


def build_draft(work_item, inquiry, identity, previous_order, resolved_fields, knowledge_by_intent,
                intents, claim_policy, style, *, context_unavailable=False, knowledge_unavailable=False):
    claims = [GeneratedClaim('acknowledgement', 'Thank you for your inquiry.')]
    plan = ['acknowledge_inquiry']
    gaps = []
    evidence_refs = set()
    by_field = {x.field: x for x in resolved_fields}
    if previous_order is not None and identity.status == 'resolved':
        ref = previous_order.source_id
        evidence_refs.add(ref)
        sku = previous_order.data['sku']
        quantity = previous_order.data['quantity']
        claims.append(GeneratedClaim('historical_order',
                    f'For the repeat order, we have {sku} from your previous completed order on file ({quantity} units).',
                    (ref,)))
        plan.append('mention_verified_previous_order_as_history')

    for intent in intents:
        evidence = knowledge_by_intent.get(intent, ())
        if not evidence:
            gap_sku = by_field['sku'].value if 'sku' in by_field else 'unconfirmed model'
            gaps.append({'intent': intent, 'query': f'{intent} for {gap_sku}',
                         'reason': 'knowledge_service_unavailable' if knowledge_unavailable else 'no_active_applicable_evidence',
                         'owner': 'knowledge_owner_confirmation_required'})
            plan.append(f'abstain_{intent}')
            continue
        item = evidence[0]
        ref = item.document_id + ':' + item.chunk_id
        evidence_refs.add(ref)
        if intent == 'warranty':
            claim = GeneratedClaim('warranty', f'Our current standard warranty is {item.fact_value}.', (ref,))
        elif intent == 'ce':
            claim = GeneratedClaim('certification', item.text, (ref,))
        elif intent == 'lead_time':
            claim = GeneratedClaim('typical_lead_time', item.text, (ref,))
        elif intent == 'outdoor':
            claim = GeneratedClaim('outdoor', item.text, (ref,))
        else:
            gaps.append({'intent': intent, 'query': f'{intent} for unconfirmed model', 'reason': 'no_approved_reply_template',
                         'owner': 'knowledge_owner_confirmation_required'})
            continue
        claims.append(claim)
        plan.append(f'answer_{intent}_with_evidence')

    # Explicit current values remain separate. Prior electrical values are questions, not current facts.
    followups = []
    if previous_order is not None:
        prior_v = previous_order.data.get('voltage_v')
        prior_f = previous_order.data.get('frequency_hz')
        if by_field.get('sku') and by_field['sku'].source_type == 'explicit_current':
            if by_field['sku'].value != previous_order.data.get('sku'):
                followups.append(f'You specified {by_field["sku"].value} now; the previous order used {previous_order.data["sku"]}. Please confirm this change.')
        if by_field.get('quantity') and by_field['quantity'].source_type == 'explicit_current':
            if by_field['quantity'].value != previous_order.data.get('quantity'):
                followups.append(f'You specified {by_field["quantity"].value} units now; the previous order was {previous_order.data["quantity"]} units. Please confirm this change.')
        if by_field.get('voltage_v') and by_field['voltage_v'].source_type == 'explicit_current':
            if by_field['voltage_v'].value != prior_v:
                followups.append(f'You specified {by_field["voltage_v"].value}V now; the previous order used {prior_v}V. Please confirm this change.')
        elif prior_v is not None:
            followups.append(f'Please confirm whether the previous {prior_v}V electrical configuration still applies.')
        if by_field.get('frequency_hz') and by_field['frequency_hz'].source_type == 'explicit_current':
            if by_field['frequency_hz'].value != prior_f:
                followups.append(f'You specified {by_field["frequency_hz"].value}Hz now; the previous order used {prior_f}Hz. Please confirm this change.')
        elif prior_f is not None:
            followups.append(f'Please confirm whether the previous {prior_f}Hz frequency still applies.')
        if followups:
            evidence_refs.add(previous_order.source_id)
            refs = (previous_order.source_id, inquiry.work_item_id) if any(
                x.source_type == 'explicit_current' for x in by_field.values()) else (previous_order.source_id,)
            evidence_refs.update(refs)
            claims.append(GeneratedClaim('historical_order', ' '.join(followups), refs))
            plan.append('confirm_historical_configuration')
    if identity.status != 'resolved' and ('previous order' in work_item.body.casefold() or 'last order' in work_item.body.casefold()):
        plan.append('request_identity_confirmation')
        claims.append(GeneratedClaim('acknowledgement',
                    'Please confirm your company and prior order reference so we can verify the configuration.'))
    if context_unavailable:
        plan.append('manual_previous_order_verification')
        claims.append(GeneratedClaim('acknowledgement',
                    'Customer history is temporarily unavailable. Please verify the prior order reference manually.'))
    for gap in gaps:
        claims.append(GeneratedClaim('acknowledgement',
                    f'We will verify the {gap["intent"].replace("_", " ").upper() if gap["intent"] in ("ce", "atex") else gap["intent"].replace("_", " ")} information for your configuration and follow up.'))
    if inquiry.flow_m3h is None or inquiry.head_m is None:
        claims.append(GeneratedClaim('acknowledgement',
                    'Please confirm the required flow and head before we prepare a product recommendation.'))
        plan.append('request_missing_duty_point')
    if 'price' in work_item.body.casefold() or 'quote' in work_item.body.casefold():
        plan.append('withhold_price_or_quote_commitment')
        claims.append(GeneratedClaim('acknowledgement',
                    'We can prepare a formal quotation once the required configuration is confirmed.'))

    validate_claims(claims, evidence_refs, claim_policy)
    reviewer = 'engineer' if any(claim_policy['claim_types'][c.claim_type].get('reviewer') == 'engineer'
                                 for c in claims) else 'sales'
    display, address = parseaddr(work_item.sender)
    first_name = (display.split()[0] if display else address.split('@')[0].split('.')[0].title()) if identity.status == 'resolved' and address else ''
    greeting = f'Dear {first_name},' if first_name and style['greeting'] == 'first_name_if_verified' else 'Hello,'
    facts, questions = [], []
    for claim in claims[1:]:
        if claim.claim_type == 'acknowledgement' or claim.text.startswith(('Please confirm', 'You specified')):
            questions.append(claim.text)
        else:
            facts.append(claim.text)
    paragraphs = [greeting, claims[0].text, ' '.join(facts), ' '.join(questions),
                  'Best regards,\nHaichuan Sales Team']
    paragraphs = [x for x in paragraphs if x]
    if len(paragraphs) > style['max_paragraphs']:
        raise ValueError('回复段落超出租户风格上限')
    body = '\n\n'.join(paragraphs)
    needs_identity = identity.status != 'resolved' and previous_order is None and (
        'previous order' in work_item.body.casefold() or 'last order' in work_item.body.casefold())
    status = 'needs_identity_review' if needs_identity else 'pending_human_review'
    return ReplyDraft(work_item.id, 'Re: ' + (work_item.subject or 'Your pump inquiry'), body,
                      tuple(claims), tuple(plan), tuple(gaps), status, reviewer, True,
                      style['version'], claim_policy['version'])
