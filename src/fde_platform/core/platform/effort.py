"""Optional human effort log; demo never fabricates delivery hours."""
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

DOMAINS = frozenset({'after_sales', 'foreign_trade'})
PHASES = frozenset({'discovery', 'integration', 'domain_rules', 'review_workflow', 'evaluation'})


class EffortLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def events(self):
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding='utf-8').splitlines() if line.strip()]

    def _append(self, event):
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + '\n')

    def start(self, *, domain, phase, actor, activity):
        if domain not in DOMAINS or phase not in PHASES or not actor.strip() or not activity.strip():
            raise ValueError('交付工时需要有效 Domain、阶段、记录人和工作描述')
        event = {'event': 'start', 'activity_id': uuid4().hex[:12], 'domain': domain,
                 'phase': phase, 'actor': actor.strip(), 'activity': activity.strip(),
                 'at': datetime.now(timezone.utc).isoformat()}
        self._append(event)
        return event

    def stop(self, activity_id):
        events = self.events()
        starts = [x for x in events if x['event'] == 'start' and x['activity_id'] == activity_id]
        if len(starts) != 1 or any(x['event'] == 'stop' and x['activity_id'] == activity_id for x in events):
            raise ValueError('工时记录不存在或已经停止')
        event = {'event': 'stop', 'activity_id': activity_id,
                 'at': datetime.now(timezone.utc).isoformat()}
        self._append(event)
        return event

    def summary(self):
        starts = {x['activity_id']: x for x in self.events() if x['event'] == 'start'}
        stops = {x['activity_id']: x for x in self.events() if x['event'] == 'stop'}
        completed, open_ids = [], []
        for activity_id, start in starts.items():
            if activity_id not in stops:
                open_ids.append(activity_id)
                continue
            duration = (datetime.fromisoformat(stops[activity_id]['at']) -
                        datetime.fromisoformat(start['at'])).total_seconds() / 60
            if duration < 0:
                raise ValueError('工时事件时间倒序')
            completed.append({**start, 'ended_at': stops[activity_id]['at'],
                              'duration_minutes': round(duration, 3)})
        totals = {domain: round(sum(x['duration_minutes'] for x in completed if x['domain'] == domain), 3)
                  for domain in DOMAINS}
        return {'mode': 'operator_recorded_actual_elapsed_time', 'completed': completed,
                'open_activity_ids': sorted(open_ids), 'total_minutes_by_domain': totals,
                'comparison_status': 'DESCRIPTIVE_ONLY' if all(
                    any(x['domain'] == domain for x in completed) for domain in DOMAINS) else
                                     'INSUFFICIENT_LOGGED_HUMAN_EFFORT',
                'causal_savings_proven': False}
