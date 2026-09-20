"""Sprint 1 text extraction pipeline. It never sends mail or selects products."""
from .core.extraction import extract
from .core.models import ExtractionConfig
from .domains.foreign_trade.baseline import RegexBaselineProvider
from .domains.foreign_trade.normalization import DomainValidationError, to_record

PROMPT_VERSION = 'inquiry_extraction_v1'
MODEL_VERSION = RegexBaselineProvider.model_version


def process(work_item, provider=None):
    provider = provider or RegexBaselineProvider()
    config = ExtractionConfig(PROMPT_VERSION, getattr(provider, 'model_version', 'external-unversioned'))
    result = extract(work_item, provider, config)
    record = None
    if result.raw_fields is not None:
        try:
            record = to_record(work_item, result.raw_fields)
        except (DomainValidationError, TypeError, ValueError) as exc:
            result.status = 'failed'
            result.error = f'schema_or_domain_validation: {exc}'
    return result, record
