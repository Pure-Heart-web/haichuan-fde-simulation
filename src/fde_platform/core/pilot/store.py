"""Local task queue with append-only decisions and trace-linked review events."""
import json
import sqlite3
from pathlib import Path

from fde_platform.core.models import utc_now


class PilotStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.conn.executescript('''
          CREATE TABLE IF NOT EXISTS traces (
            trace_id TEXT PRIMARY KEY, case_id TEXT NOT NULL UNIQUE, mode TEXT NOT NULL,
            trace_json TEXT NOT NULL, created_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS review_tasks (
            task_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, trace_id TEXT NOT NULL REFERENCES traces(trace_id),
            type TEXT NOT NULL, risk_level TEXT NOT NULL, assignee_role TEXT NOT NULL,
            assignee_id TEXT NOT NULL, prerequisite_task_id TEXT REFERENCES review_tasks(task_id),
            payload TEXT NOT NULL, evidence TEXT NOT NULL, created_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS review_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES review_tasks(task_id),
            actor_id TEXT NOT NULL, actor_role TEXT NOT NULL, action TEXT NOT NULL,
            override_category TEXT, comment TEXT NOT NULL, created_at TEXT NOT NULL
          );
        ''')
        self.conn.commit()

    def close(self):
        self.conn.close()

    def save_trace(self, trace):
        with self.conn:
            cursor = self.conn.execute('INSERT OR IGNORE INTO traces VALUES (?,?,?,?,?)',
                (trace['trace_id'], trace['case_id'], trace['mode'], json.dumps(trace, ensure_ascii=False), utc_now()))
        return cursor.rowcount == 1

    def save_task(self, task):
        if task.status != 'pending':
            raise ValueError('只能创建待审核任务')
        trace = self.conn.execute('SELECT mode FROM traces WHERE trace_id=?', (task.trace_id,)).fetchone()
        if trace is None or trace['mode'] != 'pilot':
            raise ValueError('Shadow 结果不得创建可见审核任务')
        with self.conn:
            cursor = self.conn.execute('''INSERT OR IGNORE INTO review_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                (task.task_id, task.case_id, task.trace_id, task.type, task.risk_level,
                 task.assignee_role, task.assignee_id, task.prerequisite_task_id,
                 json.dumps(task.payload, ensure_ascii=False), json.dumps(task.evidence, ensure_ascii=False), utc_now()))
        return cursor.rowcount == 1

    def events(self, task_id=None):
        rows = self.conn.execute('SELECT * FROM review_events' + (' WHERE task_id=?' if task_id else '') +
                                 ' ORDER BY id', (task_id,) if task_id else ()).fetchall()
        return [dict(x) for x in rows]

    def _status(self, task_id):
        events = self.events(task_id)
        if not events:
            return 'pending'
        return {'approve': 'completed', 'resolve': 'completed', 'override': 'completed',
                'edit': 'needs_revision', 'reject': 'rejected', 'escalate': 'escalated'}[events[-1]['action']]

    def get_task(self, task_id):
        row = self.conn.execute('SELECT * FROM review_tasks WHERE task_id=?', (task_id,)).fetchone()
        if row is None:
            return None
        item = dict(row)
        item['payload'] = json.loads(item['payload'])
        item['evidence'] = json.loads(item['evidence'])
        item['status'] = self._status(task_id)
        return item

    def list_tasks(self, *, actor_id=None, role=None):
        rows = self.conn.execute('SELECT task_id FROM review_tasks ORDER BY task_id').fetchall()
        tasks = [self.get_task(x['task_id']) for x in rows]
        if role == 'admin':
            return tasks
        if actor_id and role:
            return [x for x in tasks if x['assignee_id'] == actor_id and x['assignee_role'] == role]
        return []

    def list_traces(self):
        rows = self.conn.execute('SELECT trace_id,case_id,mode FROM traces ORDER BY case_id').fetchall()
        return [dict(x) for x in rows]

    def get_trace(self, case_id):
        row = self.conn.execute('SELECT trace_json FROM traces WHERE case_id=?', (case_id,)).fetchone()
        if row is None:
            return None
        trace = json.loads(row['trace_json'])
        reviews = self.conn.execute('''SELECT e.actor_id,e.actor_role,e.action,e.override_category,e.created_at
            FROM review_events e JOIN review_tasks t ON t.task_id=e.task_id WHERE t.trace_id=? ORDER BY e.id''',
            (trace['trace_id'],)).fetchall()
        trace['human_review_events'] = [dict(x) for x in reviews]
        return trace

    def review(self, task_id, actor_id, actor_role, action, comment='', override_category=None):
        task = self.get_task(task_id)
        if task is None:
            raise ValueError('审核任务不存在')
        if task['assignee_id'] != actor_id or task['assignee_role'] != actor_role:
            raise ValueError('当前角色或负责人无权处理此任务')
        if task['status'] != 'pending':
            raise ValueError('任务已处理，不能覆盖决定')
        if task['prerequisite_task_id'] and self._status(task['prerequisite_task_id']) != 'completed':
            raise ValueError('工程师前置审核尚未完成')
        allowed = {'sales_draft': {'approve', 'edit', 'reject', 'escalate'},
                   'engineer_review': {'resolve', 'override', 'escalate'}}
        if action not in allowed[task['type']]:
            raise ValueError('该任务类型不允许此动作')
        if action == 'approve' and (task['payload'].get('manual_fallback') or
                                    task['payload'].get('draft_status') == 'needs_identity_review'):
            raise ValueError('无可验证草稿或身份未确认，不能批准')
        if action in ('edit', 'reject', 'escalate', 'override') and not comment.strip():
            raise ValueError('修改、拒绝、升级或覆盖必须说明原因')
        if action == 'override' and override_category not in (
                'commercial_preference', 'missing_rule', 'bad_ranking', 'data_error', 'user_preference'):
            raise ValueError('覆盖必须选择原因分类')
        if action != 'override' and override_category:
            raise ValueError('非覆盖动作不能填写覆盖分类')
        with self.conn:
            self.conn.execute('''INSERT INTO review_events
                (task_id,actor_id,actor_role,action,override_category,comment,created_at)
                VALUES (?,?,?,?,?,?,?)''',
                (task_id, actor_id, actor_role, action, override_category, comment.strip(), utc_now()))
