"""SQLite store preserving model output and immutable human feedback events."""
import json
import sqlite3
from pathlib import Path

from .models import utc_now


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys = ON')
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS work_items (
              id TEXT PRIMARY KEY, source_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS extractions (
              work_item_id TEXT PRIMARY KEY REFERENCES work_items(id), status TEXT NOT NULL,
              record TEXT, result TEXT NOT NULL, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS review_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              work_item_id TEXT NOT NULL REFERENCES work_items(id), action TEXT NOT NULL,
              reviewer TEXT NOT NULL, model_record TEXT, corrected_record TEXT,
              feedback TEXT NOT NULL, comment TEXT NOT NULL, created_at TEXT NOT NULL
            );
        ''')
        self.conn.commit()

    def close(self):
        self.conn.close()

    def save_extraction(self, work_item, result, record):
        with self.conn:
            self.conn.execute('INSERT OR IGNORE INTO work_items VALUES (?, ?, ?, ?)',
                              (work_item.id, work_item.source_id, encode(work_item.to_dict()), utc_now()))
            self.conn.execute('INSERT OR IGNORE INTO extractions VALUES (?, ?, ?, ?, ?)',
                              (work_item.id, result.status, encode(record.to_dict()) if record else None,
                               encode(result.to_dict()), utc_now()))

    def list_items(self):
        rows = self.conn.execute('''SELECT w.id, w.source_id, w.payload, e.status,
             (SELECT action FROM review_events r WHERE r.work_item_id=w.id ORDER BY id DESC LIMIT 1) review_status
             FROM work_items w JOIN extractions e ON e.work_item_id=w.id ORDER BY w.source_id''').fetchall()
        return [dict(row) for row in rows]

    def get_item(self, work_item_id):
        row = self.conn.execute('''SELECT w.payload, e.status, e.record, e.result FROM work_items w
            JOIN extractions e ON e.work_item_id=w.id WHERE w.id=?''', (work_item_id,)).fetchone()
        if not row:
            return None
        return {'work_item': json.loads(row['payload']), 'status': row['status'],
                'model_record': json.loads(row['record']) if row['record'] else None,
                'result': json.loads(row['result'])}

    def review(self, work_item_id, action, reviewer, corrected_record, comment=''):
        if action not in ('approve', 'edit', 'reject'):
            raise ValueError('无效审核动作')
        if not reviewer.strip():
            raise ValueError('必须填写审核者')
        item = self.get_item(work_item_id)
        if item is None:
            raise ValueError('任务不存在')
        original = item['model_record']
        if action == 'approve' and original is None:
            raise ValueError('抽取失败时不能直接批准')
        if action == 'edit' and corrected_record is None:
            raise ValueError('修改审核必须提供修正记录')
        changes = []
        if corrected_record is not None:
            old = original or {}
            for key, value in corrected_record.items():
                if key in ('evidence', 'warnings', 'missing_fields', 'extraction_confidence'):
                    continue
                if old.get(key) != value:
                    changes.append({'stage': 'extraction', 'field': key, 'actual': old.get(key),
                                    'expected': value, 'feedback_type': 'corrected'})
        if action == 'edit' and not changes:
            raise ValueError('修改审核需要至少更正一个字段')
        if action == 'edit':
            corrected_record = dict(corrected_record)
            evidence = dict(corrected_record.get('evidence') or {})
            missing = list(corrected_record.get('missing_fields') or [])
            for change in changes:
                field = change['field']
                if change['expected'] is None:
                    evidence.pop(field, None)
                else:
                    evidence[field] = {'origin': 'human_review', 'reviewer': reviewer,
                                       'source_id': work_item_id, 'text': None,
                                       'start': None, 'end': None, 'raw_unit': None}
                    if field == 'medium_description' and change['expected'] != 'water':
                        missing = [x for x in missing if x != 'medium_detail']
                    if field in ('flow_m3h', 'head_m'):
                        missing = [x for x in missing if x != field]
            corrected_record['evidence'] = evidence
            corrected_record['missing_fields'] = missing
        with self.conn:
            self.conn.execute('''INSERT INTO review_events
              (work_item_id, action, reviewer, model_record, corrected_record, feedback, comment, created_at)
              VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (work_item_id, action, reviewer, encode(original) if original else None,
               encode(corrected_record) if corrected_record else None, encode(changes), comment, utc_now()))
        return changes

    def reviews(self, work_item_id=None):
        if work_item_id:
            rows = self.conn.execute('SELECT * FROM review_events WHERE work_item_id=? ORDER BY id',
                                     (work_item_id,)).fetchall()
        else:
            rows = self.conn.execute('SELECT * FROM review_events ORDER BY id').fetchall()
        result = []
        for row in rows:
            item = dict(row)
            for key in ('model_record', 'corrected_record', 'feedback'):
                if item[key] is not None:
                    item[key] = json.loads(item[key])
            result.append(item)
        return result
