"""Tenant-scoped local shadow store. It intentionally refuses real customer mode."""
import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from fde_platform.core.models import utc_now
from .privacy import contains_direct_identifier


class ShadowDataPlane:
    def __init__(self, path, manifest):
        if manifest['mode'] != 'synthetic_design_partner':
            raise ValueError('本地 ShadowDataPlane 不得处理真实客户数据')
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tenant_id, self.domain = manifest['tenant_id'], manifest['domain']
        self.retention_days = manifest['retention_days']
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
          CREATE TABLE IF NOT EXISTS source_events (
            tenant_id TEXT NOT NULL, domain TEXT NOT NULL, event_id TEXT NOT NULL,
            source_id TEXT NOT NULL, source_version INTEGER NOT NULL, digest TEXT NOT NULL,
            received_at TEXT NOT NULL, payload_json TEXT NOT NULL, status TEXT NOT NULL,
            superseded INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(tenant_id,domain,event_id),
            UNIQUE(tenant_id,domain,source_id,source_version)
          );
          CREATE TABLE IF NOT EXISTS shadow_cases (
            tenant_id TEXT NOT NULL, domain TEXT NOT NULL, case_id TEXT NOT NULL,
            source_id TEXT NOT NULL, source_version INTEGER NOT NULL, route TEXT NOT NULL,
            assignee_id TEXT NOT NULL, assignee_role TEXT NOT NULL,
            artifact_json TEXT NOT NULL, state TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(tenant_id,domain,case_id)
          );
          CREATE TABLE IF NOT EXISTS review_events (
            tenant_id TEXT NOT NULL, domain TEXT NOT NULL, case_id TEXT NOT NULL,
            actor_id TEXT NOT NULL, actor_role TEXT NOT NULL, action TEXT NOT NULL,
            reason TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(tenant_id,domain,case_id)
          );
          CREATE TABLE IF NOT EXISTS access_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL,
            actor_id TEXT NOT NULL, action TEXT NOT NULL, object_id TEXT NOT NULL,
            allowed INTEGER NOT NULL, created_at TEXT NOT NULL
          );
        ''')

    def close(self):
        self.conn.close()

    def _scope(self, tenant_id):
        if tenant_id != self.tenant_id:
            raise ValueError('禁止访问其他客户租户的数据面')

    def ingest(self, event):
        self._scope(event['tenant_id'])
        if contains_direct_identifier(event):
            raise ValueError('数据面拒绝保存直接邮箱或电话号码')
        canonical = json.dumps(event, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        existing_event = self.conn.execute('''SELECT digest FROM source_events WHERE
            tenant_id=? AND domain=? AND event_id=?''',
            (self.tenant_id, self.domain, event['event_id'])).fetchone()
        if existing_event:
            if existing_event['digest'] != digest:
                raise ValueError('同一事件 ID 的净化内容发生变化')
            return 'duplicate'
        prior = self.conn.execute('''SELECT MAX(source_version) version FROM source_events
            WHERE tenant_id=? AND domain=? AND source_id=?''',
            (self.tenant_id, self.domain, event['source_id'])).fetchone()['version']
        if prior is not None and event['source_version'] != prior + 1:
            raise ValueError('来源更新必须连续递增版本')
        if prior is None and event['source_version'] != 1:
            raise ValueError('新来源必须从版本 1 开始')
        with self.conn:
            if prior is not None:
                self.conn.execute('''UPDATE source_events SET superseded=1 WHERE tenant_id=?
                    AND domain=? AND source_id=?''',
                    (self.tenant_id, self.domain, event['source_id']))
            self.conn.execute('''INSERT INTO source_events VALUES (?,?,?,?,?,?,?,?,?,0)''',
                (self.tenant_id, self.domain, event['event_id'], event['source_id'],
                 event['source_version'], digest, event['received_at'], canonical, 'accepted'))
        return 'updated' if prior is not None else 'created'

    def save_case(self, case_id, source_id, source_version, route, assignee_id,
                  assignee_role, artifact):
        if contains_direct_identifier(artifact):
            raise ValueError('Shadow 产物含直接标识符')
        old = self.get_case(self.tenant_id, case_id, actor_id='system')
        payload = json.dumps(artifact, ensure_ascii=False, sort_keys=True)
        if old:
            if old['source_id'] == source_id and old['source_version'] >= source_version:
                return False
            with self.conn:
                self.conn.execute('''UPDATE shadow_cases SET source_version=?,route=?,assignee_id=?,
                    assignee_role=?,artifact_json=?,state='pending_review',created_at=?
                    WHERE tenant_id=? AND domain=? AND case_id=?''',
                    (source_version, route, assignee_id, assignee_role, payload, utc_now(),
                     self.tenant_id, self.domain, case_id))
                self.conn.execute('''DELETE FROM review_events WHERE tenant_id=? AND domain=?
                    AND case_id=?''', (self.tenant_id, self.domain, case_id))
            return True
        with self.conn:
            self.conn.execute('''INSERT INTO shadow_cases VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (self.tenant_id, self.domain, case_id, source_id, source_version, route,
                 assignee_id, assignee_role, payload, 'pending_review', utc_now()))
        return True

    def get_case(self, tenant_id, case_id, *, actor_id):
        allowed = tenant_id == self.tenant_id
        with self.conn:
            self.conn.execute('INSERT INTO access_audit (tenant_id,actor_id,action,object_id,allowed,created_at) VALUES (?,?,?,?,?,?)',
                (tenant_id, actor_id, 'read_case', case_id, int(allowed), utc_now()))
        if not allowed:
            raise ValueError('禁止访问其他客户租户的数据面')
        row = self.conn.execute('''SELECT * FROM shadow_cases WHERE tenant_id=? AND domain=?
            AND case_id=?''', (self.tenant_id, self.domain, case_id)).fetchone()
        if not row:
            return None
        item = dict(row)
        item['artifact'] = json.loads(item.pop('artifact_json'))
        return item

    def list_cases(self, tenant_id, *, actor_id):
        self._scope(tenant_id)
        ids = [x['case_id'] for x in self.conn.execute('''SELECT case_id FROM shadow_cases
            WHERE tenant_id=? AND domain=? ORDER BY case_id''', (self.tenant_id, self.domain))]
        return [self.get_case(tenant_id, case_id, actor_id=actor_id) for case_id in ids]

    def review(self, tenant_id, case_id, claims, action, reason):
        item = self.get_case(tenant_id, case_id, actor_id=claims['sub'])
        if not item or (claims['sub'], claims['role']) != (item['assignee_id'], item['assignee_role']):
            raise ValueError('当前身份不是 Shadow 案例负责人')
        if item['state'] != 'pending_review' or action not in ('accept', 'edit', 'escalate', 'reject'):
            raise ValueError('Shadow 审核状态或动作无效')
        if not reason.strip():
            raise ValueError('Shadow 审核必须说明理由')
        with self.conn:
            self.conn.execute('INSERT INTO review_events VALUES (?,?,?,?,?,?,?,?)',
                (self.tenant_id, self.domain, case_id, claims['sub'], claims['role'],
                 action, reason.strip(), utc_now()))
            self.conn.execute('''UPDATE shadow_cases SET state='reviewed' WHERE tenant_id=?
                AND domain=? AND case_id=?''', (self.tenant_id, self.domain, case_id))
        return True

    def audit(self):
        return [dict(x) for x in self.conn.execute('SELECT * FROM access_audit ORDER BY id')]

    def purge_expired(self, *, as_of):
        cutoff = datetime.fromisoformat(as_of)
        if cutoff.utcoffset() is None:
            raise ValueError('清理时间必须带时区')
        rows = self.conn.execute('''SELECT event_id,received_at FROM source_events
            WHERE tenant_id=? AND domain=?''', (self.tenant_id, self.domain)).fetchall()
        expired = [x['event_id'] for x in rows if datetime.fromisoformat(x['received_at']) +
                   timedelta(days=self.retention_days) <= cutoff]
        affected_sources = [x['source_id'] for x in self.conn.execute('''SELECT source_id
            FROM source_events WHERE tenant_id=? AND domain=? AND event_id IN (%s)''' %
            ','.join('?' for _ in expired),
            (self.tenant_id, self.domain, *expired))] if expired else []
        purged_cases = []
        with self.conn:
            for event_id in expired:
                self.conn.execute('''DELETE FROM source_events WHERE tenant_id=? AND domain=?
                    AND event_id=?''', (self.tenant_id, self.domain, event_id))
            for source_id in sorted(set(affected_sources)):
                remaining = self.conn.execute('''SELECT 1 FROM source_events WHERE tenant_id=?
                    AND domain=? AND source_id=? LIMIT 1''',
                    (self.tenant_id, self.domain, source_id)).fetchone()
                if remaining:
                    continue
                case_rows = self.conn.execute('''SELECT case_id FROM shadow_cases WHERE tenant_id=?
                    AND domain=? AND source_id=?''',
                    (self.tenant_id, self.domain, source_id)).fetchall()
                for row in case_rows:
                    purged_cases.append(row['case_id'])
                    self.conn.execute('''DELETE FROM review_events WHERE tenant_id=? AND domain=?
                        AND case_id=?''', (self.tenant_id, self.domain, row['case_id']))
                self.conn.execute('''DELETE FROM shadow_cases WHERE tenant_id=? AND domain=?
                    AND source_id=?''', (self.tenant_id, self.domain, source_id))
        return {'purged_event_ids': sorted(expired), 'as_of': as_of,
                'purged_case_ids': sorted(purged_cases),
                'retention_days': self.retention_days}
