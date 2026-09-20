"""Audit traceability and boundaries; this is not a product evaluation."""
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

STAGE2_FILES = [
    '01-problem-brief.md', '02-as-is-workflow.md', '03-bottleneck-map.md',
    '04-decision-map.md', '05-mvp-candidate.md', '06-exit-and-handoff.md',
]
STAGE3_FILES = [f'{i:02}-{name}.md' for i, name in enumerate([
    'data-inventory', 'source-of-truth', 'identity-and-rules', 'security',
    'ai-boundary', 'architecture', 'data-contracts', 'golden-dataset',
    'release-gate', 'stage-4-handoff'], 1)]
CONTRACT_FIELDS = {
    'WorkItem': ['id', 'tenant_id', 'source_type', 'source_id', 'sender', 'subject', 'body', 'attachments', 'received_at'],
    'InquiryRecord': ['work_item_id', 'customer_name', 'customer_id', 'product_type', 'quantity', 'flow_m3h', 'head_m', 'medium', 'temperature_c', 'voltage', 'frequency', 'application', 'destination_port', 'missing_fields', 'extraction_confidence', 'evidence'],
    'ProductCandidate': ['sku', 'match_score', 'matched_conditions', 'warnings', 'rule_results', 'requires_engineer_review', 'evidence'],
    'Recommendation': ['id', 'inquiry_id', 'candidate_products', 'preferred_candidate', 'reasoning_summary', 'missing_information', 'risk_level', 'required_reviewer', 'evidence'],
    'ReviewTask': ['id', 'work_item_id', 'recommendation_id', 'review_type', 'assignee_role', 'status', 'decision', 'edits', 'comment'],
}


class AuditError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise AuditError(message)


def read(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise AuditError(f'无法读取 {path}: {exc}') from exc


def report_stage2(root):
    base = Path(root) / 'stages/02-discovery'
    missing = [name for name in STAGE2_FILES if not (base / 'deliverables' / name).is_file()]
    need(not missing, 'Stage 2 缺少交付物：' + ', '.join(missing))
    notes = (base / 'data/meeting-record.md').read_text(encoding='utf-8')
    ids = set(re.findall(r'S2-E\d{2}', notes))
    need(len(ids) >= 10, 'Stage 2 证据台账少于 10 条')
    for name in STAGE2_FILES:
        content = (base / 'deliverables' / name).read_text(encoding='utf-8')
        refs = set(re.findall(r'S2-E\d{2}', content))
        need(refs <= ids, f'{name} 存在悬空证据引用：{sorted(refs - ids)}')
    return {'status': 'STAGE2_READY_FOR_DATA_DISCOVERY', 'deliverable_count': len(STAGE2_FILES),
            'evidence_count': len(ids), 'caveat': '仅检查模拟资料完整性，计时与损失主张未验证。'}


def report_stage3(root, data_dir=None):
    base = Path(data_dir) if data_dir else Path(root) / 'stages/03-data-boundary/data'
    docs = Path(root) / 'stages/03-data-boundary/deliverables'
    missing = [name for name in STAGE3_FILES if not (docs / name).is_file()]
    need(not missing, 'Stage 3 缺少交付物：' + ', '.join(missing))
    manifest = read(base / 'manifest.json')
    golden = read(base / 'golden.json')
    orders = read(base / 'bundle/orders/orders.json')
    special = read(base / 'bundle/special_cases.json')
    conflicts = read(base / 'conflicts.json')
    identities = read(base / 'identity.json')
    truth = read(base / 'source-of-truth.json')
    rules = read(base / 'rules.json')
    contracts = read(base / 'contract-examples.json')
    need(manifest.get('mode') == golden.get('mode') == 'simulation', '演练包必须明确标为 simulation')
    need(manifest.get('dataset_id') == golden.get('dataset_id'), 'manifest 与 golden 数据集 ID 不一致')
    sources = manifest.get('sources')
    need(isinstance(sources, list) and len(sources) >= 10, '来源清单不完整')
    source_ids = set()
    for item in sources:
        need(isinstance(item, dict), '来源必须为对象')
        for field in ('id', 'path', 'kind', 'owner', 'version', 'sensitivity', 'model_context'):
            need(bool(item.get(field)), f'来源缺少 {field}: {item}')
        need(item['id'] not in source_ids, f'重复来源 ID: {item["id"]}')
        source_ids.add(item['id'])
        path = (base / item['path']).resolve()
        need(path.is_relative_to(base.resolve()) and path.exists(), f'来源路径不存在或越界: {item["path"]}')
        if item['sensitivity'] == 'Highly Sensitive':
            need(item['model_context'] == 'prohibited', f'高敏感来源不能进入模型上下文: {item["id"]}')
        if item['kind'] == 'Tacit Knowledge':
            need(item['model_context'] == 'prohibited_until_verified', '原始聊天不能直接作为权威模型上下文')
    need({'SRC-TECH', 'SRC-MASTER', 'SRC-DISC', 'SRC-CHAT', 'SRC-QUOTE'} <= source_ids, '关键来源缺失')
    source_by_id = {item['id']: item for item in sources}
    need(source_by_id['SRC-DISC']['sensitivity'] == 'Highly Sensitive' and
         source_by_id['SRC-DISC']['model_context'] == 'prohibited', '特价来源必须高敏感且禁止进入模型上下文')
    need(source_by_id['SRC-QUOTE']['model_context'] == 'prohibited_in_v1', '标准报价在 V1 必须隔离于模型上下文')
    cases = golden.get('cases')
    need(isinstance(cases, list) and len(cases) == 20, 'Golden Dataset 应有 20 个案例')
    categories = Counter()
    case_ids = set()
    for case in cases:
        case_id = case.get('id')
        need(isinstance(case_id, str) and re.fullmatch(r'E-\d{3}', case_id), f'案例 ID 无效: {case_id}')
        need(case_id not in case_ids, f'重复案例 ID: {case_id}')
        case_ids.add(case_id)
        categories[case.get('category')] += 1
        number = case_id[-3:]
        for kind in ('inquiry', 'reply'):
            path = case.get(f'{kind}_path')
            folder = 'inquiries' if kind == 'inquiry' else 'replies'
            need(path == f'bundle/{folder}/{kind}_{number}.eml', f'{case_id} {kind} 路径或配对错误')
            need((base / path).is_file(), f'{case_id} {kind} 邮件不存在')
            email = (base / path).read_text(encoding='utf-8')
            need('X-Training-Only: true' in email and '\n\n' in email, f'{case_id} {kind} 不符合合成邮件格式')
        need(isinstance(case.get('expected_extraction'), dict), f'{case_id} 缺提取标签')
        need(isinstance(case.get('expected_missing'), list), f'{case_id} 缺缺口标签')
        need(case.get('expected_action') in {'CLARIFY_MEDIUM', 'VERIFY_ORDER', 'ENGINEER_REVIEW', 'PRICE_REVIEW', 'REVIEW_DRAFT'}, f'{case_id} 安全动作无效')
        need(case.get('preferred_candidate') is None and case.get('review_required') is True,
             f'{case_id} 不能设未批准的最终型号或免除人工复核')
    need(categories == {'normal': 10, 'complex': 5, 'history': 3, 'failure': 2}, f'案例分层不符: {dict(categories)}')
    by_case_id = {case['id']: case for case in cases}
    need({'E-001', 'E-002', 'E-003'} <= case_ids, '关键评估案例 E-001 至 E-003 缺失')
    need(by_case_id['E-001']['expected_action'] == 'CLARIFY_MEDIUM' and
         'medium_detail' in by_case_id['E-001']['expected_missing'], 'E-001 必须保留介质澄清动作')
    need(by_case_id['E-002']['expected_action'] == 'VERIFY_ORDER' and
         by_case_id['E-003']['expected_action'] == 'ENGINEER_REVIEW', '历史订单和海水案例安全动作错误')
    need(isinstance(orders, list) and len(orders) >= 10, '需要至少 10 个订单')
    need(len({o['order_id'] for o in orders}) == len(orders), '订单 ID 重复')
    need(isinstance(special, list) and len(special) >= 5, '需要至少 5 个特殊案例')
    need(all(x.get('inquiry_id') in case_ids for x in special), '特殊案例引用不存在的询盘')
    need(isinstance(conflicts, list) and conflicts, '冲突台账为空')
    for conflict in conflicts:
        need(set(conflict['source_ids']) <= source_ids, '冲突来源引用不存在')
        need(conflict.get('decision_owner') and conflict.get('status') and conflict.get('residual_risk'), '冲突缺少 Owner、状态或剩余风险')
    product_a = {r['sku']: r for r in read(base / 'bundle/products/Pump_Selection_NEW.json')}
    product_b = {r['sku']: r for r in read(base / 'bundle/products/Product_Master_Final_v2.json')}
    need('CP90' in product_a and 'CP90' in product_b, 'CP90 冲突案例不存在')
    differing = {k for k in ('flow_min', 'flow_max', 'head_min', 'head_max', 'material') if product_a['CP90'][k] != product_b['CP90'][k]}
    need(differing <= set(conflicts[0]['fields']), f'D-001 未记录字段冲突: {sorted(differing - set(conflicts[0]["fields"]))}')
    need(identities.get('status') == 'provisional', '模拟身份映射须保持暂定')
    need(all(e.get('autolink_allowed') is False for e in identities.get('entities', [])), '暂定客户身份不允许自动关联')
    need(isinstance(truth, list) and len(truth) >= 5, '权威来源注册表不完整')
    need(all(item.get('source_id') is None or item['source_id'] in source_ids for item in truth), '权威来源引用不存在')
    need(any(item['domain'] == 'technical_product_parameters' and item['source_id'] == 'SRC-TECH' for item in truth), '技术参数权威来源未指定')
    need(any(item['domain'] == 'special_discount' and item['status'] == 'human_only' for item in truth), '特价必须由人处理')
    need(isinstance(rules, list) and len(rules) >= 3, '规则台账不完整')
    need(all(set(r.get('source_ids', [])) <= source_ids for r in rules), '规则来源引用不存在')
    need(all(r.get('status') in ('candidate', 'verified_in_simulation', 'retired') for r in rules), '规则状态无效')
    need(any(r['status'] == 'candidate' for r in rules), '需保留未验证规则示例')
    need(isinstance(contracts, dict), '契约示例格式无效')
    for name, required in CONTRACT_FIELDS.items():
        obj = contracts.get(name)
        need(isinstance(obj, dict) and set(required) <= set(obj), f'{name} 缺少契约字段')
    need(contracts['Recommendation']['preferred_candidate'] is None, '示例推荐不能确认最终型号')
    need(contracts['ReviewTask']['status'] == 'pending', '示例审核应保持待审核')
    need(contracts['WorkItem']['source_id'] in case_ids and
         contracts['Recommendation']['inquiry_id'] == contracts['WorkItem']['source_id'], '契约示例的询盘引用不一致')
    need(contracts['InquiryRecord']['work_item_id'] == contracts['WorkItem']['id'] == contracts['ReviewTask']['work_item_id'], '契约示例的 WorkItem 引用不一致')
    need(contracts['ReviewTask']['recommendation_id'] == contracts['Recommendation']['id'], '契约示例的 Recommendation 引用不一致')
    need(set(contracts['Recommendation']['candidate_products']) <= set(product_a), '推荐示例引用了产品技术表中不存在的 SKU')
    need(contracts['ProductCandidate']['sku'] in product_a and
         contracts['ProductCandidate']['sku'] in contracts['Recommendation']['candidate_products'], '候选示例的 SKU 与推荐不一致')
    for name in ('InquiryRecord', 'ProductCandidate', 'Recommendation'):
        evidence = contracts[name].get('evidence')
        need(isinstance(evidence, list) and evidence, f'{name} 缺少字段级证据')
        for item in evidence:
            need(item.get('source_id') in source_ids | case_ids and item.get('source_version') and item.get('locator'), f'{name} 证据引用不完整')
    return {'status': 'DESIGN_READY_FOR_REVIEW', 'dataset_id': golden['dataset_id'],
            'counts': {'inquiries': len(cases), 'replies': len(cases), 'orders': len(orders),
                       'special_cases': len(special), 'source_entries': len(sources),
                       'golden_categories': dict(categories), 'stage3_deliverables': len(STAGE3_FILES)},
            'detected_product_conflict_fields': sorted(differing),
            'unresolved': ['真实数据授权和脱敏', '性能曲线/产品适用性批准', '客户身份签阅',
                           '保修/认证权威资料', '真实预测输出与 Release Gate 实测'],
            'caveat': '仅为合成资料的设计审计；未评估模型准确率，未批准生产投放。'}


def save_report(path, title, result):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    result = {**result, 'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds')}
    (path / 'audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = [f'# {title}', '', f'状态：`{result["status"]}`', '', result['caveat'], '',
             f'生成时间：{result["generated_at"]}', '']
    if 'counts' in result:
        lines += ['## 数据覆盖', ''] + [f'- {k}: {v}' for k, v in result['counts'].items()] + ['', '## 检出的 CP90 字段冲突', '', ', '.join(result['detected_product_conflict_fields']), '']
    if 'unresolved' in result:
        lines += ['## 待解决', ''] + [f'- {x}' for x in result['unresolved']] + ['']
    (path / 'audit-report.md').write_text('\n'.join(lines), encoding='utf-8')
    return result
