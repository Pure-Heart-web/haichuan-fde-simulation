"""Deterministic unit conversion and domain validation."""
import math

from .schema import InquiryRecord


class DomainValidationError(ValueError):
    pass


def positive(value, name):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise DomainValidationError(f'{name} 必须大于 0')
    return number


def integral(value, name):
    number = positive(value, name)
    if not number.is_integer():
        raise DomainValidationError(f'{name} 必须为整数')
    return int(number)


def normalize_flow(value, unit):
    amount = positive(value, 'flow')
    canonical = (unit or '').lower().replace('³', '3')
    if canonical in ('m3/h', 'cmh', 'cubic meters per hour'):
        return round(amount, 4)
    if canonical in ('l/min', 'liters per minute'):
        return round(amount * 0.06, 4)
    raise DomainValidationError(f'不支持的流量单位：{unit}')


def normalize_temperature(value, unit):
    amount = float(value)
    if not math.isfinite(amount):
        raise DomainValidationError('temperature 必须是有限数字')
    canonical = (unit or '').lower().replace('°', '')
    if canonical in ('c', 'degrees celsius'):
        return round(amount, 3)
    if canonical in ('f', 'degrees fahrenheit'):
        return round((amount - 32) * 5 / 9, 3)
    raise DomainValidationError(f'不支持的温度单位：{unit}')


def _value(raw, key):
    item = raw.get(key)
    if item is None:
        return None
    if not isinstance(item, dict) or 'value' not in item:
        raise DomainValidationError(f'{key} 需要包含 value 与原文证据')
    return item


def to_record(work_item, raw):
    if not isinstance(raw, dict):
        raise DomainValidationError('抽取结果必须是对象')
    record = InquiryRecord(work_item_id=work_item.id)
    conversions = {
        'flow': ('flow_m3h', lambda x: normalize_flow(x['value'], x.get('unit'))),
        'head': ('head_m', lambda x: positive(x['value'], 'head')),
        'temperature': ('temperature_c', lambda x: normalize_temperature(x['value'], x.get('unit'))),
        'quantity': ('quantity', lambda x: integral(x['value'], 'quantity')),
        'voltage': ('voltage_v', lambda x: integral(x['value'], 'voltage')),
        'frequency': ('frequency_hz', lambda x: integral(x['value'], 'frequency')),
    }
    for key, (target, convert) in conversions.items():
        item = _value(raw, key)
        if item:
            setattr(record, target, convert(item))
            record.evidence[target] = _evidence(work_item, item)
    product = _value(raw, 'product_type')
    if product:
        text = str(product['value']).lower()
        record.product_type = ('centrifugal_pump' if 'centrifugal' in text or '离心' in text else
                               'wastewater_pump' if 'wastewater' in text else
                               'seawater_pump' if 'seawater' in text else 'pump')
        record.evidence['product_type'] = _evidence(work_item, product)
    medium = _value(raw, 'medium')
    if medium:
        text = str(medium['value']).lower().strip()
        record.medium_description = text
        record.medium_category = ('seawater' if 'seawater' in text or '海水' in text else
                                  'chemical' if 'chemical' in text or '化工' in text else
                                  'wastewater' if 'wastewater' in text or '污水' in text else
                                  'water' if 'water' in text or '淡水' in text or '冷却水' in text else 'other')
        record.evidence['medium_description'] = _evidence(work_item, medium)
    for key in ('application', 'destination_port'):
        item = _value(raw, key)
        if item:
            setattr(record, key, str(item['value']).strip())
            record.evidence[key] = _evidence(work_item, item)
    if record.frequency_hz is not None and record.frequency_hz not in (50, 60):
        record.warnings.append('frequency_unusual_review')
    if record.voltage_v is not None and not 100 <= record.voltage_v <= 1000:
        record.warnings.append('voltage_outside_training_range_review')
    if record.medium_description in (None, 'water') and record.product_type and 'previous order' not in work_item.body.lower() and 'last order' not in work_item.body.lower():
        record.missing_fields.append('medium_detail')
    if not record.flow_m3h and not record.head_m and 'previous order' not in work_item.body.lower() and 'last order' not in work_item.body.lower() and not any(s in work_item.body for s in ('SIM-', 'CP90')):
        record.missing_fields.extend(['flow_m3h', 'head_m'])
    if work_item.attachments:
        record.missing_fields.append('attachment_processing_required')
    elif 'attached' in work_item.body.lower() or 'attachment' in work_item.body.lower():
        record.warnings.append('referenced_attachment_not_available')
    record.missing_fields = list(dict.fromkeys(record.missing_fields))
    return record


def _evidence(work_item, item):
    start, end = item.get('start'), item.get('end')
    text = item.get('text')
    if not (isinstance(start, int) and isinstance(end, int) and
            0 <= start < end <= len(work_item.body) and
            work_item.body[start:end] == text):
        raise DomainValidationError('字段证据必须准确指向邮件原文')
    return {'source_id': work_item.source_id, 'start': start, 'end': end, 'text': text,
            'origin': 'extracted', 'raw_unit': item.get('unit')}
