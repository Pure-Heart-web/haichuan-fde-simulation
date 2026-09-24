import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from stage20 import (EXTERNAL_TEMPLATE, REHEARSAL, STAGE, check_baseline, run_demo)
from fde_platform.acceptanceinvestment import (
    AcceptanceInvestmentError,
    analyze_rehearsal,
    digest,
    load_json,
    prepare_external_pack,
    preflight_external_decision,
)


class AcceptanceInvestmentTests(unittest.TestCase):
    def setUp(self):
        self.record = load_json(REHEARSAL)
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def rebind_acceptance(self, record):
        acceptance = record["acceptance"]
        controlled = {key: value for key, value in acceptance.items()
                      if key not in {"approvals", "bundle_sha256"}}
        bundle_sha = digest(controlled)
        acceptance["bundle_sha256"] = bundle_sha
        for row in acceptance["approvals"]:
            row["content_sha256"] = bundle_sha
        record["steering"]["acceptance_bundle_sha256"] = bundle_sha
        return bundle_sha

    def rebind_steering(self, record):
        steering = record["steering"]
        controlled = {key: value for key, value in steering.items()
                      if key not in {"approvals", "decision_sha256"}}
        decision_sha = digest(controlled)
        steering["decision_sha256"] = decision_sha
        for row in steering["approvals"]:
            row["content_sha256"] = decision_sha

    def external_record(self, *, decision="PILOT", ready=False):
        record = load_json(EXTERNAL_TEMPLATE)

        def replace(value):
            if isinstance(value, dict):
                return {key: replace(child) for key, child in value.items()}
            if isinstance(value, list):
                return [replace(child) for child in value]
            if isinstance(value, str) and value.upper().startswith(("REPLACE", "PENDING")):
                return "EXTERNAL-SYSTEM:REFERENCE"
            if value == "NONE":
                return "EXTERNAL-SYSTEM:REFERENCE"
            return value

        record = replace(record)
        record["partner_public_label"] = "Design Partner Alpha"
        record["engagement_id"] = "ENG-EXT-020"
        record["stage19_release"].update({
            "status": "READY_FOR_HUMAN_DISCOVERY_ACCEPTANCE_REVIEW",
            "execution_record_ref": "DELIVERY-SYS:STAGE19-001",
            "human_verified": True,
            "verified_by_role": "customer_acceptance_owner",
        })
        for row in record["acceptance"]["deliverable_decisions"]:
            row["status"] = "accepted"
            row["artifact_sha256"] = hashlib.sha256(
                row["deliverable_id"].encode("utf-8")).hexdigest()
        for row in record["acceptance"]["conditions"]:
            row["status"] = "closed"
            row["closure_evidence_ref"] = f"DELIVERY-SYS:{row['condition_id']}"
        for row in record["acceptance"]["approvals"]:
            row["status"] = "approved"
            row["evidence_ref"] = f"APPROVAL-SYS:{row['role']}"
        self.rebind_acceptance(record)

        record["steering"]["decision"] = decision
        for row in record["steering"]["approvals"]:
            row["status"] = "approved"
            row["evidence_ref"] = f"STEERING-SYS:{row['role']}"
        self.rebind_steering(record)

        if ready:
            record["pilot_plan"]["sow_status"] = "executed"
            for row in record["pilot_plan"]["mobilization_requirements"]:
                row["status"] = "ready"
                row["evidence_ref"] = f"MOBILIZATION-SYS:{row['requirement_id']}"
        return record

    def write_external(self, record):
        path = self.output / "external-acceptance.json"
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return path

    def test_reference_accepts_discovery_but_does_not_authorize_pilot(self):
        report = analyze_rehearsal(STAGE, self.record)
        self.assertTrue(check_baseline(report))
        self.assertEqual(report["accepted_deliverable_count"], 6)
        self.assertEqual(report["closed_acceptance_condition_count"], 2)
        self.assertEqual(report["base_case_net_benefit_cny"], "140000.00")
        self.assertFalse(report["pilot_sow_executed"])
        self.assertEqual(report["mobilization_ready_count"], 0)
        self.assertFalse(report["pilot_authorized"])
        self.assertFalse(report["real_customer_acceptance"])

    def test_stage19_source_and_deliverable_content_are_digest_bound(self):
        changed = copy.deepcopy(self.record)
        changed["source_stage19_sha256"] = "0" * 64
        with self.assertRaisesRegex(AcceptanceInvestmentError, "来源摘要"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["acceptance"]["deliverable_decisions"][0]["artifact_sha256"] = "0" * 64
        self.rebind_acceptance(changed)
        self.rebind_steering(changed)
        with self.assertRaisesRegex(AcceptanceInvestmentError, "内容已变化"):
            analyze_rehearsal(STAGE, changed)

    def test_open_condition_or_missing_acceptance_history_blocks_final_acceptance(self):
        changed = copy.deepcopy(self.record)
        changed["acceptance"]["conditions"][0]["status"] = "open"
        self.rebind_acceptance(changed)
        self.rebind_steering(changed)
        with self.assertRaisesRegex(AcceptanceInvestmentError, "条件尚未关闭"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["acceptance"]["decision_history"] = changed["acceptance"]["decision_history"][:1]
        self.rebind_acceptance(changed)
        self.rebind_steering(changed)
        with self.assertRaisesRegex(AcceptanceInvestmentError, "验收历史"):
            analyze_rehearsal(STAGE, changed)

    def test_acceptance_and_steering_signatures_are_content_bound(self):
        changed = copy.deepcopy(self.record)
        changed["acceptance"]["bundle_version"] = "silently-changed"
        with self.assertRaisesRegex(AcceptanceInvestmentError, "验收包摘要"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["steering"]["decision"] = "simulated_stop"
        with self.assertRaisesRegex(AcceptanceInvestmentError, "决定摘要"):
            analyze_rehearsal(STAGE, changed)

    def test_business_case_uses_actual_cost_and_separates_assumptions(self):
        changed = copy.deepcopy(self.record)
        changed["business_case"]["discovery_actual_cost"] = 1
        with self.assertRaisesRegex(AcceptanceInvestmentError, "实际成本"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["business_case"]["scenarios"][1]["assumption_refs"] = []
        with self.assertRaisesRegex(AcceptanceInvestmentError, "区分事实与假设"):
            analyze_rehearsal(STAGE, changed)

    def test_pilot_plan_requires_six_metrics_and_full_payment_split(self):
        changed = copy.deepcopy(self.record)
        changed["pilot_plan"]["success_metrics"].pop()
        with self.assertRaisesRegex(AcceptanceInvestmentError, "成功指标不完整"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["pilot_plan"]["payment_milestones"][0]["percent"] = 10
        with self.assertRaisesRegex(AcceptanceInvestmentError, "比例合计"):
            analyze_rehearsal(STAGE, changed)

    def test_external_manifest_must_stay_outside_repository(self):
        with self.assertRaisesRegex(AcceptanceInvestmentError, "Git 仓库之外"):
            preflight_external_decision(EXTERNAL_TEMPLATE, ROOT)

    def test_external_pilot_decision_without_sow_and_mobilization_is_not_ready(self):
        report = preflight_external_decision(
            self.write_external(self.external_record()), ROOT)
        self.assertEqual(report["status"], "PILOT_NOT_READY")
        self.assertEqual(report["steering_decision"], "PILOT")
        self.assertFalse(report["pilot_sow_executed"])
        self.assertFalse(report["pilot_authorized_by_code"])

    def test_complete_external_mobilization_only_reaches_human_start_review(self):
        report = preflight_external_decision(
            self.write_external(self.external_record(ready=True)), ROOT)
        self.assertEqual(report["status"], "READY_FOR_HUMAN_PILOT_START_REVIEW")
        self.assertEqual(report["mobilization_ready_count"], 10)
        self.assertFalse(report["pilot_authorized_by_code"])
        self.assertFalse(report["customer_acceptance_legally_verified_by_code"])
        self.assertNotIn("DELIVERY-SYS:STAGE19-001", json.dumps(report))

    def test_external_stop_and_iterate_have_distinct_outcomes(self):
        stop = preflight_external_decision(
            self.write_external(self.external_record(decision="STOP")), ROOT)
        self.assertEqual(stop["status"], "DISCOVERY_CLOSED_STOP")
        iterate = preflight_external_decision(
            self.write_external(self.external_record(decision="ITERATE")), ROOT)
        self.assertEqual(iterate["status"], "ADDITIONAL_DISCOVERY_REQUIRED")

    def test_external_billing_claim_requires_finance_reference(self):
        record = self.external_record()
        record["billing_release"]["invoice_status"] = "created"
        record["billing_release"]["invoice_record_ref"] = None
        with self.assertRaisesRegex(AcceptanceInvestmentError, "财务系统引用"):
            preflight_external_decision(self.write_external(record), ROOT)

    def test_prepare_and_cli_outputs(self):
        prepare_external_pack(self.output, load_json(EXTERNAL_TEMPLATE))
        self.assertTrue((self.output / "external-acceptance-investment.json").is_file())
        self.assertTrue((self.output / "mobilization-register.csv").is_file())
        report = run_demo(self.output / "demo", check=True)
        self.assertFalse(report["pilot_authorized"])
        result = subprocess.run([
            sys.executable, str(ROOT / "stage20.py"), "demo", "--check-baseline",
            "--output", str(self.output / "cli")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Pilot 授权 False", result.stdout)


if __name__ == "__main__":
    unittest.main()
