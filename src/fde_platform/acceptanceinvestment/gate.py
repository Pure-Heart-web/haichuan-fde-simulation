"""Controls for Discovery acceptance and a separate Pilot investment gate."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


class AcceptanceInvestmentError(ValueError):
    """Acceptance or investment evidence is incomplete or inconsistent."""


DELIVERABLE_IDS = {
    "D1_PROBLEM_SCOPE_RACI",
    "D2_BASELINE_SUCCESS_PLAN",
    "D3_DATA_SECURITY_IP_BOUNDARY",
    "D4_SOLUTION_INTEGRATION_PLAN",
    "D5_BUSINESS_CASE",
    "D6_PILOT_RECOMMENDATION",
}

ACCEPTANCE_ROLES = {
    "customer_acceptance_owner",
    "customer_sponsor",
    "fde_delivery_owner",
}

STEERING_ROLES = {
    "customer_sponsor",
    "customer_process_owner",
    "fde_commercial_owner",
    "fde_delivery_owner",
    "fde_security_owner",
}

SCENARIOS = {"conservative", "base", "upside"}

PILOT_SUCCESS_METRICS = {
    "field_quality",
    "evidence_coverage",
    "unsafe_action_rate",
    "operator_adoption",
    "review_cycle_time",
    "cost_per_case",
}

MOBILIZATION_REQUIREMENTS = {
    "executed_pilot_sow",
    "purchase_order_or_equivalent",
    "data_security_authorization",
    "customer_sandbox",
    "enterprise_identity_and_roles",
    "readonly_connectors",
    "approved_model_and_rules",
    "operator_training_and_roster",
    "telemetry_and_incident_route",
    "rollback_and_stop_drill",
}

HEX64 = re.compile(r"^[0-9a-f]{64}$")


def load_json(path: Path | str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceInvestmentError(f"无法读取验收资料：{exc}") from exc
    if not isinstance(value, dict):
        raise AcceptanceInvestmentError("验收资料必须是 JSON object")
    return value


def digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _require(value: dict, keys: tuple[str, ...], where: str) -> None:
    missing = [key for key in keys if value.get(key) in (None, "", [])]
    if missing:
        raise AcceptanceInvestmentError(f"{where} 缺少字段：{', '.join(missing)}")


def _index(rows: list[dict], key: str, where: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        raise AcceptanceInvestmentError(f"{where} 必须是 list")
    result: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise AcceptanceInvestmentError(f"{where} 必须是 object list")
        _require(row, (key,), where)
        if row[key] in result:
            raise AcceptanceInvestmentError(f"{where} {key} 重复：{row[key]}")
        result[row[key]] = row
    return result


def _money(value: object, where: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AcceptanceInvestmentError(f"{where} 必须是数字") from exc
    if not result.is_finite() or result < 0:
        raise AcceptanceInvestmentError(f"{where} 必须是非负有限数字")
    return result


def _parse_date(value: str, where: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise AcceptanceInvestmentError(f"{where} 日期必须为 YYYY-MM-DD") from exc


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


def _validate_conditions(rows: list[dict], *, simulated: bool) -> dict[str, dict]:
    conditions = _index(rows, "condition_id", "acceptance condition")
    expected = "simulated_closed" if simulated else "closed"
    for row in conditions.values():
        _require(row, ("deliverable_id", "description", "owner_role", "due_date",
                       "status", "closure_evidence_ref", "closed_at"),
                 f"condition {row['condition_id']}")
        if row["deliverable_id"] not in DELIVERABLE_IDS:
            raise AcceptanceInvestmentError("验收条件引用未知交付物")
        _parse_date(row["due_date"], f"condition {row['condition_id']}.due_date")
        _parse_date(row["closed_at"], f"condition {row['condition_id']}.closed_at")
        if row["status"] != expected:
            raise AcceptanceInvestmentError(f"验收条件尚未关闭：{row['condition_id']}")
    return conditions


def _validate_acceptance(acceptance: dict, source_deliverables: dict[str, dict] | None,
                         *, simulated: bool) -> dict:
    _require(acceptance, ("acceptance_id", "bundle_version", "submitted_at",
                          "deliverable_decisions", "conditions", "decision_history",
                          "approvals", "bundle_sha256"), "acceptance")
    _parse_date(acceptance["submitted_at"], "acceptance.submitted_at")
    decisions = _index(acceptance["deliverable_decisions"], "deliverable_id",
                       "deliverable decision")
    if set(decisions) != DELIVERABLE_IDS:
        raise AcceptanceInvestmentError("验收决定未覆盖六项交付物")
    expected = "simulated_accepted" if simulated else "accepted"
    for deliverable_id, row in decisions.items():
        _require(row, ("status", "artifact_ref", "artifact_sha256",
                       "criteria_ref", "decision_evidence_ref"),
                 f"decision {deliverable_id}")
        if row["status"] != expected:
            raise AcceptanceInvestmentError(f"交付物尚未最终接受：{deliverable_id}")
        if not HEX64.fullmatch(row["artifact_sha256"]):
            raise AcceptanceInvestmentError(f"交付物摘要无效：{deliverable_id}")
        if source_deliverables is not None and row["artifact_sha256"] != digest(
                source_deliverables[deliverable_id]):
            raise AcceptanceInvestmentError(f"交付物内容已变化：{deliverable_id}")
    conditions = _validate_conditions(acceptance["conditions"], simulated=simulated)
    history = acceptance["decision_history"]
    required_states = {"conditionally_accepted", "remediation_completed", "final_accepted"}
    if not isinstance(history, list) or not required_states.issubset(
            {row.get("event") for row in history}):
        raise AcceptanceInvestmentError("验收历史缺少条件、整改或最终接受事件")
    for row in history:
        _require(row, ("event", "recorded_at", "actor_role", "evidence_ref"),
                 "acceptance history")
        _parse_date(row["recorded_at"], "acceptance history.recorded_at")

    controlled = {key: value for key, value in acceptance.items()
                  if key not in {"approvals", "bundle_sha256"}}
    bundle_sha = digest(controlled)
    if acceptance["bundle_sha256"] != bundle_sha:
        raise AcceptanceInvestmentError("验收包摘要不匹配")
    approvals = _index(acceptance["approvals"], "role", "acceptance approval")
    if set(approvals) != ACCEPTANCE_ROLES:
        raise AcceptanceInvestmentError("验收签核角色不完整")
    approval_status = "simulated_approved" if simulated else "approved"
    if any(row.get("status") != approval_status or not row.get("approved_at") or
           row.get("content_sha256") != bundle_sha or not row.get("evidence_ref")
           for row in approvals.values()):
        raise AcceptanceInvestmentError("验收签核状态或内容绑定不完整")
    return {"decisions": decisions, "conditions": conditions,
            "bundle_sha256": bundle_sha}


def _validate_business_case(value: dict, *, expected_discovery_cost: Decimal | None) -> dict:
    _require(value, ("currency", "discovery_actual_cost", "scenarios",
                     "measurement_version"), "business case")
    if value["currency"] != "CNY":
        raise AcceptanceInvestmentError("Business Case 币种必须为 CNY")
    discovery_cost = _money(value["discovery_actual_cost"], "Discovery actual cost")
    if expected_discovery_cost is not None and discovery_cost != expected_discovery_cost:
        raise AcceptanceInvestmentError("Business Case 的 Discovery 实际成本与 Stage 19 不一致")
    scenarios = _index(value["scenarios"], "scenario", "business scenario")
    if set(scenarios) != SCENARIOS:
        raise AcceptanceInvestmentError("Business Case 必须包含 conservative/base/upside")
    results = {}
    for name, row in scenarios.items():
        _require(row, ("annual_benefit_cny", "pilot_cost_cny", "confidence"),
                 f"scenario {name}")
        if not isinstance(row.get("fact_refs"), list) or not row["fact_refs"] or \
                not isinstance(row.get("assumption_refs"), list) or \
                not row["assumption_refs"]:
            raise AcceptanceInvestmentError(f"scenario {name} 必须区分事实与假设")
        benefit = _money(row["annual_benefit_cny"], f"scenario {name} benefit")
        cost = _money(row["pilot_cost_cny"], f"scenario {name} cost")
        results[name] = {"benefit": benefit, "cost": cost, "net": benefit - cost}
    if not (results["conservative"]["benefit"] <= results["base"]["benefit"] <=
            results["upside"]["benefit"]):
        raise AcceptanceInvestmentError("Business Case 情景收益顺序无效")
    return {"discovery_cost": discovery_cost, "scenarios": results}


def _validate_steering(value: dict, acceptance_sha: str, *, simulated: bool) -> dict:
    _require(value, ("decision_id", "decision", "decided_at", "acceptance_bundle_sha256",
                     "rationale_evidence_refs", "dissent", "approvals",
                     "decision_sha256"), "steering decision")
    _parse_date(value["decided_at"], "steering.decided_at")
    expected_decisions = {"simulated_stop", "simulated_iterate", "simulated_pilot"} \
        if simulated else {"STOP", "ITERATE", "PILOT"}
    if value["decision"] not in expected_decisions:
        raise AcceptanceInvestmentError("Steering 决定无效")
    if value["acceptance_bundle_sha256"] != acceptance_sha:
        raise AcceptanceInvestmentError("Steering 未绑定当前验收包")
    if not isinstance(value["dissent"], list):
        raise AcceptanceInvestmentError("Steering dissent 必须是 list")
    for row in value["dissent"]:
        _require(row, ("role", "position", "resolution", "evidence_ref"), "dissent")
    controlled = {key: item for key, item in value.items()
                  if key not in {"approvals", "decision_sha256"}}
    decision_sha = digest(controlled)
    if value["decision_sha256"] != decision_sha:
        raise AcceptanceInvestmentError("Steering 决定摘要不匹配")
    approvals = _index(value["approvals"], "role", "steering approval")
    if set(approvals) != STEERING_ROLES:
        raise AcceptanceInvestmentError("Steering 签核角色不完整")
    expected_status = "simulated_approved" if simulated else "approved"
    if any(row.get("status") != expected_status or not row.get("approved_at") or
           row.get("content_sha256") != decision_sha or not row.get("evidence_ref")
           for row in approvals.values()):
        raise AcceptanceInvestmentError("Steering 签核状态或内容绑定不完整")
    return {"decision": value["decision"], "decision_sha256": decision_sha}


def _validate_pilot_plan(value: dict, *, simulated: bool) -> dict:
    _require(value, ("pilot_plan_id", "sow_status", "currency", "fee_cny",
                     "duration_weeks", "user_cap", "case_cap", "payment_milestones",
                     "success_metrics", "mobilization_requirements"), "pilot plan")
    if value["currency"] != "CNY" or _money(value["fee_cny"], "pilot fee") == 0:
        raise AcceptanceInvestmentError("Pilot 费用必须为正数 CNY")
    milestones = _index(value["payment_milestones"], "milestone_id", "payment milestone")
    if sum(_money(row.get("percent"), "milestone percent")
           for row in milestones.values()) != Decimal("100"):
        raise AcceptanceInvestmentError("Pilot 付款里程碑比例合计必须为 100")
    metrics = _index(value["success_metrics"], "metric_id", "pilot success metric")
    if set(metrics) != PILOT_SUCCESS_METRICS:
        raise AcceptanceInvestmentError("Pilot 成功指标不完整")
    for row in metrics.values():
        _require(row, ("threshold", "denominator_policy", "baseline_ref", "stop_threshold"),
                 f"pilot metric {row['metric_id']}")
    requirements = _index(value["mobilization_requirements"], "requirement_id",
                          "mobilization requirement")
    if set(requirements) != MOBILIZATION_REQUIREMENTS:
        raise AcceptanceInvestmentError("Pilot Mobilization 要求不完整")
    ready_status = "simulated_ready" if simulated else "ready"
    ready = all(row.get("status") == ready_status and row.get("evidence_ref")
                for row in requirements.values())
    executed_status = "simulated_executed" if simulated else "executed"
    sow_executed = value["sow_status"] == executed_status
    return {"requirements": requirements, "mobilization_ready": ready,
            "sow_executed": sow_executed, "fee": _money(value["fee_cny"], "pilot fee")}


def analyze_rehearsal(stage_root: Path, record: dict) -> dict:
    stage_root = Path(stage_root).resolve()
    if record.get("mode") != "synthetic_acceptance_investment_rehearsal":
        raise AcceptanceInvestmentError("公开参考数据只接受 synthetic_acceptance_investment_rehearsal")
    source_path = (stage_root.parent / record.get("source_stage19_path", "")).resolve()
    if stage_root.parent not in source_path.parents or not source_path.is_file():
        raise AcceptanceInvestmentError("Stage 19 来源路径越界或不存在")
    if record.get("source_stage19_sha256") != file_sha256(source_path):
        raise AcceptanceInvestmentError("Stage 19 来源摘要不匹配")
    source = load_json(source_path)
    source_deliverables = _index(source["deliverables"], "deliverable_id",
                                 "source deliverable")
    acceptance = _validate_acceptance(record["acceptance"], source_deliverables,
                                      simulated=True)
    expected_cost = sum(_money(row["hours"], "hours") *
                        _money(row["loaded_rate_cny"], "rate")
                        for row in source["time_ledger"])
    business = _validate_business_case(record["business_case"],
                                       expected_discovery_cost=expected_cost)
    steering = _validate_steering(record["steering"], acceptance["bundle_sha256"],
                                  simulated=True)
    pilot = _validate_pilot_plan(record["pilot_plan"], simulated=True)
    billing = record.get("billing_release", {})
    if billing.get("simulated_invoice_eligible") is not True or \
            billing.get("actual_invoice_created") is not False or \
            _money(billing.get("actual_cash_received_cny"), "actual cash") != 0:
        raise AcceptanceInvestmentError("合成验收不得声明真实发票或回款")
    assertions = record.get("real_world_assertions", {})
    zero_assertions = {
        "real_customer_acceptance": False,
        "real_steering_decision": False,
        "real_pilot_sow_executed": False,
        "real_pilot_users": 0,
        "real_pilot_cases": 0,
        "external_customer_actions": 0,
    }
    if any(assertions.get(key) != value for key, value in zero_assertions.items()):
        raise AcceptanceInvestmentError("合成分支不得声明真实验收、Pilot 或客户动作")
    decision = steering["decision"]
    pilot_authorized = decision == "simulated_pilot" and pilot["sow_executed"] and \
        pilot["mobilization_ready"]
    base = business["scenarios"]["base"]
    if decision == "simulated_stop":
        status, next_gate = "SYNTHETIC_DISCOVERY_ACCEPTED_STOP", "CONTROLLED_CLOSEOUT"
    elif decision == "simulated_iterate":
        status, next_gate = "SYNTHETIC_DISCOVERY_ACCEPTED_ITERATE", "CONTROLLED_REMEDIATION"
    elif pilot_authorized:
        status = "SYNTHETIC_PILOT_MOBILIZATION_READY_FOR_HUMAN_REVIEW"
        next_gate = "HUMAN_PILOT_START_REVIEW"
    else:
        status = "SYNTHETIC_DISCOVERY_ACCEPTED_PILOT_NOT_AUTHORIZED"
        next_gate = "EXECUTED_PILOT_SOW_AND_MOBILIZATION"
    return {
        "status": status,
        "acceptance_bundle_sha256": acceptance["bundle_sha256"],
        "accepted_deliverable_count": len(acceptance["decisions"]),
        "closed_acceptance_condition_count": len(acceptance["conditions"]),
        "steering_decision": decision,
        "dissent_count": len(record["steering"]["dissent"]),
        "discovery_actual_cost_cny": f"{business['discovery_cost']:.2f}",
        "base_case_annual_benefit_cny": f"{base['benefit']:.2f}",
        "base_case_pilot_cost_cny": f"{base['cost']:.2f}",
        "base_case_net_benefit_cny": f"{base['net']:.2f}",
        "simulated_discovery_invoice_eligible": True,
        "actual_invoice_created": False,
        "actual_cash_received_cny": "0.00",
        "pilot_sow_executed": pilot["sow_executed"],
        "mobilization_ready_count": sum(
            row.get("status") == "simulated_ready"
            for row in pilot["requirements"].values()),
        "mobilization_required_count": len(MOBILIZATION_REQUIREMENTS),
        "pilot_authorized": pilot_authorized,
        "real_customer_acceptance": False,
        "real_pilot_users": 0,
        "real_pilot_cases": 0,
        "next_gate": next_gate,
    }


def preflight_external_decision(manifest_path: Path | str, repo_root: Path | str) -> dict:
    path, root = Path(manifest_path).expanduser().resolve(), Path(repo_root).resolve()
    if _inside(path, root):
        raise AcceptanceInvestmentError("真实客户验收与投资清单必须存放在 Git 仓库之外")
    record = load_json(path)
    if record.get("mode") != "external_customer_acceptance_investment_record":
        raise AcceptanceInvestmentError("外部验收清单 mode 无效")
    placeholders = _placeholder_paths(record)
    if placeholders:
        raise AcceptanceInvestmentError(
            f"外部验收清单仍有模板占位符：{', '.join(placeholders[:5])}")
    _require(record, ("partner_public_label", "engagement_id"), "external record")
    release = record.get("stage19_release", {})
    _require(release, ("status", "execution_record_ref", "human_verified",
                       "verified_by_role", "verified_at"), "Stage 19 release")
    if release["status"] != "READY_FOR_HUMAN_DISCOVERY_ACCEPTANCE_REVIEW" or \
            release["human_verified"] is not True or \
            release["verified_by_role"] not in {
                "customer_acceptance_owner", "fde_delivery_owner"}:
        raise AcceptanceInvestmentError("Stage 19 执行记录尚未完成人工复核")
    _parse_date(release["verified_at"], "Stage 19 release.verified_at")
    privacy = record.get("privacy_assertions", {})
    expected_privacy = {
        "contains_raw_personal_data": False,
        "contains_contract_or_invoice_body": False,
        "contains_credentials": False,
        "copied_into_source_repository": False,
    }
    if any(privacy.get(key) is not value for key, value in expected_privacy.items()):
        raise AcceptanceInvestmentError("外部验收清单违反最小化或仓库隔离要求")
    acceptance = _validate_acceptance(record["acceptance"], None, simulated=False)
    business = _validate_business_case(record["business_case"], expected_discovery_cost=None)
    steering = _validate_steering(record["steering"], acceptance["bundle_sha256"],
                                  simulated=False)
    pilot = _validate_pilot_plan(record["pilot_plan"], simulated=False)
    billing = record.get("billing_release", {})
    _require(billing, ("discovery_invoice_eligible", "finance_approval_ref",
                       "invoice_status"), "billing release")
    if billing["discovery_invoice_eligible"] is not True or \
            billing["invoice_status"] not in {"not_created", "created", "paid"}:
        raise AcceptanceInvestmentError("Discovery 开票释放状态无效")
    if billing["invoice_status"] in {"created", "paid"} and not billing.get(
            "invoice_record_ref"):
        raise AcceptanceInvestmentError("已开票状态缺少财务系统引用")
    if billing["invoice_status"] == "paid" and not billing.get("payment_record_ref"):
        raise AcceptanceInvestmentError("已回款状态缺少收款系统引用")
    decision = steering["decision"]
    if decision == "STOP":
        status, next_action = "DISCOVERY_CLOSED_STOP", "CLOSEOUT_AND_KNOWLEDGE_TRANSFER"
    elif decision == "ITERATE":
        status, next_action = "ADDITIONAL_DISCOVERY_REQUIRED", "PLAN_CONTROLLED_REMEDIATION"
    elif pilot["sow_executed"] and pilot["mobilization_ready"]:
        status = "READY_FOR_HUMAN_PILOT_START_REVIEW"
        next_action = "AUTHORIZED_HUMANS_REVIEW_PILOT_START"
    else:
        status, next_action = "PILOT_NOT_READY", "CLOSE_PILOT_SOW_AND_MOBILIZATION_GAPS"
    base = business["scenarios"]["base"]
    return {
        "status": status,
        "partner_public_label": record.get("partner_public_label"),
        "engagement_id": record.get("engagement_id"),
        "execution_reference_sha256": hashlib.sha256(
            release["execution_record_ref"].encode("utf-8")).hexdigest(),
        "accepted_deliverable_count": len(acceptance["decisions"]),
        "closed_acceptance_condition_count": len(acceptance["conditions"]),
        "steering_decision": decision,
        "base_case_net_benefit_cny": f"{base['net']:.2f}",
        "pilot_sow_executed": pilot["sow_executed"],
        "mobilization_ready_count": sum(
            row.get("status") == "ready" for row in pilot["requirements"].values()),
        "mobilization_required_count": len(MOBILIZATION_REQUIREMENTS),
        "pilot_authorized_by_code": False,
        "customer_acceptance_legally_verified_by_code": False,
        "next_action": next_action,
    }


def render(report: dict) -> str:
    return f"""# Stage 20 Customer Acceptance & Pilot Investment

状态：`{report['status']}`。

- Discovery 交付物验收：{report['accepted_deliverable_count']}/6。
- 已关闭验收条件：{report['closed_acceptance_condition_count']}。
- Steering 决定：`{report['steering_decision']}`。
- Pilot SOW 已执行：{report['pilot_sow_executed']}。
- Pilot Mobilization：{report['mobilization_ready_count']}/{report['mobilization_required_count']}。
- Pilot 已授权：{report.get('pilot_authorized', report.get('pilot_authorized_by_code', False))}。
- 下一 Gate：`{report.get('next_gate', report.get('next_action'))}`。

Discovery 验收、开票条件、Pilot 投资决定和 Pilot 启动授权是四个独立控制。任何一个都不能自动推出下一个。
"""


def write_outputs(output: Path | str, report: dict, record: dict | None = None) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "stage20-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "stage20-report.md").write_text(render(report), encoding="utf-8")
    if record:
        with (output / "mobilization-register.csv").open(
                "w", newline="", encoding="utf-8-sig") as handle:
            fields = ("requirement_id", "owner_role", "status", "evidence_ref")
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in record["pilot_plan"]["mobilization_requirements"]:
                writer.writerow({key: row.get(key, "") for key in fields})


def prepare_external_pack(output: Path | str, template: dict) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "external-acceptance-investment.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sheets = {
        "acceptance-decisions.csv": ("deliverable_id", "status", "criteria_ref", "decision_evidence_ref"),
        "acceptance-conditions.csv": ("condition_id", "deliverable_id", "owner_role", "due_date", "status", "closure_evidence_ref"),
        "mobilization-register.csv": ("requirement_id", "owner_role", "status", "evidence_ref"),
    }
    for name, fields in sheets.items():
        with (output / name).open("w", newline="", encoding="utf-8-sig") as handle:
            csv.writer(handle).writerow(fields)
