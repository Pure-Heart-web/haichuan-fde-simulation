"""Typed domain record. Null means absent; no business default is inserted."""
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class InquiryRecord:
    work_item_id: str
    customer_name: str | None = None
    company_name: str | None = None
    country: str | None = None
    product_type: str | None = None
    quantity: int | None = None
    flow_m3h: float | None = None
    head_m: float | None = None
    medium_category: str | None = None
    medium_description: str | None = None
    temperature_c: float | None = None
    voltage_v: int | None = None
    frequency_hz: int | None = None
    application: str | None = None
    destination_port: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    extraction_confidence: float | None = None
    evidence: dict[str, dict[str, Any]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)
