"""Content-free OTLP-shaped spans and pilot SLO evaluation."""
import hashlib
import json
from pathlib import Path

from fde_platform.core.models import utc_now
from fde_platform.onboarding.privacy import contains_direct_identifier


class SafeSpanWriter:
    ALLOWED = frozenset({'tenant_hash', 'shift_id', 'event_type', 'outcome',
                         'route', 'model', 'duration_ms', 'cost_usd'})

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.count = 0

    def write(self, name, attributes, *, object_id):
        if set(attributes) - self.ALLOWED or contains_direct_identifier(attributes):
            raise ValueError('遥测属性包含未授权字段或直接标识符')
        seed = f'{name}|{object_id}|{self.count}'
        row = {'timestamp': utc_now(), 'name': name,
               'trace_id': hashlib.sha256(seed.encode()).hexdigest()[:32],
               'span_id': hashlib.sha256((seed + '|span').encode()).hexdigest()[:16],
               'object_hash': hashlib.sha256(object_id.encode()).hexdigest()[:16],
               'attributes': attributes}
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')
        self.count += 1
        return row

    def summary(self):
        rows = [json.loads(line) for line in self.path.read_text().splitlines()
                if line.strip()] if self.path.exists() else []
        return {'span_count': len(rows), 'semantic_shape': 'otlp_json_training_subset',
                'raw_prompt_logged': False, 'raw_output_logged': False,
                'raw_customer_content_logged': False,
                'direct_identifier_rows': sum(contains_direct_identifier(x) for x in rows)}


def evaluate_slos(delivery, model, ledger, thresholds):
    intake = delivery['intake']
    accepted = intake['created'] + intake['updated'] + intake['duplicate']
    processed = delivery['worker']['done'] + delivery['worker']['dead']
    values = {
        'intake_acceptance_rate': accepted / intake['total_received'],
        'worker_success_rate': delivery['worker']['done'] / processed,
        'review_completion_rate': delivery['workflow']['reviewed'] /
                                  delivery['workflow']['case_count'],
        'unapproved_deliveries': delivery['delivery']['unapproved_deliveries'],
        'persistent_direct_identifier_rows':
            delivery['security']['rows_with_direct_identifier'],
        'unsafe_or_leaky_model_cases': model['security']['unsafe_or_leaky_count'],
        'external_business_actions': model['external_business_actions'],
        'rollback_verified': model['rollout']['rollback_verified'],
        'incidents_resolved': ledger['all_incidents_resolved'],
    }
    checks = {
        'intake_acceptance_rate': values['intake_acceptance_rate'] >= thresholds['intake_acceptance_rate_min'],
        'worker_success_rate': values['worker_success_rate'] >= thresholds['worker_success_rate_min'],
        'review_completion_rate': values['review_completion_rate'] >= thresholds['review_completion_rate_min'],
        'unapproved_deliveries': values['unapproved_deliveries'] == 0,
        'persistent_direct_identifier_rows': values['persistent_direct_identifier_rows'] == 0,
        'unsafe_or_leaky_model_cases': values['unsafe_or_leaky_model_cases'] == 0,
        'external_business_actions': values['external_business_actions'] == 0,
        'rollback_verified': values['rollback_verified'] is True,
        'incidents_resolved': values['incidents_resolved'] is True,
    }
    return {'status': 'SYNTHETIC_PILOT_SLOS_MET' if all(checks.values()) else
            'SYNTHETIC_PILOT_SLOS_BLOCKED', 'values': values, 'checks': checks,
            'real_customer_slo_evidence': False}
