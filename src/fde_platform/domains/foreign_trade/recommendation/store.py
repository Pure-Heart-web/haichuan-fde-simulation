"""SQLite review queue: immutable recommendations and append-only human events."""
import json
import sqlite3
from pathlib import Path

from fde_platform.core.models import utc_now


class RecommendationStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
          CREATE TABLE IF NOT EXISTS recommendations (
            work_item_id TEXT PRIMARY KEY, inquiry TEXT NOT NULL, result TEXT NOT NULL,
            origin TEXT NOT NULL, created_at TEXT NOT NULL
          );
          CREATE TABLE IF NOT EXISTS recommendation_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT, work_item_id TEXT NOT NULL
              REFERENCES recommendations(work_item_id), action TEXT NOT NULL,
            reviewer TEXT NOT NULL, reviewer_role TEXT NOT NULL, chosen_sku TEXT,
            reason TEXT NOT NULL, created_at TEXT NOT NULL
          );
        ''')
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.conn.commit()

    def close(self):
        self.conn.close()

    def save(self, inquiry, recommendation, origin):
        with self.conn:
            cursor = self.conn.execute('''INSERT OR IGNORE INTO recommendations VALUES (?, ?, ?, ?, ?)''',
                (inquiry.work_item_id, json.dumps(inquiry.to_dict(), ensure_ascii=False),
                 json.dumps(recommendation.to_dict(), ensure_ascii=False), origin, utc_now()))
        return cursor.rowcount == 1

    def list_items(self):
        rows = self.conn.execute('''SELECT r.work_item_id, r.origin, r.result,
          (SELECT action FROM recommendation_reviews e WHERE e.work_item_id=r.work_item_id
           ORDER BY e.id DESC LIMIT 1) latest_action FROM recommendations r ORDER BY r.work_item_id''').fetchall()
        return [{'work_item_id': x['work_item_id'], 'origin': x['origin'],
                 'result': json.loads(x['result']), 'latest_action': x['latest_action']} for x in rows]

    def get_item(self, work_item_id):
        row = self.conn.execute('SELECT * FROM recommendations WHERE work_item_id=?', (work_item_id,)).fetchone()
        if row is None:
            return None
        return {'work_item_id': row['work_item_id'], 'inquiry': json.loads(row['inquiry']),
                'result': json.loads(row['result']), 'origin': row['origin'], 'created_at': row['created_at']}

    def reviews(self, work_item_id=None):
        if work_item_id is None:
            rows = self.conn.execute('SELECT * FROM recommendation_reviews ORDER BY id').fetchall()
        else:
            rows = self.conn.execute('SELECT * FROM recommendation_reviews WHERE work_item_id=? ORDER BY id',
                                     (work_item_id,)).fetchall()
        return [dict(row) for row in rows]

    def review(self, work_item_id, action, reviewer, reviewer_role, chosen_sku=None, reason=''):
        if action not in ('approve', 'choose_another', 'escalate'):
            raise ValueError('无效审核动作')
        if reviewer_role not in ('sales', 'engineer') or not reviewer.strip():
            raise ValueError('必须填写审核人及角色')
        item = self.get_item(work_item_id)
        if item is None:
            raise ValueError('推荐任务不存在')
        result = item['result']
        if action in ('approve', 'choose_another'):
            if item['inquiry'].get('medium_category') is None:
                raise ValueError('介质未知时只能升级或澄清，不能批准候选')
            if result['requires_engineer_review'] and reviewer_role != 'engineer':
                raise ValueError('此任务必须由工程师复核')
            if chosen_sku not in result['candidate_skus']:
                raise ValueError('只能选择未被排除的候选 SKU')
            if action == 'approve' and chosen_sku != result['provisional_top_sku']:
                raise ValueError('批准动作只能选择暂列第一的 SKU')
            if action == 'choose_another' and chosen_sku == result['provisional_top_sku']:
                raise ValueError('更换候选应选择其他 SKU')
            if action == 'choose_another' and not reason.strip():
                raise ValueError('更换候选必须说明原因')
        else:
            chosen_sku = None
            if not reason.strip():
                raise ValueError('升级必须说明原因')
        with self.conn:
            self.conn.execute('''INSERT INTO recommendation_reviews
              (work_item_id, action, reviewer, reviewer_role, chosen_sku, reason, created_at)
              VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (work_item_id, action, reviewer.strip(), reviewer_role, chosen_sku, reason.strip(), utc_now()))
