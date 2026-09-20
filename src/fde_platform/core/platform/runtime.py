"""Small shared evaluators; field vocabulary and actions stay in domain packs."""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    severity: str
    actions: tuple[str, ...]
    evidence_refs: tuple[str, ...]


def evaluate_rules(facts, rules, *, allowed_fields, allowed_actions, as_of):
    today = date.fromisoformat(as_of)
    matches = []
    for rule in rules:
        if rule['status'] != 'active' or date.fromisoformat(rule['effective_date']) > today:
            continue
        if not rule['id'] or not rule.get('source_ids') or not rule.get('when'):
            raise ValueError('规则缺少 ID、来源或条件')
        if not set(rule['actions']) <= set(allowed_actions):
            raise ValueError('规则含未批准动作')
        passed = True
        for condition in rule['when']:
            field, op, expected = condition['field'], condition['op'], condition['value']
            if field not in allowed_fields or op not in ('equals', 'gte', 'contains', 'exists'):
                raise ValueError('规则含未批准字段或操作符')
            actual = facts.get(field)
            if op == 'equals':
                ok = actual == expected
            elif op == 'gte':
                ok = isinstance(actual, (int, float)) and not isinstance(actual, bool) and actual >= expected
            elif op == 'contains':
                ok = isinstance(actual, (tuple, list, str)) and expected in actual
            else:
                ok = (actual is not None) == expected
            passed = passed and ok
        if passed:
            matches.append(RuleMatch(rule['id'], rule['severity'], tuple(rule['actions']), tuple(rule['source_ids'])))
    return tuple(matches)


class ScopedKnowledgeIndex:
    """Tenant scope is applied by TenantSession before any metadata or rank step."""
    def __init__(self, session):
        self.session = session

    def retrieve(self, *, intent, as_of, model=None, role='engineer'):
        today = date.fromisoformat(as_of)
        results = []
        for doc in self.session.list('knowledge'):
            if (doc['status'] != 'active' or date.fromisoformat(doc['effective_date']) > today or
                intent not in doc['intents'] or role not in doc['allowed_roles'] or
                (doc.get('models') and model not in doc['models'])):
                continue
            results.append({'document_id': doc['document_id'], 'version': doc['version'],
                            'owner': doc['owner'], 'source_id': doc['source_id'],
                            'intent': intent, 'text': doc['text']})
        return tuple(sorted(results, key=lambda x: x['document_id']))
