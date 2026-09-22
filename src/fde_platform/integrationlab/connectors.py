"""Read-only mailbox and CMMS contract sandboxes with resumable cursors."""
import hashlib
import json


class RateLimited(RuntimeError):
    pass


class ReadOnlyConnectorSandbox:
    ALLOWED = frozenset({'event_id', 'source_id', 'source_version', 'case_id',
                         'received_at', 'subject', 'body', 'asset_ref', 'kind'})

    def __init__(self, name, records, *, rate_limit_cursor=None):
        self.name = name
        self.records = list(records)
        self.rate_limit_cursor = rate_limit_cursor
        self.rate_limit_fired = False
        self.revoked = False
        self.write_attempts = 0

    def poll(self, cursor=0, limit=3):
        if self.revoked:
            raise PermissionError('connector_credential_revoked')
        if cursor == self.rate_limit_cursor and not self.rate_limit_fired:
            self.rate_limit_fired = True
            raise RateLimited('connector_429_retry_after')
        batch = self.records[cursor:cursor + limit]
        for record in batch:
            unexpected = set(record) - self.ALLOWED
            if unexpected:
                raise ValueError('connector_schema_drift:' + ','.join(sorted(unexpected)))
        return batch, cursor + len(batch)

    def write(self, *_args, **_kwargs):
        self.write_attempts += 1
        raise PermissionError('read_only_connector_forbids_customer_write')

    def revoke(self):
        self.revoked = True


def exercise_connectors(scenarios):
    accepted, duplicate, updated, retries = 0, 0, 0, 0
    negative_passed, negative_failed, customer_writes = 0, 0, 0
    seen_events, source_versions = {}, {}
    per_connector = {}
    for spec in scenarios['connectors']:
        connector = ReadOnlyConnectorSandbox(spec['name'], spec['records'],
            rate_limit_cursor=spec.get('rate_limit_cursor'))
        cursor = 0
        while cursor < len(connector.records):
            try:
                batch, cursor = connector.poll(cursor, limit=spec.get('page_size', 3))
            except RateLimited:
                retries += 1
                continue
            for record in batch:
                canonical = json.dumps(record, sort_keys=True, separators=(',', ':'))
                fingerprint = hashlib.sha256(canonical.encode()).hexdigest()
                old = seen_events.get(record['event_id'])
                if old:
                    if old != fingerprint:
                        raise ValueError('same_event_id_changed_content')
                    duplicate += 1
                    continue
                expected = source_versions.get(record['source_id'], 0) + 1
                if record['source_version'] != expected:
                    raise ValueError(f'connector_source_version_gap:expected_{expected}')
                seen_events[record['event_id']] = fingerprint
                source_versions[record['source_id']] = record['source_version']
                if record['source_version'] > 1:
                    updated += 1
                else:
                    accepted += 1
        try:
            connector.write({'unsafe': True})
        except PermissionError:
            negative_passed += 1
        else:
            negative_failed += 1
            customer_writes += 1
        connector.revoke()
        try:
            connector.poll(0)
        except PermissionError:
            negative_passed += 1
        else:
            negative_failed += 1
        drift = ReadOnlyConnectorSandbox(spec['name'] + '-drift',
            [dict(spec['records'][0], unexpected_field='blocked')])
        try:
            drift.poll()
        except ValueError:
            negative_passed += 1
        else:
            negative_failed += 1
        per_connector[spec['name']] = {'cursor_complete': cursor == len(connector.records),
            'rate_limit_retries': int(connector.rate_limit_fired), 'write_enabled': False}
    return {'status': 'CONNECTOR_LAB_PASSED' if negative_failed == 0 else
            'CONNECTOR_LAB_BLOCKED', 'created_events': accepted,
            'updated_events': updated, 'duplicate_events': duplicate,
            'rate_limit_retries': retries, 'negative_cases_passed': negative_passed,
            'negative_cases_failed': negative_failed, 'customer_writes': customer_writes,
            'connectors': per_connector, 'real_customer_systems_called': 0}
