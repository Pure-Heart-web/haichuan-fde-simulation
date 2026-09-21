"""Explicit simulation release gates and adjudicated challenge cases."""
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode('utf-8')).hexdigest()


def validate_release(payload, *, kind, expected_owner):
    approval = payload.get('approval', {})
    if (payload.get('mode') != 'synthetic_training_only' or
        approval.get('status') != 'approved_in_simulation' or
        approval.get('role') != expected_owner or not approval.get('actor_id') or
        approval.get('content_sha256') != digest(payload.get(kind))):
        raise ValueError(f'{kind} 缺少匹配的模拟负责人签核或内容已变更')
    return {'kind': kind, 'version': payload['version'], 'approval_status': approval['status'],
            'approved_by': approval['actor_id'], 'content_sha256': approval['content_sha256']}


def validate_service_rules(rule_payload, release_payload):
    validate_release(release_payload, kind='rules', expected_owner='safety_owner')
    if release_payload['rules'] != rule_payload['rules'] or release_payload['version'] != rule_payload['version']:
        raise ValueError('安全签核对应的规则版本与当前规则不一致')
    return {'status': 'SIMULATED_APPROVED', 'rule_count': len(rule_payload['rules']),
            'version': rule_payload['version'], 'real_safety_approval': False}


def assess_curve(curves_payload, *, sku, flow_m3h, head_m, medium, temperature_c,
                 frequency_hz, voltage_v, as_of):
    validate_release(curves_payload, kind='curves', expected_owner='product_engineer')
    row = next((x for x in curves_payload['curves'] if x['sku'] == sku), None)
    if not row or row['status'] != 'approved_in_simulation':
        return {'decision': 'abstain', 'reason': 'no_approved_curve', 'evidence_refs': []}
    refs = [row['curve_id'], row['source_id']]
    required = (flow_m3h, head_m, medium, temperature_c, frequency_hz, voltage_v)
    if any(x is None for x in required):
        return {'decision': 'abstain', 'reason': 'unknown_operating_conditions', 'evidence_refs': refs}
    if not row['valid_from'] <= as_of <= row['valid_until']:
        return {'decision': 'abstain', 'reason': 'curve_not_effective', 'evidence_refs': refs}
    if (medium != row['medium'] or frequency_hz != row['frequency_hz'] or
        voltage_v not in row['voltage_v'] or
        not row['temperature_range_c'][0] <= temperature_c <= row['temperature_range_c'][1]):
        return {'decision': 'escalate', 'reason': 'outside_approved_conditions', 'evidence_refs': refs}
    points = row['points']
    if any(len(p) != 2 for p in points) or any(points[i][0] >= points[i+1][0] or
           points[i][1] <= points[i+1][1] for i in range(len(points)-1)):
        raise ValueError('性能曲线点必须按流量升序、扬程降序')
    if not points[0][0] <= flow_m3h <= points[-1][0]:
        return {'decision': 'escalate', 'reason': 'flow_outside_approved_curve', 'evidence_refs': refs}
    for left, right in zip(points, points[1:]):
        if left[0] <= flow_m3h <= right[0]:
            available_head = left[1] + (right[1] - left[1]) * (flow_m3h - left[0]) / (right[0] - left[0])
            break
    if head_m > available_head:
        return {'decision': 'escalate', 'reason': 'required_head_exceeds_curve',
                'available_head_m': available_head, 'evidence_refs': refs}
    return {'decision': 'provisional_for_human_review', 'reason': 'inside_simulated_curve',
            'available_head_m': available_head, 'evidence_refs': refs,
            'real_product_approval': False}


def assess_challenge(case):
    """Conservative deterministic route; challenge labels are not inference inputs."""
    if case['tenant_id'] != {'after_sales': 'qihang-training',
                             'foreign_trade': 'haichuan-training'}.get(case['domain']):
        return 'reject_cross_tenant'
    flags = set(case['flags'])
    if 'prompt_injection' in flags or 'sensitive_export' in flags:
        return 'quarantine'
    if 'high_risk' in flags:
        return 'stop_and_engineer'
    if flags & {'transcription_uncertain', 'missing_serial', 'source_conflict', 'stale_manual'}:
        return 'abstain_and_escalate'
    if 'unknown_conditions' in flags:
        return 'request_clarification'
    return 'human_review'


def evaluate_challenges(cases, labels):
    indexed = {x['case_id']: x for x in labels}
    if len(indexed) != len(labels) or set(indexed) != {x['id'] for x in cases}:
        raise ValueError('双角色标注必须与挑战集一一对应')
    rows = []
    for case in cases:
        label = indexed[case['id']]
        annotations = label['annotations']
        if (set(annotations) != {'frontline', 'engineer'} or
            any(not annotations[k].get('actor_id') or not annotations[k].get('route')
                for k in annotations) or
            not label['adjudication'].get('actor_id') or
            not label['adjudication'].get('rationale') or
            label['adjudication'].get('route') not in
                (annotations['frontline']['route'], annotations['engineer']['route'])):
            raise ValueError(f'{case["id"]} 标注或裁决记录不完整')
        actual = assess_challenge(case)
        rows.append({'case_id': case['id'], 'domain': case['domain'], 'actual': actual,
                     'adjudicated': label['adjudication']['route'],
                     'correct': actual == label['adjudication']['route'],
                     'disagreement': annotations['frontline']['route'] != annotations['engineer']['route'],
                     'safety_failure': actual == 'human_review' and
                         label['adjudication']['route'] != 'human_review'})
    return {'case_count': len(rows), 'correct': sum(x['correct'] for x in rows),
            'disagreements_retained': sum(x['disagreement'] for x in rows),
            'safety_failures': sum(x['safety_failure'] for x in rows), 'rows': rows,
            'label_mode': 'synthetic_role_play_not_independent_human_annotation'}
