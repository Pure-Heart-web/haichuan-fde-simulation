"""Turn email or raw text into WorkItem without domain-specific parsing."""
import hashlib
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path
import re
from datetime import datetime

from .models import WorkItem


class IngestionError(ValueError):
    pass


class TextFromHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'):
            self.skip += 1
        if tag in ('br', 'p', 'div', 'li', 'tr'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('style', 'script') and self.skip:
            self.skip -= 1
        if tag in ('p', 'div', 'li', 'tr'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        return re.sub(r'\n{3,}', '\n\n', ''.join(self.parts)).strip()


def html_to_text(html):
    parser = TextFromHTML()
    parser.feed(html)
    return parser.text()


def _work_id(source_id, body):
    digest = hashlib.sha256((source_id + '\0' + body).encode('utf-8')).hexdigest()[:12]
    return 'WI-' + digest


def from_text(text, *, source_id='manual', tenant_id='haichuan-training', sender='', subject='', received_at=None,
              domain='foreign_trade', source_type='text'):
    if not isinstance(text, str) or not text.strip():
        raise IngestionError('邮件正文为空')
    received = received_at
    if received is not None:
        try:
            if datetime.fromisoformat(received).utcoffset() is None:
                raise ValueError('naive date')
        except ValueError:
            raise IngestionError('received_at 必须是带时区的 ISO 时间') from None
    return WorkItem(_work_id(source_id, text), tenant_id, source_type, source_id, sender,
                    subject, text.strip(), [], received, domain=domain)


def from_eml(path, *, source_id=None, tenant_id='haichuan-training', domain='foreign_trade'):
    path = Path(path)
    raw = path.read_bytes()
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    plain, html, attachments = [], [], []
    for part in msg.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if filename or part.get_content_disposition() == 'attachment':
            attachments.append({'filename': filename or 'unnamed', 'content_type': part.get_content_type()})
            continue
        if part.get_content_type() == 'text/plain':
            plain.append(part.get_content())
        elif part.get_content_type() == 'text/html':
            html.append(part.get_content())
    body = '\n'.join(plain).strip() if plain else html_to_text('\n'.join(html))
    if not body:
        raise IngestionError(f'邮件没有可用正文：{path}')
    try:
        from email.utils import parsedate_to_datetime
        received = parsedate_to_datetime(msg['Date']).isoformat()
        if datetime.fromisoformat(received).utcoffset() is None:
            raise ValueError('naive date')
    except (TypeError, ValueError, IndexError):
        received = None
    sid = source_id or path.stem
    return WorkItem(_work_id(sid, body), tenant_id, 'email', sid,
                    str(msg.get('From', '')), str(msg.get('Subject', '')), body,
                    attachments, received, 'html' if not plain else 'text', domain)
