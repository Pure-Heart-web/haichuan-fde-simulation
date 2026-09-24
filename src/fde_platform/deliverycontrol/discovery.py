"""Paid Discovery delivery and acceptance controls for a synthetic contract branch."""
from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path


class DeliveryControlError(ValueError):
    """The contracted-delivery bundle is inconsistent or overclaims reality."""


def load_json(path: Path | str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeliveryControlError(f"无法读取交付资料：{exc}") from exc
    if not isinstance(value, dict):
        raise DeliveryControlError("交付资料必须是 JSON object")
    return value


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":")).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(value: dict, keys: tuple[str, ...], where: str) -> None:
    missing = [key for key in keys if value.get(key) in (None, "", [])]
    if missing:
        raise DeliveryControlError(f"{where} 缺少字段：{', '.join(missing)}")


def _index(rows: list[dict], key: str, where: str) -> dict:
    result = {}
    for row in rows:
        _require(row, (key,), where)
        if row[key] in result:
            raise DeliveryControlError(f"{where} {key} 重复：{row[key]}")
        result[row[key]] = row
    return result


def _money(value, where: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise DeliveryControlError(f"{where} 金额无效") from exc
    if result < 0:
        raise DeliveryControlError(f"{where} 金额不能为负数")
    return result


def validate_delivery(stage_root: Path, contract: dict, acceptance: dict,
                      dependencies: dict, changes: dict) -> dict:
    stage_root = Path(stage_root).resolve()
    if contract.get("mode") != "synthetic_paid_discovery_branch":
        raise DeliveryControlError("Stage 17 只接受 synthetic_paid_discovery_branch")
    if contract.get("progression_mode") != "counterfactual_training_branch":
        raise DeliveryControlError("合成合同必须明确为 counterfactual_training_branch")
    _require(contract, ("contract_id", "deal_id", "source_deal_sha256", "effective_date",
        "period", "scope", "roles", "deliverables", "commercial", "approvals"), "contract")
    if contract.get("real_contract_signed") is not False:
        raise DeliveryControlError("合成分支不得声明真实合同已签")
    source_deal = stage_root.parent / "15-commercial-delivery/data/haichuan-deal-record.json"
    if not source_deal.is_file() or file_sha256(source_deal) != contract["source_deal_sha256"]:
        raise DeliveryControlError("Stage 15 来源交易档案摘要不匹配")

    controlled_contract = {key: value for key, value in contract.items()
                           if key not in {"approvals", "contract_sha256"}}
    contract_sha = digest(controlled_contract)
    if contract.get("contract_sha256") != contract_sha:
        raise DeliveryControlError("合同内容摘要不匹配")
    contract_approvals = _index(contract["approvals"], "role", "contract approval")
    required_contract_roles = {"customer_sponsor", "customer_procurement_owner",
                               "fde_commercial_owner", "fde_delivery_owner"}
    if set(contract_approvals) != required_contract_roles or any(
            not row.get("actor_id") or not row.get("approved_at") or
            row.get("status") != "simulated_approved" or
            row.get("content_sha256") != contract_sha
            for row in contract_approvals.values()):
        raise DeliveryControlError("合同签核角色、状态或内容绑定不完整")

    roles = _index(contract["roles"], "role", "role")
    required_roles = {"customer_sponsor", "customer_process_owner", "customer_data_owner",
        "customer_security_owner", "customer_procurement_owner", "fde_commercial_owner",
        "fde_delivery_owner", "technical_lead", "acceptance_owner", "stop_owner"}
    if not required_roles.issubset(set(roles)):
        raise DeliveryControlError("合同 RACI 缺少关键角色")

    deliverables = _index(contract["deliverables"], "deliverable_id", "deliverable")
    if len(deliverables) < 6:
        raise DeliveryControlError("付费 Discovery 至少需要六项可验收交付物")
    for item in deliverables.values():
        _require(item, ("title", "owner", "acceptance_criteria", "path"),
                 f"deliverable {item['deliverable_id']}")
        path = (stage_root / item["path"]).resolve()
        if stage_root not in path.parents or not path.is_file():
            raise DeliveryControlError(f"交付物路径越界或不存在：{item['path']}")

    dependency_rows = _index(dependencies.get("dependencies", []), "dependency_id", "dependency")
    for row in dependency_rows.values():
        _require(row, ("gate", "owner", "due_date", "status", "evidence_ref"),
                 f"dependency {row['dependency_id']}")
    discovery_dependencies = [row for row in dependency_rows.values()
                              if row["gate"] == "PAID_DISCOVERY_ACCEPTANCE"]
    if not discovery_dependencies or any(row["status"] != "closed"
                                         for row in discovery_dependencies):
        raise DeliveryControlError("Discovery 验收依赖尚未全部关闭")

    change_rows = _index(changes.get("change_requests", []), "change_id", "change request")
    delivered_scope = set(acceptance.get("delivered_scope", []))
    contracted_scope = set(contract["scope"]["in_scope"])
    if not delivered_scope.issubset(contracted_scope):
        raise DeliveryControlError("验收包包含合同外且未批准的范围")
    for row in change_rows.values():
        _require(row, ("requested_scope", "status", "decision_owner", "commercial_impact"),
                 f"change request {row['change_id']}")
        if row["status"] != "approved" and set(row["requested_scope"]) & delivered_scope:
            raise DeliveryControlError(f"未批准变更 {row['change_id']} 混入已交付范围")

    _require(acceptance, ("acceptance_id", "contract_id", "contract_sha256",
        "submitted_at", "decision", "deliverable_evidence", "metric_freeze",
        "limitations", "approvals", "bundle_sha256"), "acceptance")
    if acceptance.get("mode") != "counterfactual_training_acceptance":
        raise DeliveryControlError("验收包必须明确为 counterfactual_training_acceptance")
    if acceptance["contract_id"] != contract["contract_id"] or \
            acceptance["contract_sha256"] != contract_sha:
        raise DeliveryControlError("验收包未绑定当前合同")
    evidence = _index(acceptance["deliverable_evidence"], "deliverable_id",
                      "deliverable evidence")
    if set(evidence) != set(deliverables):
        raise DeliveryControlError("验收证据未完整覆盖合同交付物")
    for deliverable_id, row in evidence.items():
        path = (stage_root / deliverables[deliverable_id]["path"]).resolve()
        if row.get("status") != "accepted" or row.get("sha256") != file_sha256(path):
            raise DeliveryControlError(f"交付物 {deliverable_id} 未接受或内容被修改")

    freeze = acceptance["metric_freeze"]
    _require(freeze, ("frozen_before_delivery", "version", "denominator_policy",
                      "post_hoc_changes_allowed"), "metric_freeze")
    if freeze["frozen_before_delivery"] is not True or \
            freeze["post_hoc_changes_allowed"] is not False:
        raise DeliveryControlError("验收指标必须在交付前冻结且禁止事后改口径")
    if acceptance["decision"] != "simulated_accepted":
        raise DeliveryControlError("参考分支必须有明确的合成验收决定")

    controlled_acceptance = {key: value for key, value in acceptance.items()
                             if key not in {"approvals", "bundle_sha256"}}
    bundle_sha = digest(controlled_acceptance)
    if acceptance["bundle_sha256"] != bundle_sha:
        raise DeliveryControlError("验收包摘要不匹配")
    acceptance_approvals = _index(acceptance["approvals"], "role", "acceptance approval")
    required_acceptance_roles = {"customer_process_owner", "customer_sponsor",
                                 "fde_delivery_owner"}
    if set(acceptance_approvals) != required_acceptance_roles or any(
            not row.get("actor_id") or not row.get("approved_at") or
            row.get("status") != "simulated_approved" or
            row.get("content_sha256") != bundle_sha
            for row in acceptance_approvals.values()):
        raise DeliveryControlError("验收签核角色、状态或内容绑定不完整")

    commercial = contract["commercial"]
    fee = _money(commercial.get("fee_cny"), "contract fee")
    milestones = _index(commercial.get("payment_milestones", []), "milestone_id", "milestone")
    percent = sum(Decimal(str(row.get("percent", 0))) for row in milestones.values())
    if percent != Decimal("100"):
        raise DeliveryControlError("付款里程碑比例合计必须为 100")
    if commercial.get("actual_invoice_created") is not False or \
            _money(commercial.get("actual_cash_received_cny"), "cash received") != 0 or any(
                row.get("actual_invoice_id") is not None or
                row.get("actual_payment_status") != "not_created"
                for row in milestones.values()):
        raise DeliveryControlError("合成分支不得声明真实开票或回款")
    costs = contract.get("delivery_costs", [])
    if not costs:
        raise DeliveryControlError("必须记录按角色的交付成本")
    actual_cost = sum(_money(row.get("hours"), "hours") *
                      _money(row.get("internal_rate_cny"), "rate") for row in costs)
    return {"contract_sha256": contract_sha, "bundle_sha256": bundle_sha,
            "deliverables": deliverables, "dependencies": dependency_rows,
            "changes": change_rows, "milestones": milestones, "fee": fee,
            "actual_cost": actual_cost}


def analyze_delivery(stage_root: Path, contract: dict, acceptance: dict,
                     dependencies: dict, changes: dict) -> dict:
    facts = validate_delivery(stage_root, contract, acceptance, dependencies, changes)
    fee, cost = facts["fee"], facts["actual_cost"]
    eligible = sum(fee * Decimal(str(row["percent"])) / 100
                   for row in facts["milestones"].values()
                   if row.get("simulated_trigger_satisfied") is True)
    gross = fee - cost
    next_gate_open = [row["dependency_id"] for row in facts["dependencies"].values()
                      if row["gate"] == "AUTHORIZED_SHADOW_START" and row["status"] != "closed"]
    return {
        "status": "SIMULATED_PAID_DISCOVERY_ACCEPTED",
        "mode": contract["mode"], "progression_mode": contract["progression_mode"],
        "contract_id": contract["contract_id"], "deal_id": contract["deal_id"],
        "contract_sha256": facts["contract_sha256"],
        "acceptance_bundle_sha256": facts["bundle_sha256"],
        "deliverable_count": len(facts["deliverables"]),
        "accepted_deliverable_count": len(facts["deliverables"]),
        "closed_discovery_dependency_count": sum(row["gate"] == "PAID_DISCOVERY_ACCEPTANCE"
            and row["status"] == "closed" for row in facts["dependencies"].values()),
        "deferred_change_count": sum(row["status"] == "deferred"
                                     for row in facts["changes"].values()),
        "fee_cny": str(fee.quantize(Decimal("0.01"))),
        "delivery_cost_cny": str(cost.quantize(Decimal("0.01"))),
        "simulated_invoice_eligible_cny": str(eligible.quantize(Decimal("0.01"))),
        "simulated_gross_margin_percent": str(
            (gross / fee * 100).quantize(Decimal("0.01"))) if fee else "0.00",
        "actual_invoice_created": False, "actual_cash_received_cny": "0.00",
        "real_contract_signed": False, "real_customer_approvals": 0,
        "real_customer_data_used": False, "actual_customer_users": 0,
        "external_customer_actions": 0,
        "authorized_shadow_ready": len(next_gate_open) == 0,
        "next_gate": "AUTHORIZED_SHADOW_START",
        "next_gate_open_dependencies": next_gate_open,
        "decision": "PREPARE_REAL_PAID_DISCOVERY_OR_NAMED_DESIGN_PARTNER",
    }


def render(report: dict) -> str:
    missing = "\n".join(f"- `{item}`" for item in report["next_gate_open_dependencies"])
    return f"""# Stage 17 Paid Discovery Delivery & Acceptance

状态：`{report['status']}`。这是反事实教学合同分支，不是海川真实合同或客户验收。

- 合同与验收包使用 SHA-256 绑定，交付物 {report['accepted_deliverable_count']}/{report['deliverable_count']} 通过合成验收。
- 教学费用 CNY {report['fee_cny']}；交付成本 CNY {report['delivery_cost_cny']}；模拟毛利率 {report['simulated_gross_margin_percent']}%。
- 满足教学开票条件 CNY {report['simulated_invoice_eligible_cny']}；实际发票 0，实际回款 0。
- 真实合同、客户批准、真实数据、真实用户和外部客户动作均为 0。
- 下一 Gate：`{report['next_gate']}`，状态 `{'READY' if report['authorized_shadow_ready'] else 'BLOCKED'}`。

## 下一 Gate 仍缺

{missing or '- 无'}

Paid Discovery 验收只证明客户获得了可决策的范围、基线、数据边界、方案、商业测算和 Pilot 建议。它不授权 Shadow、生产接入、自动发送或客户系统写入。
"""


def write_outputs(output: Path, report: dict, contract: dict) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "stage17-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "stage17-report.md").write_text(render(report), encoding="utf-8")
    with (output / "milestone-ledger.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ("milestone_id", "trigger", "percent", "simulated_trigger_satisfied",
                  "actual_invoice_id", "actual_payment_status")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in contract["commercial"]["payment_milestones"]:
            writer.writerow({key: row.get(key, "") for key in fields})
