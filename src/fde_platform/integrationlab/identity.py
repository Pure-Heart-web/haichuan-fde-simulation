"""OIDC discovery, group mapping and key-rotation rehearsal for a local lab."""
import base64
import hashlib
import hmac
import json


def _enc(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def _dec(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


class RotatingLabOIDC:
    def __init__(self, issuer, audience, tenant_id, group_roles, keys):
        if not issuer.startswith('https://lab.invalid/') or len(keys) < 2:
            raise ValueError('OIDC Lab 需要 HTTPS 教学 issuer 和两把轮换密钥')
        if any(not isinstance(key, bytes) or len(key) < 32 for key in keys.values()):
            raise ValueError('OIDC Lab 密钥长度不足')
        self.issuer, self.audience, self.tenant_id = issuer, audience, tenant_id
        self.group_roles, self.keys = dict(group_roles), dict(keys)
        self.active_kid, self.disabled_groups = next(iter(keys)), set()

    def discovery(self):
        return {'issuer': self.issuer,
                'authorization_endpoint': self.issuer + '/authorize',
                'token_endpoint': self.issuer + '/token',
                'jwks_uri': self.issuer + '/jwks',
                'response_types_supported': ['code'],
                'code_challenge_methods_supported': ['S256']}

    def jwks_metadata(self):
        return {'keys': [{'kid': kid, 'kty': 'oct', 'alg': 'HS256',
                          'use': 'sig', 'lab_only': True} for kid in self.keys]}

    def rotate(self, kid):
        if kid not in self.keys:
            raise ValueError('JWKS kid 不存在')
        self.active_kid = kid

    def issue(self, subject, group, *, now=1000, ttl=300):
        if group not in self.group_roles or group in self.disabled_groups:
            raise ValueError('账户组无效或已停用')
        header = {'alg': 'HS256', 'typ': 'JWT', 'kid': self.active_kid}
        claims = {'iss': self.issuer, 'aud': self.audience, 'sub': subject,
                  'tenant_id': self.tenant_id, 'groups': [group],
                  'role': self.group_roles[group], 'amr': ['mfa'],
                  'iat': now, 'exp': now + ttl}
        first = _enc(json.dumps(header, sort_keys=True, separators=(',', ':')).encode())
        second = _enc(json.dumps(claims, sort_keys=True, separators=(',', ':')).encode())
        signature = _enc(hmac.new(self.keys[self.active_kid],
            f'{first}.{second}'.encode(), hashlib.sha256).digest())
        return f'{first}.{second}.{signature}'

    def verify(self, token, *, now=1001):
        try:
            first, second, supplied = token.split('.')
            header, claims = json.loads(_dec(first)), json.loads(_dec(second))
            key = self.keys[header['kid']]
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError('OIDC Lab token 或 kid 无效') from exc
        expected = _enc(hmac.new(key, f'{first}.{second}'.encode(), hashlib.sha256).digest())
        groups = claims.get('groups', [])
        timestamps_valid = (isinstance(claims.get('iat'), int) and
                            isinstance(claims.get('exp'), int) and
                            claims['iat'] <= now < claims['exp'])
        valid = (hmac.compare_digest(expected, supplied) and
                 claims.get('iss') == self.issuer and claims.get('aud') == self.audience and
                 claims.get('tenant_id') == self.tenant_id and claims.get('amr') == ['mfa'] and
                 len(groups) == 1 and groups[0] not in self.disabled_groups and
                 self.group_roles.get(groups[0]) == claims.get('role') and
                 timestamps_valid)
        if not valid:
            raise ValueError('OIDC Lab claim、MFA、组或有效期校验失败')
        return claims

    def disable_group(self, group):
        self.disabled_groups.add(group)


def rehearse_oidc(config):
    provider = RotatingLabOIDC(config['issuer'], config['audience'], config['tenant_id'],
        config['group_roles'], {'lab-key-a': b'a' * 32, 'lab-key-b': b'b' * 32})
    first = provider.issue('engineer-1', 'fde-engineers')
    provider.verify(first)
    provider.rotate('lab-key-b')
    second = provider.issue('operator-1', 'fde-operators', now=2000)
    provider.verify(second, now=2001)
    blocked = 0
    provider.disable_group('fde-operators')
    for token, now in ((second, 2002), (first, 2000)):
        try:
            provider.verify(token, now=now)
        except ValueError:
            blocked += 1
    return {'status': 'OIDC_LAB_PASSED', 'discovery': provider.discovery(),
            'jwks_key_count': len(provider.jwks_metadata()['keys']),
            'key_rotation_verified': True, 'mfa_claim_verified': True,
            'group_mapping_verified': True, 'disable_checks_blocked': blocked,
            'enterprise_oidc_used': False}
