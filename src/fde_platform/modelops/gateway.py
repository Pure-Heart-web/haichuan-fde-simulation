"""Policy-enforced candidate gateway with deterministic canary and fallback."""
import hashlib
import json
import time

from fde_platform.domains.foreign_trade.baseline import RegexBaselineProvider
from fde_platform.onboarding.privacy import (contains_direct_identifier,
                                             detect_untrusted_instruction)


class PolicyViolation(ValueError):
    pass


class MeteredCandidateProvider:
    """Deterministic candidate stand-in; it is not an external model."""
    model_version = 'candidate-structured-v1-stand-in'

    def __init__(self, cost_per_call_usd=0.0002):
        self.baseline = RegexBaselineProvider()
        self.cost_per_call_usd = cost_per_call_usd
        self.last_cost_usd = 0.0
        self.calls = 0

    def complete(self, work_item, prompt_version):
        self.calls += 1
        self.last_cost_usd = self.cost_per_call_usd
        return self.baseline.complete(work_item, prompt_version)


class ModelGateway:
    model_version = 'model-gateway-v1'

    def __init__(self, registry, candidate=None, baseline=None, telemetry=None,
                 *, force_route=None, fallback_on_provider_error=True):
        self.registry = registry
        self.candidate = candidate or MeteredCandidateProvider()
        self.baseline = baseline or RegexBaselineProvider()
        self.telemetry = telemetry
        self.force_route = force_route
        self.fallback_on_provider_error = fallback_on_provider_error
        self.failure_count = 0
        self.circuit_open = False
        self.total_cost_usd = 0.0
        self.stats = {'candidate': 0, 'baseline': 0, 'fallback': 0,
                      'blocked_input': 0, 'blocked_output': 0,
                      'circuit_open_events': 0}

    def _route(self, work_item):
        if self.force_route:
            return self.force_route
        bucket = int(hashlib.sha256(work_item.id.encode()).hexdigest()[:8], 16) % 100
        return ('candidate' if bucket < self.registry['routing']['candidate_percent']
                else 'baseline')

    def _input_gate(self, work_item):
        body = work_item.body
        if contains_direct_identifier(body):
            raise PolicyViolation('model_input_direct_identifier')
        if detect_untrusted_instruction(body):
            raise PolicyViolation('model_input_untrusted_instruction')
        if any(secret in body for secret in self.registry['secret_canaries']):
            raise PolicyViolation('model_input_secret_canary')
        if len(body.encode()) > self.registry['limits']['max_input_bytes']:
            raise PolicyViolation('model_input_too_large')

    def _output_gate(self, raw, work_item):
        if not isinstance(raw, str) or len(raw.encode()) > self.registry['limits']['max_output_bytes']:
            raise PolicyViolation('model_output_too_large_or_not_text')
        if any(secret in raw for secret in self.registry['secret_canaries']):
            raise PolicyViolation('model_output_secret_canary')
        if contains_direct_identifier(raw):
            raise PolicyViolation('model_output_direct_identifier')
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PolicyViolation('model_output_invalid_json') from exc
        if not isinstance(value, dict):
            raise PolicyViolation('model_output_not_object')
        forbidden = {x.casefold() for x in self.registry['forbidden_output_keys']}
        allowed = set(self.registry['schema']['allowed_fields'])
        if set(value) - allowed:
            raise PolicyViolation('model_output_unknown_top_level_field')

        def walk(node):
            if isinstance(node, dict):
                for key, child in node.items():
                    if str(key).casefold() in forbidden:
                        raise PolicyViolation('model_output_forbidden_action')
                    walk(child)
            elif isinstance(node, list):
                for child in node:
                    walk(child)
        walk(value)
        for field, item in value.items():
            if item is None:
                continue
            if not isinstance(item, dict) or set(item) - {'value', 'unit', 'text', 'start', 'end'}:
                raise PolicyViolation('model_output_field_contract')
            if not {'value', 'text', 'start', 'end'} <= set(item):
                raise PolicyViolation('model_output_evidence_missing')
            start, end, text = item['start'], item['end'], item['text']
            if (not isinstance(start, int) or not isinstance(end, int) or
                    not 0 <= start < end <= len(work_item.body) or
                    work_item.body[start:end] != text):
                raise PolicyViolation('model_output_false_evidence')
        return raw

    def complete(self, work_item, prompt_version):
        started = time.perf_counter()
        try:
            self._input_gate(work_item)
        except PolicyViolation as exc:
            self.stats['blocked_input'] += 1
            self._record(work_item, 'blocked', 'policy', prompt_version, started, 0.0, exc)
            raise
        route = self._route(work_item)
        if route == 'candidate' and self.circuit_open:
            self.stats['circuit_open_events'] += 1
            route = 'fallback'
        provider = self.candidate if route == 'candidate' else self.baseline
        try:
            raw = provider.complete(work_item, prompt_version)
            raw = self._output_gate(raw, work_item)
            supplied_cost = getattr(provider, 'last_cost_usd', 0.0)
            if route == 'candidate' and supplied_cost is None:
                raise PolicyViolation('model_cost_missing')
            cost = float(supplied_cost or 0.0)
            if cost > self.registry['limits']['max_cost_per_case_usd']:
                raise PolicyViolation('model_cost_budget_exceeded')
            self.total_cost_usd += cost
            self.failure_count = 0 if route == 'candidate' else self.failure_count
            self.stats['candidate' if route == 'candidate' else
                       'fallback' if route == 'fallback' else 'baseline'] += 1
            self._record(work_item, route, getattr(provider, 'model_version', 'unknown'),
                         prompt_version, started, cost)
            return raw
        except PolicyViolation as exc:
            self.stats['blocked_output'] += 1
            self._record(work_item, 'blocked', getattr(provider, 'model_version', 'unknown'),
                         prompt_version, started, 0.0, exc)
            raise
        except (OSError, TimeoutError, RuntimeError) as exc:
            if route == 'candidate':
                self.failure_count += 1
                if self.failure_count >= self.registry['limits']['circuit_failure_threshold']:
                    self.circuit_open = True
            if not self.fallback_on_provider_error:
                self._record(work_item, 'failed', getattr(provider, 'model_version', 'unknown'),
                             prompt_version, started, 0.0, exc)
                raise
            raw = self._output_gate(self.baseline.complete(work_item, prompt_version), work_item)
            self.stats['fallback'] += 1
            self._record(work_item, 'fallback', self.baseline.model_version,
                         prompt_version, started, 0.0, exc)
            return raw

    def _record(self, work, route, model, prompt, started, cost, error=None):
        if self.telemetry:
            self.telemetry.record(tenant_id=work.tenant_id, source_id=work.source_id,
                route=route, model=model, prompt_version=prompt,
                outcome='blocked' if isinstance(error, PolicyViolation) else
                        'fallback' if route == 'fallback' else 'failed' if error else 'ok',
                duration_ms=(time.perf_counter() - started) * 1000, cost_usd=cost,
                error_type=type(error).__name__ if error else None)

    def report(self):
        return {'model_version': self.model_version, 'stats': dict(self.stats),
                'candidate_failure_count': self.failure_count,
                'circuit_open': self.circuit_open,
                'total_cost_usd': round(self.total_cost_usd, 8)}
