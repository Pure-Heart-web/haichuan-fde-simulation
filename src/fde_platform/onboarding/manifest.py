"""Validate customer authorization, purpose, fields, retention and transfer policy."""
import hashlib
import json
from pathlib import Path

MODES = frozenset({'synthetic_design_partner', 'authorized_customer_data'})


def content_digest(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()


def _controlled_content(manifest):
    # Every policy and operating field is signature-bound. Approvals are the only
    # excluded value because including their own digest would be recursive.
    return {key: value for key, value in manifest.items() if key != 'approvals'}


def validate_manifest(manifest, *, base_dir=None):
    if manifest.get('mode') not in MODES or manifest.get('domain') not in (
            'foreign_trade', 'after_sales'):
        raise ValueError('客户包模式或 Domain 无效')
    for key in ('customer_id', 'tenant_id', 'purpose', 'authorized_sources',
                'allowed_fields', 'prohibited_fields', 'residency', 'scope'):
        if not manifest.get(key):
            raise ValueError(f'客户授权清单缺少 {key}')
    if not isinstance(manifest.get('retention_days'), int) or not 1 <= manifest['retention_days'] <= 365:
        raise ValueError('保存期限必须是 1–365 天')
    if set(manifest['allowed_fields']) & set(manifest['prohibited_fields']):
        raise ValueError('字段不能同时允许和禁止')
    if manifest.get('auto_send') or manifest.get('auto_quote') or manifest.get('auto_dispatch'):
        raise ValueError('客户接入阶段禁止自动发送、报价或派工')
    approvals = manifest.get('approvals', [])
    roles = {x.get('role') for x in approvals if x.get('status') == 'approved'}
    expected_digest = content_digest(_controlled_content(manifest))
    if roles != {'customer_data_owner', 'fde_security_owner'} or any(
            x.get('content_sha256') != expected_digest or not x.get('actor_id')
            for x in approvals):
        raise ValueError('客户数据负责人和 FDE 安全负责人必须签核同一清单版本')
    if manifest['cross_border'] and not manifest.get('cross_border_assessment', {}).get('approved'):
        raise ValueError('跨境处理缺少已批准的评估记录')
    if manifest['external_model_allowed'] and not manifest.get('model_data_policy', {}).get('approved'):
        raise ValueError('外部模型处理缺少数据政策批准')
    if manifest['mode'] == 'authorized_customer_data':
        evidence = manifest.get('authorization_evidence', [])
        root = Path(base_dir or '.')
        if not evidence:
            raise ValueError('真实客户包缺少外部授权证据')
        for item in evidence:
            path = (root / item['path']).resolve()
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item.get('sha256'):
                raise ValueError('真实客户授权证据不存在或哈希不匹配')
        if not manifest['storage_controls'].get('production_data_plane'):
            raise ValueError('真实客户数据必须使用生产数据面，不能使用本地教学 SQLite')
    return {'status': 'AUTHORIZED_FOR_SYNTHETIC_SHADOW' if manifest['mode'] ==
            'synthetic_design_partner' else 'AUTHORIZED_MANIFEST_VALIDATED',
            'tenant_id': manifest['tenant_id'], 'domain': manifest['domain'],
            'content_sha256': expected_digest, 'real_customer_data':
            manifest['mode'] == 'authorized_customer_data'}
