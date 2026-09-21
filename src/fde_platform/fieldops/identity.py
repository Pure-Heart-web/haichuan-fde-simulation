"""Small HS256 training issuer that exercises OIDC claim and role contracts."""
import base64
import hashlib
import hmac
import json
import time


ROLES = frozenset({'sales', 'engineer', 'release_manager', 'operator', 'auditor'})


def _encode(value):
    return base64.urlsafe_b64encode(value).decode().rstrip('=')


def _decode(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


class TrainingOIDCBroker:
    """Exercises claim validation; never represents enterprise SSO."""

    def __init__(self, key, *, issuer, audience, tenant_id, ttl_seconds=900):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError('训练 OIDC 签名密钥至少 32 字节')
        if not issuer.startswith('https://training.invalid/') or not audience:
            raise ValueError('训练 issuer 与 audience 无效')
        self.key, self.issuer, self.audience = key, issuer, audience
        self.tenant_id, self.ttl_seconds = tenant_id, ttl_seconds
        self.accounts, self.revoked = {}, set()

    def add_account(self, actor_id, role, training_code):
        if role not in ROLES or not actor_id or len(training_code) < 12:
            raise ValueError('训练 OIDC 账户无效')
        self.accounts[actor_id] = {'role': role,
            'code_sha256': hashlib.sha256(training_code.encode()).hexdigest()}

    def authenticate(self, actor_id, training_code, *, now=None):
        account = self.accounts.get(actor_id)
        supplied = hashlib.sha256(training_code.encode()).hexdigest()
        if not account or not hmac.compare_digest(account['code_sha256'], supplied):
            raise ValueError('OIDC 训练身份认证失败')
        now = int(time.time() if now is None else now)
        header = {'alg': 'HS256', 'typ': 'JWT', 'kid': 'training-hs256-v1'}
        claims = {'iss': self.issuer, 'aud': self.audience, 'sub': actor_id,
                  'tenant_id': self.tenant_id, 'role': account['role'],
                  'iat': now, 'exp': now + self.ttl_seconds,
                  'jti': hashlib.sha256(f'{actor_id}|{now}|{training_code}'.encode()).hexdigest()[:24]}
        first = _encode(json.dumps(header, sort_keys=True, separators=(',', ':')).encode())
        second = _encode(json.dumps(claims, sort_keys=True, separators=(',', ':')).encode())
        signature = _encode(hmac.new(self.key, f'{first}.{second}'.encode(), hashlib.sha256).digest())
        return f'{first}.{second}.{signature}'

    def verify(self, token, *, tenant_id=None, role=None, now=None):
        try:
            first, second, supplied = token.split('.')
            header, claims = json.loads(_decode(first)), json.loads(_decode(second))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError('OIDC 训练令牌格式无效') from exc
        expected = _encode(hmac.new(self.key, f'{first}.{second}'.encode(), hashlib.sha256).digest())
        now = int(time.time() if now is None else now)
        valid = (hmac.compare_digest(expected, supplied) and header ==
                 {'alg': 'HS256', 'kid': 'training-hs256-v1', 'typ': 'JWT'} and
                 claims.get('iss') == self.issuer and claims.get('aud') == self.audience and
                 claims.get('tenant_id') == self.tenant_id and claims.get('role') in ROLES and
                 isinstance(claims.get('exp'), int) and isinstance(claims.get('iat'), int) and
                 claims['iat'] <= now < claims['exp'] and claims.get('jti') not in self.revoked and
                 claims.get('sub') in self.accounts and
                 self.accounts[claims['sub']]['role'] == claims.get('role'))
        if tenant_id is not None:
            valid = valid and claims.get('tenant_id') == tenant_id
        if role is not None:
            valid = valid and claims.get('role') == role
        if not valid:
            raise ValueError('OIDC issuer/audience/tenant/role/有效期校验失败')
        return claims

    def revoke(self, token):
        _, second, _ = token.split('.')
        self.revoked.add(json.loads(_decode(second))['jti'])
