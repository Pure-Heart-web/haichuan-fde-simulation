import copy
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from stage15 import DEFAULT_DEAL, check_baseline, run_demo
from fde_platform.commercial import DealValidationError, analyze_deal, load_deal, write_outputs


class CommercialDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.deal = load_deal(DEFAULT_DEAL)
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_example_is_qualified_but_not_contracted_or_shadow_ready(self):
        report = analyze_deal(self.deal)
        self.assertTrue(check_baseline(report))
        self.assertEqual(report["current_approved_gate"], "A_OPPORTUNITY_QUALIFIED")
        self.assertEqual(report["next_gate"], "B_PAID_DISCOVERY_CONTRACTED")
        self.assertEqual(report["booked_value_cny"], "0.00")
        self.assertFalse(report["actual_customer_contract_signed"])
        self.assertFalse(report["authorized_shadow_ready"])
        self.assertFalse(report["production_go_live_ready"])

    def test_outputs_include_report_invoice_plan_and_evidence_register(self):
        report = write_outputs(self.deal, self.output)
        self.assertEqual(report["invoice_milestone_count"], 10)
        for name in ("commercial-readiness.json", "commercial-readiness.md",
                     "invoice-plan.csv", "evidence-register.csv"):
            self.assertTrue((self.output / name).is_file(), name)
        with (self.output / "invoice-plan.csv").open(encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 10)
        self.assertEqual(sum(float(row["amount_cny"]) for row in rows), 1480000.0)
        text = (self.output / "commercial-readiness.md").read_text(encoding="utf-8")
        self.assertIn("不构成报价、合同、客户授权、收入确认", text)

    def test_cannot_approve_gate_with_draft_evidence(self):
        changed = copy.deepcopy(self.deal)
        changed["gates"][1]["status"] = "approved"
        changed["gates"][1]["approvals"] = [{"role": "customer_sponsor"}]
        with self.assertRaisesRegex(DealValidationError, "未接受证据"):
            analyze_deal(changed)

    def test_cannot_skip_a_gate(self):
        changed = copy.deepcopy(self.deal)
        changed["gates"][2]["status"] = "approved"
        changed["gates"][2]["approvals"] = [{"role": "customer_sponsor"}]
        for evidence in changed["evidence"]:
            if evidence["evidence_id"] in changed["gates"][2]["required_evidence"]:
                evidence["status"] = "accepted"
        with self.assertRaisesRegex(DealValidationError, "不得越过前置 Gate"):
            analyze_deal(changed)

    def test_shadow_gate_requires_commercial_data_security_uat_and_incident_evidence(self):
        changed = copy.deepcopy(self.deal)
        gate = changed["gates"][2]
        gate["required_evidence"].remove("EV-INCIDENT-PLAN")
        gate["status"] = "approved"
        gate["approvals"] = [{"role": "customer_sponsor"}]
        changed["gates"][1]["status"] = "approved"
        changed["gates"][1]["approvals"] = [{"role": "customer_sponsor"}]
        for evidence in changed["evidence"]:
            if evidence["evidence_id"] in set(changed["gates"][1]["required_evidence"] + gate["required_evidence"]):
                evidence["status"] = "accepted"
        with self.assertRaisesRegex(DealValidationError, "Shadow Gate 缺少"):
            analyze_deal(changed)

    def test_payment_percentages_and_synthetic_baselines_are_guarded(self):
        bad_payment = copy.deepcopy(self.deal)
        bad_payment["phases"][0]["payment_milestones"][0]["percent"] = 40
        with self.assertRaisesRegex(DealValidationError, "付款比例合计"):
            analyze_deal(bad_payment)
        bad_metric = copy.deepcopy(self.deal)
        bad_metric["success_metrics"][0]["customer_baseline"] = 22
        with self.assertRaisesRegex(DealValidationError, "合成值"):
            analyze_deal(bad_metric)

    def test_phase_cannot_claim_contract_without_commercial_gate(self):
        changed = copy.deepcopy(self.deal)
        changed["phases"][0]["commercial_status"] = "contracted"
        with self.assertRaisesRegex(DealValidationError, "商业状态与 Gate B 不一致"):
            analyze_deal(changed)

    def test_cli_demo(self):
        result = subprocess.run([sys.executable, str(ROOT / "stage15.py"), "demo",
            "--output", str(self.output), "--check-baseline"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("真实收入声明 false", result.stdout)


if __name__ == "__main__":
    unittest.main()
