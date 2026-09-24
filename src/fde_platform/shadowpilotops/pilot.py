"""Runtime gates and evidence validation for a controlled Shadow Pilot."""
from __future__ import annotations

import csv
import hashlib
import json
import statistics
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


class ShadowPilotError(ValueError):
    """Pilot runtime records violate scope, safety or evidence controls."""


MOBILIZATION_REQUIREMENTS = {
    "executed_pilot_sow", "purchase_order_or_equivalent",
    "data_security_authorization", "customer_sandbox",
    "enterprise_identity_and_roles", "readonly_connectors",
    "approved_model_and_rules", "operator_training_and_roster",
    "telemetry_and_incident_route", "rollback_and_stop_drill",
}

START_ROLES = {
    "customer_sponsor", "customer_process_owner", "customer_security_owner",
    "fde_delivery_owner", "fde_commercial_owner",
}

EVIDENCE_ROLES = {
    "customer_process_owner", "fde_delivery_owner", "fde_security_owner",
}

VERSION_TYPES = {"model", "prompt", "rules", "knowledge", "connector"}

DECISIONS = {
    "accepted", "minor_edit", "material_edit", "alternate_selected",
    "escalated", "rejected", "bypassed",
}

REQUIRED_TRANSITIONS = [
    "planned", "start_review", "running", "paused", "remediation",
    "resume_review", "running", "completed",
]

METRIC_IDS = {
    "field_quality", "evidence_coverage", "unsafe_action_rate",
    "operator_adoption", "review_cycle_time", "cost_per_case",
}


def load_json(path: Path | str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ShadowPilotError(f"无法读取 Pilot 资料：{exc}") from exc
    if not isinstance(value, dict):
        raise ShadowPilotError("Pilot 资料必须是 JSON object")
    return value


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def file_sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(value: dict, keys: tuple[str, ...], where: str) -> None:
    missing = [key for key in keys if value.get(key) in (None, "", [])]
    if missing:
        raise ShadowPilotError(f"{where} 缺少字段：{', '.join(missing)}")


def _index(rows: list[dict], key: str, where: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        raise ShadowPilotError(f"{where} 必须是 list")
    result: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ShadowPilotError(f"{where} 必须是 object list")
        _require(row, (key,), where)
        if row[key] in result:
            raise ShadowPilotError(f"{where} {key} 重复：{row[key]}")
        result[row[key]] = row
    return result


def _number(value: object, where: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ShadowPilotError(f"{where} 必须是数字") from exc
    if not result.is_finite() or result < 0:
        raise ShadowPilotError(f"{where} 必须是非负有限数字")
    return result


def _parse_date(value: str, where: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ShadowPilotError(f"{where} 日期必须为 YYYY-MM-DD") from exc


def _parse_datetime(value: str, where: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ShadowPilotError(f"{where} 时间格式无效") from exc
    if result.tzinfo is None:
        raise ShadowPilotError(f"{where} 必须包含时区")
    return result


def _inside(path: Path, parent: Path) -> bool:
    path, parent = path.resolve(), parent.resolve()
    return path == parent or parent in path.parents


def _placeholder_paths(value: object, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            paths.extend(_placeholder_paths(child, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_placeholder_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        normalized = value.strip().upper()
        if normalized.startswith(("REPLACE", "PENDING")) or normalized == "NONE":
            paths.append(prefix)
    return paths


def _validate_mobilization(rows: list[dict], expected_status: str) -> dict[str, dict]:
    items = _index(rows, "requirement_id", "mobilization requirement")
    if set(items) != MOBILIZATION_REQUIREMENTS:
        raise ShadowPilotError("Pilot Mobilization 十项要求不完整")
    if any(row.get("status") != expected_status or not row.get("evidence_ref")
           for row in items.values()):
        raise ShadowPilotError("Pilot Mobilization 尚未全部 Ready")
    return items


def _validate_roster(rows: list[dict], expected_training: str) -> dict[str, dict]:
    roster = _index(rows, "user_ref", "pilot roster")
    if len(roster) < 4:
        raise ShadowPilotError("Pilot 至少需要 Operator、Engineer 和 Duty Manager 覆盖")
    roles = set()
    for row in roster.values():
        _require(row, ("role", "shift", "training_status", "training_evidence_ref",
                       "active_from", "active_to"), f"roster {row['user_ref']}")
        if row["training_status"] != expected_training:
            raise ShadowPilotError(f"用户尚未完成培训：{row['user_ref']}")
        active_from = _parse_date(row["active_from"], "roster.active_from")
        active_to = _parse_date(row["active_to"], "roster.active_to")
        if active_from > active_to:
            raise ShadowPilotError(f"Roster 有效期倒序：{row['user_ref']}")
        if row.get("person_name") or row.get("email"):
            raise ShadowPilotError("Pilot manifest 只保存用户引用，不保存姓名或邮箱")
        roles.add(row["role"])
    if not {"operator", "engineer", "duty_manager"}.issubset(roles):
        raise ShadowPilotError("Pilot 排班缺少 Operator、Engineer 或 Duty Manager")
    return roster


def _validate_versions(rows: list[dict], expected_status: str) -> dict[str, dict]:
    versions = _index(rows, "component_type", "approved version")
    if set(versions) != VERSION_TYPES:
        raise ShadowPilotError("Pilot 运行版本不完整")
    for row in versions.values():
        _require(row, ("version", "status", "approval_ref"),
                 f"version {row['component_type']}")
        if row["status"] != expected_status:
            raise ShadowPilotError(f"未批准运行版本：{row['component_type']}")
    return versions


def _validate_authorization(value: dict, scope: object, expected_status: str) -> str:
    _require(value, ("authorization_id", "status", "authorized_at", "scope_sha256",
                     "approvals"), "start authorization")
    _parse_datetime(value["authorized_at"], "start authorization.authorized_at")
    scope_sha = digest(scope)
    if value["scope_sha256"] != scope_sha:
        raise ShadowPilotError("Pilot 启动授权未绑定当前范围")
    if value["status"] != expected_status:
        raise ShadowPilotError("Pilot 启动授权状态无效")
    approvals = _index(value["approvals"], "role", "start approval")
    if set(approvals) != START_ROLES:
        raise ShadowPilotError("Pilot 启动签核角色不完整")
    for row in approvals.values():
        if row.get("status") != expected_status or \
                row.get("content_sha256") != scope_sha or \
                not row.get("approved_at") or not row.get("evidence_ref"):
            raise ShadowPilotError("Pilot 启动签核未绑定当前范围")
        _parse_date(row["approved_at"], "start approval.approved_at")
    return scope_sha


def _validate_state(rows: list[dict], expected_approval: str,
                    require_pause: bool) -> list[dict]:
    states = [row.get("to_state") for row in rows]
    if require_pause and states != REQUIRED_TRANSITIONS:
        raise ShadowPilotError("Pilot 状态机缺少 Pause/Remediation/Resume 或完成路径")
    if not require_pause and (states[:3] != ["planned", "start_review", "running"] or
                              not states or states[-1] != "completed"):
        raise ShadowPilotError("Pilot 状态机缺少启动或完成路径")
    allowed = {
        (None, "planned"), ("planned", "start_review"),
        ("start_review", "running"), ("running", "paused"),
        ("paused", "remediation"), ("remediation", "resume_review"),
        ("resume_review", "running"), ("running", "completed"),
    }
    previous = None
    times = []
    for row in rows:
        _require(row, ("transition_id", "to_state", "recorded_at", "actor_role",
                       "reason", "evidence_ref"), "state transition")
        at = _parse_datetime(row["recorded_at"], "state transition.recorded_at")
        times.append(at)
        if row.get("from_state") != previous:
            raise ShadowPilotError("Pilot 状态转换不连续")
        if (previous, row["to_state"]) not in allowed:
            raise ShadowPilotError("Pilot 状态转换无效")
        if row["to_state"] in {"running", "completed"} and \
                row.get("approval_status") != expected_approval:
            raise ShadowPilotError("Pilot 运行或完成转换缺少审批")
        previous = row["to_state"]
    if times != sorted(times):
        raise ShadowPilotError("Pilot 状态转换时间倒序")
    return rows


def _validate_incidents(rows: list[dict], expected_resolved: str,
                        require_incident: bool) -> dict[str, dict]:
    incidents = _index(rows, "incident_id", "pilot incident")
    if require_incident and not incidents:
        raise ShadowPilotError("参考 Pilot 至少需要一次 Pause/Resume 事故演练")
    for row in incidents.values():
        _require(row, ("severity", "detected_at", "type", "status", "pause_ref",
                       "remediation_ref", "resume_approval_ref"),
                 f"incident {row['incident_id']}")
        _parse_datetime(row["detected_at"], "incident.detected_at")
        if row["status"] != expected_resolved:
            raise ShadowPilotError(f"Pilot 事故尚未解决：{row['incident_id']}")
    return incidents


def _validate_incident_state_links(incidents: dict[str, dict], transitions: list[dict]) -> None:
    state_ids: dict[str, set[str]] = {}
    for row in transitions:
        state_ids.setdefault(row["to_state"], set()).add(row["transition_id"])
    for incident_id, row in incidents.items():
        if row["pause_ref"] not in state_ids.get("paused", set()) or \
                row["resume_approval_ref"] not in state_ids.get("running", set()):
            raise ShadowPilotError(f"事故未绑定 Pause/Resume 状态：{incident_id}")
    pause_ids = state_ids.get("paused", set())
    if pause_ids != {row["pause_ref"] for row in incidents.values()}:
        raise ShadowPilotError("每次 Pause 必须有且仅引用当前状态机中的事故")


GATE_CHECKS = {
    "contract_valid", "roster_covered", "connector_readonly", "no_open_sev1",
    "versions_approved", "budget_available", "kill_switch_tested",
}


def _validate_daily_gates(rows: list[dict], incident_ids: set[str],
                          require_pause: bool) -> dict[str, dict]:
    gates = _index(rows, "pilot_date", "daily gate")
    paused_dates = []
    for pilot_date, row in gates.items():
        _parse_date(pilot_date, "daily gate.pilot_date")
        _require(row, ("status", "checks", "decision_owner_role", "evidence_ref"),
                 f"daily gate {pilot_date}")
        if row["decision_owner_role"] not in {"duty_manager", "fde_delivery_owner"}:
            raise ShadowPilotError(f"daily gate {pilot_date} 决策角色无权")
        if set(row["checks"]) != GATE_CHECKS or any(
                not isinstance(value, bool) for value in row["checks"].values()):
            raise ShadowPilotError(f"daily gate {pilot_date} 检查项不完整")
        if row["status"] == "ready" and not all(row["checks"].values()):
            raise ShadowPilotError(f"daily gate {pilot_date} 错误标记 Ready")
        if row["status"] == "paused":
            paused_dates.append(pilot_date)
            if all(row["checks"].values()) or row.get("incident_ref") not in incident_ids:
                raise ShadowPilotError(f"daily gate {pilot_date} 暂停证据无效")
        elif row["status"] != "ready":
            raise ShadowPilotError(f"daily gate {pilot_date} 状态无效")
    if require_pause and not paused_dates:
        raise ShadowPilotError("参考 Pilot 缺少受控暂停日演练")
    return gates


def _validate_cases(rows: list[dict], pilot: dict, roster: dict[str, dict],
                    versions: dict[str, dict], gates: dict[str, dict]) -> dict:
    cases = _index(rows, "case_id", "pilot case")
    if not cases:
        raise ShadowPilotError("Pilot 没有案例证据")
    if len(cases) > int(pilot["case_cap"]):
        raise ShadowPilotError("Pilot 案例数超过 SOW 上限")
    totals = {"fields": 0, "correct": 0, "claims": 0, "evidenced": 0,
              "unsafe": 0, "external_sent": 0, "customer_write": 0,
              "expert_minutes": Decimal("0"), "cost": Decimal("0")}
    reviews = []
    decisions = {item: 0 for item in DECISIONS}
    version_map = {key: row["version"] for key, row in versions.items()}
    period_from = _parse_date(pilot["period"]["from"], "pilot.period.from")
    period_to = _parse_date(pilot["period"]["to"], "pilot.period.to")
    for row in cases.values():
        _require(row, ("pilot_date", "tenant_ref", "operator_ref", "source_event_ref",
                       "trace_ref", "versions", "fields_total", "fields_correct",
                       "material_claims", "evidenced_claims", "unsafe_actions",
                       "decision", "review_minutes", "expert_minutes", "cost_cny",
                       "external_sent", "customer_write", "outcome_ref"),
                 f"case {row['case_id']}")
        case_date = _parse_date(row["pilot_date"], "case.pilot_date")
        if not period_from <= case_date <= period_to:
            raise ShadowPilotError(f"案例日期不在 Pilot 周期内：{row['case_id']}")
        gate = gates.get(row["pilot_date"])
        if not gate or gate["status"] != "ready":
            message = "暂停日仍处理案例" if gate and gate["status"] == "paused" \
                else "案例缺少 Ready Daily Gate"
            raise ShadowPilotError(f"{message}：{row['case_id']}")
        if row["tenant_ref"] != pilot["tenant_ref"]:
            raise ShadowPilotError(f"案例跨租户：{row['case_id']}")
        if row["operator_ref"] not in roster or roster[row["operator_ref"]]["role"] != "operator":
            raise ShadowPilotError(f"案例 Reviewer 不在 Operator roster：{row['case_id']}")
        reviewer = roster[row["operator_ref"]]
        if not _parse_date(reviewer["active_from"], "roster.active_from") <= case_date <= \
                _parse_date(reviewer["active_to"], "roster.active_to"):
            raise ShadowPilotError(f"案例 Reviewer 不在有效排班期：{row['case_id']}")
        if row["versions"] != version_map:
            raise ShadowPilotError(f"案例运行版本漂移：{row['case_id']}")
        fields, correct = int(row["fields_total"]), int(row["fields_correct"])
        claims, evidenced = int(row["material_claims"]), int(row["evidenced_claims"])
        if fields <= 0 or not 0 <= correct <= fields or claims <= 0 or not 0 <= evidenced <= claims:
            raise ShadowPilotError(f"案例质量分母无效：{row['case_id']}")
        if row["decision"] not in DECISIONS:
            raise ShadowPilotError(f"案例人工决定无效：{row['case_id']}")
        if row["external_sent"] is not False or row["customer_write"] is not False:
            raise ShadowPilotError(f"Shadow 边界被突破：{row['case_id']}")
        totals["fields"] += fields; totals["correct"] += correct
        totals["claims"] += claims; totals["evidenced"] += evidenced
        unsafe = int(row["unsafe_actions"])
        if unsafe < 0:
            raise ShadowPilotError(f"案例危险动作计数无效：{row['case_id']}")
        totals["unsafe"] += unsafe
        totals["external_sent"] += int(row["external_sent"])
        totals["customer_write"] += int(row["customer_write"])
        totals["expert_minutes"] += _number(row["expert_minutes"], "expert minutes")
        totals["cost"] += _number(row["cost_cny"], "case cost")
        reviews.append(float(_number(row["review_minutes"], "review minutes")))
        decisions[row["decision"]] += 1
    return {"cases": cases, "totals": totals, "reviews": reviews,
            "decisions": decisions}


def _calculate_metrics(case_facts: dict) -> dict[str, Decimal]:
    totals, count = case_facts["totals"], len(case_facts["cases"])
    used = count - case_facts["decisions"]["bypassed"]
    return {
        "field_quality": Decimal(totals["correct"]) / Decimal(totals["fields"]),
        "evidence_coverage": Decimal(totals["evidenced"]) / Decimal(totals["claims"]),
        "unsafe_action_rate": Decimal(totals["unsafe"]) / Decimal(count),
        "operator_adoption": Decimal(used) / Decimal(count),
        "review_cycle_time": Decimal(str(statistics.median(case_facts["reviews"]))),
        "cost_per_case": totals["cost"] / Decimal(count),
    }


def _validate_targets(rows: list[dict], metrics: dict[str, Decimal]) -> dict[str, dict]:
    targets = _index(rows, "metric_id", "pilot metric target")
    if set(targets) != METRIC_IDS:
        raise ShadowPilotError("Pilot 六项指标目标不完整")
    for metric_id, row in targets.items():
        _require(row, ("direction", "target", "stop_threshold", "denominator_policy",
                       "baseline_ref"), f"metric target {metric_id}")
        target = _number(row["target"], "metric target")
        stop_threshold = _number(row["stop_threshold"], "metric stop threshold")
        value = metrics[metric_id]
        passed = value >= target if row["direction"] == "min" else value <= target
        if row["direction"] not in {"min", "max"}:
            raise ShadowPilotError(f"指标方向无效：{metric_id}")
        if row["direction"] == "min" and stop_threshold > target or \
                row["direction"] == "max" and stop_threshold < target:
            raise ShadowPilotError(f"Stop Threshold 与目标方向矛盾：{metric_id}")
        stopped = value < stop_threshold if row["direction"] == "min" \
            else value > stop_threshold
        if stopped:
            raise ShadowPilotError(f"Pilot 指标触发 Stop Threshold：{metric_id}")
        row["calculated_passed"] = passed
    return targets


def _validate_bundle(value: dict, evidence: object, expected_status: str) -> str:
    _require(value, ("bundle_id", "bundle_sha256", "approvals"), "evidence bundle")
    bundle_sha = digest(evidence)
    if value["bundle_sha256"] != bundle_sha:
        raise ShadowPilotError("Pilot Evidence Bundle 摘要不匹配")
    approvals = _index(value["approvals"], "role", "evidence approval")
    if set(approvals) != EVIDENCE_ROLES:
        raise ShadowPilotError("Pilot Evidence Bundle 签核角色不完整")
    for row in approvals.values():
        if row.get("status") != expected_status or \
                row.get("content_sha256") != bundle_sha or \
                not row.get("approved_at") or not row.get("evidence_ref"):
            raise ShadowPilotError("Pilot Evidence Bundle 签核未绑定当前内容")
        _parse_date(row["approved_at"], "evidence approval.approved_at")
    return bundle_sha


def _validate_common(record: dict, *, simulated: bool) -> dict:
    _require(record, ("pilot", "mobilization_requirements", "roster", "versions",
                      "start_authorization", "state_transitions",
                      "daily_gates", "case_events", "metric_targets",
                      "evidence_bundle"), "pilot record")
    if "incidents" not in record:
        raise ShadowPilotError("pilot record 缺少字段：incidents")
    pilot = record["pilot"]
    _require(pilot, ("pilot_id", "tenant_ref", "period", "case_cap", "user_cap",
                     "outbox_enabled", "customer_write_enabled"), "pilot")
    period_from = _parse_date(pilot["period"]["from"], "pilot.period.from")
    period_to = _parse_date(pilot["period"]["to"], "pilot.period.to")
    if period_from > period_to:
        raise ShadowPilotError("Pilot 周期倒序")
    if pilot["outbox_enabled"] is not False or pilot["customer_write_enabled"] is not False:
        raise ShadowPilotError("Shadow Pilot 必须禁用 Outbox 和客户系统写入")
    status_prefix = "simulated_" if simulated else ""
    mobilization = _validate_mobilization(record["mobilization_requirements"],
                                          status_prefix + "ready")
    roster = _validate_roster(record["roster"], status_prefix + "trained")
    if len(roster) > int(pilot["user_cap"]):
        raise ShadowPilotError("Pilot roster 超过 SOW 用户上限")
    versions = _validate_versions(record["versions"], status_prefix + "approved")
    scope = {"pilot": pilot, "mobilization_requirements": record["mobilization_requirements"],
             "roster": record["roster"], "versions": record["versions"],
             "metric_targets": record["metric_targets"]}
    scope_sha = _validate_authorization(record["start_authorization"], scope,
                                        status_prefix + "approved")
    transitions = _validate_state(record["state_transitions"],
                                  status_prefix + "approved", simulated)
    incidents = _validate_incidents(record["incidents"],
                                    status_prefix + "resolved", simulated)
    _validate_incident_state_links(incidents, transitions)
    gates = _validate_daily_gates(record["daily_gates"], set(incidents), simulated)
    if any(not period_from <= _parse_date(day, "daily gate.pilot_date") <= period_to
           for day in gates):
        raise ShadowPilotError("Daily Gate 日期不在 Pilot 周期内")
    cases = _validate_cases(record["case_events"], pilot, roster, versions, gates)
    if cases["totals"]["unsafe"] > 0:
        raise ShadowPilotError("Shadow Pilot 出现危险动作，必须 Stop 而非完成")
    metrics = _calculate_metrics(cases)
    targets = _validate_targets(record["metric_targets"], metrics)
    evidence = {"scope_sha256": scope_sha, "state_transitions": transitions,
                "incidents": record["incidents"], "daily_gates": record["daily_gates"],
                "case_events": record["case_events"], "metric_targets": record["metric_targets"]}
    bundle_sha = _validate_bundle(record["evidence_bundle"], evidence,
                                  status_prefix + "approved")
    return {"pilot": pilot, "roster": roster, "versions": versions,
            "mobilization": mobilization, "transitions": transitions,
            "incidents": incidents, "gates": gates, "cases": cases,
            "metrics": metrics, "targets": targets, "bundle_sha256": bundle_sha}


def _report(facts: dict, status: str, *, real: bool) -> dict:
    metrics, cases = facts["metrics"], facts["cases"]
    return {
        "status": status,
        "pilot_id": facts["pilot"]["pilot_id"],
        "processed_case_count": len(cases["cases"]),
        "roster_user_count": len(facts["roster"]),
        "daily_gate_count": len(facts["gates"]),
        "pause_count": sum(row["to_state"] == "paused" for row in facts["transitions"]),
        "resolved_incident_count": len(facts["incidents"]),
        "field_quality": f"{metrics['field_quality']:.4f}",
        "evidence_coverage": f"{metrics['evidence_coverage']:.4f}",
        "unsafe_action_rate": f"{metrics['unsafe_action_rate']:.4f}",
        "operator_adoption": f"{metrics['operator_adoption']:.4f}",
        "median_review_minutes": f"{metrics['review_cycle_time']:.2f}",
        "cost_per_case_cny": f"{metrics['cost_per_case']:.2f}",
        "expert_minutes": f"{cases['totals']['expert_minutes']:.2f}",
        "decision_counts": cases["decisions"],
        "external_sent_count": cases["totals"]["external_sent"],
        "customer_write_count": cases["totals"]["customer_write"],
        "metric_pass_count": sum(row["calculated_passed"] for row in facts["targets"].values()),
        "metric_count": len(METRIC_IDS),
        "real_pilot": False,
        "external_record_asserts_real_pilot": real,
        "real_pilot_verified_by_code": False,
        "pilot_acceptance_recorded": False,
        "production_authorized": False,
        "next_gate": "PILOT_ACCEPTANCE_AND_PRODUCTION_DECISION",
    }


def analyze_rehearsal(stage_root: Path, record: dict) -> dict:
    stage_root = Path(stage_root).resolve()
    if record.get("mode") != "counterfactual_shadow_pilot_rehearsal" or \
            record.get("progression_mode") != "synthetic_authorized_branch":
        raise ShadowPilotError("公开参考数据必须是明确的反事实 Shadow Pilot 分支")
    source_path = (stage_root.parent / record.get("source_stage20_path", "")).resolve()
    if stage_root.parent not in source_path.parents or not source_path.is_file() or \
            record.get("source_stage20_sha256") != file_sha256(source_path):
        raise ShadowPilotError("Stage 20 来源路径或摘要不匹配")
    assertions = record.get("real_world_assertions", {})
    expected = {"real_pilot_authorized": False, "real_pilot_users": 0,
                "real_pilot_cases": 0, "external_customer_actions": 0,
                "real_production_authorized": False}
    if any(assertions.get(key) != value for key, value in expected.items()):
        raise ShadowPilotError("反事实分支不得声明真实 Pilot、客户动作或生产授权")
    facts = _validate_common(record, simulated=True)
    return _report(facts, "SYNTHETIC_SHADOW_PILOT_COMPLETED_FOR_ACCEPTANCE_REHEARSAL",
                   real=False)


def preflight_external_pilot(manifest_path: Path | str, repo_root: Path | str) -> dict:
    path, root = Path(manifest_path).expanduser().resolve(), Path(repo_root).resolve()
    if _inside(path, root):
        raise ShadowPilotError("真实 Pilot 运行清单必须存放在 Git 仓库之外")
    record = load_json(path)
    if record.get("mode") != "external_controlled_shadow_pilot_record":
        raise ShadowPilotError("外部 Pilot 清单 mode 无效")
    placeholders = _placeholder_paths(record)
    if placeholders:
        raise ShadowPilotError(f"外部 Pilot 清单仍有模板占位符：{', '.join(placeholders[:5])}")
    release = record.get("stage20_release", {})
    _require(release, ("status", "decision_record_ref", "human_start_authorized",
                       "authorized_by_role", "authorized_at"), "Stage 20 release")
    if release["status"] != "READY_FOR_HUMAN_PILOT_START_REVIEW" or \
            release["human_start_authorized"] is not True or \
            release["authorized_by_role"] not in {"customer_sponsor", "fde_delivery_owner"}:
        raise ShadowPilotError("Stage 20 尚未完成人工 Pilot 启动授权")
    _parse_datetime(release["authorized_at"], "Stage 20 release.authorized_at")
    privacy = record.get("privacy_assertions", {})
    expected_privacy = {"contains_raw_customer_content": False,
                        "contains_person_names_or_emails": False,
                        "contains_credentials": False,
                        "copied_into_source_repository": False}
    if any(privacy.get(key) is not value for key, value in expected_privacy.items()):
        raise ShadowPilotError("外部 Pilot 清单违反数据最小化或仓库隔离要求")
    facts = _validate_common(record, simulated=False)
    report = _report(facts, "READY_FOR_HUMAN_PILOT_ACCEPTANCE_REVIEW", real=True)
    report["partner_public_label"] = record.get("partner_public_label")
    report["decision_reference_sha256"] = hashlib.sha256(
        release["decision_record_ref"].encode("utf-8")).hexdigest()
    report["pilot_acceptance_recorded"] = False
    return report


def render(report: dict) -> str:
    return f"""# Stage 21 Controlled Shadow Pilot Operations

状态：`{report['status']}`。

- 案例：{report['processed_case_count']}；受控用户：{report['roster_user_count']}。
- Daily Gate：{report['daily_gate_count']}；暂停：{report['pause_count']}；已解决事故：{report['resolved_incident_count']}。
- 字段质量：{report['field_quality']}；证据覆盖：{report['evidence_coverage']}；危险动作率：{report['unsafe_action_rate']}。
- 采用率：{report['operator_adoption']}；审核中位数：{report['median_review_minutes']} 分钟；单案成本：CNY {report['cost_per_case_cny']}。
- 外部发送：{report['external_sent_count']}；客户系统写入：{report['customer_write_count']}。
- 下一 Gate：`{report['next_gate']}`。

完成 Shadow Pilot 只形成验收证据，不自动授权生产、自动外发或客户系统写入。
"""


def write_outputs(output: Path | str, report: dict, record: dict | None = None) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "stage21-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "stage21-report.md").write_text(render(report), encoding="utf-8")
    if record:
        with (output / "daily-gates.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            fields = ("pilot_date", "status", "decision_owner_role", "evidence_ref", "incident_ref")
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in record["daily_gates"]:
                writer.writerow({key: row.get(key, "") for key in fields})
        with (output / "decision-distribution.csv").open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle); writer.writerow(("decision", "count"))
            for decision, count in report["decision_counts"].items():
                writer.writerow((decision, count))


def prepare_external_pack(output: Path | str, template: dict) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "external-shadow-pilot.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sheets = {
        "daily-gates.csv": ("pilot_date", "status", "decision_owner_role", "evidence_ref", "incident_ref"),
        "case-ledger.csv": ("case_id", "pilot_date", "operator_ref", "decision", "trace_ref", "outcome_ref"),
        "incident-register.csv": ("incident_id", "severity", "type", "status", "pause_ref", "resume_approval_ref"),
        "shift-roster.csv": ("user_ref", "role", "shift", "training_status", "active_from", "active_to"),
    }
    for name, fields in sheets.items():
        with (output / name).open("w", newline="", encoding="utf-8-sig") as handle:
            csv.writer(handle).writerow(fields)
