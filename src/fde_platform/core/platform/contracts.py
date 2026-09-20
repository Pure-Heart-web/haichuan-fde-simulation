"""Typed decision and context contracts, without a pump or repair ontology."""
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EntityRef:
    tenant_id: str
    domain: str
    entity_type: str
    entity_id: str


@dataclass(frozen=True)
class ContextRequest:
    kind: str
    as_of: str


@dataclass(frozen=True)
class ContextRecord:
    entity_ref: EntityRef
    kind: str
    source_id: str
    source_version: str
    effective_date: str
    facts: dict[str, Any]

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class CaseRecord:
    case_record_id: str
    tenant_id: str
    domain: str
    case_id: str
    kind: str
    source_event_id: str
    source_id: str
    status: str

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class DecisionOption:
    code: str
    label: str
    score_proxy: float
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True)
class Recommendation:
    options: tuple[DecisionOption, ...]
    actions: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    risk_level: str
    requires_review: bool
    confidence: float | None = None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class FeedbackEvent:
    event_id: str
    tenant_id: str
    domain: str
    task_id: str
    trace_id: str
    actor_id: str
    actor_role: str
    action: str
    reason: str
    created_at: str

    def to_dict(self):
        return asdict(self)
