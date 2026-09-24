import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from stage22 import EXTERNAL_TEMPLATE, REHEARSAL, STAGE, check_baseline, run_demo
from fde_platform.pilotacceptance import (
    PilotAcceptanceError, analyze_rehearsal, digest, load_json,
    prepare_external_pack, preflight_external_decision,
)


class PilotAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.record = load_json(REHEARSAL)
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def rebind_acceptance(self, record):
        scope = {key: record[key] for key in (
            "pilot_summary", "acceptance_criteria", "acceptance_conditions",
            "residual_risks")}
        sha = digest(scope)
        record["acceptance_record"]["content_sha256"] = sha
        for row in record["acceptance_record"]["approvals"]:
            row["content_sha256"] = sha

    def rebind_decision(self, record):
        decision = record["production_decision"]
        scope = {
            "acceptance_sha256": record["acceptance_record"]["content_sha256"],
            "decision": decision["decision"], "rationale": decision["rationale"],
            "dissent": decision["dissent"],
            "production_readiness": record["production_readiness"],
            "launch_plan": record["launch_plan"],
        }
        sha = digest(scope)
        decision["decision_record"]["content_sha256"] = sha
        for row in decision["decision_record"]["approvals"]:
            row["content_sha256"] = sha

    def external_record(self, *, all_ready=True):
        record = load_json(EXTERNAL_TEMPLATE)

        def replace(value):
            if isinstance(value, dict):
                return {key: replace(child) for key, child in value.items()}
            if isinstance(value, list):
                return [replace(child) for child in value]
            if isinstance(value, str) and value.upper().startswith(("REPLACE", "PENDING")):
                return "EXTERNAL-SYSTEM:REFERENCE"
            return value

        record = replace(record)
        record["partner_public_label"] = "Design Partner Alpha"
        record["stage21_release"].update({
            "evidence_bundle_ref": "EVIDENCE-SYS:BUNDLE-021",
            "human_verified": True,
            "verified_by_role": "customer_process_owner",
            "verified_at": "2026-12-01T10:00:00+08:00",
        })
        record["pilot_summary"].update({
            "pilot_id": "PILOT-EXT-022", "evidence_bundle_id": "BUNDLE-EXT-021",
            "evidence_bundle_sha256": "a" * 64, "case_count": 120, "user_count": 8,
        })
        actuals = {row["criterion_id"]: source["actual"] for row, source in zip(
            record["acceptance_criteria"], self.record["acceptance_criteria"])}
        for row in record["acceptance_criteria"]:
            row["actual"] = actuals[row["criterion_id"]]
            row["source_ref"] = f"METRIC-SYS:{row['criterion_id']}"
        if all_ready:
            for row in record["production_readiness"]:
                row["status"] = "ready"
        self.rebind_acceptance(record)
        self.rebind_decision(record)
        return record

    def write_external(self, record):
        path = self.output / "external-pilot-acceptance.json"
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return path

    def test_reference_accepts_pilot_but_does_not_authorize_production(self):
        report = analyze_rehearsal(STAGE, self.record)
        self.assertTrue(check_baseline(report))
        self.assertEqual(report["accepted_criteria_count"], 6)
        self.assertEqual(report["production_readiness_ready_count"], 7)
        self.assertFalse(report["production_authorized"])
        self.assertFalse(report["automatic_external_send_authorized"])

    def test_stage21_source_is_digest_bound(self):
        changed = copy.deepcopy(self.record)
        changed["source_stage21_sha256"] = "0" * 64
        with self.assertRaisesRegex(PilotAcceptanceError, "Stage 21 来源"):
            analyze_rehearsal(STAGE, changed)

    def test_all_six_acceptance_criteria_must_pass(self):
        changed = copy.deepcopy(self.record)
        changed["acceptance_criteria"][0]["actual"] = 0.1
        changed["acceptance_criteria"][0]["decision"] = "simulated_rejected"
        self.rebind_acceptance(changed); self.rebind_decision(changed)
        with self.assertRaisesRegex(PilotAcceptanceError, "Production Evaluation 要求"):
            analyze_rehearsal(STAGE, changed)

    def test_conditions_must_close_on_time(self):
        changed = copy.deepcopy(self.record)
        changed["acceptance_conditions"][0]["status"] = "open"
        changed["acceptance_conditions"][0]["closure_evidence_ref"] = None
        changed["acceptance_conditions"][0]["closed_at"] = None
        self.rebind_acceptance(changed); self.rebind_decision(changed)
        with self.assertRaisesRegex(PilotAcceptanceError, "Production Evaluation 要求"):
            analyze_rehearsal(STAGE, changed)

    def test_acceptance_and_decision_are_content_bound(self):
        changed = copy.deepcopy(self.record)
        changed["residual_risks"][0]["mitigation"] = "changed"
        with self.assertRaisesRegex(PilotAcceptanceError, "acceptance record 未绑定"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["production_readiness"][0]["status"] = "simulated_ready"
        with self.assertRaisesRegex(PilotAcceptanceError, "Production decision record 未绑定"):
            analyze_rehearsal(STAGE, changed)

    def test_critical_open_risk_and_incomplete_control_set_are_blocked(self):
        changed = copy.deepcopy(self.record)
        changed["residual_risks"][0].update({"severity": "critical", "status": "open"})
        self.rebind_acceptance(changed); self.rebind_decision(changed)
        with self.assertRaisesRegex(PilotAcceptanceError, "Critical 风险"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["production_readiness"].pop()
        self.rebind_decision(changed)
        with self.assertRaisesRegex(PilotAcceptanceError, "十项控制不完整"):
            analyze_rehearsal(STAGE, changed)

    def test_launch_plan_cannot_enable_actions_before_authorization(self):
        changed = copy.deepcopy(self.record)
        changed["launch_plan"]["automatic_external_send"] = True
        self.rebind_decision(changed)
        with self.assertRaisesRegex(PilotAcceptanceError, "不得开启自动发送"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["production_authorization"]["authorized"] = True
        with self.assertRaisesRegex(PilotAcceptanceError, "不得把投资决定写成生产授权"):
            analyze_rehearsal(STAGE, changed)

    def test_external_manifest_must_be_outside_repository(self):
        with self.assertRaisesRegex(PilotAcceptanceError, "Git 仓库之外"):
            preflight_external_decision(EXTERNAL_TEMPLATE, ROOT)

    def test_complete_external_record_only_reaches_human_authorization_review(self):
        report = preflight_external_decision(
            self.write_external(self.external_record()), ROOT)
        self.assertEqual(report["status"], "READY_FOR_HUMAN_PRODUCTION_AUTHORIZATION_REVIEW")
        self.assertTrue(report["external_record_asserts_real_pilot"])
        self.assertFalse(report["real_pilot_verified_by_code"])
        self.assertFalse(report["pilot_acceptance_verified_by_code"])
        self.assertFalse(report["production_authorized"])
        self.assertNotIn("EVIDENCE-SYS:BUNDLE-021", json.dumps(report))

    def test_external_open_controls_remain_in_evaluation(self):
        report = preflight_external_decision(
            self.write_external(self.external_record(all_ready=False)), ROOT)
        self.assertEqual(report["status"], "PRODUCTION_EVALUATION_OPEN")
        self.assertEqual(report["production_readiness_ready_count"], 0)

    def test_open_high_risk_blocks_human_authorization_review(self):
        record = self.external_record()
        record["residual_risks"][0]["status"] = "open"
        self.rebind_acceptance(record); self.rebind_decision(record)
        report = preflight_external_decision(self.write_external(record), ROOT)
        self.assertEqual(report["status"], "PRODUCTION_EVALUATION_OPEN")
        self.assertEqual(report["blocking_risk_count"], 1)

    def test_external_requires_human_source_verification_and_privacy(self):
        record = self.external_record()
        record["stage21_release"]["human_verified"] = False
        with self.assertRaisesRegex(PilotAcceptanceError, "人工真实性复核"):
            preflight_external_decision(self.write_external(record), ROOT)
        record = self.external_record()
        record["privacy_assertions"]["contains_person_names_or_emails"] = True
        with self.assertRaisesRegex(PilotAcceptanceError, "隐私"):
            preflight_external_decision(self.write_external(record), ROOT)

    def test_stop_iterate_and_extend_are_distinct(self):
        expected = {
            "stop": "PILOT_STOP_DECISION_RECORDED",
            "iterate": "PILOT_ITERATION_REQUIRED",
            "extend_shadow": "SHADOW_EXTENSION_REQUIRES_NEW_AUTHORIZATION",
        }
        for decision, status in expected.items():
            record = self.external_record(all_ready=False)
            record["production_decision"]["decision"] = decision
            self.rebind_decision(record)
            report = preflight_external_decision(self.write_external(record), ROOT)
            self.assertEqual(report["status"], status)

    def test_stop_can_preserve_failed_metric_and_open_condition(self):
        record = self.external_record(all_ready=False)
        record["acceptance_criteria"][0]["actual"] = 0.1
        record["acceptance_criteria"][0]["decision"] = "rejected"
        record["acceptance_conditions"] = []
        record["production_decision"]["decision"] = "stop"
        self.rebind_acceptance(record); self.rebind_decision(record)
        report = preflight_external_decision(self.write_external(record), ROOT)
        self.assertEqual(report["status"], "PILOT_STOP_DECISION_RECORDED")
        self.assertEqual(report["accepted_criteria_count"], 5)

    def test_prepare_and_cli_outputs(self):
        prepare_external_pack(self.output, load_json(EXTERNAL_TEMPLATE))
        self.assertTrue((self.output / "external-pilot-acceptance.json").is_file())
        self.assertTrue((self.output / "residual-risk-register.csv").is_file())
        report = run_demo(self.output / "demo", check=True)
        self.assertFalse(report["production_authorized"])
        result = subprocess.run([
            sys.executable, str(ROOT / "stage22.py"), "demo", "--check-baseline",
            "--output", str(self.output / "cli")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("生产授权 False", result.stdout)


if __name__ == "__main__":
    unittest.main()
