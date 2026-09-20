"""Validated Rule V1 DSL: equals, in, gte, lte, exists and four actions."""
from dataclasses import dataclass
from datetime import date

ALLOWED_OPS = {'equals', 'in', 'gte', 'lte', 'exists'}
ALLOWED_ACTIONS = {'exclude_candidate', 'add_warning', 'require_review', 'add_requirement'}
ALLOWED_FIELDS = {
    'inquiry.medium_category', 'inquiry.temperature_c', 'inquiry.frequency_hz',
    'product.material', 'product.range_edge_proxy',
}


class RuleError(ValueError):
    pass


@dataclass(frozen=True)
class RuleHit:
    rule_id: str
    severity: str
    actions: tuple[dict, ...]
    source_ids: tuple[str, ...]
    version: str
    owner: str


def validate_registry(registry):
    if registry.get('mode') != 'simulation' or not isinstance(registry.get('rules'), list):
        raise RuleError('规则注册表模式或结构无效')
    seen = set()
    for rule in registry['rules']:
        if rule.get('id') in seen or not rule.get('id'):
            raise RuleError('重复或空规则 ID')
        seen.add(rule['id'])
        for key in ('description', 'domain', 'version', 'owner', 'severity', 'status'):
            if not rule.get(key):
                raise RuleError(f'{rule["id"]} 缺少 {key}')
        if rule['status'] not in ('active_in_simulation', 'candidate', 'retired'):
            raise RuleError(f'{rule["id"]} 状态无效')
        if rule['status'] == 'active_in_simulation':
            try:
                date.fromisoformat(rule['effective_date'])
            except (TypeError, ValueError):
                raise RuleError(f'{rule["id"]} 缺少生效日期') from None
        if not rule.get('source_ids') or not isinstance(rule.get('when'), list) or not rule['when']:
            raise RuleError(f'{rule["id"]} 缺少来源或条件')
        if not isinstance(rule.get('actions'), list) or not rule['actions']:
            raise RuleError(f'{rule["id"]} 缺少动作')
        for condition in rule['when']:
            if condition.get('field') not in ALLOWED_FIELDS or condition.get('op') not in ALLOWED_OPS:
                raise RuleError(f'{rule["id"]} 使用未允许的字段/操作符')
            if 'value' not in condition:
                raise RuleError(f'{rule["id"]} 条件缺值')
            if condition['op'] == 'in' and not isinstance(condition['value'], list):
                raise RuleError(f'{rule["id"]} in 必须使用列表')
            if condition['op'] == 'exists' and type(condition['value']) is not bool:
                raise RuleError(f'{rule["id"]} exists 必须使用布尔值')
        for action in rule['actions']:
            if action.get('type') not in ALLOWED_ACTIONS:
                raise RuleError(f'{rule["id"]} 动作未允许')
            if action['type'] == 'require_review' and action.get('role') not in ('sales', 'engineer'):
                raise RuleError(f'{rule["id"]} 审核角色无效')
    return registry


def _value(field, inquiry, product):
    root, name = field.split('.', 1)
    return getattr(inquiry if root == 'inquiry' else product, name)


def _matches(condition, inquiry, product):
    actual = _value(condition['field'], inquiry, product)
    expected = condition['value']
    op = condition['op']
    if op == 'exists':
        return (actual is not None) == expected
    if actual is None:
        return False
    if op == 'equals':
        return actual == expected
    if op == 'in':
        return actual in expected
    if op in ('gte', 'lte'):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool) or not isinstance(expected, (int, float)):
            raise RuleError(f'数值规则字段无效：{condition["field"]}')
        return actual >= expected if op == 'gte' else actual <= expected
    raise RuleError(f'未知操作符：{op}')


def evaluate(registry, inquiry, product):
    validate_registry(registry)
    hits = []
    for rule in registry['rules']:
        if rule['status'] != 'active_in_simulation':
            continue
        if all(_matches(condition, inquiry, product) for condition in rule['when']):
            hits.append(RuleHit(rule['id'], rule['severity'], tuple(rule['actions']),
                                tuple(rule['source_ids']), rule['version'], rule['owner']))
    return hits
