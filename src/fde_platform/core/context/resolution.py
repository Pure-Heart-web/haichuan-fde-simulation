"""Exact identifiers before names; fuzzy matches are suggestions only."""
import re
from email.utils import parseaddr

from .models import IdentityResolution, ResolvedField


def _normal_name(value):
    return re.sub(r'[^a-z0-9]+', '', (value or '').casefold())


def _resolve_ids(ids, method, evidence):
    ids = tuple(sorted(ids))
    if len(ids) == 1:
        return IdentityResolution('resolved', ids[0], method, ids, evidence)
    if ids:
        return IdentityResolution('needs_confirmation', None, method, ids, evidence)
    return None


def resolve_identity(entities, sender='', company_name=''):
    sender = parseaddr(sender)[1].strip().casefold()
    domain = sender.rpartition('@')[2] if sender.count('@') == 1 else ''
    if domain in ('example.com', 'gmail.com', 'outlook.com', 'yahoo.com'):
        domain = ''
    exact = {e.customer_id for e in entities if sender and sender in (x.casefold() for x in e.contacts)}
    named = {e.customer_id for e in entities if company_name and _normal_name(company_name) in
             {_normal_name(x) for x in (e.canonical_name, *e.aliases)}}
    if exact:
        result = _resolve_ids(exact, 'exact_contact', sender)
        if named and result.customer_id not in named:
            return IdentityResolution('needs_confirmation', None, 'contact_name_conflict',
                                      tuple(sorted(exact | named)), sender + ' / ' + company_name)
        return result
    by_domain = {e.customer_id for e in entities if domain and domain in (x.casefold() for x in e.domains)}
    if by_domain:
        result = _resolve_ids(by_domain, 'exact_domain', domain)
        if named and result.customer_id not in named:
            return IdentityResolution('needs_confirmation', None, 'domain_name_conflict',
                                      tuple(sorted(by_domain | named)), domain + ' / ' + company_name)
        return result
    if named:
        return _resolve_ids(named, 'exact_alias', company_name)
    # Similar names may be shown to a human, but never unlock order history.
    suggestions = tuple(sorted(e.customer_id for e in entities if company_name and
                  any(_normal_name(company_name) in _normal_name(x) or _normal_name(x) in _normal_name(company_name)
                      for x in (e.canonical_name, *e.aliases))))
    return IdentityResolution('needs_confirmation' if suggestions else 'unresolved', None,
                              'fuzzy_suggestion' if suggestions else 'none', suggestions,
                              company_name or sender or None)


def has_previous_order_reference(text):
    return bool(re.search(r'\b(same as (?:the )?(?:previous|last) order|as (?:per|before) last order|repeat (?:our )?last order)\b|同上一单|与上次订单相同',
                          text, re.I))


def resolve_fields(inquiry, previous_order, text):
    """Expose prior values as historical suggestions, never mutate InquiryRecord."""
    fields = []
    for name in ('quantity', 'voltage_v', 'frequency_hz'):
        current = getattr(inquiry, name)
        if current is not None:
            fields.append(ResolvedField(name, current, 'explicit_current', inquiry.work_item_id, 1.0))
        elif previous_order is not None and has_previous_order_reference(text):
            fields.append(ResolvedField(name, previous_order.data.get(name), 'historical_reference',
                                        previous_order.source_id, 1.0))
    sku = re.search(r'\bCP(?:80|90|100)\b', text, re.I)
    if sku:
        fields.append(ResolvedField('sku', sku.group(0).upper(), 'explicit_current', inquiry.work_item_id, 1.0))
    elif previous_order is not None and has_previous_order_reference(text):
        fields.append(ResolvedField('sku', previous_order.data['sku'], 'historical_reference',
                                    previous_order.source_id, 1.0))
    return tuple(field for field in fields if field.value is not None)
