"""Run deterministic model canary and circuit-breaker drills on synthetic events."""
from fde_platform.core.ingestion import from_text
from fde_platform.domains.foreign_trade.recommendation.service import load_components
from fde_platform.onboarding.privacy import PrivacyFilter
from fde_platform.onboarding.shadow import process_shadow

from .gateway import MeteredCandidateProvider, ModelGateway
from .telemetry import ModelTelemetry


class AlwaysFailProvider:
    model_version = 'simulated-unavailable-candidate'
    calls = 0
    last_cost_usd = 0.0

    def complete(self, work, prompt_version):
        self.calls += 1
        raise TimeoutError('simulated_candidate_timeout')


def latest_cases(events):
    values = {}
    for event in events:
        old = values.get(event['case_id'])
        if old is None or event['source_version'] > old['source_version']:
            values[event['case_id']] = event
    return [values[key] for key in sorted(values)]


def run_canary(events, manifest, registry, root, telemetry_path=None):
    telemetry = ModelTelemetry(telemetry_path)
    gateway = ModelGateway(registry, candidate=MeteredCandidateProvider(),
                           telemetry=telemetry)
    privacy = PrivacyFilter(b'Stage12-fixed-training-key-32bytes!!')
    components = load_components(root)
    routes, quarantined = {}, 0
    for raw in latest_cases(events):
        event, _ = privacy.sanitize(raw, manifest)
        artifact = process_shadow(event, components, provider=gateway)
        routes[artifact['route']] = routes.get(artifact['route'], 0) + 1
        quarantined += artifact['route'] == 'quarantine'
    return {'case_count': len(latest_cases(events)), 'workflow_routes': routes,
            'quarantined_before_model': quarantined,
            'gateway': gateway.report(), 'telemetry': telemetry.summary(),
            'external_actions': 0, 'real_customer_data': False}


def run_circuit_drill(registry):
    failing = AlwaysFailProvider()
    telemetry = ModelTelemetry()
    gateway = ModelGateway(registry, candidate=failing, telemetry=telemetry,
                           force_route='candidate', fallback_on_provider_error=True)
    for index in range(4):
        work = from_text(f'Centrifugal pump for water flow {30 + index} m3/h, head 20 m.',
            source_id=f'CIRCUIT-{index}', tenant_id=registry['tenant_id'])
        gateway.complete(work, registry['prompt']['version'])
    return {'candidate_calls': failing.calls, 'requests': 4,
            'fallback_responses': gateway.stats['fallback'],
            'circuit_open_events': gateway.stats['circuit_open_events'],
            'circuit_open': gateway.circuit_open,
            'telemetry': telemetry.summary(), 'business_actions': 0}
