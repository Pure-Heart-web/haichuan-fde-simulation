import copy
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from stage18 import (MANIFEST_TEMPLATE, PIPELINE, check_baseline, run_demo)
from fde_platform.partnercontracting import (
    ContractingError,
    analyze_candidate_pipeline,
    load_json,
    preflight_external_manifest,
    prepare_partner_pack,
)


class DesignPartnerContractingTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = load_json(PIPELINE)
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def complete_manifest(self):
        manifest = load_json(MANIFEST_TEMPLATE)
        manifest["partner"].update({
            "legal_entity_ref": "CONTRACT-SYS:ENTITY-123",
            "public_label": "Design Partner Alpha",
            "crm_account_ref": "CRM:ACCOUNT-123",
        })
        manifest["offer"].update({
            "offer_id": "OFFER-123",
            "scope_ref": "CONTRACT-SYS:SOW-123:v3",
            "target_kickoff_date": "2026-10-15",
        })
        for index, evidence in enumerate(manifest["evidence"], 1):
            evidence.update({
                "status": "accepted",
                "evidence_ref": f"SYS:EVIDENCE-{index:02d}",
                "verified_at": "2026-09-24",
            })
        manifest["contract_execution_assertion"].update({
            "status": "executed",
            "asserted_at": "2026-09-24",
            "asserted_by_role": "fde_legal_owner",
            "evidence_ref": "CONTRACT-SYS:EXECUTED-123",
        })
        for index, approval in enumerate(manifest["release_approvals"], 1):
            approval.update({
                "status": "approved",
                "approved_at": "2026-09-24",
                "evidence_ref": f"APPROVAL-SYS:{index}",
            })
        return manifest

    def write_manifest(self, manifest):
        path = self.output / "external-manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return path

    def test_reference_pipeline_has_no_real_customer_or_contract_claim(self):
        report = analyze_candidate_pipeline(self.pipeline)
        self.assertTrue(check_baseline(report))
        self.assertEqual(report["training_selected_score"], 85)
        self.assertEqual(report["named_real_design_partner_count"], 0)
        self.assertFalse(report["external_contract_record_complete"])
        self.assertFalse(report["legally_verified_by_code"])
        self.assertEqual(len(report["external_evidence_missing"]), 10)

    def test_disqualifier_blocks_even_a_high_scoring_candidate(self):
        changed = copy.deepcopy(self.pipeline)
        selected = changed["candidates"][0]
        selected["disqualifiers"] = ["requires_unreviewed_auto_send"]
        with self.assertRaisesRegex(ContractingError, "合格候选"):
            analyze_candidate_pipeline(changed)

    def test_synthetic_pipeline_cannot_claim_real_commercial_events(self):
        changed = copy.deepcopy(self.pipeline)
        changed["real_world_assertions"]["real_contracts_executed"] = 1
        with self.assertRaisesRegex(ContractingError, "不得声明真实客户"):
            analyze_candidate_pipeline(changed)

    def test_real_manifest_must_stay_outside_repository(self):
        with self.assertRaisesRegex(ContractingError, "Git 仓库之外"):
            preflight_external_manifest(MANIFEST_TEMPLATE, ROOT,
                                        as_of=date(2026, 9, 24))

    def test_complete_external_record_reaches_kickoff_but_not_legal_verification(self):
        report = preflight_external_manifest(
            self.write_manifest(self.complete_manifest()), ROOT,
            as_of=date(2026, 9, 24))
        self.assertEqual(report["status"], "READY_FOR_PAID_DISCOVERY_KICKOFF")
        self.assertTrue(report["external_contract_record_complete"])
        self.assertTrue(report["contract_execution_asserted"])
        self.assertFalse(report["legally_verified_by_code"])
        self.assertNotIn("CONTRACT-SYS:ENTITY-123", json.dumps(report))

    def test_missing_expired_or_unapproved_evidence_blocks_release(self):
        manifest = self.complete_manifest()
        manifest["evidence"].pop()
        manifest["evidence"][0]["expires_at"] = "2026-09-23"
        manifest["release_approvals"][0]["status"] = "pending"
        report = preflight_external_manifest(self.write_manifest(manifest), ROOT,
                                             as_of=date(2026, 9, 24))
        self.assertEqual(report["status"], "EXTERNAL_CONTRACT_RECORD_INCOMPLETE")
        self.assertIn("kickoff_commitment", report["missing_evidence"])
        self.assertIn("legal_entity_verification", report["expired_evidence"])
        self.assertIn("fde_commercial_owner", report["release_invalid_roles"])

    def test_external_offer_must_bind_supported_stage17_version(self):
        manifest = self.complete_manifest()
        manifest["offer"]["stage17_offer_version"] = "uncontrolled-draft"
        with self.assertRaisesRegex(ContractingError, "Stage 17 版本"):
            preflight_external_manifest(self.write_manifest(manifest), ROOT,
                                        as_of=date(2026, 9, 24))

    def test_prepare_creates_fillable_manifest_and_mutual_action_plan(self):
        prepare_partner_pack(self.output, load_json(MANIFEST_TEMPLATE))
        self.assertTrue((self.output / "external-partner-manifest.json").is_file())
        self.assertTrue((self.output / "mutual-action-plan.csv").is_file())
        prepared = load_json(self.output / "external-partner-manifest.json")
        self.assertEqual(len(prepared["evidence"]), 10)

    def test_demo_cli_and_outputs(self):
        report = run_demo(self.output, check=True)
        self.assertEqual(report["status"], "REAL_PAID_DISCOVERY_NOT_READY")
        self.assertTrue((self.output / "stage18-report.md").is_file())
        self.assertTrue((self.output / "candidate-shortlist.csv").is_file())
        result = subprocess.run([
            sys.executable, str(ROOT / "stage18.py"), "demo", "--check-baseline",
            "--output", str(self.output / "cli")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("真实具名客户 0", result.stdout)
        self.assertIn("真实合同 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
