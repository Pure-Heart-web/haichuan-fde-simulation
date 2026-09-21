"""Read-only migration of Stage 7's single-tenant queue into scoped artifacts."""
from fde_platform.core.pilot.store import PilotStore


def migrate_stage7(source_path, session):
    if (session.tenant_id, session.domain) != ('haichuan-training', 'foreign_trade'):
        raise ValueError('Stage 7 来源只能迁入海川外贸租户')
    old = PilotStore(source_path)
    try:
        traces = old.list_traces()
        tasks = old.list_tasks(actor_id='admin', role='admin')
        events = old.events()
        for row in traces:
            trace = old.get_trace(row['case_id'])
            session.put('legacy_trace', trace['trace_id'],
                        {**trace, 'tenant_id': session.tenant_id, 'domain': session.domain,
                         'migration_mode': 'read_only_archive'})
        for task in tasks:
            session.put('legacy_review_task', task['task_id'],
                        {**task, 'tenant_id': session.tenant_id, 'domain': session.domain,
                         'migration_mode': 'read_only_archive'})
        for event in events:
            event_id = 'S7-EVENT-' + str(event['id'])
            session.put('legacy_review_event', event_id,
                        {**event, 'event_id': event_id, 'tenant_id': session.tenant_id,
                         'domain': session.domain, 'migration_mode': 'read_only_archive'})
        return {'traces': len(traces), 'tasks': len(tasks), 'events': len(events),
                'mode': 'read_only_archive', 'source_unchanged': True}
    finally:
        old.close()


def scoped_export(store, broker, token, tenant_id, domain):
    broker.verify(token, tenant_id=tenant_id)
    session = store.scope(tenant_id, domain)
    return {kind: session.list(kind) for kind in
            ('legacy_trace', 'legacy_review_task', 'legacy_review_event')}
