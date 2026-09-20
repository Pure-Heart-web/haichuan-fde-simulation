"""Local JSONL telemetry for reproducible extraction reviews."""
import json
from pathlib import Path

from .models import utc_now


def log_extraction(path, work_item, result, record=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {'time': utc_now(), 'event': 'extraction', 'trace_id': result.trace_id,
             'work_item_id': work_item.id, 'source_id': work_item.source_id,
             'prompt_version': result.prompt_version, 'model_version': result.model_version,
             'status': result.status, 'attempts': result.attempts, 'latency_ms': result.latency_ms,
             'error': result.error, 'raw_outputs': result.raw_outputs,
             'warnings': record.warnings if record else [],
             'needs_review': True}
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + '\n')
