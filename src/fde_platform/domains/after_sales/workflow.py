"""Qihang ticket → typed case → asset context → evidence/rules → internal review."""
import hashlib

from fde_platform.core.ingestion import from_text
from fde_platform.core.platform.contracts import ContextRequest, EntityRef
from fde_platform.core.pilot.models import ReviewTask
from .context import AssetContextProvider
from .diagnosis import diagnose
from .extraction import extract_service_case


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]


def process_service_case(case, session, *, use_context=True):
    if (session.tenant_id, session.domain) != ('qihang-training', 'after_sales'):
        raise ValueError('启航流程不能在其他租户运行')
    if case['source_type'] not in ('ticket', 'call_transcript', 'wechat_transcript'):
        raise ValueError('不支持的售后输入来源')
    work = from_text(case['text'], source_id=case['id'], tenant_id=session.tenant_id,
                     domain=session.domain, source_type=case['source_type'])
    extraction, service_case = extract_service_case(work)
    ref = EntityRef(session.tenant_id, session.domain, 'asset', service_case.serial_number or 'UNKNOWN')
    context = AssetContextProvider(session).get_context(ref, ContextRequest('maintenance_history', case['as_of']))
    recommendation, hits, provenance = diagnose(service_case, context, session,
                                                as_of=case['as_of'], use_context=use_context)
    trace_id = 'trace_' + _digest(session.tenant_id + '|' + case['id'])
    trace = {
        'trace_id': trace_id, 'tenant_id': session.tenant_id, 'domain': session.domain,
        'case_id': case['id'], 'mode': 'synthetic_internal_review',
        'input_digest': _digest(case['text']), 'raw_text_in_trace': False,
        'versions': {'work_item': 'shared-workitem-v2', 'extraction_runtime': 'core-json-v1',
                     'extraction_schema': 'qihang-service-case-v1',
                     'asset_data': context[0].source_version if context else 'no_matching_asset_context',
                     'knowledge': 'qihang-knowledge-sim-v1', 'rules': 'qihang-rules-sim-v1',
                     'ranking': 'qihang-diagnosis-v2-context-aware'},
        'stages': [
            {'stage': 'ingestion', 'status': 'ok', 'source_type': work.source_type},
            {'stage': 'extraction', 'status': extraction.status, 'model_version': extraction.model_version,
             'prompt_version': extraction.prompt_version, 'missing_fields': list(service_case.missing_fields)},
            {'stage': 'asset_context', 'status': 'ok' if context else 'not_found',
             'source_ids': [x.source_id for x in context]},
            {'stage': 'knowledge_retrieval', 'status': 'ok', 'document_ids': provenance['knowledge_ids'],
             'tenant_filter_applied_before_rank': True},
            {'stage': 'diagnostic_rules', 'status': 'ok', 'rule_ids': [x.rule_id for x in hits]},
            {'stage': 'recommendation', 'status': 'requires_review',
             'option_codes': [x.code for x in recommendation.options], 'risk': recommendation.risk_level},
        ],
        'observed_api_cost_usd': 0.0,
    }
    assignee_role = 'engineer' if recommendation.risk_level in ('high', 'critical') else 'support'
    assignee_id = 'engineer-chen' if assignee_role == 'engineer' else 'zhou'
    task = ReviewTask(f'{case["id"]}-REVIEW', case['id'], trace_id, 'service_guidance',
        recommendation.risk_level, assignee_role, assignee_id,
        {'device_model': service_case.device_model, 'serial_number': service_case.serial_number,
         'error_code': service_case.error_code, 'pressure_bar': service_case.current_pressure_bar,
         'maintenance_summary': context[0].facts['maintenance_summary'] if context else None,
         'top_option': recommendation.options[0].code,
         'options': [x.__dict__ for x in recommendation.options],
         'warnings': list(recommendation.warnings),
         'blocking_risk': recommendation.risk_level in ('high', 'critical'),
         'note': '仅供内部判断；审核动作不向客户发送维修指导，也不派工。'},
        {'trace_id': trace_id, 'knowledge_ids': provenance['knowledge_ids'],
         'rule_ids': [x.rule_id for x in hits], 'context_source_ids': [x.source_id for x in context]},
        tenant_id=session.tenant_id, domain=session.domain)
    session.put('work_item', work.id, work.to_dict())
    session.put('trace', trace_id, trace)
    session.put('recommendation', case['id'], {'tenant_id': session.tenant_id, 'domain': session.domain,
                                                'case_id': case['id'], **recommendation.to_dict()})
    session.put('review_task', task.task_id, task.to_dict())
    return {'work_item': work.to_dict(), 'service_case': service_case.to_dict(),
            'context': [x.to_dict() for x in context], 'recommendation': recommendation.to_dict(),
            'rule_hits': [x.__dict__ for x in hits], 'provenance': provenance,
            'trace': trace, 'review_task': task.to_dict()}
