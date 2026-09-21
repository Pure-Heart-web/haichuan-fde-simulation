"""Validate a signature-bound synthetic field-pilot authorization bundle."""
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest()


def controlled(bundle):
    return {key: value for key, value in bundle.items() if key != 'approvals'}


def validate_bundle(bundle, root):
    required = ('version', 'mode', 'tenant_id', 'domain', 'customer_manifest',
                'data_boundary', 'identity', 'connector', 'operations',
                'slo_thresholds', 'approvals')
    if any(key not in bundle for key in required):
        raise ValueError('现场试点授权包字段不完整')
    if bundle['mode'] != 'synthetic_field_rehearsal':
        raise ValueError('本地 Stage 13 只允许合成现场演练')
    manifest_ref = bundle['customer_manifest']
    path = Path(root) / manifest_ref['path']
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != manifest_ref['sha256']:
        raise ValueError('客户授权清单不存在或哈希变化')
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if (manifest.get('mode') != 'synthetic_design_partner' or
            manifest.get('tenant_id') != bundle['tenant_id'] or
            manifest.get('domain') != bundle['domain']):
        raise ValueError('客户授权清单与 Pilot 租户、Domain 或模式不一致')
    boundary = bundle['data_boundary']
    if (boundary.get('external_mount_required') is not True or
            boundary.get('customer_records_embedded') is not False or
            boundary.get('raw_payload_persisted') is not False or
            boundary.get('git_storage_allowed') is not False):
        raise ValueError('客户数据必须外置挂载且禁止写入 Git')
    identity = bundle['identity']
    if (identity.get('protocol') != 'oidc_contract' or
            identity.get('training_issuer_only') is not True or
            not identity.get('audience') or not identity.get('roles')):
        raise ValueError('身份契约不完整')
    connector = bundle['connector']
    if (connector.get('read_only_source') is not True or
            connector.get('customer_write_enabled') is not False or
            connector.get('delivery_target') != 'local_mock_only'):
        raise ValueError('Connector 必须只读且不能写入客户系统')
    operations = bundle['operations']
    if (not operations.get('stop_owner') or not operations.get('incident_owner') or
            operations.get('real_customer_release') is not False):
        raise ValueError('试点运营责任或发布边界不完整')
    thresholds = bundle['slo_thresholds']
    if (set(thresholds) != {'intake_acceptance_rate_min', 'worker_success_rate_min',
                            'review_completion_rate_min'} or
            any(type(value) not in (int, float) or not 0 <= value <= 1
                for value in thresholds.values())):
        raise ValueError('Pilot SLO 阈值必须是 0–1 之间的完整集合')
    expected = digest(controlled(bundle))
    approvals = bundle['approvals']
    wanted = {'customer_sponsor', 'customer_data_owner', 'fde_security_owner', 'pilot_owner'}
    roles = {item.get('role') for item in approvals if item.get('status') == 'approved'}
    actors = {item.get('actor_id') for item in approvals}
    if (len(approvals) != 4 or roles != wanted or len(actors) != 4 or any(
            item.get('content_sha256') != expected or not item.get('actor_id')
            for item in approvals)):
        raise ValueError('四方必须用不同身份签核同一授权包')
    return {'status': 'SYNTHETIC_FIELD_BUNDLE_APPROVED',
            'content_sha256': expected, 'tenant_id': bundle['tenant_id'],
            'domain': bundle['domain'], 'real_customer_data_authorized': False}


def validate_postgres_rls(sql_text):
    lowered = ' '.join(sql_text.casefold().split())
    tables = ('inbox', 'cases', 'reviews', 'outbox', 'audit', 'incidents')
    checks = {
        'tenant_setting_required': "current_setting('app.tenant_id', true)" in lowered,
        'runtime_role_declared': 'create role fde_runtime' in lowered,
        'bypass_role_not_granted': 'bypassrls' not in lowered,
    }
    for table in tables:
        checks[f'{table}_rls_enabled'] = f'alter table {table} enable row level security' in lowered
        checks[f'{table}_rls_forced'] = f'alter table {table} force row level security' in lowered
        checks[f'{table}_policy'] = f'create policy {table}_tenant_scope on {table}' in lowered
    return {'status': 'POSTGRES_RLS_CONTRACT_READY' if all(checks.values()) else
            'POSTGRES_RLS_CONTRACT_BLOCKED', 'checks': checks,
            'runtime_executed_against_postgres': False}
