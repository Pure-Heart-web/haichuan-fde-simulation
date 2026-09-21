"""Write model spans without prompts, bodies, raw outputs or direct identifiers."""
import hashlib
import json
from pathlib import Path
import threading

from fde_platform.core.models import utc_now
from fde_platform.onboarding.privacy import contains_direct_identifier


class ModelTelemetry:
    def __init__(self, path=None):
        self.path = Path(path) if path else None
        self.rows, self.lock = [], threading.Lock()
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, *, tenant_id, source_id, route, model, prompt_version,
               outcome, duration_ms, cost_usd, error_type=None):
        row = {'timestamp': utc_now(), 'span_name': 'gen_ai.extraction',
            'tenant_id': tenant_id,
            'source_hash': hashlib.sha256(source_id.encode()).hexdigest()[:16],
            'route': route, 'model': model, 'prompt_version': prompt_version,
            'outcome': outcome, 'duration_ms': round(duration_ms, 4),
            'cost_usd': cost_usd, 'error_type': error_type}
        if contains_direct_identifier(row):
            raise ValueError('模型遥测包含直接标识符')
        with self.lock:
            self.rows.append(row)
            if self.path:
                with self.path.open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps(row, ensure_ascii=False) + '\n')

    def summary(self):
        routes = {}
        for row in self.rows:
            routes[row['route']] = routes.get(row['route'], 0) + 1
        return {'span_count': len(self.rows), 'routes': routes,
                'raw_prompt_logged': False, 'raw_output_logged': False,
                'direct_identifier_rows': sum(contains_direct_identifier(x) for x in self.rows)}
