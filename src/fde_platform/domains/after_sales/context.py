"""Asset context adapter behind the shared entity-reference interface."""
from datetime import date

from fde_platform.core.platform.contracts import ContextRecord


class AssetContextProvider:
    def __init__(self, session):
        self.session = session

    def get_context(self, entity_ref, request):
        if (entity_ref.tenant_id, entity_ref.domain) != (self.session.tenant_id, self.session.domain):
            raise ValueError('跨租户资产上下文请求被拒绝')
        if entity_ref.entity_type != 'asset' or request.kind != 'maintenance_history':
            raise ValueError('不支持的上下文类型')
        row = self.session.get('context', entity_ref.entity_id)
        if row is None:
            return ()
        cutoff = date.fromisoformat(request.as_of)
        history = [x for x in row['maintenance'] if x['status'] == 'completed' and
                   date.fromisoformat(x['date']) <= cutoff]
        history.sort(key=lambda x: x['date'], reverse=True)
        if not history:
            return ()
        latest = history[0]
        recent = (cutoff - date.fromisoformat(latest['date'])).days <= 7
        return (ContextRecord(entity_ref, request.kind, latest['work_order_id'], row['source_version'],
                              latest['date'], {'device_model': row['device_model'],
                                               'recent_maintenance': recent,
                                               'maintenance_summary': latest['summary']}),)
