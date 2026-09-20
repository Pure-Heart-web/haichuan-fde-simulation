"""Load authoritative Stage 3 technical fields plus explicit Stage 5 supplements."""
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class ProductRecord:
    sku: str
    product_family: str
    flow_min_m3h: float
    flow_max_m3h: float
    head_min_m: float
    head_max_m: float
    material_raw: str
    material: str
    material_mapping_version: str
    temperature_min_c: float | None
    temperature_max_c: float | None
    motor_power_kw: float | None
    supported_frequency_hz: tuple[int, ...]
    status: str
    standard_configuration: bool
    source_id: str
    source_version: str
    extension_source_id: str | None
    owner: str

    def to_dict(self):
        return asdict(self)


@dataclass
class Catalog:
    products: list[ProductRecord]
    quarantined: list[dict]
    mapping_version: str


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_catalog(root):
    root = Path(root)
    stage3 = root / 'stages/03-data-boundary/data'
    stage5 = root / 'stages/05-product-recommendation/data'
    technical = read_json(stage3 / 'bundle/products/Pump_Selection_NEW.json')
    extensions = read_json(stage5 / 'technical-extensions.json')
    extra = read_json(stage5 / 'supplemental-products.json')
    mapping = read_json(stage5 / 'material-mapping.json')
    manifest = read_json(stage3 / 'manifest.json')
    source = next((s for s in manifest['sources'] if s['id'] == 'SRC-TECH'), None)
    truth = read_json(stage3 / 'source-of-truth.json')
    if not source or not any(x['domain'] == 'technical_product_parameters' and x['source_id'] == 'SRC-TECH' for x in truth):
        raise CatalogError('Stage 3 技术参数权威来源未确认')
    if set(extensions['by_sku']) != {p['sku'] for p in technical}:
        raise CatalogError('技术扩展 SKU 必须与 Stage 3 技术表一一对应')
    seen, products, quarantined = set(), [], []
    for raw in technical:
        sku = raw['sku']
        if sku in seen:
            raise CatalogError(f'重复 SKU：{sku}')
        seen.add(sku)
        extension = extensions['by_sku'][sku]
        row = {
            'sku': sku, 'product_family': 'centrifugal_pump',
            'flow_min_m3h': raw['flow_min'], 'flow_max_m3h': raw['flow_max'],
            'head_min_m': raw['head_min'], 'head_max_m': raw['head_max'],
            'material': raw['material'], 'status': 'active_simulated',
            **extension,
        }
        _append(row, products, quarantined, mapping, 'SRC-TECH', source['version'], extensions['source_id'], source['owner'])
    for row in extra['products']:
        sku = row['sku']
        if sku in seen:
            raise CatalogError(f'补充产品覆盖了权威 SKU：{sku}')
        seen.add(sku)
        _append(row, products, quarantined, mapping, extra['source_id'], extra['source_version'], None, extra['owner'])
    return Catalog(products, quarantined, mapping['version'])


def _append(row, products, quarantined, mapping, source_id, source_version, extension_source_id, owner):
    sku = row['sku']
    raw_material = row.get('material')
    aliases = {key.casefold(): value for key, value in mapping['aliases'].items()}
    material = aliases.get(raw_material.casefold()) if isinstance(raw_material, str) else None
    if material is None:
        quarantined.append({'sku': sku, 'field': 'material', 'raw_value': raw_material,
                            'reason': 'material_ambiguous_or_unmapped', 'source_id': source_id})
        return
    for low, high, label in [('flow_min_m3h', 'flow_max_m3h', 'flow'), ('head_min_m', 'head_max_m', 'head')]:
        a, b = row.get(low), row.get(high)
        if not (type(a) in (int, float) and type(b) in (int, float) and
                math.isfinite(a) and math.isfinite(b) and 0 < a < b):
            quarantined.append({'sku': sku, 'field': label, 'reason': 'invalid_range', 'source_id': source_id})
            return
    if row.get('status') not in ('active_simulated', 'retired'):
        quarantined.append({'sku': sku, 'field': 'status', 'reason': 'unknown_status', 'source_id': source_id})
        return
    tmin, tmax = row.get('temperature_min_c'), row.get('temperature_max_c')
    if (tmin is None) != (tmax is None) or (tmin is not None and
            not (type(tmin) in (int, float) and type(tmax) in (int, float) and
                 math.isfinite(tmin) and math.isfinite(tmax) and tmin < tmax)):
        quarantined.append({'sku': sku, 'field': 'temperature', 'reason': 'invalid_range', 'source_id': source_id})
        return
    frequencies = row.get('supported_frequency_hz') or []
    if not isinstance(frequencies, list) or any(type(x) is not int or x <= 0 for x in frequencies):
        quarantined.append({'sku': sku, 'field': 'frequency', 'reason': 'invalid_frequency', 'source_id': source_id})
        return
    if row.get('product_family') != 'centrifugal_pump':
        quarantined.append({'sku': sku, 'field': 'product_family', 'reason': 'unsupported_family', 'source_id': source_id})
        return
    products.append(ProductRecord(
        sku=sku, product_family=row['product_family'],
        flow_min_m3h=row['flow_min_m3h'], flow_max_m3h=row['flow_max_m3h'],
        head_min_m=row['head_min_m'], head_max_m=row['head_max_m'],
        material_raw=raw_material, material=material, material_mapping_version=mapping['version'],
        temperature_min_c=row.get('temperature_min_c'), temperature_max_c=row.get('temperature_max_c'),
        motor_power_kw=row.get('motor_power_kw'),
        supported_frequency_hz=tuple(frequencies),
        status=row['status'], standard_configuration=bool(row.get('standard_configuration', False)),
        source_id=source_id, source_version=source_version,
        extension_source_id=extension_source_id, owner=owner,
    ))
