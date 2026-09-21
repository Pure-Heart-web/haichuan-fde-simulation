"""Durable local mailbox, ticket, CRM/CMMS and unsent outbox simulation."""
import hashlib
import json
import sqlite3
from pathlib import Path

from fde_platform.integrations.mock_inbound import adapt_event


class MockServices:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
          CREATE TABLE IF NOT EXISTS inbox (
            event_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, domain TEXT NOT NULL,
            source_id TEXT NOT NULL, version INTEGER NOT NULL, digest TEXT NOT NULL,
            payload_json TEXT NOT NULL, state TEXT NOT NULL, attempts INTEGER NOT NULL,
            available_tick INTEGER NOT NULL, last_error TEXT,
            UNIQUE(tenant_id,domain,source_id)
          );
          CREATE TABLE IF NOT EXISTS records (
            tenant_id TEXT NOT NULL, domain TEXT NOT NULL, kind TEXT NOT NULL,
            record_id TEXT NOT NULL, payload_json TEXT NOT NULL,
            PRIMARY KEY(tenant_id,domain,kind,record_id)
          );
          CREATE TABLE IF NOT EXISTS outbox (
            tenant_id TEXT NOT NULL, domain TEXT NOT NULL, episode_id TEXT NOT NULL,
            actor_id TEXT NOT NULL, content TEXT NOT NULL, state TEXT NOT NULL,
            PRIMARY KEY(tenant_id,domain,episode_id)
          );
          CREATE TABLE IF NOT EXISTS service_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL, domain TEXT NOT NULL,
            kind TEXT NOT NULL, record_id TEXT NOT NULL, found INTEGER NOT NULL
          );
        ''')

    def close(self):
        self.conn.close()

    def receive(self, event, *, version=1, supersedes_source_id=None):
        adapt_event(event)
        if version < 1 or type(version) is not int:
            raise ValueError('来源版本无效')
        if version > 1:
            prior = self.conn.execute('''SELECT version FROM inbox WHERE tenant_id=? AND domain=?
                AND source_id=?''', (event['tenant_id'], event['domain'], supersedes_source_id)).fetchone()
            if not prior or version != prior['version'] + 1:
                raise ValueError('数据更新缺少上一来源版本')
        digest = hashlib.sha256(json.dumps({k: v for k, v in event.items() if k != 'event_id'},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        old = self.conn.execute('''SELECT digest FROM inbox WHERE event_id=? OR
            (tenant_id=? AND domain=? AND source_id=?)''',
            (event['event_id'], event['tenant_id'], event['domain'], event['source_id'])).fetchone()
        if old:
            if old['digest'] != digest:
                raise ValueError('重复来源或事件 ID 的内容发生变化')
            return False
        with self.conn:
            self.conn.execute('''INSERT INTO inbox VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (event['event_id'], event['tenant_id'], event['domain'], event['source_id'], version,
                 digest, json.dumps(event, ensure_ascii=False), 'pending', 0, 0, None))
        return True

    def work(self, deliver, *, tick=0, timeout_once=()):
        rows = self.conn.execute('''SELECT * FROM inbox WHERE state IN ('pending','retry')
            AND available_tick<=? ORDER BY event_id''', (tick,)).fetchall()
        processed = []
        for row in rows:
            attempt = row['attempts'] + 1
            try:
                if row['event_id'] in timeout_once and attempt == 1:
                    raise TimeoutError('模拟依赖超时')
                event = json.loads(row['payload_json'])
                deliver(event)
                with self.conn:
                    self.conn.execute('''UPDATE inbox SET state='done',attempts=?,last_error=NULL
                        WHERE event_id=?''', (attempt, row['event_id']))
                processed.append({'event_id': row['event_id'], 'state': 'done', 'attempts': attempt})
            except (TimeoutError, OSError, ValueError) as exc:
                state = 'dead_letter' if attempt >= 3 else 'retry'
                with self.conn:
                    self.conn.execute('''UPDATE inbox SET state=?,attempts=?,available_tick=?,last_error=?
                        WHERE event_id=?''', (state, attempt, tick + 2 ** attempt,
                                               type(exc).__name__ + ': ' + str(exc), row['event_id']))
                processed.append({'event_id': row['event_id'], 'state': state, 'attempts': attempt})
        return processed

    def record(self, tenant_id, domain, kind, record_id, payload):
        if kind not in ('ticket', 'sales_inquiry', 'crm', 'cmms'):
            raise ValueError('模拟外部记录类型无效')
        old = self.conn.execute('''SELECT payload_json FROM records WHERE tenant_id=? AND domain=?
            AND kind=? AND record_id=?''', (tenant_id, domain, kind, record_id)).fetchone()
        if old:
            if json.loads(old['payload_json']) != payload:
                raise ValueError('外部记录同 ID 不同版本；必须显式新增版本')
            return False
        with self.conn:
            self.conn.execute('''INSERT INTO records VALUES (?,?,?,?,?)''',
                (tenant_id, domain, kind, record_id, json.dumps(payload, ensure_ascii=False)))
        return True

    def get_record(self, tenant_id, domain, kind, record_id):
        row = self.conn.execute('''SELECT payload_json FROM records WHERE tenant_id=? AND domain=?
            AND kind=? AND record_id=?''', (tenant_id, domain, kind, record_id)).fetchone()
        with self.conn:
            self.conn.execute('''INSERT INTO service_queries
                (tenant_id,domain,kind,record_id,found) VALUES (?,?,?,?,?)''',
                (tenant_id, domain, kind, record_id, int(row is not None)))
        return json.loads(row['payload_json']) if row else None

    def confirm_to_outbox(self, episode, claims, content):
        if episode['tenant_id'] != claims['tenant_id'] or episode['state'] not in ('reviewed', 'closed'):
            raise ValueError('只有同租户已审核案例可人工确认')
        if not content.strip() or claims['role'] not in ('engineer', 'sales'):
            raise ValueError('待发送内容或确认角色无效')
        old = self.conn.execute('''SELECT actor_id,content,state FROM outbox WHERE tenant_id=?
            AND domain=? AND episode_id=?''', (episode['tenant_id'], episode['domain'],
                                             episode['episode_id'])).fetchone()
        if old:
            if old['actor_id'] != claims['sub'] or old['content'] != content.strip():
                raise ValueError('待发送区已有不同人工确认内容；需要版本化重审')
            return old
        with self.conn:
            self.conn.execute('''INSERT INTO outbox VALUES (?,?,?,?,?,?)''',
                (episode['tenant_id'], episode['domain'], episode['episode_id'],
                 claims['sub'], content.strip(), 'pending_send'))
        return self.conn.execute('''SELECT * FROM outbox WHERE tenant_id=? AND domain=?
            AND episode_id=?''', (episode['tenant_id'], episode['domain'], episode['episode_id'])).fetchone()

    def status(self):
        states = {r['state']: r['n'] for r in self.conn.execute('''SELECT state,COUNT(*) n FROM inbox GROUP BY state''')}
        outbox = {r['state']: r['n'] for r in self.conn.execute('''SELECT state,COUNT(*) n FROM outbox GROUP BY state''')}
        retries = self.conn.execute('SELECT SUM(CASE WHEN attempts>1 THEN attempts-1 ELSE 0 END) FROM inbox').fetchone()[0] or 0
        queries = [dict(x) for x in self.conn.execute('''SELECT tenant_id,domain,kind,record_id,found
            FROM service_queries ORDER BY id''')]
        return {'inbox': states, 'outbox': outbox, 'retry_attempts': retries,
                'service_queries': queries, 'sent_messages': 0, 'external_dispatches': 0}
