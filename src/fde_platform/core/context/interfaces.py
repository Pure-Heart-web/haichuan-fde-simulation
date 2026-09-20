"""Business-system context boundary; production adapters must keep customer-scoped semantics."""
from typing import Protocol

from .models import ContextItem
from fde_platform.core.platform.contracts import ContextRecord, ContextRequest, EntityRef


class ContextProvider(Protocol):
    def previous_order(self, customer_id: str, product_family: str = 'centrifugal_pump',
                       as_of: str = '2026-09-20') -> ContextItem | None: ...


class ScopedContextProvider(Protocol):
    """Cross-domain context contract; implementations must enforce tenant scope."""
    def get_context(self, entity_ref: EntityRef, request: ContextRequest) -> tuple[ContextRecord, ...]: ...
