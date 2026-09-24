import copy
import csv
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from stage17 import (ACCEPTANCE, CHANGES, CONTRACT, DEPENDENCIES, STAGE,
                     check_baseline, run_demo)
from fde_platform.deliverycontrol import (DeliveryControlError, analyze_delivery,
                                          load_json)
from fde_platform.deliverycontrol.discovery import digest


class PaidDiscoveryDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.contract = load_json(CONTRACT)
        self.acceptance = load_json(ACCEPTANCE)
        self.dependencies = load_json(DEPENDENCIES)
        self.changes = load_json(CHANGES)
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def analyze(self, contract=None, acceptance=None, dependencies=None, changes=None,
                stage_root=STAGE):
        return analyze_delivery(stage_root, contract or self.contract,
            acceptance or self.acceptance, dependencies or self.dependencies,
            changes or self.changes)

    def test_reference_paid_discovery_is_accepted_without_real_world_overclaim(self):
        report = self.analyze()
        self.assertTrue(check_baseline(report))
        self.assertEqual(report["accepted_deliverable_count"], 6)
        self.assertEqual(report["simulated_invoice_eligible_cny"], "120000.00")
        self.assertEqual(report["delivery_cost_cny"], "72800.00")
        self.assertEqual(report["simulated_gross_margin_percent"], "39.33")
        self.assertFalse(report["real_contract_signed"])
        self.assertFalse(report["actual_invoice_created"])
        self.assertEqual(report["actual_cash_received_cny"], "0.00")
        self.assertFalse(report["authorized_shadow_ready"])
        self.assertEqual(len(report["next_gate_open_dependencies"]), 8)

    def test_contract_changes_require_new_bound_approvals(self):
        changed = copy.deepcopy(self.contract)
        changed["commercial"]["fee_cny"] = 1
        with self.assertRaisesRegex(DeliveryControlError, "合同内容摘要"):
            self.analyze(contract=changed)
        missing = copy.deepcopy(self.contract)
        missing["approvals"].pop()
        with self.assertRaisesRegex(DeliveryControlError, "合同签核角色"):
            self.analyze(contract=missing)

    def test_deliverable_tampering_invalidates_acceptance(self):
        stages = self.output / "stages"
        shutil.copytree(STAGE, stages / STAGE.name)
        target15 = stages / "15-commercial-delivery/data"
        target15.mkdir(parents=True)
        shutil.copy2(ROOT / "stages/15-commercial-delivery/data/haichuan-deal-record.json",
                     target15 / "haichuan-deal-record.json")
        copied_stage = stages / STAGE.name
        (copied_stage / "deliverables/01-problem-scope-and-raci.md").write_text(
            "tampered\n", encoding="utf-8")
        with self.assertRaisesRegex(DeliveryControlError, "内容被修改"):
            analyze_delivery(copied_stage,
                load_json(copied_stage / "data/synthetic-contract.json"),
                load_json(copied_stage / "data/synthetic-acceptance.json"),
                load_json(copied_stage / "data/dependency-register.json"),
                load_json(copied_stage / "data/change-requests.json"))

    def test_open_discovery_dependency_blocks_acceptance(self):
        changed = copy.deepcopy(self.dependencies)
        changed["dependencies"][0]["status"] = "open"
        with self.assertRaisesRegex(DeliveryControlError, "依赖尚未全部关闭"):
            self.analyze(dependencies=changed)

    def test_unapproved_change_cannot_enter_delivered_scope(self):
        changed = copy.deepcopy(self.acceptance)
        changed["delivered_scope"].append("erp_write")
        with self.assertRaisesRegex(DeliveryControlError, "合同外"):
            self.analyze(acceptance=changed)

    def test_acceptance_cannot_rewrite_metrics_or_claim_real_cash(self):
        metric = copy.deepcopy(self.acceptance)
        metric["metric_freeze"]["post_hoc_changes_allowed"] = True
        with self.assertRaisesRegex(DeliveryControlError, "禁止事后改口径"):
            self.analyze(acceptance=metric)
        money = copy.deepcopy(self.contract)
        money["commercial"]["actual_invoice_created"] = True
        controlled = {key: value for key, value in money.items()
                      if key not in {"approvals", "contract_sha256"}}
        money["contract_sha256"] = digest(controlled)
        for approval in money["approvals"]:
            approval["content_sha256"] = money["contract_sha256"]
        rebound_acceptance = copy.deepcopy(self.acceptance)
        rebound_acceptance["contract_sha256"] = money["contract_sha256"]
        controlled_acceptance = {key: value for key, value in rebound_acceptance.items()
                                 if key not in {"approvals", "bundle_sha256"}}
        rebound_acceptance["bundle_sha256"] = digest(controlled_acceptance)
        for approval in rebound_acceptance["approvals"]:
            approval["content_sha256"] = rebound_acceptance["bundle_sha256"]
        with self.assertRaisesRegex(DeliveryControlError, "真实开票或回款"):
            self.analyze(contract=money, acceptance=rebound_acceptance)

    def test_demo_outputs_milestone_ledger_without_invoice_ids(self):
        report = run_demo(self.output, check=True)
        self.assertEqual(report["actual_cash_received_cny"], "0.00")
        with (self.output / "milestone-ledger.csv").open(encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(not row["actual_invoice_id"] for row in rows))
        self.assertTrue((self.output / "stage17-report.md").is_file())

    def test_cli_demo(self):
        result = subprocess.run([sys.executable, str(ROOT / "stage17.py"), "demo",
            "--check-baseline", "--output", str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("实际回款 0", result.stdout)
        self.assertIn("Shadow 未授权", result.stdout)


if __name__ == "__main__":
    unittest.main()
