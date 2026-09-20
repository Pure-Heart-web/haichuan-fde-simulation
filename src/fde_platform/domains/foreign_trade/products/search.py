"""Hard eligibility is separate from domain rules and ranking."""
from dataclasses import dataclass

from .catalog import ProductRecord


@dataclass(frozen=True)
class SearchResult:
    eligible: tuple[ProductRecord, ...]
    rejected: tuple[dict, ...]


def search(inquiry, catalog):
    if inquiry.flow_m3h is None or inquiry.head_m is None:
        return SearchResult((), ())
    eligible, rejected = [], []
    for product in catalog.products:
        reasons = []
        if product.product_family != 'centrifugal_pump' or inquiry.product_type != 'centrifugal_pump':
            reasons.append('unsupported_product_family')
        if product.status != 'active_simulated':
            reasons.append('inactive_product')
        if not product.flow_min_m3h <= inquiry.flow_m3h <= product.flow_max_m3h:
            reasons.append('flow_out_of_range')
        if not product.head_min_m <= inquiry.head_m <= product.head_max_m:
            reasons.append('head_out_of_range')
        if inquiry.temperature_c is not None:
            if product.temperature_min_c is None or product.temperature_max_c is None:
                reasons.append('temperature_capability_unknown')
            elif not product.temperature_min_c <= inquiry.temperature_c <= product.temperature_max_c:
                reasons.append('temperature_out_of_range')
        if inquiry.frequency_hz is not None:
            if not product.supported_frequency_hz:
                reasons.append('frequency_capability_unknown')
            elif inquiry.frequency_hz not in product.supported_frequency_hz:
                reasons.append('frequency_unsupported')
        if reasons:
            rejected.append({'sku': product.sku, 'reasons': reasons, 'source_id': product.source_id})
        else:
            eligible.append(product)
    rejected.extend({'sku': item['sku'], 'reasons': [item['reason']], 'source_id': item['source_id']}
                    for item in catalog.quarantined)
    return SearchResult(tuple(eligible), tuple(rejected))
