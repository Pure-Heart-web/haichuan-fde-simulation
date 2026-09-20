"""One explicit bridge; product ranking remains in the foreign-trade domain."""
import hashlib

from fde_platform.core.ingestion import from_text
from fde_platform.core.platform.contracts import DecisionOption, Recommendation
from fde_platform.core.pilot.models import ReviewTask
from fde_platform.core.knowledge.retrieval import KnowledgeIndex
from fde_platform.domains.foreign_trade.context.provider import SimulatedContextProvider
from fde_platform.domains.foreign_trade.pilot.orchestration import simulate_case
from fde_platform.domains.foreign_trade.recommendation.service import load_components


def bridge_haichuan(case, session, root):
    if (session.tenant_id, session.domain) != ('haichuan-training', 'foreign_trade'):
        raise ValueError('海川适配器不能在其他租户运行')
    artifact, old_trace = simulate_case(case, root=root, provider=SimulatedContextProvider(root),
                                         index=KnowledgeIndex(root), products=load_components(root))
    old_rec = artifact['recommendation'] or {}
    options = tuple(DecisionOption(x['sku'], '需销售/工程师核实的暂定产品候选',
                                   x['score'], tuple(old_rec.get('source_ids', ())))
                    for x in old_rec.get('candidates', ()))
    recommendation = Recommendation(options, ('sales_review',), tuple(old_rec.get('warnings', ())),
                                    tuple(old_rec.get('source_ids', ())), 'low', True)
    work = from_text(case['text'], source_id=case['id'], tenant_id=session.tenant_id,
                     domain=session.domain, sender=case['sender'])
    trace_id = 'trace_' + hashlib.sha256((session.tenant_id + '|' + case['id']).encode()).hexdigest()[:16]
    trace = {'trace_id': trace_id, 'tenant_id': session.tenant_id, 'domain': session.domain,
             'case_id': case['id'], 'mode': 'synthetic_adapter',
             'input_digest': old_trace['input_digest'], 'raw_text_in_trace': False,
             'versions': old_trace['versions'], 'candidate_ids': [x.code for x in options],
             'legacy_trace_id': old_trace['trace_id'], 'observed_api_cost_usd': 0.0}
    task = ReviewTask(case['id'] + '-PLATFORM-REVIEW', case['id'], trace_id, 'sales_draft', 'low',
                      'sales', 'linda',
                      {'candidate_skus': [x.code for x in options], 'blocking_risk': False,
                       'note': '仅教学审核，不发送邮件或报价'},
                      {'legacy_trace_id': old_trace['trace_id']}, tenant_id=session.tenant_id,
                      domain=session.domain)
    session.put('work_item', work.id, work.to_dict())
    session.put('trace', trace_id, trace)
    session.put('recommendation', case['id'], {'tenant_id': session.tenant_id, 'domain': session.domain,
                                                'case_id': case['id'], **recommendation.to_dict()})
    session.put('review_task', task.task_id, task.to_dict())
    return {'trace': trace, 'recommendation': recommendation.to_dict(), 'review_task': task.to_dict()}
