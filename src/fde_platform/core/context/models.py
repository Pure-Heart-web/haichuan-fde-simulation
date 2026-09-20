from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class CustomerEntity:
    customer_id: str
    canonical_name: str
    aliases: tuple[str, ...]
    domains: tuple[str, ...]
    contacts: tuple[str, ...]
    country: str | None


@dataclass(frozen=True)
class IdentityResolution:
    status: str
    customer_id: str | None
    method: str
    candidate_ids: tuple[str, ...]
    evidence: str | None

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ContextItem:
    type: str
    entity_id: str
    data: dict
    source: str
    source_id: str
    source_version: str
    timestamp: str | None
    relevance_reason: str

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class ResolvedField:
    field: str
    value: object
    source_type: str
    source_ref: str | None
    confidence: float | None

    def to_dict(self):
        return asdict(self)
