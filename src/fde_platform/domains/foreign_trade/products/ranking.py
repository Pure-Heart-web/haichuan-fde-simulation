"""Transparent proxy ranking, deliberately not a pump performance curve."""
import json
from pathlib import Path


def load_preferences(root):
    path = Path(root) / 'tenants/haichuan/product-preferences.json'
    preferences = json.loads(path.read_text(encoding='utf-8'))
    weights = preferences['score_weights']
    if set(weights) != {'flow_center_proxy', 'head_center_proxy', 'standard_configuration'}:
        raise ValueError('排序权重字段不完整')
    if any(type(x) not in (int, float) or x < 0 for x in weights.values()) or abs(sum(weights.values()) - 1) > 1e-9:
        raise ValueError('排序权重必须非负且总和为 1')
    if preferences['status'] != 'hypothesis_for_eval':
        raise ValueError('排序配置必须明确为待评估假设')
    return preferences


def _center_fit(requested, low, high):
    middle = (low + high) / 2
    half = (high - low) / 2
    return max(0.0, 1.0 - abs(requested - middle) / half)


def _edge_ratio(requested, low, high):
    return min(requested - low, high - requested) / (high - low)


def rank(inquiry, products, preferences):
    weights = preferences['score_weights']
    output = []
    for product in products:
        parts = {
            'flow_center_proxy': _center_fit(inquiry.flow_m3h, product.flow_min_m3h, product.flow_max_m3h),
            'head_center_proxy': _center_fit(inquiry.head_m, product.head_min_m, product.head_max_m),
            'standard_configuration': 1.0 if product.standard_configuration else 0.0,
        }
        score = sum(parts[key] * weights[key] for key in parts)
        edge = min(_edge_ratio(inquiry.flow_m3h, product.flow_min_m3h, product.flow_max_m3h),
                   _edge_ratio(inquiry.head_m, product.head_min_m, product.head_max_m))
        output.append({'product': product, 'score': round(score, 6), 'components': parts,
                       'range_edge_proxy': round(edge, 6)})
    return sorted(output, key=lambda x: (-x['score'], x['product'].sku))
