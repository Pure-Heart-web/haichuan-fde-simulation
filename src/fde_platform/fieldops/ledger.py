"""Append-only field-operations ledger with role-gated event types."""
import hashlib
import json
from pathlib import Path

from fde_platform.core.models import utc_now


ALLOWED = {
    'shift_start': {'operator'}, 'queue_check': {'operator', 'auditor'},
    'incident_declared': {'operator'}, 'canary_stopped': {'operator'},
    'baseline_restored': {'operator'}, 'incident_resolved': {'operator'},
    'shift_handoff': {'operator'}, 'shift_end': {'operator'},
    'pilot_reviewed': {'auditor'},
}


class FieldOpsLedger:
    def __init__(self, path, tenant_id):
        self.path, self.tenant_id = Path(path), tenant_id
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def events(self):
        if not self.path.exists():
            return []
        rows = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]
        previous = 'GENESIS'
        for index, row in enumerate(rows, 1):
            supplied = row.pop('event_sha256', None)
            expected = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True,
                separators=(',', ':')).encode()).hexdigest()
            row['event_sha256'] = supplied
            if (supplied != expected or row.get('sequence') != index or
                    row.get('previous_sha256') != previous or
                    row.get('tenant_id') != self.tenant_id):
                raise ValueError('现场运营事件链损坏')
            previous = supplied
        return rows

    def append(self, actor_id, role, event_type, detail, *, shift_id, incident_id=None):
        if role not in ALLOWED.get(event_type, set()) or not actor_id or not detail.strip():
            raise ValueError('现场运营事件角色或内容无效')
        rows = self.events()
        event = {'sequence': len(rows) + 1,
            'previous_sha256': rows[-1]['event_sha256'] if rows else 'GENESIS',
            'tenant_id': self.tenant_id, 'actor_id': actor_id, 'role': role,
            'event_type': event_type, 'detail': detail.strip(), 'shift_id': shift_id,
            'incident_id': incident_id, 'created_at': utc_now()}
        event['event_sha256'] = hashlib.sha256(json.dumps(event, ensure_ascii=False,
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + '\n')
        return event

    def summary(self):
        rows = self.events()
        kinds = {}
        for row in rows:
            kinds[row['event_type']] = kinds.get(row['event_type'], 0) + 1
        shifts = {x['shift_id'] for x in rows}
        incident_ids = {x['incident_id'] for x in rows if x['incident_id']}
        resolved = {x['incident_id'] for x in rows if x['event_type'] == 'incident_resolved'}
        return {'event_count': len(rows), 'shift_count': len(shifts), 'event_types': kinds,
                'incident_count': len(incident_ids),
                'all_incidents_resolved': incident_ids == resolved,
                'hash_chain_valid': True,
                'handoff_count': kinds.get('shift_handoff', 0)}
