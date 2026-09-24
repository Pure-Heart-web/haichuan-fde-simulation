"""Evidence-first controls for a live paid Discovery engagement."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


class DiscoveryExecutionError(ValueError):
    """Discovery execution records are incomplete, inconsistent or unsafe."""


REQUIRED_SESSION_TYPES = {
    "kickoff",
    "sponsor_interview",
    "process_owner_interview",
    "process_observation",
    "sample_audit",
    "data_security_workshop",
    "solution_workshop",
    "steering_readout",
}

REQUIRED_BASELINE_METRICS = {
    "inquiry_volume",
    "end_to_end_cycle_time",
    "rework_rate",
    "missed_or_delayed_rate",
    "expert_escalation_rate",
}

REQUIRED_DELIVERABLES = {
    "D1_PROBLEM_SCOPE_RACI",
    "D2_BASELINE_SUCCESS_PLAN",
    "D3_DATA_SECURITY_IP_BOUNDARY",
    "D4_SOLUTION_INTEGRATION_PLAN",
    "D5_BUSINESS_CASE",
    "D6_PILOT_RECOMMENDATION",
}

REQUIRED_BASELINE_APPROVAL_ROLES = {
    "customer_process_owner",
    "fde_delivery_owner",
}

REQUIRED_FIELDWORK_ROLES = {
    "customer_sponsor",
    "customer_process_owner",
    "customer_data_or_security_owner",
    "fde_delivery_owner",
}


def load_json(path: Path | str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DiscoveryExecutionError(f"无法读取 Discovery 资料：{exc}") from exc
    if not isinstance(value, dict):
        raise DiscoveryExecutionError("Discovery 资料必须是 JSON object")
    return value


def _require(value: dict, keys: tuple[str, ...], where: str) -> None:
    missing = [key for key in keys if value.get(key) in (None, "", [])]
    if missing:
        raise DiscoveryExecutionError(f"{where} 缺少字段：{', '.join(missing)}")


def _index(rows: list[dict], key: str, where: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        raise DiscoveryExecutionError(f"{where} 必须是 list")
    result: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise DiscoveryExecutionError(f"{where} 必须是 object list")
        _require(row, (key,), where)
        if row[key] in result:
            raise DiscoveryExecutionError(f"{where} {key} 重复：{row[key]}")
        result[row[key]] = row
    return result


def _parse_date(value: str, where: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise DiscoveryExecutionError(f"{where} 日期必须为 YYYY-MM-DD") from exc


def _money(value: object, where: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DiscoveryExecutionError(f"{where} 必须是数字") from exc
    if not result.is_finite() or result < 0:
        raise DiscoveryExecutionError(f"{where} 必须是非负有限数字")
    return result


def _inside(path: Path, parent: Path) -> bool:
    path, parent = path.resolve(), parent.resolve()
    return path == parent or parent in path.parents


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _placeholder_paths(value: object, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            paths.extend(_placeholder_paths(child, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            paths.extend(_placeholder_paths(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and value.strip().upper().startswith("REPLACE"):
        paths.append(prefix)
    return paths


def _validate_sessions(rows: list[dict], *, simulated: bool) -> dict[str, dict]:
    sessions = _index(rows, "session_id", "fieldwork session")
    types = set()
    for row in sessions.values():
        _require(row, ("session_type", "held_on", "status", "facilitator_role",
                       "participant_roles", "evidence_ref"),
                 f"session {row['session_id']}")
        _parse_date(row["held_on"], f"session {row['session_id']}.held_on")
        if row["status"] != ("simulated_completed" if simulated else "completed"):
            raise DiscoveryExecutionError(f"session {row['session_id']} 尚未完成")
        if not isinstance(row["participant_roles"], list):
            raise DiscoveryExecutionError("participant_roles 必须是 list")
        types.add(row["session_type"])
    missing = REQUIRED_SESSION_TYPES - types
    if missing:
        raise DiscoveryExecutionError(f"现场活动缺失：{', '.join(sorted(missing))}")
    return sessions


def _validate_evidence(rows: list[dict], *, simulated: bool) -> dict[str, dict]:
    evidence = _index(rows, "evidence_id", "field evidence")
    for row in evidence.values():
        _require(row, ("statement_type", "status", "source_ref", "owner_role",
                       "captured_on"), f"evidence {row['evidence_id']}")
        _parse_date(row["captured_on"], f"evidence {row['evidence_id']}.captured_on")
        if row["statement_type"] not in {"customer_fact", "fde_inference", "hypothesis"}:
            raise DiscoveryExecutionError("statement_type 必须区分 fact/inference/hypothesis")
        if "used_by" not in row or not isinstance(row["used_by"], list):
            raise DiscoveryExecutionError("evidence.used_by 必须是 list")
        if row["statement_type"] == "customer_fact":
            expected = "simulated_confirmed" if simulated else "customer_confirmed"
            if row["status"] != expected or not row.get("confirmation_ref"):
                raise DiscoveryExecutionError(
                    f"客户事实 {row['evidence_id']} 缺少独立确认")
        elif row["statement_type"] == "fde_inference" and row["status"] != "supported":
            raise DiscoveryExecutionError(f"FDE 推断 {row['evidence_id']} 尚无支持")
        elif row["statement_type"] == "hypothesis" and row["status"] not in {
                "open", "validated", "rejected"}:
            raise DiscoveryExecutionError(f"假设 {row['evidence_id']} 状态无效")
    return evidence


def _validate_baseline(baseline: dict, evidence: dict[str, dict], *, simulated: bool) -> None:
    _require(baseline, ("version", "frozen_before_solution_decision", "period",
                        "metrics", "approvals", "post_hoc_changes_allowed"), "baseline")
    if baseline["frozen_before_solution_decision"] is not True or \
            baseline["post_hoc_changes_allowed"] is not False:
        raise DiscoveryExecutionError("基线必须在方案决定前冻结且禁止事后修改口径")
    _parse_date(baseline["period"]["from"], "baseline.period.from")
    _parse_date(baseline["period"]["to"], "baseline.period.to")
    metrics = _index(baseline["metrics"], "metric_id", "baseline metric")
    if set(metrics) != REQUIRED_BASELINE_METRICS:
        missing = REQUIRED_BASELINE_METRICS - set(metrics)
        extra = set(metrics) - REQUIRED_BASELINE_METRICS
        raise DiscoveryExecutionError(
            f"基线指标不完整；缺少 {sorted(missing)}；多出 {sorted(extra)}")
    for row in metrics.values():
        _require(row, ("denominator_policy", "measurement_ref", "source_evidence_id",
                       "value_mode"), f"baseline metric {row['metric_id']}")
        source = evidence.get(row["source_evidence_id"])
        if not source or source["statement_type"] != "customer_fact":
            raise DiscoveryExecutionError(
                f"基线指标 {row['metric_id']} 必须引用已确认客户事实")
        expected_mode = "synthetic_training_value" if simulated else "external_value_reference"
        if row["value_mode"] != expected_mode:
            raise DiscoveryExecutionError(f"基线指标 {row['metric_id']} value_mode 无效")
        if not simulated and "value" in row:
            raise DiscoveryExecutionError("外部 manifest 不应复制客户基线数值，只保存 measurement_ref")
    approvals = _index(baseline["approvals"], "role", "baseline approval")
    if set(approvals) != REQUIRED_BASELINE_APPROVAL_ROLES:
        raise DiscoveryExecutionError("基线签核角色不完整")
    expected = "simulated_approved" if simulated else "approved"
    if any(row.get("status") != expected or not row.get("approved_at") or
           not row.get("evidence_ref") for row in approvals.values()):
        raise DiscoveryExecutionError("基线签核状态或证据不完整")


def _validate_dependencies(rows: list[dict]) -> dict[str, dict]:
    dependencies = _index(rows, "dependency_id", "dependency")
    for row in dependencies.values():
        _require(row, ("owner_role", "due_date", "status", "evidence_ref"),
                 f"dependency {row['dependency_id']}")
        _parse_date(row["due_date"], f"dependency {row['dependency_id']}.due_date")
        if row["status"] != "closed":
            raise DiscoveryExecutionError(
                f"Discovery 交付前仍有未关闭依赖：{row['dependency_id']}")
    return dependencies


def _validate_changes(rows: list[dict]) -> dict[str, dict]:
    changes = _index(rows, "change_id", "change request")
    for row in changes.values():
        _require(row, ("requested_scope", "decision", "decision_owner_role",
                       "schedule_impact", "fee_impact"), f"change {row['change_id']}")
        if row["decision"] not in {"approved", "rejected", "deferred"}:
            raise DiscoveryExecutionError(f"change {row['change_id']} 决定无效")
        if row["decision"] == "approved" and not row.get("approval_ref"):
            raise DiscoveryExecutionError(f"已批准变更 {row['change_id']} 缺少证据")
    return changes


def _validate_time(rows: list[dict], *, simulated: bool) -> tuple[Decimal, Decimal]:
    entries = _index(rows, "entry_id", "time entry")
    total_hours, total_cost = Decimal("0"), Decimal("0")
    for row in entries.values():
        _require(row, ("role", "work_date", "hours", "loaded_rate_cny", "workstream",
                       "evidence_ref"), f"time entry {row['entry_id']}")
        _parse_date(row["work_date"], f"time entry {row['entry_id']}.work_date")
        hours = _money(row["hours"], "time hours")
        rate = _money(row["loaded_rate_cny"], "loaded rate")
        if hours == 0:
            raise DiscoveryExecutionError("time entry hours 必须大于 0")
        if not simulated and row.get("person_name"):
            raise DiscoveryExecutionError("外部 manifest 不应包含人员姓名")
        total_hours += hours
        total_cost += hours * rate
    return total_hours, total_cost


def _validate_deliverables(rows: list[dict], evidence: dict[str, dict],
                           *, simulated: bool) -> dict[str, dict]:
    deliverables = _index(rows, "deliverable_id", "deliverable")
    if set(deliverables) != REQUIRED_DELIVERABLES:
        raise DiscoveryExecutionError("六项 Discovery 交付物不完整")
    expected = "simulated_ready_for_acceptance" if simulated else "ready_for_acceptance"
    for row in deliverables.values():
        _require(row, ("title", "owner_role", "status", "evidence_ids",
                       "artifact_ref", "acceptance_criteria_ref"),
                 f"deliverable {row['deliverable_id']}")
        if row["status"] != expected or not row["evidence_ids"]:
            raise DiscoveryExecutionError(
                f"交付物 {row['deliverable_id']} 尚未准备验收")
        unknown = set(row["evidence_ids"]) - set(evidence)
        if unknown:
            raise DiscoveryExecutionError(
                f"交付物 {row['deliverable_id']} 引用未知证据：{sorted(unknown)}")
        unsafe = [item for item in row["evidence_ids"]
                  if evidence[item]["statement_type"] == "hypothesis" and
                  evidence[item]["status"] == "open"]
        if unsafe:
            raise DiscoveryExecutionError(
                f"交付物 {row['deliverable_id']} 将开放假设写成结论")
    return deliverables


def _common_validate(record: dict, *, simulated: bool) -> dict:
    _require(record, ("mode", "engagement", "fieldwork_sessions", "evidence_register",
                       "baseline", "dependencies", "change_requests", "time_ledger",
                       "deliverables", "fieldwork_role_confirmations"), "execution record")
    engagement = record["engagement"]
    _require(engagement, ("engagement_id", "stage18_release_ref", "scope_ref",
                          "start_date", "target_end_date"), "engagement")
    _parse_date(engagement["start_date"], "engagement.start_date")
    _parse_date(engagement["target_end_date"], "engagement.target_end_date")
    roles = _index(record["fieldwork_role_confirmations"], "role", "fieldwork role")
    if not REQUIRED_FIELDWORK_ROLES.issubset(set(roles)):
        raise DiscoveryExecutionError("现场工作缺少客户或 FDE 责任角色")
    expected_role_status = "simulated_confirmed" if simulated else "confirmed"
    if any(row.get("status") != expected_role_status or not row.get("evidence_ref")
           for row in roles.values() if row["role"] in REQUIRED_FIELDWORK_ROLES):
        raise DiscoveryExecutionError("现场角色确认不完整")
    sessions = _validate_sessions(record["fieldwork_sessions"], simulated=simulated)
    evidence = _validate_evidence(record["evidence_register"], simulated=simulated)
    _validate_baseline(record["baseline"], evidence, simulated=simulated)
    dependencies = _validate_dependencies(record["dependencies"])
    changes = _validate_changes(record["change_requests"])
    hours, cost = _validate_time(record["time_ledger"], simulated=simulated)
    deliverables = _validate_deliverables(record["deliverables"], evidence,
                                          simulated=simulated)
    return {"sessions": sessions, "evidence": evidence,
            "dependencies": dependencies, "changes": changes,
            "hours": hours, "cost": cost, "deliverables": deliverables}


def analyze_rehearsal(record: dict) -> dict:
    if record.get("mode") != "synthetic_live_discovery_rehearsal":
        raise DiscoveryExecutionError("公开参考数据只接受 synthetic_live_discovery_rehearsal")
    assertions = record.get("real_world_assertions", {})
    expected = {
        "real_customer_sessions": 0,
        "real_customer_data_records": 0,
        "real_customer_approvals": 0,
        "real_contracts_executed": 0,
        "real_invoices_created": 0,
        "actual_cash_received_cny": 0,
    }
    if any(assertions.get(key) != value for key, value in expected.items()):
        raise DiscoveryExecutionError("合成演练不得声明真实客户、合同、数据、批准或回款")
    facts = _common_validate(record, simulated=True)
    facts_count = sum(row["statement_type"] == "customer_fact"
                      for row in facts["evidence"].values())
    inference_count = sum(row["statement_type"] == "fde_inference"
                          for row in facts["evidence"].values())
    open_hypotheses = sum(row["statement_type"] == "hypothesis" and row["status"] == "open"
                          for row in facts["evidence"].values())
    return {
        "status": "SYNTHETIC_DISCOVERY_READY_FOR_ACCEPTANCE_REHEARSAL",
        "engagement_id": record["engagement"]["engagement_id"],
        "session_count": len(facts["sessions"]),
        "required_session_type_count": len(REQUIRED_SESSION_TYPES),
        "confirmed_fact_count": facts_count,
        "supported_inference_count": inference_count,
        "open_hypothesis_count": open_hypotheses,
        "baseline_metric_count": len(REQUIRED_BASELINE_METRICS),
        "closed_dependency_count": len(facts["dependencies"]),
        "change_request_count": len(facts["changes"]),
        "ready_deliverable_count": len(facts["deliverables"]),
        "logged_hours": f"{facts['hours']:.2f}",
        "delivery_cost_cny": f"{facts['cost']:.2f}",
        "real_customer_sessions": 0,
        "real_customer_data_records": 0,
        "real_customer_approvals": 0,
        "actual_cash_received_cny": "0.00",
        "next_gate": "CUSTOMER_DISCOVERY_ACCEPTANCE_AND_PILOT_DECISION",
        "decision": "RUN_WITH_NAMED_DESIGN_PARTNER_USING_EXTERNAL_RECORD",
    }


def preflight_external_execution(manifest_path: Path | str, repo_root: Path | str) -> dict:
    path, root = Path(manifest_path).expanduser().resolve(), Path(repo_root).resolve()
    if _inside(path, root):
        raise DiscoveryExecutionError("真实 Discovery 执行清单必须存放在 Git 仓库之外")
    record = load_json(path)
    if record.get("mode") != "external_live_paid_discovery_record":
        raise DiscoveryExecutionError("外部执行清单 mode 无效")
    placeholders = _placeholder_paths(record)
    if placeholders:
        raise DiscoveryExecutionError(
            f"外部执行清单仍有模板占位符：{', '.join(placeholders[:5])}")
    release = record.get("stage18_contract_release", {})
    _require(release, ("preflight_status", "contract_record_ref",
                       "human_legal_validity_verified", "verified_by_role",
                       "verified_at"), "Stage 18 contract release")
    if release["preflight_status"] != "READY_FOR_PAID_DISCOVERY_KICKOFF" or \
            release["human_legal_validity_verified"] is not True or \
            release["verified_by_role"] not in {
                "fde_legal_owner", "fde_authorized_signatory"}:
        raise DiscoveryExecutionError("Stage 18 合同释放尚未完成人工真实性复核")
    _parse_date(release["verified_at"], "Stage 18 contract release.verified_at")
    privacy = record.get("privacy_assertions", {})
    required_privacy = {
        "contains_raw_personal_data": False,
        "contains_credentials": False,
        "contains_contract_body_or_signature": False,
        "copied_into_source_repository": False,
    }
    if any(privacy.get(key) is not value for key, value in required_privacy.items()):
        raise DiscoveryExecutionError("外部 manifest 违反最小化或仓库隔离要求")
    facts = _common_validate(record, simulated=False)
    public_label = record.get("partner_public_label")
    if not public_label:
        raise DiscoveryExecutionError("外部执行清单缺少 partner_public_label")
    return {
        "status": "READY_FOR_HUMAN_DISCOVERY_ACCEPTANCE_REVIEW",
        "partner_public_label": public_label,
        "engagement_id": record["engagement"]["engagement_id"],
        "contract_reference_sha256": _sha256(release["contract_record_ref"]),
        "session_count": len(facts["sessions"]),
        "confirmed_fact_count": sum(row["statement_type"] == "customer_fact"
                                      for row in facts["evidence"].values()),
        "baseline_metric_count": len(REQUIRED_BASELINE_METRICS),
        "closed_dependency_count": len(facts["dependencies"]),
        "ready_deliverable_count": len(facts["deliverables"]),
        "logged_hours": f"{facts['hours']:.2f}",
        "delivery_cost_cny": f"{facts['cost']:.2f}",
        "customer_acceptance_recorded": False,
        "pilot_authorized": False,
        "legally_verified_by_code": False,
        "next_action": "CUSTOMER_REVIEWS_SIX_DELIVERABLES_AND_STEERING_DECIDES",
    }


def render(report: dict) -> str:
    return f"""# Stage 19 Live Paid Discovery Execution

状态：`{report['status']}`。

- 现场活动：{report['session_count']}；基线指标：{report['baseline_metric_count']}。
- 已确认事实：{report['confirmed_fact_count']}；六项交付物：{report['ready_deliverable_count']}/6。
- 登记工时：{report['logged_hours']}；交付成本：CNY {report['delivery_cost_cny']}。
- 下一 Gate：`{report.get('next_gate', report.get('next_action'))}`。

当前报告只表示 Discovery 资料已准备进入人工验收。它不表示客户已经接受、不授权 Pilot，也不授权生产访问、自动外发或客户系统写入。
"""


def write_outputs(output: Path | str, report: dict, record: dict | None = None) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "stage19-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "stage19-report.md").write_text(render(report), encoding="utf-8")
    if record:
        with (output / "delivery-cost-ledger.csv").open(
                "w", newline="", encoding="utf-8-sig") as handle:
            fields = ("entry_id", "role", "work_date", "hours", "loaded_rate_cny",
                      "workstream", "evidence_ref")
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in record["time_ledger"]:
                writer.writerow({key: row.get(key, "") for key in fields})


def prepare_external_pack(output: Path | str, template: dict) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "external-discovery-execution.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sheets = {
        "fieldwork-schedule.csv": ("session_type", "owner_role", "target_date", "status", "evidence_ref"),
        "evidence-register.csv": ("evidence_id", "statement_type", "source_ref", "status", "confirmation_ref", "used_by"),
        "dependency-register.csv": ("dependency_id", "owner_role", "due_date", "status", "evidence_ref"),
        "time-ledger.csv": ("entry_id", "role", "work_date", "hours", "loaded_rate_cny", "workstream", "evidence_ref"),
    }
    for name, fields in sheets.items():
        with (output / name).open("w", newline="", encoding="utf-8-sig") as handle:
            csv.writer(handle).writerow(fields)
