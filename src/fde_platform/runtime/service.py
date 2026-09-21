"""Application service combining authorization, privacy, worker and review contracts."""
from fde_platform.onboarding.privacy import PrivacyFilter


class DeliveryRoomService:
    def __init__(self, store, manifest, broker, components, privacy_key, *, service_token):
        if manifest['mode'] != 'synthetic_design_partner':
            raise ValueError('本地 Delivery Room 不得处理真实客户数据')
        if not service_token or len(service_token) < 24:
            raise ValueError('Connector 服务令牌至少 24 字符')
        self.store, self.manifest, self.broker = store, manifest, broker
        self.components, self.service_token = components, service_token
        self.privacy = PrivacyFilter(privacy_key)

    def accept(self, raw_event, service_token):
        if service_token != self.service_token:
            raise ValueError('Connector 服务身份认证失败')
        sanitized, privacy_audit = self.privacy.sanitize(raw_event, self.manifest)
        state = self.store.accept(sanitized)
        return {'state': state, 'event_id': sanitized['event_id'],
                'privacy': privacy_audit}

    def claims(self, token):
        return self.broker.verify(token, tenant_id=self.manifest['tenant_id'])

    def require_role(self, token, *roles):
        claims = self.claims(token)
        if claims['role'] not in roles:
            raise ValueError('当前角色无运行操作权限')
        return claims

    def cases(self, token):
        claims = self.claims(token)
        return self.store.cases(claims['tenant_id'], claims['sub'])

    def trace(self, token, case_id):
        claims = self.claims(token)
        return self.store.trace(claims['tenant_id'], case_id, claims['sub'])

    def review(self, token, case_id, action, reason):
        claims = self.claims(token)
        return self.store.review(claims['tenant_id'], case_id, claims, action, reason)

    def approve(self, token, message_id):
        claims = self.claims(token)
        return self.store.approve_message(claims['tenant_id'], message_id, claims)

    def requeue_event(self, token, event_id, reason):
        claims = self.require_role(token, 'operator')
        return self.store.requeue_dead_event(claims['tenant_id'], event_id, claims, reason)

    def requeue_message(self, token, message_id, reason):
        claims = self.require_role(token, 'operator')
        return self.store.requeue_dead_message(claims['tenant_id'], message_id, claims, reason)
