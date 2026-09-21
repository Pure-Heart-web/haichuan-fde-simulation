"""Append-only blind first-pass labels and reasoned adjudication for learners."""
import sqlite3
from pathlib import Path

from fde_platform.core.models import utc_now

ROUTES = frozenset({'reject_cross_tenant', 'quarantine', 'stop_and_engineer',
                    'abstain_and_escalate', 'request_clarification', 'human_review'})


class AnnotationBook:
    def __init__(self, path, cases):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.cases = {x['id']: x for x in cases}
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
          CREATE TABLE IF NOT EXISTS labels (
            case_id TEXT NOT NULL, annotation_role TEXT NOT NULL, actor_id TEXT NOT NULL,
            route TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(case_id,annotation_role)
          );
          CREATE TABLE IF NOT EXISTS adjudications (
            case_id TEXT PRIMARY KEY, actor_id TEXT NOT NULL, route TEXT NOT NULL,
            rationale TEXT NOT NULL, created_at TEXT NOT NULL
          );
        ''')

    def close(self):
        self.conn.close()

    def _check_case(self, case_id, claims):
        case = self.cases.get(case_id)
        if not case:
            raise ValueError('挑战案例不存在')
        owner = 'qihang-training' if case['domain'] == 'after_sales' else 'haichuan-training'
        if claims['tenant_id'] != owner:
            raise ValueError('不能标注其他租户的案例')
        return case

    def submit(self, case_id, claims, route, reason):
        case = self._check_case(case_id, claims)
        frontline_role = 'support' if case['domain'] == 'after_sales' else 'sales'
        role = ('frontline' if claims['role'] == frontline_role
                else 'engineer' if claims['role'] == 'engineer' else None)
        if role is None or route not in ROUTES or not reason.strip():
            raise ValueError('标注角色、路线或原因无效')
        with self.conn:
            self.conn.execute('''INSERT INTO labels VALUES (?,?,?,?,?,?)''',
                (case_id, role, claims['sub'], route, reason.strip(), utc_now()))
        return {'case_id': case_id, 'role': role, 'recorded': True,
                'other_label_hidden_until_adjudication': True}

    def adjudicate(self, case_id, claims, route, rationale):
        self._check_case(case_id, claims)
        if claims['role'] != 'adjudicator' or route not in ROUTES or not rationale.strip():
            raise ValueError('裁决角色、路线或原因无效')
        rows = self.conn.execute('SELECT annotation_role,route FROM labels WHERE case_id=?',
                                 (case_id,)).fetchall()
        if {x['annotation_role'] for x in rows} != {'frontline', 'engineer'}:
            raise ValueError('必须先有前线与工程师两份独立标注')
        if route not in {x['route'] for x in rows}:
            raise ValueError('裁决需选择一份原始标注路线；新路线要退回重新标注')
        with self.conn:
            self.conn.execute('INSERT INTO adjudications VALUES (?,?,?,?,?)',
                              (case_id, claims['sub'], route, rationale.strip(), utc_now()))
        return {'case_id': case_id, 'adjudicated': True, 'route': route}

    def report(self):
        labels = [dict(x) for x in self.conn.execute('SELECT * FROM labels ORDER BY case_id,annotation_role')]
        adjudications = [dict(x) for x in self.conn.execute('SELECT * FROM adjudications ORDER BY case_id')]
        return {'mode': 'operator_submitted_training_labels', 'label_count': len(labels),
                'adjudicated_count': len(adjudications), 'labels': labels,
                'adjudications': adjudications}
