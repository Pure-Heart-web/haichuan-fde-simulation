"""Validate a commercial deal record without confusing intent with approval."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path


class DealValidationError(ValueError):
    """The deal record is structurally invalid or overclaims approval."""


GATE_ORDER = (
    "A_OPPORTUNITY_QUALIFIED",
    "B_PAID_DISCOVERY_CONTRACTED",
    "C_AUTHORIZED_SHADOW_START",
    "D_PAID_PILOT_ACCEPTED",
    "E_PRODUCTION_GO_LIVE",
    "F_FINAL_HANDOVER",
)
GATE_STATES = {"approved", "pending", "blocked", "not_started"}
EVIDENCE_STATES = {"draft", "requested", "received", "accepted", "rejected", "expired"}


def load_deal(path: Path | str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DealValidationError(f"无法读取交易档案：{exc}") from exc
    if not isinstance(value, dict):
        raise DealValidationError("交易档案必须是 JSON object")
    return value


def _require(value: dict, keys: tuple[str, ...], where: str) -> None:
    missing = [key for key in keys if value.get(key) in (None, "", [])]
    if missing:
        raise DealValidationError(f"{where} 缺少字段：{', '.join(missing)}")


def _unique(rows: list[dict], key: str, where: str) -> dict:
    index = {}
    for row in rows:
        _require(row, (key,), where)
        if row[key] in index:
            raise DealValidationError(f"{where} {key} 重复：{row[key]}")
        index[row[key]] = row
    return index


def _money(value, where: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise DealValidationError(f"{where} 不是有效金额") from exc
    if result < 0:
        raise DealValidationError(f"{where} 不能为负数")
    return result


def validate_deal(deal: dict) -> dict:
    _require(deal, ("version", "mode", "deal", "stakeholders", "scope", "phases",
                    "success_metrics", "evidence", "gates", "risks"), "根节点")
    if deal["mode"] != "synthetic_commercial_rehearsal":
        raise DealValidationError("仓库内示例只接受 synthetic_commercial_rehearsal")

    header = deal["deal"]
    _require(header, ("deal_id", "account_name", "currency", "commercial_owner",
                      "opportunity_stage", "next_step", "next_step_owner",
                      "next_step_due"), "deal")
    if header["currency"] != "CNY":
        raise DealValidationError("Stage 15 示例只使用 CNY，真实项目需显式扩展币种规则")

    stakeholder_roles = {row.get("role") for row in deal["stakeholders"]}
    required_roles = {"customer_sponsor", "customer_process_owner", "customer_data_owner",
                      "customer_security_owner", "customer_procurement_owner",
                      "fde_commercial_owner", "fde_delivery_owner", "fde_security_owner"}
    missing_roles = sorted(required_roles - stakeholder_roles)
    if missing_roles:
        raise DealValidationError("缺少关键干系人角色：" + ", ".join(missing_roles))

    scope = deal["scope"]
    _require(scope, ("business_outcome", "in_scope", "out_of_scope", "assumptions",
                     "customer_dependencies", "change_control"), "scope")

    evidence = _unique(deal["evidence"], "evidence_id", "evidence")
    for item in evidence.values():
        _require(item, ("title", "status", "owner", "required_for_gate"),
                 f"evidence {item['evidence_id']}")
        if item["status"] not in EVIDENCE_STATES:
            raise DealValidationError(f"证据 {item['evidence_id']} 状态无效")
        if item["required_for_gate"] not in GATE_ORDER:
            raise DealValidationError(f"证据 {item['evidence_id']} 引用未知 Gate")

    phases = _unique(deal["phases"], "phase_id", "phase")
    required_phases = {"P1-DISCOVERY", "P2-SHADOW-PILOT", "P3-PRODUCTION", "P4-SUPPORT"}
    if set(phases) != required_phases:
        raise DealValidationError("阶段必须包含 Discovery、Shadow Pilot、Production 和 Support")
    total_contract = Decimal("0")
    booked = Decimal("0")
    invoice_rows = []
    for phase in phases.values():
        _require(phase, ("name", "commercial_status", "fee", "duration_weeks",
                         "deliverables", "acceptance_criteria", "payment_milestones"),
                 f"phase {phase['phase_id']}")
        fee = _money(phase["fee"], f"phase {phase['phase_id']} fee")
        total_contract += fee
        if phase["commercial_status"] in {"contracted", "in_delivery", "accepted"}:
            booked += fee
        percentages = Decimal("0")
        for milestone in phase["payment_milestones"]:
            _require(milestone, ("milestone_id", "trigger", "percent", "invoice_status"),
                     f"phase {phase['phase_id']} payment milestone")
            percent = Decimal(str(milestone["percent"]))
            if percent <= 0:
                raise DealValidationError("付款里程碑比例必须大于 0")
            percentages += percent
            invoice_rows.append({
                "phase_id": phase["phase_id"], "phase_name": phase["name"],
                "milestone_id": milestone["milestone_id"], "trigger": milestone["trigger"],
                "percent": str(percent), "amount_cny": str((fee * percent / 100).quantize(Decimal("0.01"))),
                "invoice_status": milestone["invoice_status"],
            })
        if percentages != Decimal("100"):
            raise DealValidationError(f"phase {phase['phase_id']} 付款比例合计应为 100")

    metric_ids = _unique(deal["success_metrics"], "metric_id", "success metric")
    for metric in metric_ids.values():
        _require(metric, ("name", "definition", "baseline_status", "target",
                          "measurement_window", "owner", "acceptance_use"),
                 f"metric {metric['metric_id']}")
        if metric["baseline_status"] == "synthetic_only" and metric.get("customer_baseline") is not None:
            raise DealValidationError(f"metric {metric['metric_id']} 不能把合成值写成客户 baseline")

    gates = _unique(deal["gates"], "gate_id", "gate")
    if tuple(gates) != GATE_ORDER:
        raise DealValidationError("Gate 必须完整并按 A-F 排列")
    approved_prefix = True
    for gate_id in GATE_ORDER:
        gate = gates[gate_id]
        missing_fields = [key for key in ("name", "status", "owner", "required_evidence",
            "approvals", "missing_decisions") if key not in gate]
        if missing_fields:
            raise DealValidationError(
                f"gate {gate_id} 缺少字段：{', '.join(missing_fields)}")
        _require(gate, ("name", "status", "owner", "required_evidence"),
                 f"gate {gate_id}")
        if gate["status"] not in GATE_STATES:
            raise DealValidationError(f"Gate {gate_id} 状态无效")
        dangling = sorted(set(gate["required_evidence"]) - set(evidence))
        if dangling:
            raise DealValidationError(f"Gate {gate_id} 有未知证据：{dangling}")
        if gate["status"] == "approved":
            if not approved_prefix:
                raise DealValidationError(f"Gate {gate_id} 不得越过前置 Gate 批准")
            unavailable = [eid for eid in gate["required_evidence"]
                           if evidence[eid]["status"] != "accepted"]
            if unavailable:
                raise DealValidationError(f"Gate {gate_id} 用未接受证据批准：{unavailable}")
            if not gate["approvals"]:
                raise DealValidationError(f"Gate {gate_id} 批准但没有签核记录")
        else:
            approved_prefix = False
            if not gate["missing_decisions"]:
                raise DealValidationError(f"未批准 Gate {gate_id} 必须说明缺失决定")

    if gates["C_AUTHORIZED_SHADOW_START"]["status"] == "approved":
        external = {"EV-DATA-AUTH", "EV-SECURITY-APPROVAL", "EV-SHADOW-SOW",
                    "EV-UAT-PLAN", "EV-INCIDENT-PLAN"}
        if not external.issubset(set(gates["C_AUTHORIZED_SHADOW_START"]["required_evidence"])):
            raise DealValidationError("Shadow Gate 缺少数据、安全、SOW、UAT 或事故证据")

    open_risks = [row for row in deal["risks"] if row.get("status") != "closed"]
    critical_open = [row for row in open_risks if row.get("severity") == "critical"]
    next_gate = next((gate_id for gate_id in GATE_ORDER
                      if gates[gate_id]["status"] != "approved"), None)
    contracted_states = {"contracted", "in_delivery", "accepted"}
    if ((phases["P1-DISCOVERY"]["commercial_status"] in contracted_states) !=
            (gates["B_PAID_DISCOVERY_CONTRACTED"]["status"] == "approved")):
        raise DealValidationError("Discovery 商业状态与 Gate B 不一致")
    if gates["C_AUTHORIZED_SHADOW_START"]["status"] == "approved" and \
            phases["P2-SHADOW-PILOT"]["commercial_status"] not in contracted_states:
        raise DealValidationError("Gate C 已批准但 Shadow Pilot 尚未签约")
    if gates["D_PAID_PILOT_ACCEPTED"]["status"] == "approved" and \
            phases["P2-SHADOW-PILOT"]["commercial_status"] != "accepted":
        raise DealValidationError("Gate D 已批准但 Shadow Pilot 未标记为 accepted")
    if gates["E_PRODUCTION_GO_LIVE"]["status"] == "approved" and \
            phases["P3-PRODUCTION"]["commercial_status"] not in {"in_delivery", "accepted"}:
        raise DealValidationError("Gate E 已批准但 Production 未进入交付")
    if gates["F_FINAL_HANDOVER"]["status"] == "approved" and \
            phases["P3-PRODUCTION"]["commercial_status"] != "accepted":
        raise DealValidationError("Gate F 已批准但 Production 未验收")
    if next_gate is None:
        current_gate = GATE_ORDER[-1]
    elif next_gate == GATE_ORDER[0]:
        current_gate = None
    else:
        current_gate = GATE_ORDER[GATE_ORDER.index(next_gate) - 1]
    return {
        "phase_index": phases,
        "evidence_index": evidence,
        "gate_index": gates,
        "invoice_rows": invoice_rows,
        "total_potential_contract_value_cny": str(total_contract.quantize(Decimal("0.01"))),
        "booked_value_cny": str(booked.quantize(Decimal("0.01"))),
        "next_gate": next_gate,
        "current_approved_gate": current_gate,
        "open_risk_count": len(open_risks),
        "critical_open_risk_count": len(critical_open),
    }


def analyze_deal(deal: dict) -> dict:
    facts = validate_deal(deal)
    gates = facts["gate_index"]
    next_gate = facts["next_gate"]
    missing_evidence = []
    missing_decisions = []
    if next_gate:
        gate = gates[next_gate]
        missing_evidence = [eid for eid in gate["required_evidence"]
                            if facts["evidence_index"][eid]["status"] != "accepted"]
        missing_decisions = list(gate["missing_decisions"])
    shadow_ready = gates["C_AUTHORIZED_SHADOW_START"]["status"] == "approved"
    production_ready = gates["E_PRODUCTION_GO_LIVE"]["status"] == "approved"
    report = {
        "status": "COMMERCIAL_DEAL_ROOM_VALID",
        "deal_id": deal["deal"]["deal_id"],
        "mode": deal["mode"],
        "opportunity_stage": deal["deal"]["opportunity_stage"],
        "current_approved_gate": facts["current_approved_gate"],
        "next_gate": next_gate,
        "next_gate_status": gates[next_gate]["status"] if next_gate else "complete",
        "missing_evidence_for_next_gate": missing_evidence,
        "missing_decisions_for_next_gate": missing_decisions,
        "total_potential_contract_value_cny": facts["total_potential_contract_value_cny"],
        "booked_value_cny": facts["booked_value_cny"],
        "invoice_milestone_count": len(facts["invoice_rows"]),
        "open_risk_count": facts["open_risk_count"],
        "critical_open_risk_count": facts["critical_open_risk_count"],
        "authorized_shadow_ready": shadow_ready,
        "production_go_live_ready": production_ready,
        "actual_customer_contract_signed": any(
            p["commercial_status"] in {"contracted", "in_delivery", "accepted"}
            for p in deal["phases"]),
        "real_revenue_claimed": False,
        "commercial_boundary": "模板通过表示档案结构完整，不表示合同成立、收入确认或客户授权",
    }
    return report


def render_report(deal: dict, report: dict) -> str:
    gate_rows = "\n".join(
        f"| {g['gate_id']} | {g['name']} | {g['status']} | {g['owner']} |"
        for g in deal["gates"])
    missing = report["missing_decisions_for_next_gate"] or ["无"]
    evidence = report["missing_evidence_for_next_gate"] or ["无"]
    return f"""# 商务交付室报告：{deal['deal']['account_name']}

> 教学虚构案例。验证通过仅表示商务档案字段与 Gate 关系自洽，不构成报价、合同、客户授权、收入确认或生产上线批准。

- Deal：`{report['deal_id']}`
- 当前商机阶段：`{report['opportunity_stage']}`
- 当前已批准 Gate：`{report['current_approved_gate'] or '无'}`
- 下一 Gate：`{report['next_gate'] or '全部完成'}`（`{report['next_gate_status']}`）
- 潜在合同总额：CNY {report['total_potential_contract_value_cny']}；已签约金额：CNY {report['booked_value_cny']}
- 授权 Shadow 就绪：`{str(report['authorized_shadow_ready']).lower()}`；生产上线就绪：`{str(report['production_go_live_ready']).lower()}`

## 商务 Gate

| Gate | 名称 | 状态 | Owner |
|---|---|---|---|
{gate_rows}

## 下一 Gate 尚缺

**客户/双方决定**

{chr(10).join('- ' + item for item in missing)}

**证据**

{chr(10).join('- `' + item + '`' for item in evidence)}

## 下一步

负责人：{deal['deal']['next_step_owner']}；截止：{deal['deal']['next_step_due']}。

{deal['deal']['next_step']}
"""


def write_outputs(deal: dict, output: Path | str) -> dict:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    facts = validate_deal(deal)
    report = analyze_deal(deal)
    (output / "commercial-readiness.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "commercial-readiness.md").write_text(render_report(deal, report), encoding="utf-8")
    with (output / "invoice-plan.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=("phase_id", "phase_name", "milestone_id",
            "trigger", "percent", "amount_cny", "invoice_status"))
        writer.writeheader()
        writer.writerows(facts["invoice_rows"])
    with (output / "evidence-register.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ("evidence_id", "title", "status", "owner", "required_for_gate", "path")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in deal["evidence"]:
            writer.writerow({key: row.get(key, "") for key in fields})
    return report
