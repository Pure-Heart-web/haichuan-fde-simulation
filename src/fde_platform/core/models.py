"""Contracts shared by adapters and domain code."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@dataclass(frozen=True)
class WorkItem:
    id: str
    tenant_id: str
    source_type: str
    source_id: str
    sender: str
    subject: str
    body: str
    attachments: list[dict[str, str]]
    received_at: str | None
    body_format: str = 'text'
    domain: str = 'foreign_trade'

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ExtractionConfig:
    prompt_version: str
    model_version: str
    max_parse_retries: int = 1


@dataclass
class ExtractionResult:
    work_item_id: str
    status: str
    raw_fields: dict[str, Any] | None
    attempts: int
    trace_id: str
    prompt_version: str
    model_version: str
    raw_outputs: list[str] = field(default_factory=list)
    error: str | None = None
    latency_ms: float | None = None

    def to_dict(self):
        return asdict(self)
