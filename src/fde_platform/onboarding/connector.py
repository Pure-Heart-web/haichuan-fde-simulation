"""Versioned JSONL drop implements the same pull boundary as a real source connector."""
import json
from pathlib import Path


class JsonlDropConnector:
    def __init__(self, path, manifest):
        self.path = Path(path)
        self.manifest = manifest
        allowed = {x['source_type'] for x in manifest['authorized_sources']
                   if x.get('read_only') is True}
        if 'authorized_jsonl_drop' not in allowed:
            raise ValueError('客户清单未授权只读 JSONL Connector')

    def records(self):
        for number, line in enumerate(self.path.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip():
                continue
            event = json.loads(line)
            for key in ('event_id', 'source_id', 'source_version', 'received_at', 'tenant_id',
                        'domain', 'case_id', 'body', 'sender', 'company_name'):
                if event.get(key) in (None, ''):
                    raise ValueError(f'第 {number} 行缺少 {key}')
            if type(event['source_version']) is not int or event['source_version'] < 1:
                raise ValueError('来源版本必须是正整数')
            # Deliberately yield redeliveries. The durable data plane, rather than a
            # transient connector process, owns idempotency.
            yield event
