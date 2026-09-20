"""Typed service case; missing identity and readings remain explicit unknowns."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ServiceCase:
    work_item_id: str
    device_model: str | None
    serial_number: str | None
    error_code: str | None
    current_pressure_bar: float | None
    normal_pressure_bar: float | None
    temperature_c: float | None
    abnormal_noise: bool
    electrical_cabinet: bool
    pressure_vessel: bool
    recent_maintenance_reported: bool
    symptoms: tuple[str, ...]
    missing_fields: tuple[str, ...]

    @classmethod
    def from_fields(cls, work_item_id, fields):
        if not isinstance(fields, dict):
            raise ValueError('售后抽取结果必须为对象')
        numbers = ('current_pressure_bar', 'normal_pressure_bar', 'temperature_c')
        for key in numbers:
            value = fields.get(key)
            if value is not None and (type(value) not in (int, float) or value < 0):
                raise ValueError(f'{key} 必须为非负数字或未知')
        missing = tuple(key for key in ('device_model', 'serial_number', 'error_code', 'current_pressure_bar')
                        if fields.get(key) is None)
        return cls(work_item_id, fields.get('device_model'), fields.get('serial_number'),
                   fields.get('error_code'), fields.get('current_pressure_bar'),
                   fields.get('normal_pressure_bar'), fields.get('temperature_c'),
                   bool(fields.get('abnormal_noise')), bool(fields.get('electrical_cabinet')),
                   bool(fields.get('pressure_vessel')), bool(fields.get('recent_maintenance_reported')),
                   tuple(fields.get('symptoms', ())), missing)

    def to_dict(self):
        return asdict(self)
