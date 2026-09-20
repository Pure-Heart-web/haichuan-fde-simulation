"""Deterministic product matching. No model can override eligibility or rules."""
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from fde_platform.core.rules.engine import evaluate, validate_registry
from fde_platform.domains.foreign_trade.products.catalog import load_catalog
from fde_platform.domains.foreign_trade.products.ranking import load_preferences, rank
from fde_platform.domains.foreign_trade.products.search import search


@dataclass(frozen=True)
class Recommendation:
    work_item_id: str
    status: str
    candidate_skus: tuple[str, ...]
    candidates: tuple[dict, ...]
    rejected_candidates: tuple[dict, ...]
    provisional_top_sku: str | None
    required_reviewer: str
    requires_engineer_review: bool
    missing_information: tuple[str, ...]
    warnings: tuple[str, ...]
    triggered_rules: tuple[dict, ...]
    catalog_mapping_version: str
    ranking_version: str
    rule_registry_version: str
    human_review_required: bool = True

    def to_dict(self):
        return asdict(self)


def load_registry(root):
    path = Path(root) / 'stages/05-product-recommendation/data/rule-registry.json'
    return validate_registry(json.loads(path.read_text(encoding='utf-8')))


def _hit_dict(hit):
    return {'rule_id': hit.rule_id, 'severity': hit.severity, 'actions': list(hit.actions),
            'source_ids': list(hit.source_ids), 'version': hit.version, 'owner': hit.owner}


def recommend(inquiry, catalog, registry, preferences):
    """Return a reviewable artifact. All outputs are provisional, even a clear top SKU."""
    validate_registry(registry)
    for field in ('flow_m3h', 'head_m', 'temperature_c'):
        value = getattr(inquiry, field)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value)):
            raise ValueError(f'{field} 必须是有限数值')
    for field in ('frequency_hz', 'voltage_v'):
        value = getattr(inquiry, field)
        if value is not None and (type(value) is not int or value <= 0):
            raise ValueError(f'{field} 必须是正整数')
    missing = set(inquiry.missing_fields)
    warnings = set(inquiry.warnings)
    engineer = False
    if inquiry.flow_m3h is None or inquiry.flow_m3h <= 0:
        missing.add('flow_m3h')
    if inquiry.head_m is None or inquiry.head_m <= 0:
        missing.add('head_m')
    if inquiry.medium_category is None:
        missing.add('medium_detail')
    if inquiry.product_type != 'centrifugal_pump':
        missing.add('product_type_confirmation')
        engineer = True
    if inquiry.medium_category not in (None, 'water'):
        engineer = True
        warnings.add('special_medium_engineer_review')
    if inquiry.voltage_v is not None and inquiry.voltage_v not in (220, 380, 400, 415, 440):
        engineer = True
        warnings.add('nonstandard_voltage_review')
    if inquiry.frequency_hz is not None and inquiry.frequency_hz not in (50, 60):
        engineer = True
        warnings.add('nonstandard_frequency_review')
    if inquiry.extraction_confidence is not None and inquiry.extraction_confidence < 0.7:
        engineer = True
        warnings.add('low_extraction_confidence')
    if any(x in missing for x in ('flow_m3h', 'head_m', 'product_type_confirmation')) or inquiry.medium_category is None:
        engineer = True

    # Inquiry-only rules must fire even when hard search yields no products (e.g. 90 C).
    global_hits = []
    for rule in registry['rules']:
        if rule['status'] == 'active_in_simulation' and all(c['field'].startswith('inquiry.') for c in rule['when']):
            subset = {**registry, 'rules': [rule]}
            global_hits.extend(evaluate(subset, inquiry, None))
    hits_by_id = {hit.rule_id: _hit_dict(hit) for hit in global_hits}
    for hit in global_hits:
        for action in hit.actions:
            if action['type'] == 'require_review' and action['role'] == 'engineer':
                engineer = True
            elif action['type'] == 'add_warning':
                warnings.add(action['text'])
            elif action['type'] == 'add_requirement':
                missing.add(action['field'])

    if 'flow_m3h' in missing or 'head_m' in missing or 'product_type_confirmation' in missing:
        eligible, rejected = [], []
    else:
        found = search(inquiry, catalog)
        eligible, rejected = [], list(found.rejected)
        for product in found.eligible:
            hits = evaluate(registry, inquiry, product)
            excluded = []
            for hit in hits:
                hits_by_id[hit.rule_id] = _hit_dict(hit)
                for action in hit.actions:
                    if action['type'] == 'exclude_candidate':
                        excluded.append(action['reason'])
                    elif action['type'] == 'require_review' and action['role'] == 'engineer':
                        engineer = True
                    elif action['type'] == 'add_warning':
                        warnings.add(action['text'])
                    elif action['type'] == 'add_requirement':
                        missing.add(action['field'])
            if excluded:
                rejected.append({'sku': product.sku, 'reasons': excluded, 'source_id': product.source_id,
                                 'rule_ids': [h.rule_id for h in hits if any(a['type'] == 'exclude_candidate' for a in h.actions)]})
            else:
                eligible.append(product)

    ranked = rank(inquiry, eligible, preferences) if eligible else []
    candidates = []
    for item in ranked:
        product = item['product']
        edge = item['range_edge_proxy']
        candidate_warnings = []
        if edge <= preferences['edge_warning_ratio']:
            # This is a range-edge proxy, not the unverified R-003 curve rule.
            candidate_warnings.append('near_range_edge_proxy_unverified')
        candidates.append({'sku': product.sku, 'score': item['score'],
                           'ranking_components': item['components'], 'range_edge_proxy': edge,
                           'warnings': candidate_warnings,
                           'evidence': {'source_id': product.source_id, 'source_version': product.source_version,
                                        'extension_source_id': product.extension_source_id,
                                        'material_mapping_version': product.material_mapping_version,
                                        'material': product.material,
                                        'flow_range_m3h': [product.flow_min_m3h, product.flow_max_m3h],
                                        'head_range_m': [product.head_min_m, product.head_max_m],
                                        'temperature_range_c': [product.temperature_min_c, product.temperature_max_c],
                                        'frequency_hz': list(product.supported_frequency_hz)}})
    if not candidates:
        engineer = True
        warnings.add('no_eligible_candidate')
    if candidates and candidates[0]['warnings']:
        engineer = True
        warnings.update(candidates[0]['warnings'])
    if len(candidates) > 1 and candidates[0]['score'] - candidates[1]['score'] < preferences['close_candidate_gap']:
        engineer = True
        warnings.add('close_candidate_scores')
    if missing:
        warnings.add('missing_information')
    status = 'needs_engineer_review' if engineer else 'provisional_pending_sales_review'
    return Recommendation(inquiry.work_item_id, status, tuple(c['sku'] for c in candidates),
                          tuple(candidates), tuple(rejected), candidates[0]['sku'] if candidates else None,
                          'engineer' if engineer else 'sales', engineer, tuple(sorted(missing)),
                          tuple(sorted(warnings)), tuple(hits_by_id[k] for k in sorted(hits_by_id)),
                          catalog.mapping_version, preferences['version'], registry['registry_version'])


def load_components(root):
    return load_catalog(root), load_registry(root), load_preferences(root)
