"""Cross-layer gates backed by runtime facts rather than scripted declarations."""


def operational_gate(delivery, model, telemetry, connectors):
    incidents = delivery['runtime']['incidents']
    unresolved = [item for item in incidents if item['state'] != 'resolved']
    dead_inbox = delivery['worker']['dead']
    dead_outbox = delivery['delivery']['states'].get('dead', 0)
    checks = {
        'no_unresolved_runtime_incidents': len(unresolved) == 0,
        'no_inbox_dead_letters': dead_inbox == 0,
        'no_outbox_dead_letters': dead_outbox == 0,
        'no_unapproved_deliveries': delivery['delivery']['unapproved_deliveries'] == 0,
        'no_persistent_direct_identifiers':
            delivery['security']['rows_with_direct_identifier'] == 0,
        'model_safety_gate': model['security']['unsafe_or_leaky_count'] == 0,
        'model_baseline_restored': model['rollout']['active_route'] == 'baseline',
        'telemetry_content_free': telemetry['direct_identifier_rows'] == 0 and
                                  telemetry['raw_content_exported'] is False,
        'connectors_read_only': connectors['customer_writes'] == 0,
        'connector_negative_cases_passed': connectors['negative_cases_failed'] == 0,
    }
    return {
        'status': 'OPERATIONAL_GATE_READY' if all(checks.values()) else
                  'OPERATIONAL_GATE_BLOCKED',
        'checks': checks,
        'unresolved_incident_ids': [item['incident_id'] for item in unresolved],
        'dead_inbox_count': dead_inbox,
        'dead_outbox_count': dead_outbox,
    }


def real_shadow_gate(evidence):
    required_true = ('authorization_verified', 'external_mount_verified',
                     'postgres_runtime_verified', 'enterprise_oidc_verified',
                     'connector_sandbox_verified', 'otlp_backend_verified',
                     'customer_uat_approved', 'on_call_drill_passed')
    missing = [name for name in required_true if evidence.get(name) is not True]
    invalid = (evidence.get('mode') != 'authorized_customer_shadow' or
               evidence.get('customer_writes_enabled') is not False or
               evidence.get('git_contains_customer_records') is not False)
    if invalid:
        missing.append('safe_shadow_boundary')
    return {'status': 'AUTHORIZED_SHADOW_READY' if not missing else
            'AUTHORIZED_SHADOW_NOT_READY', 'missing_evidence': missing,
            'real_customer_data_authorized': not missing}
