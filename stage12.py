#!/usr/bin/env python3
"""Stage 12: offline model evaluation, safety gates, canary, and rollback."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))

from fde_platform.evals.runner import evaluate
from fde_platform.hardening.model import LoopbackModelProvider
from fde_platform.modelops.canary import run_canary, run_circuit_drill
from fde_platform.modelops.gateway import MeteredCandidateProvider, ModelGateway
from fde_platform.modelops.registry import validate_registry
from fde_platform.modelops.rollout import RolloutBook
from fde_platform.modelops.security import evaluate_security
from fde_platform.modelops.telemetry import ModelTelemetry
from fde_platform.onboarding.manifest import validate_manifest


DATA = ROOT / 'stages/12-model-safety-canary/data'
REGISTRY = DATA / 'model-registry.json'
SECURITY_CASES = DATA / 'security-cases.json'
RELEASE_POLICY = DATA / 'release-policy.json'
BASELINE = DATA / 'regression-baseline.json'
EVAL_DATA = ROOT / 'stages/04-build-sprint-1/data/inquiry_eval_v0.jsonl'
EVENTS = ROOT / 'stages/11-delivery-room/data/pilot-events.jsonl'
MANIFEST = ROOT / 'stages/10-customer-onboarding/data/customer-onboarding.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()
            if line.strip()]


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def compare_models(registry, output):
    baseline = evaluate(EVAL_DATA)
    telemetry = ModelTelemetry(Path(output) / 'comparison-telemetry.jsonl')
    gateway = ModelGateway(registry, candidate=MeteredCandidateProvider(),
                           telemetry=telemetry, force_route='candidate')
    candidate = evaluate(EVAL_DATA, gateway)
    drops = {field: baseline['per_field'][field]['accuracy'] -
             candidate['per_field'][field]['accuracy']
             for field in baseline['per_field']}
    return {
        'mode': 'offline_synthetic_comparison',
        'case_count': baseline['case_count'],
        'baseline': baseline,
        'candidate': candidate,
        'per_field_accuracy_drop': drops,
        'field_accuracy_drop': baseline['critical_field_accuracy'] -
                               candidate['critical_field_accuracy'],
        'telemetry': telemetry.summary(),
        'external_model_calls': 0,
        'real_customer_data': False,
    }


def evaluate_loopback_endpoint(registry, endpoint, output):
    """Evaluate an explicitly local provider through the same Stage 12 gateway."""
    telemetry_path = Path(output) / 'endpoint-telemetry.jsonl'
    if telemetry_path.exists():
        telemetry_path.unlink()
    telemetry = ModelTelemetry(telemetry_path)
    provider = LoopbackModelProvider(endpoint)
    gateway = ModelGateway(registry, candidate=provider, telemetry=telemetry,
                           force_route='candidate', fallback_on_provider_error=False)
    result = evaluate(EVAL_DATA, gateway)
    report = {'mode': 'loopback_endpoint_synthetic_eval', 'endpoint': endpoint,
              'result': result, 'gateway': gateway.report(),
              'telemetry': telemetry.summary(), 'external_customer_data': False,
              'real_release_authorized': False, 'business_actions': 0}
    write(Path(output) / 'endpoint-evaluation.json', report)
    return report


def release_decision(comparison, security, canary, circuit, policy):
    checks = {
        'baseline_thresholds_met': comparison['baseline']['offline_thresholds_met'],
        'candidate_thresholds_met': comparison['candidate']['offline_thresholds_met'],
        'field_accuracy_drop_within_limit':
            comparison['field_accuracy_drop'] <= policy['allowed_critical_field_drop'],
        'parse_failure_within_limit':
            comparison['candidate']['parse_failure_rate'] <= policy['max_parse_failure_rate'],
        'evidence_coverage_met':
            comparison['candidate']['evidence_coverage_rate'] >= policy['min_evidence_coverage'],
        'unsafe_or_leaky_zero':
            security['unsafe_or_leaky_count'] <= policy['max_unsafe_or_leaky'],
        'security_expectations_met': security['correct'] == security['case_count'],
        'cost_within_limit':
            comparison['candidate']['cost_per_inquiry_usd'] <= policy['max_cost_per_case_usd'],
        'circuit_fallback_verified': (not policy['require_circuit_fallback'] or
            circuit['circuit_open'] and circuit['fallback_responses'] == circuit['requests']),
        'external_actions_zero':
            (not policy['require_external_actions_zero'] or canary['external_actions'] == 0),
    }
    return {'decision': 'SIMULATED_CANARY_APPROVED' if all(checks.values()) else
            'SIMULATED_CANARY_REJECTED', 'checks': checks,
            'scope': 'synthetic_training_only', 'real_pilot_authorized': False}


def exercise_rollout(output, registry_validation, candidate_percent, release):
    path = Path(output) / 'model-rollout.jsonl'
    if path.exists():
        path.unlink()
    book = RolloutBook(path, registry_validation['content_sha256'])
    book.append('sim-model-owner', 'model_owner', 'approve_candidate',
                '100-case synthetic extraction comparison passed')
    book.append('sim-ai-safety-owner', 'ai_safety_owner', 'approve_candidate',
                '24-case adversarial gateway evaluation passed')
    if release['decision'] == 'SIMULATED_CANARY_APPROVED':
        book.append('sim-release-manager', 'release_manager', 'activate_canary',
                    'all synthetic release gates passed',
                    candidate_percent=candidate_percent)
        book.append('sim-operator', 'operator', 'rollback_baseline',
                    'scheduled rollback drill after circuit-breaker exercise')
    status = book.status()
    return {**status, 'rollback_verified': status['active_route'] == 'baseline' and
            any(x['action'] == 'rollback_baseline' for x in status['events'])}


def render(report):
    comp = report['comparison']
    sec = report['security']
    canary = report['canary']
    circuit = report['circuit']
    release = report['release']
    return f"""# Stage 12 Model Evaluation, Safety & Canary 报告

状态：`{report['status']}`；真实 Pilot Gate：`{report['real_pilot_gate']}`。

- 模型对比：{comp['case_count']} 个合成案例；baseline / candidate 字段准确率 {comp['baseline']['critical_field_accuracy']:.1%} / {comp['candidate']['critical_field_accuracy']:.1%}；下降 {comp['field_accuracy_drop']:.1%}。
- 安全评估：{sec['correct']}/{sec['case_count']} 符合预期；危险动作或秘密泄漏 {sec['unsafe_or_leaky_count']}。
- Canary：{canary['case_count']} 个 Stage 11 案例；入模型前隔离 {canary['quarantined_before_model']}；对外动作 {canary['external_actions']}。
- 熔断演练：{circuit['requests']} 个请求；candidate 调用 {circuit['candidate_calls']}；回退响应 {circuit['fallback_responses']}；熔断 `{str(circuit['circuit_open']).lower()}`。
- 发布判定：`{release['decision']}`；演练后活跃路由 `{report['rollout']['active_route']}`；哈希链有效 `{str(report['rollout']['hash_chain_valid']).lower()}`。
- 外部模型调用 0；真实客户数据 0；真实客户侧发送 0。

候选模型是可计费的确定性 stand-in，用于练习网关、评估、Canary、熔断和发布职责。本报告不证明任何真实模型或客户现场表现。
"""


def run_demo(output, *, check_baseline=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name in ('comparison-telemetry.jsonl', 'canary-telemetry.jsonl'):
        path = output / name
        if path.exists():
            path.unlink()
    registry = read(REGISTRY)
    validation = validate_registry(registry, ROOT)
    manifest = read(MANIFEST)
    validate_manifest(manifest, base_dir=MANIFEST.parent)
    comparison = compare_models(registry, output)
    security = evaluate_security(read(SECURITY_CASES)['cases'], registry)
    canary = run_canary(read_jsonl(EVENTS), manifest, registry, ROOT,
                        output / 'canary-telemetry.jsonl')
    circuit = run_circuit_drill(registry)
    release = release_decision(comparison, security, canary, circuit,
                               read(RELEASE_POLICY))
    rollout = exercise_rollout(output, validation,
                               registry['routing']['candidate_percent'], release)
    report = {
        'status': ('SYNTHETIC_MODEL_CANARY_READY' if
                   release['decision'] == 'SIMULATED_CANARY_APPROVED' and
                   rollout['rollback_verified'] else 'SYNTHETIC_MODEL_CANARY_BLOCKED'),
        'registry': validation,
        'comparison': comparison,
        'security': security,
        'canary': canary,
        'circuit': circuit,
        'release': release,
        'rollout': rollout,
        'telemetry_boundary': {
            'raw_prompt_logged': False, 'raw_output_logged': False,
            'direct_identifiers_logged': False,
        },
        'external_model_calls': 0,
        'external_business_actions': 0,
        'real_customer_data_ingested': False,
        'actual_pilot_users': 0,
        'real_pilot_gate': 'NOT_EVALUATED',
    }
    write(output / 'model-comparison.json', comparison)
    write(output / 'security-evaluation.json', security)
    write(output / 'canary-report.json', canary)
    write(output / 'circuit-drill.json', circuit)
    write(output / 'release-decision.json', release)
    write(output / 'stage12-report.json', report)
    (output / 'stage12-report.md').write_text(render(report), encoding='utf-8')
    if check_baseline:
        check_report(report)
    print(f"Stage 12：{report['status']}；安全用例 {security['correct']}/{security['case_count']}，Canary {canary['case_count']}，真实模型调用 0。")
    return report


def _resolve(value, path):
    for part in path.split('.'):
        value = value[part]
    return value


def check_report(report):
    for path, expected in read(BASELINE).items():
        actual = _resolve(report, path)
        if actual != expected:
            raise ValueError(f'Stage 12 回归失败：{path} 期望 {expected!r}，实际 {actual!r}')
    return True


def main():
    parser = argparse.ArgumentParser(description='Stage 12 模型评估、安全、Canary 与回滚演练')
    parser.add_argument('command', choices=['demo', 'registry', 'security', 'endpoint-eval'])
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-12')
    parser.add_argument('--check-baseline', action='store_true')
    parser.add_argument('--endpoint')
    args = parser.parse_args()
    try:
        if args.command == 'registry':
            print(json.dumps(validate_registry(read(REGISTRY), ROOT), ensure_ascii=False, indent=2))
        elif args.command == 'security':
            registry = read(REGISTRY)
            validate_registry(registry, ROOT)
            result = evaluate_security(read(SECURITY_CASES)['cases'], registry)
            write(args.output / 'security-evaluation.json', result)
            print(json.dumps({k: v for k, v in result.items() if k != 'rows'},
                             ensure_ascii=False, indent=2))
        elif args.command == 'endpoint-eval':
            if not args.endpoint:
                parser.error('endpoint-eval 需要 --endpoint 本机 HTTP 地址')
            registry = read(REGISTRY)
            validate_registry(registry, ROOT)
            result = evaluate_loopback_endpoint(registry, args.endpoint,
                                                args.output.resolve())
            print(json.dumps({'output': str(args.output / 'endpoint-evaluation.json'),
                              'case_count': result['result']['case_count'],
                              'release_authorized': False}, ensure_ascii=False, indent=2))
        else:
            run_demo(args.output.resolve(), check_baseline=args.check_baseline)
        return 0
    except (OSError, KeyError, TypeError, ValueError) as exc:
        print(f'Stage 12 失败：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
