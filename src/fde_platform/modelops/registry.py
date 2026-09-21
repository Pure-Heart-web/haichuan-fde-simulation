"""Validate a hash-bound synthetic model and prompt registry."""
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()


def controlled(registry):
    return {key: value for key, value in registry.items() if key != 'approvals'}


def validate_registry(registry, root):
    required = ('version', 'mode', 'tenant_id', 'prompt', 'schema', 'providers',
                'routing', 'limits', 'forbidden_output_keys', 'secret_canaries')
    if any(key not in registry for key in required):
        raise ValueError('模型注册表字段不完整')
    if registry['mode'] != 'synthetic_model_lab':
        raise ValueError('本地 Model Lab 只接受 synthetic_model_lab')
    if registry.get('external_customer_data_allowed') is not False:
        raise ValueError('教学注册表必须明确禁止外部客户数据')
    prompt = Path(root) / registry['prompt']['path']
    if not prompt.is_file() or hashlib.sha256(prompt.read_bytes()).hexdigest() != registry['prompt']['sha256']:
        raise ValueError('Prompt 文件不存在或内容哈希变化')
    if not 0 <= registry['routing']['candidate_percent'] <= 100:
        raise ValueError('Canary 比例必须在 0–100')
    if registry['routing'].get('shadow_only') is not True:
        raise ValueError('教学 Canary 必须为 shadow_only')
    if registry['limits']['circuit_failure_threshold'] < 1:
        raise ValueError('熔断阈值必须为正整数')
    if registry['limits']['max_output_bytes'] > 200_000:
        raise ValueError('模型输出上限过大')
    providers = registry['providers']
    if set(providers) != {'baseline', 'candidate'} or providers['baseline']['kind'] != 'offline_baseline':
        raise ValueError('注册表必须有 baseline 与 candidate')
    if providers['candidate'].get('external_network') is not False:
        raise ValueError('默认演练禁止外部模型网络')
    expected = digest(controlled(registry))
    approvals = registry.get('approvals', [])
    roles = {x.get('role') for x in approvals if x.get('status') == 'approved'}
    if (len(approvals) != 2 or roles != {'model_owner', 'ai_safety_owner'} or
            len({x.get('actor_id') for x in approvals}) != 2 or any(
            x.get('content_sha256') != expected or not x.get('actor_id') for x in approvals)):
        raise ValueError('Model Owner 与 AI Safety Owner 必须签核同一注册表版本')
    return {'status': 'SYNTHETIC_MODEL_REGISTRY_APPROVED',
            'version': registry['version'], 'content_sha256': expected,
            'external_customer_data_allowed': False}
