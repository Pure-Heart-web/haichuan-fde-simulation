"""Pseudonymize direct identifiers before data reaches the training data plane."""
import hashlib
import hmac
import re

EMAIL = re.compile(r'(?<![\w.+-])([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})(?![\w.-])')
# Phone-like numbers must contain a plausible mobile or grouped subscriber
# pattern. This avoids treating ISO timestamps and SHA/token fragments as phones.
PHONE = re.compile(
    r'(?<![\w-])((?:\+?\d{1,3}[ -]?)?(?:1[3-9]\d[ -]?\d{4}[ -]?\d{4}|'
    r'\(?\d{2,4}\)?[ -]\d{3,4}[ -]\d{4}))(?![\w-])'
)


class PrivacyFilter:
    def __init__(self, key):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ValueError('脱敏密钥至少需要 32 字节')
        self.key = key

    def token(self, tenant_id, kind, value):
        digest = hmac.new(self.key, f'{tenant_id}|{kind}|{value.casefold()}'.encode(),
                          hashlib.sha256).hexdigest()[:20]
        return f'{kind.upper()}-{digest}'

    def sanitize(self, event, manifest):
        if event.get('tenant_id') != manifest['tenant_id'] or event.get('domain') != manifest['domain']:
            raise ValueError('输入记录与客户租户或 Domain 不匹配')
        unexpected = set(event) - set(manifest['allowed_fields']) - {'tenant_id', 'domain'}
        prohibited = set(event) & set(manifest['prohibited_fields'])
        if unexpected or prohibited:
            raise ValueError('输入包含未授权或禁止字段：' + ','.join(sorted(unexpected | prohibited)))
        sanitized = {k: v for k, v in event.items() if k not in ('sender', 'company_name')}
        sanitized['contact_ref'] = self.token(event['tenant_id'], 'contact', event.get('sender', 'unknown'))
        sanitized['customer_ref'] = self.token(event['tenant_id'], 'customer', event.get('company_name', 'unknown'))
        counts = {'email': 0, 'phone': 0}

        def replace_email(match):
            counts['email'] += 1
            return self.token(event['tenant_id'], 'email', match.group(1))

        def replace_phone(match):
            counts['phone'] += 1
            return self.token(event['tenant_id'], 'phone', match.group(1))

        def scrub(value):
            text = EMAIL.sub(replace_email, str(value or ''))
            text = PHONE.sub(replace_phone, text)
            sender = str(event.get('sender', '')).strip()
            company = str(event.get('company_name', '')).strip()
            if sender:
                text = text.replace(sender, sanitized['contact_ref'])
            if company:
                text = text.replace(company, sanitized['customer_ref'])
            return text

        sanitized['body'] = scrub(event.get('body', ''))
        if 'subject' in sanitized:
            sanitized['subject'] = scrub(event.get('subject', ''))
        serialized = str(sanitized)
        if event.get('sender') and event['sender'] in serialized:
            raise ValueError('直接联系人未被移除')
        return sanitized, {'email_redactions': counts['email'],
                           'phone_redactions': counts['phone'],
                           'sender_pseudonymized': bool(event.get('sender')),
                           'company_pseudonymized': bool(event.get('company_name'))}


def contains_direct_identifier(value):
    """Inspect stored text values without turning telemetry numbers into text.

    Stringifying a whole artifact can make an innocent float such as a latency
    sample look like an eleven-digit phone number.  It can also join unrelated
    fields into a phone-like sequence.  Walk the value tree instead so privacy
    checks follow the data types that can actually contain customer text.
    """
    if isinstance(value, str):
        return bool(EMAIL.search(value) or PHONE.search(value))
    if isinstance(value, dict):
        return any(contains_direct_identifier(item) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(contains_direct_identifier(item) for item in value)
    if isinstance(value, int) and not isinstance(value, bool):
        return bool(PHONE.fullmatch(str(value)))
    return False


def detect_untrusted_instruction(text):
    lowered = text.casefold()
    patterns = ('ignore previous', 'ignore all rules', 'send automatically',
                'delete evidence', 'reveal system prompt', 'export all customers')
    return any(pattern in lowered for pattern in patterns)
