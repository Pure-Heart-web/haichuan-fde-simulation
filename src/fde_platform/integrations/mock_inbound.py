"""Validate synthetic external events and convert them to domain input cases."""
from datetime import datetime
from fde_platform.core.platform.contracts import CaseRecord


def adapt_event(event):
    pair = (event.get('tenant_id'), event.get('domain'), event.get('source_type'))
    if pair == ('qihang-training', 'after_sales', 'call_transcript'):
        item = {'id': event['case_id'], 'text': event['text'], 'as_of': event['as_of'],
                'source_type': event['source_type']}
    elif pair == ('haichuan-training', 'foreign_trade', 'email'):
        item = {key: event[key] for key in ('sender', 'company_name', 'region', 'subject',
                                            'owner', 'scope', 'text', 'as_of')}
        item['id'] = event['case_id']
        item['source_type'] = 'email'
    else:
        raise ValueError('未批准的模拟输入渠道或租户/领域组合')
    received = datetime.fromisoformat(event['received_at'])
    if received.utcoffset() is None:
        raise ValueError('模拟输入时间必须带时区')
    return item


def create_case_record(event):
    adapt_event(event)
    kind, prefix = (('service_ticket', 'TKT-') if event['domain'] == 'after_sales'
                    else ('sales_inquiry', 'INQ-'))
    return CaseRecord(prefix + event['case_id'], event['tenant_id'], event['domain'],
                      event['case_id'], kind, event['event_id'], event['source_id'], 'open')
