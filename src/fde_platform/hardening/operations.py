"""Version-bound synthetic Stop/Iterate signoffs; Expand is never authorized here."""
import sqlite3
from pathlib import Path

from fde_platform.core.models import utc_now
from .governance import digest


def decision_basis_digest(report):
    """Bind approval to evidence and metrics without hashing the approval display itself."""
    return digest({'mode': report['mode'], 'stage4': report['stage4'],
                   'episodes': report['episodes'], 'mock_services': report['mock_services'],
                   'controls': report['controls'], 'legacy_migration': report['legacy_migration'],
                   'model_comparison': report['model_comparison'],
                   'operations_metrics': {k: v for k, v in report['operations'].items()
                       if k not in ('simulated_signoffs_recorded', 'real_signoffs')},
                   'real_pilot_gate': report['real_pilot_gate']})


class OperationsSignoffs:
    def __init__(self, path, required):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.required = dict(required)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('''CREATE TABLE IF NOT EXISTS signoffs (
            role TEXT PRIMARY KEY, actor_id TEXT NOT NULL, decision TEXT NOT NULL,
            reason TEXT NOT NULL, report_digest TEXT NOT NULL, created_at TEXT NOT NULL)''')

    def close(self):
        self.conn.close()

    def sign(self, claims, report, decision, reason):
        role = claims['role']
        if self.required.get(role) != claims['sub']:
            raise ValueError('当前身份不是该运营决策的指定签核人')
        if decision not in ('STOP', 'ITERATE') or not reason.strip():
            raise ValueError('本演练不允许 EXPAND，且签核必须说明原因')
        if report['operations']['stop_triggered'] and decision != 'STOP':
            raise ValueError('Stop 条件触发时只能签核 STOP')
        version = decision_basis_digest(report)
        old = self.conn.execute('SELECT * FROM signoffs WHERE role=?', (role,)).fetchone()
        if old:
            if (old['actor_id'], old['decision'], old['reason'], old['report_digest']) != (
                    claims['sub'], decision, reason.strip(), version):
                raise ValueError('签核已有不同版本或决定；不得覆盖')
            return dict(old)
        with self.conn:
            self.conn.execute('INSERT INTO signoffs VALUES (?,?,?,?,?,?)',
                (role, claims['sub'], decision, reason.strip(), version, utc_now()))
        return dict(self.conn.execute('SELECT * FROM signoffs WHERE role=?', (role,)).fetchone())

    def status(self, report):
        rows = [dict(x) for x in self.conn.execute('SELECT * FROM signoffs ORDER BY role')]
        current = [x for x in rows if x['report_digest'] == decision_basis_digest(report)]
        decisions = {x['decision'] for x in current}
        complete = ({x['role'] for x in current} == set(self.required) and len(decisions) == 1)
        return {'status': 'SIMULATED_SIGNED' if complete else 'AWAITING_SIMULATED_SIGNOFF',
                'decision': next(iter(decisions)) if complete else None,
                'current_signoffs': current, 'stale_signoffs': len(rows) - len(current),
                'real_pilot_approval': False}
