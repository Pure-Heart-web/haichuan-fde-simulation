"""Allowlist and redaction pipeline shaped like an OTLP Collector processor."""
import hashlib
import json
from pathlib import Path

from fde_platform.onboarding.privacy import contains_direct_identifier


class LabCollector:
    ALLOWED = frozenset({'service.name', 'event.type', 'outcome', 'duration_ms',
                         'tenant.hash', 'connector.name', 'gate.status'})
    FORBIDDEN = frozenset({'prompt', 'body', 'content', 'model.output', 'tool.arguments'})

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.exported, self.dropped_attributes = [], 0

    def export(self, name, trace_id, attributes):
        clean = {}
        for key, value in attributes.items():
            if key in self.ALLOWED and not contains_direct_identifier(value):
                clean[key] = value
            else:
                self.dropped_attributes += 1
        row = {'name': name, 'trace_id': hashlib.sha256(trace_id.encode()).hexdigest()[:32],
               'attributes': clean}
        if contains_direct_identifier(row):
            raise ValueError('脱敏后的遥测仍含直接标识符')
        self.exported.append(row)
        return row

    def flush(self):
        self.path.write_text('\n'.join(json.dumps(row, ensure_ascii=False)
            for row in self.exported) + ('\n' if self.exported else ''), encoding='utf-8')
        return {'status': 'OTLP_LAB_PIPELINE_PASSED', 'span_count': len(self.exported),
                'dropped_attribute_count': self.dropped_attributes,
                'direct_identifier_rows': sum(contains_direct_identifier(x)
                    for x in self.exported), 'raw_content_exported': any(
                    key in self.FORBIDDEN for row in self.exported
                    for key in row['attributes']), 'real_otlp_backend_used': False}
