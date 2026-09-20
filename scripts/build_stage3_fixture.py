#!/usr/bin/env python3
"""Regenerate the fully fictional Stage 3 text fixture, without dependencies."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'stages/03-data-boundary/data'
BUNDLE = BASE / 'bundle'


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def write_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding='utf-8')


CASES = [
    ('normal', 'Need centrifugal pump. Flow 85 m3/h, head 38 m, 42 C water, 6 pcs, 380V/50Hz. Please quote CIF Jebel Ali.', 'CLARIFY_MEDIUM', {'flow_m3h': 85, 'head_m': 38, 'temperature_c': 42, 'quantity': 6}, ['medium_detail']),
    ('history', 'Same as last order. Need 20 pcs. Reference SO-DEMO-02.', 'VERIFY_ORDER', {'quantity': 20}, ['customer_identity']),
    ('complex', 'Seawater project: flow 90 m3/h, head 40 m, 4 pcs. Please suggest cast iron.', 'ENGINEER_REVIEW', {'flow_m3h': 90, 'head_m': 40, 'quantity': 4}, ['material_compatibility']),
    ('normal', 'Please quote 2 pcs of SIM-C100 according to confirmed sheet.', 'REVIEW_DRAFT', {'quantity': 2}, []),
    ('normal', 'Need 3 pcs SIM-W300 for wastewater, approved specification attached.', 'REVIEW_DRAFT', {'quantity': 3}, []),
    ('normal', 'Pump inquiry: 65 m3/h, 30 m head, freshwater, 5 pcs.', 'REVIEW_DRAFT', {'flow_m3h': 65, 'head_m': 30, 'quantity': 5}, []),
    ('normal', 'Need 2 centrifugal pumps, 70 m3/h, 34 m head, freshwater.', 'REVIEW_DRAFT', {'flow_m3h': 70, 'head_m': 34, 'quantity': 2}, []),
    ('normal', 'Repeat SIM-S200 R2, 8 pcs, order SO-DEMO-04.', 'VERIFY_ORDER', {'quantity': 8}, []),
    ('normal', 'Flow 80 m3/h, head 36 m, freshwater at 25 C. Qty 6.', 'REVIEW_DRAFT', {'flow_m3h': 80, 'head_m': 36, 'temperature_c': 25, 'quantity': 6}, []),
    ('normal', 'We need 10 units SIM-C100, standard freshwater duty. Specs confirmed.', 'REVIEW_DRAFT', {'quantity': 10}, []),
    ('normal', 'Flow 50 m3/h, head 20 m, freshwater. 3 units.', 'REVIEW_DRAFT', {'flow_m3h': 50, 'head_m': 20, 'quantity': 3}, []),
    ('normal', 'Send product information for 2 units SIM-W300, confirmed duty sheet.', 'REVIEW_DRAFT', {'quantity': 2}, []),
    ('complex', 'Hot water at 90 C; flow 80 m3/h, head 38 m; 2 units.', 'ENGINEER_REVIEW', {'flow_m3h': 80, 'head_m': 38, 'temperature_c': 90, 'quantity': 2}, ['seal_configuration']),
    ('complex', 'Chemical process pump; 75 m3/h, 35 m head, 2 units. Material unknown.', 'ENGINEER_REVIEW', {'flow_m3h': 75, 'head_m': 35, 'quantity': 2}, ['chemical_properties', 'material']),
    ('complex', 'CP90 specifications differ between catalog and selection sheet. Need 3 units.', 'ENGINEER_REVIEW', {'quantity': 3}, ['authoritative_version']),
    ('complex', '85 CMH, head 38 m, 4 sets; medium to be confirmed.', 'CLARIFY_MEDIUM', {'flow_m3h': 85, 'head_m': 38, 'quantity': 4}, ['medium_detail']),
    ('history', 'Same as previous order, 4 pcs; our company is ABC Marine.', 'VERIFY_ORDER', {'quantity': 4}, ['customer_identity', 'order_reference']),
    ('history', 'Please repeat SO-DEMO-07, 5 units, customer ABC-Marine BV.', 'VERIFY_ORDER', {'quantity': 5}, ['customer_identity']),
    ('failure', 'Old CP90 quote attached; can you send same price and delivery? 2 units.', 'PRICE_REVIEW', {'quantity': 2}, ['price_validity', 'version']),
    ('failure', 'Urgent 6 units for sea water; no duty point yet. Quote immediately.', 'ENGINEER_REVIEW', {'quantity': 6}, ['flow_m3h', 'head_m', 'material_compatibility']),
]


def build():
    company = ['Al Noor Engineering', 'ABC Marine', 'Bluewater Demo', 'Delta Demo']
    golden = []
    for index, (category, body, action, expected, missing) in enumerate(CASES, 1):
        number = f'{index:03}'
        inquiry_path = f'bundle/inquiries/inquiry_{number}.eml'
        reply_path = f'bundle/replies/reply_{number}.eml'
        sender = company[(index - 1) % len(company)]
        write_text(BASE / inquiry_path, f'From: sales@{sender.lower().replace(" ", "-")}.example\nTo: linda@haichuan.example\nSubject: Synthetic pump inquiry {number}\nDate: Mon, 14 Sep 2026 09:00:00 +0800\nX-Training-Only: true\n\n{body}\n')
        reply = {'CLARIFY_MEDIUM': 'Please confirm the medium properties before product selection.', 'VERIFY_ORDER': 'Please confirm the relevant order and company identity before we prepare a proposal.', 'ENGINEER_REVIEW': 'Our engineer will review the application and missing operating conditions before a recommendation.', 'PRICE_REVIEW': 'We will check current price approval and validity before quoting.', 'REVIEW_DRAFT': 'Thank you. We will review the confirmed specifications and respond with a checked proposal.'}[action]
        write_text(BASE / reply_path, f'From: linda@haichuan.example\nTo: sales@{sender.lower().replace(" ", "-")}.example\nSubject: Re: Synthetic pump inquiry {number}\nDate: Mon, 14 Sep 2026 10:00:00 +0800\nX-Training-Only: true\n\n{reply}\n')
        golden.append({'id': f'E-{number}', 'category': category, 'inquiry_path': inquiry_path, 'reply_path': reply_path,
                       'expected_extraction': expected, 'expected_missing': missing, 'expected_action': action,
                       'preferred_candidate': None, 'label_status': 'training_draft',
                       'review_required': True, 'source_note': '合成案例；须由技术/业务 Owner 审核后才能用作真实评估'})
    write_json(BASE / 'golden.json', {'dataset_id': 'haichuan-stage3-synthetic-v1', 'mode': 'simulation', 'cases': golden})
    orders = [{'order_id': f'SO-DEMO-{i:02}', 'customer_name': ['ABC Marine', 'ABC MARINE', 'ABC-Marine BV', 'Bluewater Demo'][i % 4],
               'customer_id': 'CUST-DEMO-001' if i % 4 != 3 else 'CUST-DEMO-002', 'sku': ['SIM-C100', 'CP90', 'SIM-S200'][i % 3], 'status': 'synthetic_completed'} for i in range(1, 11)]
    write_json(BUNDLE / 'orders/orders.json', orders)
    write_json(BUNDLE / 'special_cases.json', [
        {'id': f'X-{i:03}', 'inquiry_id': f'E-{n:03}', 'type': kind, 'lesson': lesson} for i, (n, kind, lesson) in enumerate([
            (3, 'rule_violation', '海水介质的材料限制需要规则和人工审查'),
            (13, 'high_temperature', '高温时密封配置需工程师确认'),
            (15, 'source_conflict', 'CP90 技术字段冲突，暂停推荐'),
            (19, 'stale_price', '历史报价不可直接复用'),
            (20, 'missing_duty', '缺少工况不能正式报价')], 1)])
    technical = [{'sku': 'CP80', 'flow_min': 70, 'flow_max': 90, 'head_min': 32, 'head_max': 40, 'material': 'SS316', 'status': 'training_only'},
                 {'sku': 'CP90', 'flow_min': 80, 'flow_max': 100, 'head_min': 35, 'head_max': 42, 'material': 'SS316', 'status': 'training_only'},
                 {'sku': 'CP100', 'flow_min': 90, 'flow_max': 115, 'head_min': 38, 'head_max': 48, 'material': 'SS316', 'status': 'training_only'}]
    commercial = [{'sku': 'CP90', 'flow_min': 75, 'flow_max': 95, 'head_min': 32, 'head_max': 40, 'material': 'SS304', 'sales_description': 'synthetic commercial listing'}]
    write_json(BUNDLE / 'products/Pump_Selection_NEW.json', technical)
    write_json(BUNDLE / 'products/Product_Master_Final_v2.json', commercial)
    write_text(BUNDLE / 'products/Pump_Catalog_2024.md', '# Synthetic Catalog 2024\n\nCP90: archived listing. Not approved for technical selection.\n')
    write_text(BUNDLE / 'products/Pump_Catalog_2025.md', '# Synthetic Catalog 2025\n\nCP90: public summary only; details may lag technical selection sheet.\n')
    write_text(BUNDLE / 'faq.md', '# Synthetic FAQ\n\nWarranty and certifications must be checked against current approved policy and certificate repository. These documents are absent from this packet.\n')
    write_text(BUNDLE / 'tech_chat.txt', 'TRAINING ONLY — unapproved chat excerpts\nLinda: Seawater project, can standard CP100 work?\nChen: Ordinary configuration may be unsuitable; check approved material and duty.\nMike: 90 C hot water with CP90?\nChen: Ask engineering to review seal and material configuration.\n')
    write_json(BUNDLE / 'pricing/Quote_2025.json', [{'sku': 'CP90', 'list_price': 1000, 'currency': 'SIM', 'note': 'fictional value; not for quoting'}])
    write_json(BUNDLE / 'pricing/Special_Discount.json', [{'customer_id': 'CUST-DEMO-001', 'sku': 'CP90', 'special_price': 700, 'currency': 'SIM', 'approved_by': 'fictional_manager'}])
    sources = [
        {'id': 'SRC-INQ', 'path': 'bundle/inquiries', 'name': 'Historical inquiry emails', 'kind': 'Data', 'owner': 'Sales', 'version': 'synthetic-v1', 'sensitivity': 'Confidential', 'model_context': 'redacted_only', 'confidence': 'sample_only'},
        {'id': 'SRC-REP', 'path': 'bundle/replies', 'name': 'Sales replies', 'kind': 'Data', 'owner': 'Sales', 'version': 'synthetic-v1', 'sensitivity': 'Confidential', 'model_context': 'redacted_only', 'confidence': 'sample_only'},
        {'id': 'SRC-TECH', 'path': 'bundle/products/Pump_Selection_NEW.json', 'name': 'Technical selection', 'kind': 'Structured Data', 'owner': 'Technical', 'version': 'R2-simulated', 'sensitivity': 'Internal', 'model_context': 'approved_extract_only', 'confidence': 'approved_in_simulation'},
        {'id': 'SRC-MASTER', 'path': 'bundle/products/Product_Master_Final_v2.json', 'name': 'Commercial product master', 'kind': 'Structured Data', 'owner': 'Sales', 'version': 'R2-simulated', 'sensitivity': 'Internal', 'model_context': 'approved_extract_only', 'confidence': 'conflicted_for_technical_fields'},
        {'id': 'SRC-CAT24', 'path': 'bundle/products/Pump_Catalog_2024.md', 'name': 'Public catalog 2024', 'kind': 'Knowledge', 'owner': 'Marketing', 'version': '2024', 'sensitivity': 'Public', 'model_context': 'retrieval_with_version', 'confidence': 'archived'},
        {'id': 'SRC-CAT25', 'path': 'bundle/products/Pump_Catalog_2025.md', 'name': 'Public catalog 2025', 'kind': 'Knowledge', 'owner': 'Marketing/Technical', 'version': '2025', 'sensitivity': 'Public', 'model_context': 'retrieval_with_version', 'confidence': 'may_lag'},
        {'id': 'SRC-ORD', 'path': 'bundle/orders/orders.json', 'name': 'Historical orders', 'kind': 'Context', 'owner': 'Sales Operations', 'version': 'synthetic-v1', 'sensitivity': 'Confidential', 'model_context': 'redacted_only', 'confidence': 'identity_pending'},
        {'id': 'SRC-FAQ', 'path': 'bundle/faq.md', 'name': 'FAQ', 'kind': 'Knowledge', 'owner': 'Sales', 'version': 'synthetic-v1', 'sensitivity': 'Internal', 'model_context': 'approved_extract_only', 'confidence': 'policy_missing'},
        {'id': 'SRC-CHAT', 'path': 'bundle/tech_chat.txt', 'name': 'Technical chat', 'kind': 'Tacit Knowledge', 'owner': 'Technical', 'version': 'unversioned', 'sensitivity': 'Confidential', 'model_context': 'prohibited_until_verified', 'confidence': 'candidate_only'},
        {'id': 'SRC-QUOTE', 'path': 'bundle/pricing/Quote_2025.json', 'name': 'Standard quote', 'kind': 'Pricing Data', 'owner': 'Sales', 'version': '2025', 'sensitivity': 'Confidential', 'model_context': 'prohibited_in_v1', 'confidence': 'stale_possible'},
        {'id': 'SRC-DISC', 'path': 'bundle/pricing/Special_Discount.json', 'name': 'Special discount', 'kind': 'Sensitive Policy', 'owner': 'Management', 'version': 'synthetic-v1', 'sensitivity': 'Highly Sensitive', 'model_context': 'prohibited', 'confidence': 'approval_only'},
    ]
    write_json(BASE / 'manifest.json', {'dataset_id': 'haichuan-stage3-synthetic-v1', 'mode': 'simulation', 'sources': sources})
    write_json(BASE / 'conflicts.json', [{'id': 'D-001', 'entity': 'CP90', 'fields': ['flow_min', 'flow_max', 'head_min', 'head_max', 'material'],
        'source_ids': ['SRC-TECH', 'SRC-MASTER'], 'decision_owner': 'Technical', 'status': 'resolved_for_technical_fields',
        'decision': '以技术部 Pump_Selection_NEW 的技术参数为模拟权威；销售主数据仅用于商业描述。',
        'evidence': 'Stage 3 原始模拟会议中陈工确认技术表；真实环境仍需签署版本、生效日期。',
        'residual_risk': '缺少性能曲线和应用/介质确认，不因此批准 CP90 最终选型。'}])
    write_json(BASE / 'identity.json', {'status': 'provisional', 'entities': [{'customer_id': 'CUST-DEMO-001', 'canonical_name': 'ABC Marine BV',
        'aliases': ['ABC Marine', 'ABC MARINE', 'ABC-Marine BV'], 'owner': 'Sales Operations',
        'evidence': '合成订单中的共享 customer_id；真实合同/CRM 身份待核', 'autolink_allowed': False}]})
    write_json(BASE / 'source-of-truth.json', [
        {'domain': 'technical_product_parameters', 'source_id': 'SRC-TECH', 'owner': 'Technical', 'status': 'approved_in_simulation', 'caveat': '型号适用性仍待曲线与工况审核'},
        {'domain': 'commercial_product_description', 'source_id': 'SRC-MASTER', 'owner': 'Sales', 'status': 'provisional', 'caveat': '技术字段不可使用'},
        {'domain': 'customer_history', 'source_id': 'SRC-ORD', 'owner': 'Sales Operations', 'status': 'provisional', 'caveat': '身份归并需确认'},
        {'domain': 'standard_price', 'source_id': 'SRC-QUOTE', 'owner': 'Sales', 'status': 'out_of_v1', 'caveat': '时效与审批待核'},
        {'domain': 'special_discount', 'source_id': 'SRC-DISC', 'owner': 'Management', 'status': 'human_only', 'caveat': '不进入模型上下文'},
        {'domain': 'warranty', 'source_id': None, 'owner': 'Sales/Legal', 'status': 'missing', 'caveat': '需当前批准政策'},
        {'domain': 'certifications', 'source_id': None, 'owner': 'Quality', 'status': 'missing', 'caveat': '需证书库和有效期'},
    ])
    write_json(BASE / 'rules.json', [
        {'id': 'R-001', 'condition': 'medium=seawater', 'action': 'reject_cast_iron_candidate', 'status': 'verified_in_simulation', 'owner': 'Technical', 'source_ids': ['SRC-CHAT', 'SRC-TECH'], 'scope': 'teaching scenario only', 'exception': 'specific materials require engineering review'},
        {'id': 'R-002', 'condition': 'temperature_c>=80', 'action': 'require_engineer_review', 'status': 'verified_in_simulation', 'owner': 'Technical', 'source_ids': ['SRC-CHAT'], 'scope': 'teaching scenario only', 'exception': 'product-specific limits need current technical file'},
        {'id': 'R-003', 'condition': 'candidate_near_curve_edge', 'action': 'prefer_inner_duty_point', 'status': 'candidate', 'owner': 'Technical', 'source_ids': ['SRC-TECH'], 'scope': 'CP-series pending curves', 'exception': 'cannot execute until curve data and acceptance threshold approved'},
    ])


if __name__ == '__main__':
    build()
    print(f'已重建合成资料包：{BASE}')
