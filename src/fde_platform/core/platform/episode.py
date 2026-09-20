"""Tenant-scoped, append-only workflow journal for two-domain vertical slices."""
import hashlib
import json
from datetime import datetime

from fde_platform.core.models import utc_now


def _digest(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()[:20]


class EpisodeJournal:
    def __init__(self, session):
        self.session = session
        self.conn = session.store.conn
        self.conn.executescript('''
          CREATE TABLE IF NOT EXISTS episodes (
            tenant_id TEXT NOT NULL, domain TEXT NOT NULL, episode_id TEXT NOT NULL,
            case_id TEXT NOT NULL, source_type TEXT NOT NULL, source_id TEXT NOT NULL,
            source_digest TEXT NOT NULL, state TEXT NOT NULL,
            case_record_id TEXT, work_item_id TEXT, trace_id TEXT, review_task_id TEXT, outcome_id TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, domain, episode_id),
            UNIQUE (tenant_id, domain, source_type, source_id)
          );
          CREATE TABLE IF NOT EXISTS episode_events (
            tenant_id TEXT NOT NULL, domain TEXT NOT NULL, episode_id TEXT NOT NULL,
            seq INTEGER NOT NULL, event_type TEXT NOT NULL, actor_id TEXT NOT NULL,
            payload_json TEXT NOT NULL, occurred_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, domain, episode_id, seq),
            FOREIGN KEY (tenant_id, domain, episode_id)
              REFERENCES episodes(tenant_id, domain, episode_id)
          );
        ''')

    def _row(self, episode_id):
        row = self.conn.execute('''SELECT * FROM episodes
            WHERE tenant_id=? AND domain=? AND episode_id=?''',
            (self.session.tenant_id, self.session.domain, episode_id)).fetchone()
        return dict(row) if row else None

    def get(self, episode_id):
        return self._row(episode_id)

    def list(self):
        rows = self.conn.execute('''SELECT * FROM episodes WHERE tenant_id=? AND domain=?
            ORDER BY case_id''', (self.session.tenant_id, self.session.domain)).fetchall()
        return [dict(row) for row in rows]

    def events(self, episode_id):
        if self._row(episode_id) is None:
            return []
        rows = self.conn.execute('''SELECT seq,event_type,actor_id,payload_json,occurred_at
            FROM episode_events WHERE tenant_id=? AND domain=? AND episode_id=? ORDER BY seq''',
            (self.session.tenant_id, self.session.domain, episode_id)).fetchall()
        return [{'seq': row['seq'], 'event_type': row['event_type'], 'actor_id': row['actor_id'],
                 'payload': json.loads(row['payload_json']), 'occurred_at': row['occurred_at']}
                for row in rows]

    def _append(self, episode_id, event_type, actor_id, payload):
        seq = self.conn.execute('''SELECT COALESCE(MAX(seq), 0) + 1 FROM episode_events
            WHERE tenant_id=? AND domain=? AND episode_id=?''',
            (self.session.tenant_id, self.session.domain, episode_id)).fetchone()[0]
        self.conn.execute('''INSERT INTO episode_events VALUES (?,?,?,?,?,?,?,?)''',
            (self.session.tenant_id, self.session.domain, episode_id, seq,
             event_type, actor_id, json.dumps(payload, ensure_ascii=False, sort_keys=True), utc_now()))

    def receive(self, event):
        if (event['tenant_id'], event['domain']) != (self.session.tenant_id, self.session.domain):
            raise ValueError('输入事件与当前租户不匹配')
        for key in ('case_id', 'event_id', 'source_type', 'source_id', 'text', 'received_at'):
            if not event.get(key):
                raise ValueError(f'输入事件缺少 {key}')
        # Treat metadata changes (owner, subject, as_of, etc.) as a new source version too.
        source_digest = _digest(json.dumps(event, sort_keys=True, ensure_ascii=False))
        episode_id = 'EP-' + _digest('|'.join((self.session.tenant_id, self.session.domain,
                                               event['source_type'], event['source_id'])))
        old = self._row(episode_id)
        if old:
            if old['source_digest'] != source_digest or old['case_id'] != event['case_id']:
                raise ValueError('同一来源 ID 的内容已改变；必须人工核对版本')
            return old, False
        now = utc_now()
        with self.conn:
            self.conn.execute('''INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (self.session.tenant_id, self.session.domain, episode_id, event['case_id'],
                 event['source_type'], event['source_id'], source_digest, 'received',
                 None, None, None, None, None, now, now))
            self._append(episode_id, 'inbound_received', 'mock_integration',
                {'event_id': event['event_id'], 'source_type': event['source_type'],
                 'source_id': event['source_id'], 'source_digest': source_digest,
                 'received_at': event['received_at'], 'raw_text_in_journal': False})
        return self._row(episode_id), True

    def case_created(self, episode_id, case_record_id):
        episode = self._row(episode_id)
        if episode is None:
            raise ValueError('当前租户找不到流程')
        if episode['state'] != 'received':
            if episode['case_record_id'] == case_record_id:
                return False
            raise ValueError('当前状态不能替换工单或询盘')
        record = self.session.get('case_record', case_record_id)
        if not record or record['case_id'] != episode['case_id'] or record['source_id'] != episode['source_id']:
            raise ValueError('工单/询盘与输入来源不一致')
        with self.conn:
            self.conn.execute('''UPDATE episodes SET state=?,case_record_id=?,updated_at=?
                WHERE tenant_id=? AND domain=? AND episode_id=?''',
                ('case_open', case_record_id, utc_now(),
                 self.session.tenant_id, self.session.domain, episode_id))
            self._append(episode_id, 'case_created', 'mock_integration',
                {'case_record_id': case_record_id, 'kind': record['kind'],
                 'source_event_id': record['source_event_id'], 'status': record['status']})
        return True

    def proposal_ready(self, episode_id, work_item_id, trace_id, review_task_id, *, actor_id='system'):
        episode = self._row(episode_id)
        if episode is None:
            raise ValueError('当前租户找不到流程')
        if episode['state'] != 'case_open':
            if (episode['work_item_id'], episode['trace_id'], episode['review_task_id']) == (
                    work_item_id, trace_id, review_task_id):
                return False
            raise ValueError('当前状态不能替换建议')
        trace = self.session.get('trace', trace_id)
        task = self.session.get('review_task', review_task_id)
        work = self.session.get('work_item', work_item_id)
        case_record = self.session.get('case_record', episode['case_record_id'])
        recommendation = self.session.get('recommendation', episode['case_id'])
        if (not trace or not task or not work or not case_record or not recommendation or
            task['trace_id'] != trace_id or trace['case_id'] != episode['case_id'] or
            work['source_id'] != episode['case_id']):
            raise ValueError('建议、Trace 与审核任务未在当前租户闭环')
        if not recommendation['requires_review']:
            raise ValueError('纵向演练必须进入人工审核')
        with self.conn:
            self.conn.execute('''UPDATE episodes SET state=?,work_item_id=?,trace_id=?,review_task_id=?,updated_at=?
                WHERE tenant_id=? AND domain=? AND episode_id=?''',
                ('pending_review', work_item_id, trace_id, review_task_id, utc_now(),
                 self.session.tenant_id, self.session.domain, episode_id))
            self._append(episode_id, 'proposal_ready', actor_id,
                {'work_item_id': work_item_id, 'trace_id': trace_id, 'review_task_id': review_task_id,
                 'top_option': recommendation['options'][0]['code'],
                 'evidence_refs': recommendation['evidence_refs'],
                 'risk_level': recommendation['risk_level'],
                 'auto_send': False, 'auto_dispatch': False})
        return True

    def record_edit(self, episode_id, *, actor_id, actor_role, edited_action, reason):
        episode = self._row(episode_id)
        if episode is None or episode['state'] != 'pending_review':
            raise ValueError('只有待审核流程可以记录人工修改')
        if not edited_action.strip() or not reason.strip():
            raise ValueError('人工修改与原因不能为空')
        recommendation = self.session.get('recommendation', episode['case_id'])
        before = recommendation['options'][0]['label']
        if edited_action.strip() == before:
            raise ValueError('修改后内容必须与系统建议不同')
        with self.conn:
            feedback = self.session._review_uncommitted(
                episode['review_task_id'], actor_id, actor_role, 'edit', reason)
            self.conn.execute('''UPDATE episodes SET state=?,updated_at=?
                WHERE tenant_id=? AND domain=? AND episode_id=?''',
                ('reviewed', utc_now(), self.session.tenant_id, self.session.domain, episode_id))
            self._append(episode_id, 'human_edited', actor_id,
                {'actor_role': actor_role, 'feedback_event_id': feedback.event_id,
                 'before': before, 'after': edited_action.strip(), 'reason': reason.strip(),
                 'customer_message_sent': False})
        return feedback

    def close(self, episode_id, outcome):
        episode = self._row(episode_id)
        if episode is None or episode['state'] != 'reviewed':
            raise ValueError('必须先完成对应人工审核才能记录最终结果')
        if (outcome.get('tenant_id'), outcome.get('domain'), outcome.get('case_id')) != (
                self.session.tenant_id, self.session.domain, episode['case_id']):
            raise ValueError('最终结果与当前租户或案例不匹配')
        for key in ('outcome_id', 'outcome_type', 'value', 'evidence_ref', 'observed_by', 'recorded_at'):
            if not outcome.get(key):
                raise ValueError(f'最终结果缺少 {key}')
        allowed = {'after_sales': 'confirmed_fault', 'foreign_trade': 'customer_requirements_confirmed'}
        if outcome['outcome_type'] != allowed[self.session.domain] or outcome.get('status') != 'synthetic_reviewed':
            raise ValueError('结果类型或模拟复核状态无效')
        occurred = datetime.fromisoformat(outcome['recorded_at'])
        received = datetime.fromisoformat(self.events(episode_id)[0]['payload']['received_at'])
        if occurred.utcoffset() is None or occurred < received:
            raise ValueError('结果记录时间无时区或早于输入')
        with self.conn:
            self.conn.execute('''UPDATE episodes SET state=?,outcome_id=?,updated_at=?
                WHERE tenant_id=? AND domain=? AND episode_id=?''',
                ('closed', outcome['outcome_id'], utc_now(),
                 self.session.tenant_id, self.session.domain, episode_id))
            self._append(episode_id, 'outcome_recorded', outcome['observed_by'],
                {'outcome_id': outcome['outcome_id'], 'outcome_type': outcome['outcome_type'],
                 'value': outcome['value'], 'evidence_ref': outcome['evidence_ref'],
                 'recorded_at': outcome['recorded_at'], 'status': outcome['status'],
                 'actual_customer_or_asset_observation': False})
        return self._row(episode_id)
