"""Hash-chained synthetic model release approvals and emergency rollback."""
import hashlib
import json
from pathlib import Path

from fde_platform.core.models import utc_now


class RolloutBook:
    def __init__(self, path, registry_digest):
        self.path, self.registry_digest = Path(path), registry_digest
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _events(self):
        if not self.path.exists():
            return []
        rows = [json.loads(x) for x in self.path.read_text().splitlines() if x.strip()]
        previous = 'GENESIS'
        for index, row in enumerate(rows, 1):
            supplied = row.pop('event_sha256')
            expected = hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True,
                separators=(',', ':')).encode()).hexdigest()
            row['event_sha256'] = supplied
            if supplied != expected or row['sequence'] != index or row['previous_sha256'] != previous:
                raise ValueError('模型发布记录哈希链损坏')
            previous = supplied
        return rows

    def append(self, actor_id, role, action, reason, *, candidate_percent=0):
        allowed = {'approve_candidate': {'model_owner', 'ai_safety_owner'},
                   'activate_canary': {'release_manager'},
                   'rollback_baseline': {'operator'}}
        if action not in allowed or role not in allowed[action] or not reason.strip():
            raise ValueError('模型发布动作、角色或理由无效')
        if action == 'activate_canary' and not 1 <= candidate_percent <= 100:
            raise ValueError('Canary 比例必须在 1–100')
        rows = self._events()
        if action == 'activate_canary':
            approvals = [x for x in rows if x['action'] == 'approve_candidate']
            signed = {x['role'] for x in approvals}
            actors = {x['actor_id'] for x in approvals}
            if signed != {'model_owner', 'ai_safety_owner'} or len(actors) < 2:
                raise ValueError('Canary 激活前缺少 Model/Safety 双签')
        if action == 'rollback_baseline' and not rows:
            raise ValueError('没有可回退的发布记录')
        event = {'sequence': len(rows) + 1,
            'previous_sha256': rows[-1]['event_sha256'] if rows else 'GENESIS',
            'registry_sha256': self.registry_digest, 'actor_id': actor_id, 'role': role,
            'action': action, 'reason': reason.strip(),
            'candidate_percent': candidate_percent, 'created_at': utc_now()}
        event['event_sha256'] = hashlib.sha256(json.dumps(event, ensure_ascii=False,
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + '\n')
        return event

    def status(self):
        rows = self._events()
        active = 0
        if rows:
            for row in rows:
                if row['action'] == 'activate_canary':
                    active = row['candidate_percent']
                elif row['action'] == 'rollback_baseline':
                    active = 0
        return {'event_count': len(rows), 'active_candidate_percent': active,
                'active_route': 'candidate_canary' if active else 'baseline',
                'hash_chain_valid': True, 'events': rows}
