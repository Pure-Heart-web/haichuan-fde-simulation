"""Domain diagnosis and safety policy; output remains internal decision support."""
from fde_platform.core.platform.contracts import DecisionOption, Recommendation
from fde_platform.core.platform.runtime import ScopedKnowledgeIndex, evaluate_rules

ALLOWED_FIELDS = frozenset({'error_code', 'abnormal_noise', 'temperature_c', 'electrical_cabinet',
                            'pressure_vessel', 'asset_known'})
ALLOWED_ACTIONS = frozenset({'block_remote_guidance', 'engineer_review',
                             'consider_safe_shutdown_sop', 'verify_asset_identity'})
SEVERITY = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}


def diagnose(service_case, context_records, session, *, as_of, use_context=True):
    asset = context_records[0] if context_records else None
    asset_known = bool(asset and asset.facts['device_model'] == service_case.device_model)
    recent = bool(use_context and asset_known and asset.facts['recent_maintenance'])
    facts = {'error_code': service_case.error_code,
             'abnormal_noise': service_case.abnormal_noise,
             'temperature_c': service_case.temperature_c,
             'electrical_cabinet': service_case.electrical_cabinet,
             'pressure_vessel': service_case.pressure_vessel,
             'asset_known': asset_known}
    hits = evaluate_rules(facts, session.list('rule'), allowed_fields=ALLOWED_FIELDS,
                          allowed_actions=ALLOWED_ACTIONS, as_of=as_of)
    risk = max((hit.severity for hit in hits), key=lambda x: SEVERITY[x], default='low')
    knowledge = ScopedKnowledgeIndex(session)
    e37 = knowledge.retrieve(intent='e37', as_of=as_of, model=service_case.device_model)
    maint = knowledge.retrieve(intent='recent_maintenance', as_of=as_of, model=service_case.device_model)
    safety = knowledge.retrieve(intent='safety', as_of=as_of, model=service_case.device_model)
    options = []
    if not asset_known:
        options.append(DecisionOption('verify_asset_identity', '核对设备序列号及档案后再诊断', .99,
                                      ('SIM-ASSET-IDENTITY-POLICY',)))
    else:
        if recent and service_case.error_code == 'E37' and maint:
            options.append(DecisionOption('review_maintenance_work_order',
                '请工程师先核对近期保养工单与装配记录', .90,
                (asset.source_id, maint[0]['document_id'])))
        if service_case.error_code == 'E37' and e37:
            options.append(DecisionOption('inspect_intake_condition',
                '由工程师核查进气条件与滤芯状态', .70, (e37[0]['document_id'],)))
        if (service_case.electrical_cabinet or service_case.pressure_vessel or
            service_case.temperature_c is not None and service_case.temperature_c >= 95) and safety:
            options.append(DecisionOption('engineer_safety_review',
                '停止自动指导，交工程师按安全 SOP 评估', .85, (safety[0]['document_id'],)))
        if not options:
            options.append(DecisionOption('collect_diagnostic_details',
                '收集报警码、运行读数与维护记录供人工诊断', .50, ()))
    options.sort(key=lambda x: -x.score_proxy)
    actions = sorted({action for hit in hits for action in hit.actions})
    warnings = []
    if risk in ('high', 'critical'):
        warnings.append('高风险：禁止自动客户维修指导，需工程师确认')
    if not asset_known:
        warnings.append('设备身份未确认，不能使用历史档案推断')
    if service_case.error_code == 'E37' and not e37:
        warnings.append('缺少当前有效故障码证据，必须人工核实')
    refs = sorted({ref for option in options for ref in option.evidence_refs} |
                  {ref for hit in hits for ref in hit.evidence_refs})
    return Recommendation(tuple(options), tuple(actions), tuple(warnings), tuple(refs),
                          risk, True), hits, {'asset_known': asset_known, 'recent_maintenance_used': recent,
                                             'knowledge_ids': [x['document_id'] for x in (*e37, *maint, *safety)]}
