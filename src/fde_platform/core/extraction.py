"""Generic JSON extraction orchestration with one bounded parse retry."""
import json
import time
from typing import Protocol
from uuid import uuid4

from .models import ExtractionConfig, ExtractionResult, WorkItem


class Provider(Protocol):
    def complete(self, work_item: WorkItem, prompt_version: str) -> str:
        """Return JSON text containing raw extracted fields and evidence."""


def extract(work_item: WorkItem, provider: Provider, config: ExtractionConfig) -> ExtractionResult:
    if config.max_parse_retries < 0 or config.max_parse_retries > 1:
        raise ValueError('演练版本只允许 0 或 1 次解析重试')
    trace_id = uuid4().hex
    outputs = []
    start = time.perf_counter()
    last_error = None
    for attempt in range(1, config.max_parse_retries + 2):
        try:
            raw = provider.complete(work_item, config.prompt_version)
            outputs.append(raw)
            fields = json.loads(raw)
            if not isinstance(fields, dict):
                raise ValueError('抽取结果必须为 JSON 对象')
            return ExtractionResult(work_item.id, 'extracted', fields, attempt, trace_id,
                                    config.prompt_version, config.model_version, outputs,
                                    latency_ms=(time.perf_counter() - start) * 1000)
        except (ValueError, TypeError, OSError, RuntimeError) as exc:
            last_error = str(exc)
    return ExtractionResult(work_item.id, 'failed', None, attempt, trace_id,
                            config.prompt_version, config.model_version, outputs,
                            error=last_error, latency_ms=(time.perf_counter() - start) * 1000)
