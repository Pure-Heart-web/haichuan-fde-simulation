"""Customer-scoped, dated, completed-order retrieval. No name-based joins."""
import json
from datetime import date
from pathlib import Path

from fde_platform.core.context.models import ContextItem, CustomerEntity


class ContextError(ValueError):
    pass


class SimulatedContextProvider:
    def __init__(self, root):
        folder = Path(root) / 'stages/06-context-knowledge-reply/data'
        customers = json.loads((folder / 'customers.json').read_text(encoding='utf-8'))
        orders = json.loads((folder / 'orders.json').read_text(encoding='utf-8'))
        if customers['status'] != 'training_only' or orders['status'] != 'training_only':
            raise ContextError('仅允许模拟身份与订单源')
        self.entities = tuple(CustomerEntity(x['customer_id'], x['canonical_name'], tuple(x['aliases']),
                                             tuple(x['domains']), tuple(x['contacts']), x.get('country'))
                              for x in customers['customers'])
        ids = [x.customer_id for x in self.entities]
        if len(ids) != len(set(ids)):
            raise ContextError('重复 customer_id')
        self.orders = orders['orders']
        self.source_id = orders['source_id']
        self.version = orders['version']
        seen = set()
        for order in self.orders:
            if order['order_id'] in seen or order['customer_id'] not in ids:
                raise ContextError('订单 ID 重复或 customer_id 无效')
            seen.add(order['order_id'])
            date.fromisoformat(order['order_date'])

    def previous_order(self, customer_id, product_family='centrifugal_pump', as_of='2026-09-20'):
        if customer_id not in {x.customer_id for x in self.entities}:
            raise ContextError('未知 customer_id')
        cutoff = date.fromisoformat(as_of)
        matches = [x for x in self.orders if x['customer_id'] == customer_id and
                   x['status'] == 'completed' and x['product_family'] == product_family and
                   date.fromisoformat(x['order_date']) <= cutoff]
        if not matches:
            return None
        matches.sort(key=lambda x: x['order_date'], reverse=True)
        if len(matches) > 1 and matches[0]['order_date'] == matches[1]['order_date']:
            raise ContextError('同日多笔最近相关已完成订单，必须人工确认')
        row = matches[0]
        return ContextItem('previous_order', customer_id,
                           {k: row[k] for k in ('sku', 'quantity', 'voltage_v', 'frequency_hz', 'status')},
                           'simulated_order_store', row['order_id'], self.version,
                           row['order_date'], 'most_recent_completed_relevant_order')
