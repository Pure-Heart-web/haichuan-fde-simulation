"""Append-only draft review and knowledge-gap feedback; never sends messages."""
import json
import sqlite3
from pathlib import Path

from fde_platform.core.models import utc_now


class DraftStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.conn.executescript('''
          CREATE TABLE IF NOT EXISTS drafts (
            case_id TEXT PRIMARY KEY, artifact TEXT NOT NULL, created_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS draft_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL REFERENCES drafts(case_id), action TEXT NOT NULL,
            reviewer TEXT NOT NULL, reviewer_role TEXT NOT NULL, comment TEXT NOT NULL,
            edited_body TEXT, human_authored_unverified INTEGER NOT NULL,
            created_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS knowledge_gaps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL REFERENCES drafts(case_id), intent TEXT NOT NULL,
            query TEXT NOT NULL, reason TEXT NOT NULL, owner TEXT NOT NULL,
            human_answer TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(case_id, intent)
          );
          CREATE TABLE IF NOT EXISTS knowledge_gap_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gap_id INTEGER NOT NULL REFERENCES knowledge_gaps(id),
            owner TEXT NOT NULL, human_answer TEXT NOT NULL,
            status TEXT NOT NULL, created_at TEXT NOT NULL
          );
          CREATE UNIQUE INDEX IF NOT EXISTS one_gap_feedback ON knowledge_gap_feedback(gap_id);
        ''')
        self.conn.commit()

    def close(self):
        self.conn.close()

    def save(self, artifact):
        with self.conn:
            cursor = self.conn.execute('INSERT OR IGNORE INTO drafts VALUES (?, ?, ?)',
                (artifact['case_id'], json.dumps(artifact, ensure_ascii=False), utc_now()))
            if cursor.rowcount:
                for gap in artifact['draft']['knowledge_gaps']:
                    self.conn.execute('''INSERT OR IGNORE INTO knowledge_gaps
                       (case_id,intent,query,reason,owner,human_answer,status,created_at)
                       VALUES (?,?,?,?,?,?,?,?)''',
                       (artifact['case_id'], gap['intent'], gap['query'], gap['reason'],
                        gap['owner'], None, 'open', utc_now()))
        return cursor.rowcount == 1

    def get(self, case_id):
        row = self.conn.execute('SELECT * FROM drafts WHERE case_id=?', (case_id,)).fetchone()
        return {'case_id': case_id, 'artifact': json.loads(row['artifact']),
                'created_at': row['created_at']} if row else None

    def list_items(self):
        rows = self.conn.execute('''SELECT d.case_id, d.artifact,
          (SELECT action FROM draft_reviews r WHERE r.case_id=d.case_id ORDER BY r.id DESC LIMIT 1) latest_action
          FROM drafts d ORDER BY d.case_id''').fetchall()
        return [{'case_id': row['case_id'], 'draft_status': json.loads(row['artifact'])['draft']['status'],
                 'latest_action': row['latest_action']} for row in rows]

    def reviews(self, case_id=None):
        rows = self.conn.execute('SELECT * FROM draft_reviews' +
            (' WHERE case_id=?' if case_id else '') + ' ORDER BY id', (case_id,) if case_id else ()).fetchall()
        return [dict(x) for x in rows]

    def gaps(self, case_id=None):
        rows = self.conn.execute('SELECT * FROM knowledge_gaps' +
            (' WHERE case_id=?' if case_id else '') + ' ORDER BY id', (case_id,) if case_id else ()).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            feedback = self.conn.execute('''SELECT owner,human_answer,status,created_at FROM knowledge_gap_feedback
                WHERE gap_id=? ORDER BY id DESC LIMIT 1''', (item['id'],)).fetchone()
            if feedback:
                item.update(dict(feedback))
            result.append(item)
        return result

    def review(self, case_id, action, reviewer, reviewer_role, comment='', edited_body=None):
        if action not in ('approve', 'minor_edit', 'major_edit', 'reject', 'escalate'):
            raise ValueError('无效草稿审核动作')
        if reviewer_role not in ('sales', 'engineer') or not reviewer.strip():
            raise ValueError('审核者及角色不能为空')
        item = self.get(case_id)
        if item is None:
            raise ValueError('草稿不存在')
        draft = item['artifact']['draft']
        if action == 'approve':
            if draft['status'] == 'needs_identity_review':
                raise ValueError('身份未确认，不能批准草稿')
            if draft['required_reviewer'] == 'engineer' and reviewer_role != 'engineer':
                raise ValueError('该草稿需要工程师审核')
            if self.reviews(case_id) and self.reviews(case_id)[-1]['action'] in ('minor_edit', 'major_edit'):
                raise ValueError('人工改写文本未重新验证，不能直接批准')
        if action in ('minor_edit', 'major_edit'):
            if not edited_body or not edited_body.strip() or edited_body == draft['body']:
                raise ValueError('编辑审核必须提供修改后的正文')
        elif edited_body:
            raise ValueError('只有编辑动作可提交改写正文')
        if action in ('reject', 'escalate', 'major_edit') and not comment.strip():
            raise ValueError('该动作必须说明原因')
        with self.conn:
            self.conn.execute('''INSERT INTO draft_reviews
              (case_id, action, reviewer, reviewer_role, comment, edited_body,
               human_authored_unverified, created_at) VALUES (?,?,?,?,?,?,?,?)''',
               (case_id, action, reviewer.strip(), reviewer_role, comment.strip(), edited_body,
                int(action in ('minor_edit', 'major_edit')), utc_now()))

    def confirm_gap(self, case_id, intent, owner, human_answer):
        if not owner.strip() or not human_answer.strip():
            raise ValueError('知识缺口确认必须填写负责人和答案')
        row = self.conn.execute('SELECT id FROM knowledge_gaps WHERE case_id=? AND intent=?',
                                (case_id, intent)).fetchone()
        if row is None:
            raise ValueError('知识缺口不存在')
        if self.conn.execute('SELECT 1 FROM knowledge_gap_feedback WHERE gap_id=?', (row['id'],)).fetchone():
            raise ValueError('知识缺口已提交治理')
        with self.conn:
            self.conn.execute('''INSERT INTO knowledge_gap_feedback
               (gap_id,owner,human_answer,status,created_at) VALUES (?,?,?,?,?)''',
               (row['id'], owner.strip(), human_answer.strip(), 'pending_governance', utc_now()))
