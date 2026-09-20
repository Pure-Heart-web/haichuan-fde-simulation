#!/usr/bin/env python3
"""Deterministically rebuild 180 simulated pilot events; never reads user activity."""
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'stages/07-pilot-operations/data'


def build_events():
    baseline = json.loads((DATA / 'baseline.json').read_text(encoding='utf-8'))
    users = json.loads((DATA / 'pilot-config.json').read_text(encoding='utf-8'))['users'][:3]
    days = []
    day = date(2026, 9, 21)
    while len(days) < 10:
        if day.weekday() < 5:
            days.append(day.isoformat())
        day += timedelta(days=1)
    rows = []
    for d, day in enumerate(days):
        week = 1 if d < 5 else 2
        for u, user in enumerate(users):
            for j in range(6):
                complexity = 'complex' if j in (1, 2, 4) else 'simple'
                repeat = j == 4
                eligible = not (j == 5 and d % 3 == 0)
                recommended = eligible and (complexity == 'complex' or repeat)
                # Workflow v2 targets expensive inquiries; simple senior work remains optional.
                thresholds = {
                    'senior': (12 if complexity == 'simple' else (42 if week == 1 else 76)),
                    'junior': (78 if complexity == 'simple' else 92),
                    'mid': (42 if complexity == 'simple' else (62 if week == 1 else 78)),
                }
                score = (d * 17 + u * 31 + j * 23) % 100
                attempted = eligible and score < thresholds[user['experience']]
                abandoned = attempted and ((d + u * 3 + j * 5) % (11 if week == 1 else 23) == 0)
                failure = attempted and (d == 6 and u == 1 and j == 2)
                effective = attempted and not abandoned and not failure
                baseline_minutes = baseline['processing_minutes'][user['experience']][complexity]
                processing = (round(baseline_minutes * .62 + 1, 1) if effective and complexity == 'complex' else
                              round(baseline_minutes + 1, 1) if effective and user['experience'] == 'senior' else
                              round(max(1, baseline_minutes - 1), 1) if effective else baseline_minutes)
                response = baseline['first_response_minutes'][user['experience']][complexity]
                first_response = round(response * (.70 if effective and complexity == 'complex' else .94 if effective else 1), 1)
                outcome = ('none' if not effective else
                           'major_edit' if (d + u + j) % 13 == 0 else
                           'minor_edit' if (d + 2*u + j) % 5 == 0 else
                           'reject' if (d + j) % 19 == 0 else 'accept')
                rows.append({
                    'id': f'PILOT-{len(rows)+1:03d}', 'date': day, 'week': week,
                    'user_id': user['user_id'], 'experience': user['experience'],
                    'complexity': complexity, 'customer_type': 'repeat' if repeat else 'new',
                    'product_family': 'centrifugal_pump' if eligible else 'unsupported',
                    'eligible': eligible, 'assistance_recommended': recommended,
                    'attempted': attempted, 'assisted': effective, 'abandoned': abandoned or failure,
                    'review_outcome': outcome, 'processing_minutes': processing,
                    'first_response_minutes': first_response,
                    'engineer_consulted': complexity == 'complex' and (j == 2 or (not effective and j == 4)),
                    'extraction_corrected': effective and (d + u + j) % 17 == 0,
                    'top3_accepted': (outcome in ('accept', 'minor_edit')) if effective else None,
                    'critical_rule_violation': False, 'system_success': not failure,
                    'latency_ms': (12200 if d == 6 and j in (1, 2) else 3100 + ((d+u+j)*137) % 1900) if attempted else None,
                    'integration_error': failure, 'api_cost_usd_observed': 0.0,
                    'context_switches': 5 if week == 1 and attempted else 1 if attempted else 0,
                    'rollout': 'manual_copy_v1' if week == 1 else 'targeted_side_panel_v2',
                    'failure_category': 'integration' if failure else 'workflow' if abandoned else
                                        'human' if outcome == 'major_edit' else None,
                    'data_classification': 'synthetic_training_event'
                })
    return rows


if __name__ == '__main__':
    rows = build_events()
    target = DATA / 'pilot-events.jsonl'
    target.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')
    print(f'Wrote {len(rows)} deterministic synthetic pilot events to {target}')
