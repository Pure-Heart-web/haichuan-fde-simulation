"""Business-system context boundary; production adapters must keep customer-scoped semantics."""
from typing import Protocol

from .models import ContextItem


class ContextProvider(Protocol):
    def previous_order(self, customer_id: str, product_family: str = 'centrifugal_pump',
                       as_of: str = '2026-09-20') -> ContextItem | None: ...
