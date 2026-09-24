"""Evidence-bound Pilot acceptance and production investment gates."""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path


class PilotAcceptanceError(ValueError):
    """Stage 22 evidence or decision records violate the delivery contract."""


CRITERIA = {
    "field_quality", "evidence_coverage", "unsafe_action_rate",
    "operator_adoption", "review_cycle_time", "cost_per_case",
}
READINESS = {
    "security_threat_model", "privacy_and_retention", "data_governance",
    "identity_and_access", "reliability_slo", "capacity_and_performance",
    "support_and_oncall", "deployment_and_rollback", "observability",
    "commercial_and_legal",
}
ACCEPTANCE_ROLES = {
    "customer_sponsor", "customer_process_owner", "fde_delivery_owner",
}
DECISION_ROLES = {
    "customer_sponsor", "customer_process_owner", "customer_security_owner",
    "fde_delivery_owner", "fde_commercial_owner",
}
DECISIONS = {"stop", "iterate", "extend_shadow", "production_evaluation"}


def load_json(path: Path | str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PilotAcceptanceError(f"无法读取 Stage 22 资料：{exc}") from exc
    if not isinstance(value, dict):
        raise PilotAcceptanceError("Stage 22 资料必须是 JSON object")
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
        raise PilotAcceptanceError(f"{where} 缺少字段：{', '.join(missing)}")


def _index(rows: list[dict], key: str, where: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        raise PilotAcceptanceError(f"{where} 必须是 list")
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get(key):
            raise PilotAcceptanceError(f"{where} 缺少 {key}")
        if row[key] in result:
            raise PilotAcceptanceError(f"{where} {key} 重复：{row[key]}")
        result[row[key]] = row
    return result


def _number(value: object, where: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise PilotAcceptanceError(f"{where} 必须是数字") from exc
    if not result.is_finite() or result < 0:
        raise PilotAcceptanceError(f"{where} 必须是非负有限数字")
    return result


def _date(value: str, where: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise PilotAcceptanceError(f"{where} 日期无效") from exc


def _datetime(value: str, where: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise PilotAcceptanceError(f"{where} 时间无效") from exc
    if result.tzinfo is None:
        raise PilotAcceptanceError(f"{where} 必须包含时区")
    return result


def _inside(path: Path, parent: Path) -> bool:
    path, parent = path.resolve(), parent.resolve()
    return path == parent or parent in path.parents


def _placeholders(value: object, prefix: str = "") -> list[str]:
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            found.extend(_placeholders(child, f"{prefix}.{key}" if prefix else key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_placeholders(child, f"{prefix}[{index}]"))
    elif isinstance(value, str) and value.strip().upper().startswith(("REPLACE", "PENDING")):
        found.append(prefix)
    return found


def _validate_summary(value: dict) -> None:
    _require(value, ("pilot_id", "evidence_bundle_id", "evidence_bundle_sha256",
                     "case_count", "user_count", "external_sent_count",
                     "customer_write_count", "unsafe_action_count"), "pilot summary")
    if int(value["case_count"]) <= 0 or int(value["user_count"]) <= 0:
        raise PilotAcceptanceError("Pilot 验收缺少实际案例或用户分母")
    if any(int(value[key]) != 0 for key in (
            "external_sent_count", "customer_write_count", "unsafe_action_count")):
        raise PilotAcceptanceError("Pilot 安全边界被突破，不能最终验收")


def _validate_criteria(rows: list[dict], accepted_status: str) -> tuple[dict[str, dict], int]:
    criteria = _index(rows, "criterion_id", "acceptance criterion")
    if set(criteria) != CRITERIA:
        raise PilotAcceptanceError("Pilot 六项验收指标不完整")
    accepted_count = 0
    rejected_status = accepted_status.replace("accepted", "rejected")
    for criterion_id, row in criteria.items():
        _require(row, ("direction", "target", "actual", "denominator_policy",
                       "source_ref", "decision"), f"criterion {criterion_id}")
        target, actual = _number(row["target"], "criterion target"), _number(
            row["actual"], "criterion actual")
        if row["direction"] not in {"min", "max"}:
            raise PilotAcceptanceError(f"验收指标方向无效：{criterion_id}")
        passed = actual >= target if row["direction"] == "min" else actual <= target
        if row["decision"] not in {accepted_status, rejected_status}:
            raise PilotAcceptanceError(f"Pilot 验收决定无效：{criterion_id}")
        if not passed and row["decision"] == accepted_status:
            raise PilotAcceptanceError(f"不得接受未达标的 Pilot 验收指标：{criterion_id}")
        if passed and row["decision"] == accepted_status:
            accepted_count += 1
    return criteria, accepted_count


def _validate_conditions(rows: list[dict], closed_status: str,
                         require_condition: bool) -> tuple[dict[str, dict], int]:
    conditions = _index(rows, "condition_id", "acceptance condition")
    if require_condition and not conditions:
        raise PilotAcceptanceError("参考验收必须展示至少一个条件整改")
    closed_count = 0
    for condition_id, row in conditions.items():
        _require(row, ("description", "owner_role", "due_date", "status"),
                 f"condition {condition_id}")
        due = _date(row["due_date"], "condition.due_date")
        if row["status"] == closed_status:
            _require(row, ("closure_evidence_ref", "closed_at"),
                     f"condition {condition_id}")
            if _date(row["closed_at"], "condition.closed_at") > due:
                raise PilotAcceptanceError(f"Pilot 验收条件未按期关闭：{condition_id}")
            closed_count += 1
        elif row["status"] != "open":
            raise PilotAcceptanceError(f"Pilot 验收条件状态无效：{condition_id}")
    return conditions, closed_count


def _validate_risks(rows: list[dict]) -> dict[str, dict]:
    risks = _index(rows, "risk_id", "residual risk")
    if not risks:
        raise PilotAcceptanceError("生产决策缺少残余风险登记")
    for risk_id, row in risks.items():
        _require(row, ("severity", "status", "owner_role", "mitigation",
                       "due_date", "evidence_ref"), f"risk {risk_id}")
        _date(row["due_date"], "risk.due_date")
        if row["severity"] not in {"low", "medium", "high", "critical"}:
            raise PilotAcceptanceError(f"风险级别无效：{risk_id}")
        if row["status"] not in {"open", "mitigated", "accepted"}:
            raise PilotAcceptanceError(f"风险状态无效：{risk_id}")
        if row["severity"] == "critical" and row["status"] != "mitigated":
            raise PilotAcceptanceError(f"开放 Critical 风险阻断决策：{risk_id}")
    return risks


def _validate_approvals(value: dict, scope: object, roles: set[str],
                        expected_status: str, where: str) -> str:
    _require(value, ("record_id", "content_sha256", "approvals"), where)
    sha = digest(scope)
    if value["content_sha256"] != sha:
        raise PilotAcceptanceError(f"{where} 未绑定当前内容")
    approvals = _index(value["approvals"], "role", f"{where} approval")
    if set(approvals) != roles:
        raise PilotAcceptanceError(f"{where} 签核角色不完整")
    for row in approvals.values():
        if row.get("status") != expected_status or row.get("content_sha256") != sha or \
                not row.get("approved_at") or not row.get("evidence_ref"):
            raise PilotAcceptanceError(f"{where} 签核未绑定当前内容")
        _date(row["approved_at"], f"{where}.approved_at")
    return sha


def _validate_readiness(rows: list[dict], ready_status: str) -> tuple[dict[str, dict], int]:
    controls = _index(rows, "control_id", "production readiness control")
    if set(controls) != READINESS:
        raise PilotAcceptanceError("生产准备十项控制不完整")
    ready = 0
    for control_id, row in controls.items():
        _require(row, ("status", "owner_role", "evidence_ref", "exit_criterion"),
                 f"readiness {control_id}")
        if row["status"] == ready_status:
            ready += 1
        elif row["status"] != "open":
            raise PilotAcceptanceError(f"生产准备状态无效：{control_id}")
    return controls, ready


def _validate_launch(value: dict) -> None:
    _require(value, ("strategy", "cohorts", "rollback_triggers", "rollback_rto_minutes",
                     "automatic_external_send", "customer_system_write",
                     "change_window_ref", "rollback_owner_role"), "launch plan")
    if value["strategy"] != "human_approved_canary" or not value["cohorts"] or \
            not value["rollback_triggers"]:
        raise PilotAcceptanceError("生产计划缺少人工 Canary 或回退触发器")
    if _number(value["rollback_rto_minutes"], "rollback RTO") > 30:
        raise PilotAcceptanceError("回退 RTO 超过 30 分钟")
    if value["automatic_external_send"] is not False or \
            value["customer_system_write"] is not False:
        raise PilotAcceptanceError("生产授权前不得开启自动发送或客户系统写入")


def _validate_common(record: dict, simulated: bool) -> dict:
    _require(record, ("pilot_summary", "acceptance_criteria",
                      "residual_risks", "acceptance_record", "production_decision",
                      "production_readiness", "launch_plan"), "Stage 22 record")
    if "acceptance_conditions" not in record:
        raise PilotAcceptanceError("Stage 22 record 缺少字段：acceptance_conditions")
    _validate_summary(record["pilot_summary"])
    prefix = "simulated_" if simulated else ""
    criteria, accepted_count = _validate_criteria(
        record["acceptance_criteria"], prefix + "accepted")
    conditions, closed_count = _validate_conditions(
        record["acceptance_conditions"], prefix + "closed", simulated)
    risks = _validate_risks(record["residual_risks"])
    acceptance_scope = {
        "pilot_summary": record["pilot_summary"],
        "acceptance_criteria": record["acceptance_criteria"],
        "acceptance_conditions": record["acceptance_conditions"],
        "residual_risks": record["residual_risks"],
    }
    acceptance_sha = _validate_approvals(
        record["acceptance_record"], acceptance_scope, ACCEPTANCE_ROLES,
        prefix + "approved", "Pilot acceptance record")
    decision = record["production_decision"]
    _require(decision, ("decision", "decided_at", "rationale", "dissent",
                        "decision_record"), "production decision")
    if decision["decision"] not in DECISIONS:
        raise PilotAcceptanceError("生产决策值无效")
    if decision["decision"] == "production_evaluation" and \
            (accepted_count != len(CRITERIA) or closed_count != len(conditions)):
        raise PilotAcceptanceError("Production Evaluation 要求六项指标接受且验收条件全部关闭")
    _datetime(decision["decided_at"], "production decision.decided_at")
    decision_scope = {
        "acceptance_sha256": acceptance_sha,
        "decision": decision["decision"], "rationale": decision["rationale"],
        "dissent": decision["dissent"],
        "production_readiness": record["production_readiness"],
        "launch_plan": record["launch_plan"],
    }
    decision_sha = _validate_approvals(
        decision["decision_record"], decision_scope, DECISION_ROLES,
        prefix + "approved", "Production decision record")
    controls, ready = _validate_readiness(record["production_readiness"],
                                          prefix + "ready")
    _validate_launch(record["launch_plan"])
    if record.get("production_authorization", {}).get("authorized") is not False:
        raise PilotAcceptanceError("Stage 22 不得把投资决定写成生产授权")
    return {"criteria": criteria, "accepted_count": accepted_count,
            "conditions": conditions, "closed_count": closed_count, "risks": risks,
            "acceptance_sha": acceptance_sha, "decision_sha": decision_sha,
            "decision": decision["decision"], "controls": controls,
            "ready": ready, "summary": record["pilot_summary"]}


def _report(facts: dict, *, external: bool) -> dict:
    decision = facts["decision"]
    blocking_risks = sum(
        row["status"] == "open" and row["severity"] in {"high", "critical"}
        for row in facts["risks"].values())
    if decision == "stop":
        status = "PILOT_STOP_DECISION_RECORDED"
    elif decision == "iterate":
        status = "PILOT_ITERATION_REQUIRED"
    elif decision == "extend_shadow":
        status = "SHADOW_EXTENSION_REQUIRES_NEW_AUTHORIZATION"
    elif facts["ready"] == len(READINESS) and not blocking_risks and external:
        status = "READY_FOR_HUMAN_PRODUCTION_AUTHORIZATION_REVIEW"
    elif external:
        status = "PRODUCTION_EVALUATION_OPEN"
    else:
        status = "SYNTHETIC_PILOT_ACCEPTED_PRODUCTION_EVALUATION_OPEN"
    return {
        "status": status,
        "pilot_id": facts["summary"]["pilot_id"],
        "accepted_criteria_count": facts["accepted_count"],
        "closed_condition_count": facts["closed_count"],
        "residual_risk_count": len(facts["risks"]),
        "open_risk_count": sum(r["status"] == "open" for r in facts["risks"].values()),
        "blocking_risk_count": blocking_risks,
        "production_decision": decision,
        "production_readiness_ready_count": facts["ready"],
        "production_readiness_count": len(READINESS),
        "external_record_asserts_real_pilot": external,
        "real_pilot_verified_by_code": False,
        "pilot_acceptance_verified_by_code": False,
        "production_authorized": False,
        "automatic_external_send_authorized": False,
        "customer_system_write_authorized": False,
        "next_gate": "HUMAN_PRODUCTION_AUTHORIZATION_AND_CONTROLLED_GO_LIVE",
    }


def analyze_rehearsal(stage_root: Path, record: dict) -> dict:
    stage_root = Path(stage_root).resolve()
    if record.get("mode") != "counterfactual_pilot_acceptance_rehearsal" or \
            record.get("progression_mode") != "synthetic_stage21_evidence_branch":
        raise PilotAcceptanceError("公开 Stage 22 数据必须是反事实验收分支")
    source = (stage_root.parent / record.get("source_stage21_path", "")).resolve()
    if stage_root.parent not in source.parents or not source.is_file() or \
            record.get("source_stage21_sha256") != file_sha256(source):
        raise PilotAcceptanceError("Stage 21 来源路径或摘要不匹配")
    assertions = record.get("real_world_assertions", {})
    expected = {"real_pilot_accepted": False, "real_production_authorized": False,
                "real_customer_users": 0, "real_customer_actions": 0,
                "real_revenue_recognized_cny": 0}
    if any(assertions.get(key) != value for key, value in expected.items()):
        raise PilotAcceptanceError("反事实分支不得声明真实验收、生产或收入")
    return _report(_validate_common(record, True), external=False)


def preflight_external_decision(manifest_path: Path | str, repo_root: Path | str) -> dict:
    path, root = Path(manifest_path).expanduser().resolve(), Path(repo_root).resolve()
    if _inside(path, root):
        raise PilotAcceptanceError("真实 Pilot 验收清单必须存放在 Git 仓库之外")
    record = load_json(path)
    if record.get("mode") != "external_pilot_acceptance_record":
        raise PilotAcceptanceError("外部 Stage 22 mode 无效")
    placeholders = _placeholders(record)
    if placeholders:
        raise PilotAcceptanceError(f"外部 Stage 22 清单仍有占位符：{', '.join(placeholders[:5])}")
    release = record.get("stage21_release", {})
    _require(release, ("status", "evidence_bundle_ref", "human_verified",
                       "verified_by_role", "verified_at"), "Stage 21 release")
    if release["status"] != "READY_FOR_HUMAN_PILOT_ACCEPTANCE_REVIEW" or \
            release["human_verified"] is not True or \
            release["verified_by_role"] not in {"customer_process_owner", "fde_delivery_owner"}:
        raise PilotAcceptanceError("Stage 21 Evidence Bundle 尚未完成人工真实性复核")
    _datetime(release["verified_at"], "Stage 21 release.verified_at")
    privacy = record.get("privacy_assertions", {})
    expected = {"contains_raw_customer_content": False,
                "contains_person_names_or_emails": False,
                "contains_credentials": False,
                "copied_into_source_repository": False}
    if any(privacy.get(key) is not value for key, value in expected.items()):
        raise PilotAcceptanceError("外部 Stage 22 清单违反隐私或仓库隔离要求")
    report = _report(_validate_common(record, False), external=True)
    report["partner_public_label"] = record.get("partner_public_label")
    report["source_reference_sha256"] = hashlib.sha256(
        release["evidence_bundle_ref"].encode("utf-8")).hexdigest()
    return report


def render(report: dict) -> str:
    return f"""# Stage 22 Pilot Acceptance & Production Decision

状态：`{report['status']}`。

- Pilot：`{report['pilot_id']}`；验收指标：{report['accepted_criteria_count']}/6。
- 已关闭条件：{report['closed_condition_count']}；残余风险：{report['residual_risk_count']}，其中开放 {report['open_risk_count']}、阻断 {report['blocking_risk_count']}。
- 决策：`{report['production_decision']}`。
- 生产准备：{report['production_readiness_ready_count']}/{report['production_readiness_count']}。
- 生产授权：{report['production_authorized']}；自动外发授权：{report['automatic_external_send_authorized']}；客户写入授权：{report['customer_system_write_authorized']}。
- 下一 Gate：`{report['next_gate']}`。

Pilot 验收、生产投资和生产授权是三个独立决定。代码预检不能验证客户签字真实性，也不能授权上线。
"""


def write_outputs(output: Path | str, report: dict, record: dict | None = None) -> None:
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    (output / "stage22-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "stage22-report.md").write_text(render(report), encoding="utf-8")
    if record:
        with (output / "production-readiness.csv").open(
                "w", newline="", encoding="utf-8-sig") as handle:
            fields = ("control_id", "status", "owner_role", "evidence_ref", "exit_criterion")
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
            for row in record["production_readiness"]:
                writer.writerow({key: row.get(key, "") for key in fields})


def prepare_external_pack(output: Path | str, template: dict) -> None:
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    (output / "external-pilot-acceptance.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sheets = {
        "acceptance-criteria.csv": ("criterion_id", "target", "actual", "decision", "source_ref"),
        "residual-risk-register.csv": ("risk_id", "severity", "status", "owner_role", "due_date", "evidence_ref"),
        "production-readiness.csv": ("control_id", "status", "owner_role", "evidence_ref", "exit_criterion"),
    }
    for name, fields in sheets.items():
        with (output / name).open("w", newline="", encoding="utf-8-sig") as handle:
            csv.writer(handle).writerow(fields)
