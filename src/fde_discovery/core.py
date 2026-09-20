"""Validate evidence, calculate sample metrics, and check discovery coverage."""
import json
import math
from datetime import datetime
from pathlib import Path
from statistics import mean, median

STEPS = {
    'requirements': '需求整理', 'lookup': '资料查找', 'selection': '产品选型',
    'history': '客户历史', 'quote': '报价准备', 'draft': '回复草稿',
}
CHECKS = {'bottleneck': '知道复杂询盘主要耗时', 'escalation': '知道专家升级原因',
          'error_cost': '初步知道错误成本'}


class DataError(ValueError):
    """An actionable input validation error."""


def require(condition, message):
    if not condition:
        raise DataError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def fields(obj, names, label):
    require(isinstance(obj, dict), f'{label} 必须为对象')
    for name in names:
        require(nonempty(obj.get(name)), f'{label}.{name} 必须为非空文本')


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        raise DataError(f'无效时间：{value!r}') from None
    require(parsed.utcoffset() is not None, f'时间必须带时区：{value}')
    return parsed


def number(value, label):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            f'{label} 必须为有限非负数')


def validate(data, base_dir):
    require(isinstance(data, dict), '输入必须是 JSON 对象')
    require(type(data.get('schema_version')) is int and data['schema_version'] == 1,
            'schema_version 必须为 1')
    fields(data, ['dataset_id'], 'dataset')
    require(data.get('mode') in ('simulation', 'real'), 'mode 必须为 simulation 或 real')
    for key in ('sources', 'interviews', 'observations', 'inventory', 'decisions', 'questions'):
        require(isinstance(data.get(key), list), f'{key} 必须为列表')
    source_ids = set()
    for source in data['sources']:
        fields(source, ['id', 'title', 'path', 'origin'], 'source')
        require(source['id'] not in source_ids, f'重复证据 ID：{source["id"]}')
        source_ids.add(source['id'])
        require(source['origin'] in ('simulation', 'real'), 'source.origin 无效')
        if data['mode'] == 'real':
            require(source['origin'] == 'real', '真实模式不能使用模拟证据')
        require((Path(base_dir) / source['path']).is_file(), f'证据文件不存在：{source["path"]}')

    def ref(value):
        require(isinstance(value, str) and value in source_ids, f'证据引用不存在：{value!r}')

    def refs(values, required=False):
        require(isinstance(values, list), 'source_ids 必须为列表')
        require(not required or len(values) > 0, '已确认结论或已知信息必须有证据')
        for value in values:
            ref(value)

    for interview in data['interviews']:
        fields(interview, ['role', 'source_id'], 'interview')
        require(interview['role'] in ('buyer', 'sales', 'engineer'), '访谈角色无效')
        ref(interview['source_id'])
    case_ids = set()
    for obs in data['observations']:
        fields(obs, ['id', 'complexity', 'source_id', 'received_at', 'first_reply_at'], 'observation')
        require(obs['id'] not in case_ids, f'重复案例 ID：{obs["id"]}')
        case_ids.add(obs['id'])
        ref(obs['source_id'])
        require(obs['complexity'] in ('simple', 'complex'), 'complexity 无效')
        require(isinstance(obs.get('steps'), dict) and set(obs['steps']) == set(STEPS),
                f'{obs["id"]} 必须完整记录六个步骤')
        for key, value in obs['steps'].items():
            number(value, f'{obs["id"]}.{key}')
        number(obs.get('engineer_minutes'), 'engineer_minutes')
        require(type(obs.get('escalated')) is bool, 'escalated 必须为布尔值')
        require(isinstance(obs.get('escalation_reason'), str), 'escalation_reason 必须为文本')
        if obs['escalated']:
            require(nonempty(obs['escalation_reason']), '升级案例必须记录原因')
        else:
            require(obs['engineer_minutes'] == 0, '无升级案例不能记录工程师投入')
        elapsed = (timestamp(obs['first_reply_at']) - timestamp(obs['received_at'])).total_seconds() / 60
        require(elapsed >= 0, f'{obs["id"]} 回复时间早于收件时间')
        require(sum(obs['steps'].values()) <= elapsed, f'{obs["id"]} 主动处理时间超过自然时长')
    for item in data['inventory']:
        fields(item, ['name', 'source_id', 'kind', 'owner', 'version', 'quality', 'access'], 'inventory')
        ref(item['source_id'])
    assessment = data.get('assessment')
    fields(assessment, ['problem', 'hypothesis'], 'assessment')
    for key in ('non_goals', 'evidence', 'workflow'):
        require(isinstance(assessment.get(key), list), f'assessment.{key} 必须为列表')
    require(all(nonempty(x) for x in assessment['non_goals']), 'non_goals 不能含空文本')
    for entry in assessment['evidence']:
        fields(entry, ['type', 'text'], 'evidence')
        require(entry['type'] in ('Fact', 'Claim', 'Hypothesis', 'Unknown'), '证据分类无效')
        refs(entry.get('source_ids'), entry['type'] in ('Fact', 'Claim'))
    for step in assessment['workflow']:
        fields(step, ['step', 'owner', 'detail', 'source_id'], 'workflow')
        ref(step['source_id'])
    for decision in data['decisions']:
        fields(decision, ['name', 'inputs', 'basis', 'owner', 'fallback', 'boundary', 'source_id'], 'decision')
        ref(decision['source_id'])
    for q in data['questions']:
        fields(q, ['question', 'owner', 'due', 'method', 'impact'], 'question')
    require(isinstance(data.get('checks'), dict), 'checks 必须为对象')
    for key in CHECKS:
        item = data['checks'].get(key)
        fields(item, ['note'], f'checks.{key}')
        require(type(item.get('confirmed')) is bool, f'checks.{key}.confirmed 必须为布尔值')
        refs(item.get('source_ids'), item['confirmed'])
    return data


def load(path):
    path = Path(path).resolve()
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, ValueError) as exc:
        raise DataError(f'无法读取 JSON：{exc}') from exc
    return validate(data, path.parent)


def summary(values):
    if not values:
        return {'n': 0, 'total': 0, 'mean': None, 'median': None, 'p90': None}
    ordered = sorted(values)
    position = (len(ordered) - 1) * 0.9
    low, high = math.floor(position), math.ceil(position)
    p90 = ordered[low] + (ordered[high] - ordered[low]) * (position - low)
    return {'n': len(values), 'total': sum(values), 'mean': mean(values),
            'median': median(values), 'p90': p90}


def metrics(data):
    observations = data['observations']
    active = lambda o: sum(o['steps'].values())
    complex_cases = [o for o in observations if o['complexity'] == 'complex']
    escalated = sum(o['escalated'] for o in observations)
    return {
        'sample_count': len(observations),
        'sales_active_minutes': summary([active(o) for o in observations]),
        'simple_active_minutes': summary([active(o) for o in observations if o['complexity'] == 'simple']),
        'complex_active_minutes': summary([active(o) for o in complex_cases]),
        'first_reply_minutes': summary([(timestamp(o['first_reply_at']) - timestamp(o['received_at'])).total_seconds()/60 for o in observations]),
        'engineer_total_minutes': sum(o['engineer_minutes'] for o in observations),
        'escalated_count': escalated,
        'escalation_ratio': escalated / len(observations) if observations else None,
        'complex_step_mean_minutes': {key: mean([o['steps'][key] for o in complex_cases]) if complex_cases else None for key in STEPS},
        'daily_valid_inquiries': None, 'engineer_daily_consultations': None,
    }


def gate(data):
    obs = data['observations']
    roles = {i['role'] for i in data['interviews']}
    inventory = data['inventory']
    rows = [
        {'criterion': '观察至少 3 个询盘流程', 'passed': len(obs) >= 3, 'evidence': [o['source_id'] for o in obs]},
        {'criterion': '访谈老板、销售、工程师', 'passed': roles == {'buyer', 'sales', 'engineer'}, 'evidence': [i['source_id'] for i in data['interviews']]},
    ]
    for key, label in CHECKS.items():
        check = data['checks'][key]
        supported = check['confirmed']
        if key == 'bottleneck':
            supported = supported and any(o['complexity'] == 'complex' for o in obs)
        if key == 'escalation':
            supported = supported and any(o['escalated'] for o in obs)
        rows.append({'criterion': label, 'passed': supported, 'evidence': check['source_ids'], 'note': check['note']})
    for kind, label in [('inquiries', '拿到一批历史询盘样本'), ('product', '拿到基础产品资料')]:
        refs = [i['source_id'] for i in inventory if i['kind'] == kind]
        rows.append({'criterion': label, 'passed': bool(refs), 'evidence': refs})
    rows.extend([
        {'criterion': '建立第一版业务指标 Baseline', 'passed': bool(obs), 'evidence': [o['source_id'] for o in obs]},
        {'criterion': '明确至少一个 V1 Non-goal', 'passed': bool(data['assessment']['non_goals']), 'evidence': ['人工填写 assessment.non_goals']},
    ])
    complete = all(row['passed'] for row in rows)
    status = ('SIMULATION_READY' if data['mode'] == 'simulation' else 'REAL_REVIEW_REQUIRED') if complete else 'NEEDS_MORE_DISCOVERY'
    return {'status': status, 'complete': complete, 'checks': rows}
