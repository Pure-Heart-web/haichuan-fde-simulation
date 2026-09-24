"""Controls for moving a synthetic offer toward a real Design Partner contract.

The repository can prepare and check a contracting record. It cannot verify a
signature's legal validity or execute customer, procurement, billing, or CRM
actions. Real records must stay outside the source repository.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date
from pathlib import Path


class ContractingError(ValueError):
    """The Design Partner or contracting record is incomplete or unsafe."""


REQUIRED_EVIDENCE = {
    "legal_entity_verification",
    "sponsor_authority",
    "discovery_scope_approval",
    "sow_execution",
    "msa_or_terms_execution",
    "privacy_dpa_resolution",
    "security_path_agreement",
    "procurement_authority",
    "billing_profile_verification",
    "kickoff_commitment",
}

REQUIRED_RELEASE_ROLES = {
    "fde_commercial_owner",
    "fde_legal_or_procurement_owner",
    "fde_delivery_owner",
}

CRITERIA_WEIGHTS = {
    "named_executive_sponsor": 15,
    "named_process_owner": 10,
    "quantified_problem": 10,
    "stage17_offer_fit": 10,
    "accepts_paid_discovery": 15,
    "budget_owner_and_range": 10,
    "procurement_path": 10,
    "data_and_security_owners": 10,
    "compelling_event": 5,
    "customer_working_time": 5,
}

DISQUALIFIERS = {
    "requires_unreviewed_auto_send",
    "refuses_paid_discovery",
    "refuses_process_or_data_observation",
    "no_accountable_owner",
    "prohibited_data_without_approved_path",
}


def load_json(path: Path | str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractingError(f"无法读取资料：{exc}") from exc
    if not isinstance(value, dict):
        raise ContractingError("资料必须是 JSON object")
    return value


def _require(value: dict, keys: tuple[str, ...], where: str) -> None:
    missing = [key for key in keys if value.get(key) in (None, "", [])]
    if missing:
        raise ContractingError(f"{where} 缺少字段：{', '.join(missing)}")


def _index(rows: list[dict], key: str, where: str) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ContractingError(f"{where} 必须是 object list")
        _require(row, (key,), where)
        if row[key] in result:
            raise ContractingError(f"{where} {key} 重复：{row[key]}")
        result[row[key]] = row
    return result


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _inside(path: Path, parent: Path) -> bool:
    path, parent = path.resolve(), parent.resolve()
    return path == parent or parent in path.parents


def _score_candidate(candidate: dict) -> dict:
    _require(candidate, ("candidate_id", "display_name", "fictional", "criteria",
                         "decision"), "candidate")
    if "disqualifiers" not in candidate or not isinstance(candidate["disqualifiers"], list):
        raise ContractingError("candidate 缺少字段：disqualifiers")
    if candidate["fictional"] is not True:
        raise ContractingError("公开参考候选必须明确标记 fictional=true")
    criteria = candidate["criteria"]
    if set(criteria) != set(CRITERIA_WEIGHTS):
        raise ContractingError(f"候选 {candidate['candidate_id']} 的资格项不完整")
    invalid = {key for key, value in criteria.items()
               if value not in {"confirmed", "unknown", "rejected"}}
    if invalid:
        raise ContractingError(f"候选资格状态无效：{', '.join(sorted(invalid))}")
    unknown = sorted(key for key, value in criteria.items() if value == "unknown")
    rejected = sorted(key for key, value in criteria.items() if value == "rejected")
    active_disqualifiers = sorted(set(candidate["disqualifiers"]) & DISQUALIFIERS)
    unknown_disqualifiers = sorted(set(candidate["disqualifiers"]) - DISQUALIFIERS)
    if unknown_disqualifiers:
        raise ContractingError(f"未知淘汰项：{', '.join(unknown_disqualifiers)}")
    score = sum(CRITERIA_WEIGHTS[key] for key, value in criteria.items()
                if value == "confirmed")
    qualified = score >= 75 and not rejected and not active_disqualifiers
    return {
        "candidate_id": candidate["candidate_id"],
        "display_name": candidate["display_name"],
        "score": score,
        "qualified": qualified,
        "unknown_criteria": unknown,
        "rejected_criteria": rejected,
        "active_disqualifiers": active_disqualifiers,
        "decision": candidate["decision"],
    }


def analyze_candidate_pipeline(pipeline: dict) -> dict:
    _require(pipeline, ("mode", "portfolio_id", "as_of", "candidates",
                        "real_world_assertions"), "candidate pipeline")
    if pipeline["mode"] != "synthetic_design_partner_pipeline":
        raise ContractingError("公开参考数据只接受 synthetic_design_partner_pipeline")
    assertions = pipeline["real_world_assertions"]
    expected_zero = {
        "named_real_design_partners": 0,
        "real_contracts_executed": 0,
        "real_purchase_orders": 0,
        "real_invoices_created": 0,
        "actual_cash_received_cny": 0,
    }
    if any(assertions.get(key) != value for key, value in expected_zero.items()):
        raise ContractingError("合成候选管道不得声明真实客户、合同、PO、发票或回款")
    indexed = _index(pipeline["candidates"], "candidate_id", "candidate")
    scored = [_score_candidate(row) for row in indexed.values()]
    selected = [row for row in scored if row["decision"] == "selected_for_training"]
    if len(selected) != 1 or not selected[0]["qualified"]:
        raise ContractingError("教学管道必须且只能选择一个合格候选")
    return {
        "status": "REAL_PAID_DISCOVERY_NOT_READY",
        "mode": pipeline["mode"],
        "portfolio_id": pipeline["portfolio_id"],
        "candidate_count": len(scored),
        "qualified_candidate_count": sum(row["qualified"] for row in scored),
        "training_selected_candidate_id": selected[0]["candidate_id"],
        "training_selected_score": selected[0]["score"],
        "candidate_results": scored,
        "named_real_design_partner_count": 0,
        "external_evidence_received_count": 0,
        "external_evidence_required_count": len(REQUIRED_EVIDENCE),
        "external_evidence_missing": sorted(REQUIRED_EVIDENCE),
        "external_contract_record_complete": False,
        "legally_verified_by_code": False,
        "actual_cash_received_cny": "0.00",
        "decision": "ACQUIRE_NAMED_DESIGN_PARTNER",
    }


def _parse_date(value: str, where: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ContractingError(f"{where} 日期必须为 YYYY-MM-DD") from exc


def preflight_external_manifest(manifest_path: Path | str, repo_root: Path | str,
                                *, as_of: date | None = None) -> dict:
    """Check an externally stored deal manifest without claiming legal validity."""
    path, root = Path(manifest_path).expanduser().resolve(), Path(repo_root).resolve()
    if _inside(path, root):
        raise ContractingError("真实客户交易清单必须存放在 Git 仓库之外")
    manifest = load_json(path)
    _require(manifest, ("manifest_version", "mode", "partner", "offer", "evidence",
                        "contract_execution_assertion", "release_approvals"),
             "external manifest")
    if manifest["mode"] != "external_design_partner_contract_record":
        raise ContractingError("外部清单 mode 无效")
    partner = manifest["partner"]
    _require(partner, ("legal_entity_ref", "public_label", "jurisdiction",
                       "crm_account_ref"), "partner")
    if partner.get("fictional") is not False:
        raise ContractingError("外部清单必须明确 fictional=false")
    offer = manifest["offer"]
    _require(offer, ("offer_id", "stage17_offer_version", "currency", "fee",
                     "scope_ref", "target_kickoff_date"), "offer")
    if offer["currency"] != "CNY" or not isinstance(offer["fee"], (int, float)) \
            or isinstance(offer["fee"], bool) or offer["fee"] <= 0:
        raise ContractingError("offer 必须包含正数 CNY fee")
    if offer["stage17_offer_version"] != "stage17-v1":
        raise ContractingError("offer 未绑定受支持的 Stage 17 版本")
    _parse_date(offer["target_kickoff_date"], "offer.target_kickoff_date")

    evidence = _index(manifest["evidence"], "evidence_type", "evidence")
    missing = sorted(REQUIRED_EVIDENCE - set(evidence))
    extra = sorted(set(evidence) - REQUIRED_EVIDENCE)
    if extra:
        raise ContractingError(f"未知 evidence_type：{', '.join(extra)}")
    check_date = as_of or date.today()
    invalid: list[str] = []
    expired: list[str] = []
    for evidence_type, row in evidence.items():
        _require(row, ("status", "evidence_ref", "system_of_record", "verified_at",
                       "verifier_role"), f"evidence {evidence_type}")
        if row["status"] != "accepted":
            invalid.append(evidence_type)
        _parse_date(row["verified_at"], f"evidence {evidence_type}.verified_at")
        if row.get("expires_at") and _parse_date(
                row["expires_at"], f"evidence {evidence_type}.expires_at") < check_date:
            expired.append(evidence_type)

    assertion = manifest["contract_execution_assertion"]
    _require(assertion, ("status", "asserted_at", "asserted_by_role", "evidence_ref"),
             "contract execution assertion")
    assertion_complete = assertion["status"] == "executed" and \
        assertion["asserted_by_role"] in {"fde_authorized_signatory", "fde_legal_owner"}
    _parse_date(assertion["asserted_at"], "contract execution assertion.asserted_at")

    approvals = _index(manifest["release_approvals"], "role", "release approval")
    release_missing = sorted(REQUIRED_RELEASE_ROLES - set(approvals))
    release_invalid = sorted(role for role, row in approvals.items()
                             if role in REQUIRED_RELEASE_ROLES and (
                                 row.get("status") != "approved" or
                                 not row.get("approved_at") or
                                 not row.get("evidence_ref")))
    for role, row in approvals.items():
        if row.get("approved_at"):
            _parse_date(row["approved_at"], f"release approval {role}.approved_at")

    evidence_complete = not missing and not invalid and not expired
    release_complete = not release_missing and not release_invalid
    complete = evidence_complete and assertion_complete and release_complete
    status = ("READY_FOR_PAID_DISCOVERY_KICKOFF" if complete else
              "EXTERNAL_CONTRACT_RECORD_INCOMPLETE")
    return {
        "status": status,
        "partner_public_label": partner["public_label"],
        "partner_reference_sha256": _sha256(partner["legal_entity_ref"]),
        "offer_id": offer["offer_id"],
        "stage17_offer_version": offer["stage17_offer_version"],
        "currency": offer["currency"],
        "fee": f"{offer['fee']:.2f}",
        "evidence_received_count": len(evidence),
        "evidence_required_count": len(REQUIRED_EVIDENCE),
        "missing_evidence": missing,
        "invalid_evidence": sorted(invalid),
        "expired_evidence": sorted(expired),
        "contract_execution_asserted": assertion_complete,
        "release_missing_roles": release_missing,
        "release_invalid_roles": release_invalid,
        "external_contract_record_complete": complete,
        "legally_verified_by_code": False,
        "legal_validity_note": "代码仅校验外部记录结构；授权签字人与合同法律效力须由人工及权威系统确认。",
        "next_action": ("HUMAN_KICKOFF_RELEASE_AND_STAGE10_EXTERNAL_ONBOARDING" if complete
                        else "CLOSE_CONTRACTING_EVIDENCE_GAPS"),
    }


def render_report(report: dict) -> str:
    if report["status"] == "REAL_PAID_DISCOVERY_NOT_READY":
        return f"""# Stage 18 Design Partner Acquisition & Contracting

状态：`{report['status']}`。

- 合成候选：{report['candidate_count']}；达到资格线：{report['qualified_candidate_count']}。
- 教学选中候选：`{report['training_selected_candidate_id']}`，评分 {report['training_selected_score']}/100。
- 真实具名 Design Partner：0；真实合同：0；真实回款：CNY 0.00。
- 外部签约证据：0/{report['external_evidence_required_count']}。
- 下一决定：`{report['decision']}`。

教学候选只能训练团队，不能成为客户事实。真实合同、授权、PO、账单资料和联系人信息应保存在客户、CRM、合同或采购系统中；仓库只保存脱敏引用。
"""
    gaps = report["missing_evidence"] + report["invalid_evidence"] + report["expired_evidence"]
    gap_lines = "\n".join(f"- `{item}`" for item in gaps) or "- 无结构性缺口"
    return f"""# Stage 18 External Contract Preflight

状态：`{report['status']}`；客户公开标签：`{report['partner_public_label']}`。

- 外部证据：{report['evidence_received_count']}/{report['evidence_required_count']}。
- 外部记录宣称合同已执行：{report['contract_execution_asserted']}。
- 释放审批缺失：{len(report['release_missing_roles'])}。
- 代码验证法律效力：False。

## 结构性缺口

{gap_lines}

{report['legal_validity_note']}
"""


def write_demo_outputs(output: Path | str, report: dict) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "stage18-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "stage18-report.md").write_text(render_report(report), encoding="utf-8")
    with (output / "candidate-shortlist.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        fields = ("candidate_id", "display_name", "score", "qualified", "decision")
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in report["candidate_results"]:
            writer.writerow({key: row[key] for key in fields})


def prepare_partner_pack(output: Path | str, template: dict) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "external-partner-manifest.json").write_text(
        json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rows = [
        ("Confirm legal entity and NDA route", "fde_commercial_owner", "customer_procurement_owner"),
        ("Confirm sponsor, problem and paid scope", "fde_delivery_owner", "customer_sponsor"),
        ("Close MSA/SOW/DPA/security path", "fde_legal_or_procurement_owner", "customer_security_owner"),
        ("Receive PO/equivalent and billing profile", "fde_commercial_owner", "customer_procurement_owner"),
        ("Approve kickoff release", "fde_delivery_owner", "customer_process_owner"),
    ]
    with (output / "mutual-action-plan.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(("action", "fde_owner", "customer_owner", "target_date", "status", "evidence_ref"))
        for action, fde_owner, customer_owner in rows:
            writer.writerow((action, fde_owner, customer_owner, "", "open", ""))


def write_preflight_outputs(output: Path | str, report: dict) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "contract-preflight.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "contract-preflight.md").write_text(render_report(report), encoding="utf-8")
