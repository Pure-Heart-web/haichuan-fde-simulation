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

from stage19 import (EXTERNAL_TEMPLATE, REHEARSAL, check_baseline, run_demo)
from fde_platform.discoveryexecution import (
    DiscoveryExecutionError,
    analyze_rehearsal,
    load_json,
    prepare_external_pack,
    preflight_external_execution,
)


class LiveDiscoveryExecutionTests(unittest.TestCase):
    def setUp(self):
        self.record = load_json(REHEARSAL)
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def external_record(self):
        record = load_json(EXTERNAL_TEMPLATE)
        record["partner_public_label"] = "Design Partner Alpha"
        record["stage18_contract_release"].update({
            "preflight_status": "READY_FOR_PAID_DISCOVERY_KICKOFF",
            "contract_record_ref": "CONTRACT-SYS:EXECUTED-SOW-19",
            "human_legal_validity_verified": True,
            "verified_by_role": "fde_legal_owner",
        })
        record["engagement"].update({
            "engagement_id": "DISC-EXT-001",
            "stage18_release_ref": "STAGE18-RELEASE-001",
            "scope_ref": "CONTRACT-SYS:SOW-19:SCOPE",
        })
        for row in record["fieldwork_role_confirmations"]:
            row["status"] = "confirmed"
            row["evidence_ref"] = f"CRM:ROLE:{row['role']}"
        for row in record["fieldwork_sessions"]:
            row["status"] = "completed"
            row["evidence_ref"] = f"FIELDWORK:{row['session_id']}"
        for row in record["evidence_register"]:
            row["source_ref"] = f"EVIDENCE-SYS:{row['evidence_id']}"
            if row["statement_type"] == "customer_fact":
                row["status"] = "customer_confirmed"
                row["confirmation_ref"] = f"CRM:CONFIRM:{row['evidence_id']}"
            elif row["statement_type"] == "fde_inference":
                row["status"] = "supported"
        for row in record["baseline"]["metrics"]:
            row["denominator_policy"] = f"POLICY:{row['metric_id']}"
            row["measurement_ref"] = f"MEASUREMENT-SYS:{row['metric_id']}"
        for row in record["baseline"]["approvals"]:
            row["status"] = "approved"
            row["evidence_ref"] = f"APPROVAL-SYS:{row['role']}"
        for row in record["dependencies"]:
            row["status"] = "closed"
            row["evidence_ref"] = f"DEPENDENCY-SYS:{row['dependency_id']}"
        record["change_requests"][0].update({
            "requested_scope": "No scope change; tracking record retained",
            "schedule_impact": "none",
            "fee_impact": "none",
        })
        for row in record["deliverables"]:
            row["status"] = "ready_for_acceptance"
            row["artifact_ref"] = f"DOCUMENT-SYS:{row['deliverable_id']}"
            row["acceptance_criteria_ref"] = f"SOW:{row['deliverable_id']}"
        record["time_ledger"][0].update({
            "hours": 112,
            "loaded_rate_cny": 855.357142857,
            "workstream": "paid_discovery",
            "evidence_ref": "TIMESHEET-SYS:DISC-EXT-001",
        })
        return record

    def write_external(self, record):
        path = self.output / "external-discovery.json"
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return path

    def test_reference_rehearsal_is_ready_without_real_world_claims(self):
        report = analyze_rehearsal(self.record)
        self.assertTrue(check_baseline(report))
        self.assertEqual(report["session_count"], 8)
        self.assertEqual(report["ready_deliverable_count"], 6)
        self.assertEqual(report["logged_hours"], "112.00")
        self.assertEqual(report["delivery_cost_cny"], "95800.00")
        self.assertEqual(report["real_customer_sessions"], 0)
        self.assertEqual(report["actual_cash_received_cny"], "0.00")

    def test_synthetic_record_cannot_claim_customer_activity_or_cash(self):
        changed = copy.deepcopy(self.record)
        changed["real_world_assertions"]["real_customer_sessions"] = 8
        with self.assertRaisesRegex(DiscoveryExecutionError, "不得声明真实客户"):
            analyze_rehearsal(changed)

    def test_all_eight_fieldwork_types_are_required(self):
        changed = copy.deepcopy(self.record)
        changed["fieldwork_sessions"].pop()
        with self.assertRaisesRegex(DiscoveryExecutionError, "现场活动缺失"):
            analyze_rehearsal(changed)

    def test_baseline_must_be_frozen_and_fact_backed(self):
        changed = copy.deepcopy(self.record)
        changed["baseline"]["post_hoc_changes_allowed"] = True
        with self.assertRaisesRegex(DiscoveryExecutionError, "禁止事后修改"):
            analyze_rehearsal(changed)
        changed = copy.deepcopy(self.record)
        changed["baseline"]["metrics"][0]["source_evidence_id"] = "E-I001"
        with self.assertRaisesRegex(DiscoveryExecutionError, "已确认客户事实"):
            analyze_rehearsal(changed)

    def test_open_hypothesis_cannot_be_used_as_deliverable_conclusion(self):
        changed = copy.deepcopy(self.record)
        changed["deliverables"][5]["evidence_ids"].append("E-H002")
        with self.assertRaisesRegex(DiscoveryExecutionError, "开放假设写成结论"):
            analyze_rehearsal(changed)

    def test_open_dependency_and_unapproved_change_block(self):
        changed = copy.deepcopy(self.record)
        changed["dependencies"][0]["status"] = "open"
        with self.assertRaisesRegex(DiscoveryExecutionError, "未关闭依赖"):
            analyze_rehearsal(changed)
        changed = copy.deepcopy(self.record)
        changed["change_requests"][0]["decision"] = "approved"
        with self.assertRaisesRegex(DiscoveryExecutionError, "缺少证据"):
            analyze_rehearsal(changed)

    def test_external_record_must_be_outside_repo_and_contract_human_verified(self):
        with self.assertRaisesRegex(DiscoveryExecutionError, "Git 仓库之外"):
            preflight_external_execution(EXTERNAL_TEMPLATE, ROOT)
        record = self.external_record()
        record["stage18_contract_release"]["human_legal_validity_verified"] = False
        with self.assertRaisesRegex(DiscoveryExecutionError, "人工真实性复核"):
            preflight_external_execution(self.write_external(record), ROOT)

    def test_external_template_placeholders_cannot_pass_as_evidence(self):
        record = self.external_record()
        record["deliverables"][0]["artifact_ref"] = "REPLACE_WITH_DOCUMENT"
        with self.assertRaisesRegex(DiscoveryExecutionError, "模板占位符"):
            preflight_external_execution(self.write_external(record), ROOT)

    def test_complete_external_record_reaches_human_acceptance_review_only(self):
        report = preflight_external_execution(
            self.write_external(self.external_record()), ROOT)
        self.assertEqual(report["status"], "READY_FOR_HUMAN_DISCOVERY_ACCEPTANCE_REVIEW")
        self.assertFalse(report["customer_acceptance_recorded"])
        self.assertFalse(report["pilot_authorized"])
        self.assertFalse(report["legally_verified_by_code"])
        self.assertEqual(report["ready_deliverable_count"], 6)
        self.assertNotIn("CONTRACT-SYS:EXECUTED-SOW-19", json.dumps(report))

    def test_external_manifest_rejects_customer_values_and_person_names(self):
        record = self.external_record()
        record["baseline"]["metrics"][0]["value"] = 420
        with self.assertRaisesRegex(DiscoveryExecutionError, "不应复制客户基线数值"):
            preflight_external_execution(self.write_external(record), ROOT)
        record = self.external_record()
        record["time_ledger"][0]["person_name"] = "Private Person"
        with self.assertRaisesRegex(DiscoveryExecutionError, "不应包含人员姓名"):
            preflight_external_execution(self.write_external(record), ROOT)

    def test_prepare_and_cli_outputs(self):
        prepare_external_pack(self.output, load_json(EXTERNAL_TEMPLATE))
        self.assertTrue((self.output / "external-discovery-execution.json").is_file())
        self.assertTrue((self.output / "evidence-register.csv").is_file())
        report = run_demo(self.output / "demo", check=True)
        self.assertEqual(report["real_customer_sessions"], 0)
        result = subprocess.run([
            sys.executable, str(ROOT / "stage19.py"), "demo", "--check-baseline",
            "--output", str(self.output / "cli")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("真实客户活动 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
