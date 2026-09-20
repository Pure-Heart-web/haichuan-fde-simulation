"""SQLite teaching store: every application read is tenant/domain scoped."""
import hashlib
import json
import sqlite3
from pathlib import Path

from fde_platform.core.models import utc_now
from fde_platform.core.platform.contracts import FeedbackEvent

KINDS = frozenset({'case_record', 'work_item', 'context', 'knowledge', 'rule', 'trace',
                   'eval', 'review_task', 'recommendation'})
IDENTIFIER_FIELDS = {'work_item': 'id', 'context': 'serial_number', 'knowledge': 'document_id',
                     'rule': 'id', 'trace': 'trace_id', 'review_task': 'task_id',
                     'recommendation': 'case_id', 'case_record': 'case_record_id'}


class TenantStore:
    def __init__(self, path, tenant_domains):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.tenant_domains = dict(tenant_domains)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.conn.executescript('''
          CREATE TABLE IF NOT EXISTS artifacts (
            tenant_id TEXT NOT NULL, domain TEXT NOT NULL, kind TEXT NOT NULL,
            artifact_id TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, domain, kind, artifact_id)
          );
          CREATE TABLE IF NOT EXISTS feedback_events (
            tenant_id TEXT NOT NULL, domain TEXT NOT NULL, event_id TEXT NOT NULL,
            task_id TEXT NOT NULL, trace_id TEXT NOT NULL, actor_id TEXT NOT NULL,
            actor_role TEXT NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, domain, event_id)
          );
        ''')
        self.conn.commit()

    def close(self):
        self.conn.close()

    def scope(self, tenant_id, domain):
        if self.tenant_domains.get(tenant_id) != domain:
            raise ValueError('未知租户或租户与 Domain 不匹配')
        return TenantSession(self, tenant_id, domain)


class TenantSession:
    def __init__(self, store, tenant_id, domain):
        self.store, self.tenant_id, self.domain = store, tenant_id, domain

    def put(self, kind, artifact_id, payload):
        if kind not in KINDS or not artifact_id or not isinstance(payload, dict):
            raise ValueError('无效的租户数据类型或内容')
        if payload.get('tenant_id', self.tenant_id) != self.tenant_id or payload.get('domain', self.domain) != self.domain:
            raise ValueError('内容与当前租户范围不匹配')
        field = IDENTIFIER_FIELDS.get(kind)
        if field and payload.get(field) != artifact_id:
            raise ValueError('内容 ID 与存储键不匹配')
        value = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        old = self.get(kind, artifact_id)
        if old is not None:
            if old != json.loads(value):
                raise ValueError('已有同 ID 不同版本；请使用新的演练目录')
            return False
        with self.store.conn:
            self.store.conn.execute('INSERT INTO artifacts VALUES (?,?,?,?,?,?)',
                (self.tenant_id, self.domain, kind, artifact_id, value, utc_now()))
        return True

    def get(self, kind, artifact_id):
        if kind not in KINDS:
            raise ValueError('未知数据类型')
        row = self.store.conn.execute('''SELECT payload_json FROM artifacts
            WHERE tenant_id=? AND domain=? AND kind=? AND artifact_id=?''',
            (self.tenant_id, self.domain, kind, artifact_id)).fetchone()
        return json.loads(row['payload_json']) if row else None

    def list(self, kind):
        if kind not in KINDS:
            raise ValueError('未知数据类型')
        rows = self.store.conn.execute('''SELECT payload_json FROM artifacts
            WHERE tenant_id=? AND domain=? AND kind=? ORDER BY artifact_id''',
            (self.tenant_id, self.domain, kind)).fetchall()
        return [json.loads(row['payload_json']) for row in rows]

    def feedback(self, task_id=None):
        sql = 'SELECT * FROM feedback_events WHERE tenant_id=? AND domain=?'
        args = [self.tenant_id, self.domain]
        if task_id is not None:
            sql += ' AND task_id=?'
            args.append(task_id)
        rows = self.store.conn.execute(sql + ' ORDER BY created_at,event_id', args).fetchall()
        return [dict(x) for x in rows]

    def review(self, task_id, actor_id, actor_role, action, reason=''):
        with self.store.conn:
            return self._review_uncommitted(task_id, actor_id, actor_role, action, reason)

    def _review_uncommitted(self, task_id, actor_id, actor_role, action, reason=''):
        task = self.get('review_task', task_id)
        if task is None:
            raise ValueError('任务不存在于当前租户')
        if task['assignee_id'] != actor_id or task['assignee_role'] != actor_role:
            raise ValueError('当前人员或角色无权处理任务')
        if self.feedback(task_id):
            raise ValueError('任务已有审核决定')
        if action not in ('approve', 'edit', 'reject', 'escalate', 'resolve'):
            raise ValueError('审核动作无效')
        if action == 'resolve' and actor_role != 'engineer':
            raise ValueError('只有工程师可完成技术复核')
        if action != 'approve' and not reason.strip():
            raise ValueError('修改、拒绝或升级必须说明原因')
        if action == 'approve' and task['payload'].get('blocking_risk'):
            raise ValueError('高风险安全阻断项不能批准远程指导')
        if self.get('trace', task['trace_id']) is None:
            raise ValueError('审核任务缺少当前租户 Trace')
        event_id = 'FB-' + hashlib.sha256((self.tenant_id + '|' + task_id + '|' + actor_id + '|' + action).encode()).hexdigest()[:16]
        event = FeedbackEvent(event_id, self.tenant_id, self.domain, task_id, task['trace_id'],
                              actor_id, actor_role, action, reason.strip(), utc_now())
        self.store.conn.execute('''INSERT INTO feedback_events
          (tenant_id,domain,event_id,task_id,trace_id,actor_id,actor_role,action,reason,created_at)
          VALUES (?,?,?,?,?,?,?,?,?,?)''',
          (event.tenant_id, event.domain, event.event_id, event.task_id, event.trace_id,
           event.actor_id, event.actor_role, event.action, event.reason, event.created_at))
        return event
