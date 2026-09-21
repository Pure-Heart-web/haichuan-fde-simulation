"""Local training identity broker: signed, expiring tenant/role claims."""
import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path


def _encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _decode(value):
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))


class IdentityBroker:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'local-identity.json'
        if not self.path.exists():
            raw = {'mode': 'local_training_identity_not_sso', 'signing_key': secrets.token_hex(32),
                   'accounts': {}}
            self.path.write_text(json.dumps(raw, indent=2) + '\n')
            self.path.chmod(0o600)
        self.data = json.loads(self.path.read_text())
        self.key = bytes.fromhex(self.data['signing_key'])

    def add_account(self, actor_id, tenant_id, role, password):
        if not all((actor_id, tenant_id, role, password)):
            raise ValueError('身份字段不能为空')
        existing = self.data['accounts'].get(actor_id)
        if existing:
            if (existing['tenant_id'], existing['role']) != (tenant_id, role):
                raise ValueError('已有身份不能改租户或角色')
            return False
        salt = secrets.token_bytes(16)
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 200_000)
        self.data['accounts'][actor_id] = {'tenant_id': tenant_id, 'role': role,
            'salt': salt.hex(), 'password_hash': hashed.hex(), 'active': True}
        self.path.write_text(json.dumps(self.data, indent=2) + '\n')
        self.path.chmod(0o600)
        return True

    def authenticate(self, actor_id, password, *, ttl_seconds=900):
        record = self.data['accounts'].get(actor_id)
        if not record or not record['active']:
            raise ValueError('身份认证失败')
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(),
                                     bytes.fromhex(record['salt']), 200_000)
        if not hmac.compare_digest(hashed, bytes.fromhex(record['password_hash'])):
            raise ValueError('身份认证失败')
        now = int(time.time())
        claims = {'sub': actor_id, 'tenant_id': record['tenant_id'], 'role': record['role'],
                  'iat': now, 'exp': now + ttl_seconds, 'mode': 'local_training_identity'}
        body = _encode(json.dumps(claims, sort_keys=True, separators=(',', ':')).encode())
        signature = _encode(hmac.new(self.key, body.encode(), hashlib.sha256).digest())
        return body + '.' + signature

    def verify(self, token, *, tenant_id=None, role=None):
        try:
            body, signature = token.split('.')
            expected = _encode(hmac.new(self.key, body.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(signature, expected):
                raise ValueError
            claims = json.loads(_decode(body))
        except (ValueError, TypeError, KeyError, UnicodeDecodeError, binascii.Error,
                json.JSONDecodeError) as exc:
            raise ValueError('身份令牌无效') from exc
        account = self.data['accounts'].get(claims.get('sub'))
        if (not account or not account['active'] or claims.get('exp', 0) <= time.time() or
            (claims['tenant_id'], claims['role']) != (account['tenant_id'], account['role'])):
            raise ValueError('身份令牌过期或权限已撤销')
        if tenant_id and claims['tenant_id'] != tenant_id:
            raise ValueError('禁止跨租户访问')
        if role and claims['role'] != role:
            raise ValueError('角色权限不匹配')
        return claims

    def revoke(self, actor_id):
        if actor_id not in self.data['accounts']:
            raise ValueError('身份不存在')
        self.data['accounts'][actor_id]['active'] = False
        self.path.write_text(json.dumps(self.data, indent=2) + '\n')
        self.path.chmod(0o600)
