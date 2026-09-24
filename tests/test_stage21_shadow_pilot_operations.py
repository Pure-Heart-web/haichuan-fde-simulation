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

from stage21 import (EXTERNAL_TEMPLATE, REHEARSAL, STAGE, check_baseline, run_demo)
from fde_platform.shadowpilotops import (
    ShadowPilotError, analyze_rehearsal, digest, load_json,
    prepare_external_pack, preflight_external_pilot,
)


class ShadowPilotOperationsTests(unittest.TestCase):
    def setUp(self):
        self.record = load_json(REHEARSAL)
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def rebind_start(self, record):
        scope = {"pilot": record["pilot"],
                 "mobilization_requirements": record["mobilization_requirements"],
                 "roster": record["roster"], "versions": record["versions"],
                 "metric_targets": record["metric_targets"]}
        sha = digest(scope)
        record["start_authorization"]["scope_sha256"] = sha
        for row in record["start_authorization"]["approvals"]:
            row["content_sha256"] = sha

    def rebind_bundle(self, record):
        evidence = {"scope_sha256": record["start_authorization"]["scope_sha256"],
                    "state_transitions": record["state_transitions"],
                    "incidents": record["incidents"],
                    "daily_gates": record["daily_gates"],
                    "case_events": record["case_events"],
                    "metric_targets": record["metric_targets"]}
        sha = digest(evidence)
        record["evidence_bundle"]["bundle_sha256"] = sha
        for row in record["evidence_bundle"]["approvals"]:
            row["content_sha256"] = sha

    def external_record(self):
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
        record["stage20_release"].update({
            "status": "READY_FOR_HUMAN_PILOT_START_REVIEW",
            "decision_record_ref": "DECISION-SYS:STAGE20-001",
            "human_start_authorized": True,
            "authorized_by_role": "customer_sponsor",
        })
        record["pilot"]["pilot_id"] = "PILOT-EXT-021"
        record["pilot"]["tenant_ref"] = "tenant-ref-alpha"
        version_map = {row["component_type"]: row["version"]
                       for row in record["versions"]}
        operators = [row["user_ref"] for row in record["roster"]
                     if row["role"] == "operator"]
        for index, row in enumerate(record["case_events"]):
            row["tenant_ref"] = record["pilot"]["tenant_ref"]
            row["operator_ref"] = operators[index % len(operators)]
            row["versions"] = version_map
            row["source_event_ref"] = f"EVENT-SYS:{index + 1}"
            row["trace_ref"] = f"TRACE-SYS:{index + 1}"
            row["outcome_ref"] = f"OUTCOME-SYS:{index + 1}"
        self.rebind_start(record)
        self.rebind_bundle(record)
        return record

    def write_external(self, record):
        path = self.output / "external-shadow-pilot.json"
        path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return path

    def test_reference_pilot_completes_without_real_or_external_actions(self):
        report = analyze_rehearsal(STAGE, self.record)
        self.assertTrue(check_baseline(report))
        self.assertEqual(report["processed_case_count"], 30)
        self.assertEqual(report["pause_count"], 1)
        self.assertEqual(report["metric_pass_count"], 6)
        self.assertEqual(report["external_sent_count"], 0)
        self.assertEqual(report["customer_write_count"], 0)
        self.assertFalse(report["real_pilot"])
        self.assertFalse(report["production_authorized"])

    def test_stage20_source_and_start_scope_are_digest_bound(self):
        changed = copy.deepcopy(self.record)
        changed["source_stage20_sha256"] = "0" * 64
        with self.assertRaisesRegex(ShadowPilotError, "Stage 20 来源"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["pilot"]["case_cap"] = 1
        with self.assertRaisesRegex(ShadowPilotError, "启动授权未绑定"):
            analyze_rehearsal(STAGE, changed)

    def test_mobilization_training_and_role_coverage_are_required(self):
        changed = copy.deepcopy(self.record)
        changed["mobilization_requirements"][0]["status"] = "open"
        self.rebind_start(changed); self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "尚未全部 Ready"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["roster"][0]["training_status"] = "pending"
        self.rebind_start(changed); self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "尚未完成培训"):
            analyze_rehearsal(STAGE, changed)

    def test_state_machine_requires_pause_remediation_and_resume(self):
        changed = copy.deepcopy(self.record)
        changed["state_transitions"].pop(3)
        self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "状态机缺少"):
            analyze_rehearsal(STAGE, changed)

    def test_ready_gate_cannot_hide_failed_check_and_paused_day_cannot_process(self):
        changed = copy.deepcopy(self.record)
        changed["daily_gates"][0]["checks"]["roster_covered"] = False
        self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "错误标记 Ready"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["case_events"][0]["pilot_date"] = "2026-11-19"
        self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "暂停日仍处理"):
            analyze_rehearsal(STAGE, changed)

    def test_case_requires_ready_gate_and_stop_threshold_is_enforced(self):
        changed = copy.deepcopy(self.record)
        changed["case_events"][0]["pilot_date"] = "2026-11-22"
        self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "缺少 Ready Daily Gate"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        for row in changed["metric_targets"]:
            if row["metric_id"] == "field_quality":
                row["target"] = 0.995
                row["stop_threshold"] = 0.99
        self.rebind_start(changed); self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "Stop Threshold"):
            analyze_rehearsal(STAGE, changed)

    def test_cross_tenant_version_drift_and_external_actions_are_blocked(self):
        changed = copy.deepcopy(self.record)
        changed["case_events"][0]["tenant_ref"] = "other-tenant"
        self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "跨租户"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["case_events"][0]["versions"]["model"] = "unapproved"
        self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "版本漂移"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["case_events"][0]["external_sent"] = True
        self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "Shadow 边界"):
            analyze_rehearsal(STAGE, changed)

    def test_unsafe_action_and_unresolved_incident_cannot_complete(self):
        changed = copy.deepcopy(self.record)
        changed["case_events"][0]["unsafe_actions"] = 1
        self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "危险动作"):
            analyze_rehearsal(STAGE, changed)
        changed = copy.deepcopy(self.record)
        changed["incidents"][0]["status"] = "open"
        self.rebind_bundle(changed)
        with self.assertRaisesRegex(ShadowPilotError, "尚未解决"):
            analyze_rehearsal(STAGE, changed)

    def test_evidence_bundle_is_content_bound(self):
        changed = copy.deepcopy(self.record)
        changed["case_events"][0]["review_minutes"] = 999
        with self.assertRaisesRegex(ShadowPilotError, "Evidence Bundle 摘要"):
            analyze_rehearsal(STAGE, changed)

    def test_external_manifest_must_stay_outside_repository(self):
        with self.assertRaisesRegex(ShadowPilotError, "Git 仓库之外"):
            preflight_external_pilot(EXTERNAL_TEMPLATE, ROOT)

    def test_complete_external_record_only_reaches_human_acceptance_review(self):
        report = preflight_external_pilot(
            self.write_external(self.external_record()), ROOT)
        self.assertEqual(report["status"], "READY_FOR_HUMAN_PILOT_ACCEPTANCE_REVIEW")
        self.assertTrue(report["external_record_asserts_real_pilot"])
        self.assertFalse(report["real_pilot_verified_by_code"])
        self.assertFalse(report["pilot_acceptance_recorded"])
        self.assertFalse(report["production_authorized"])
        self.assertNotIn("DECISION-SYS:STAGE20-001", json.dumps(report))

    def test_external_record_does_not_require_an_incident_that_never_happened(self):
        record = self.external_record()
        record["state_transitions"] = [
            record["state_transitions"][0], record["state_transitions"][1],
            record["state_transitions"][2], record["state_transitions"][7],
        ]
        record["incidents"] = []
        record["daily_gates"] = [row for row in record["daily_gates"]
                                 if row["status"] == "ready"]
        self.rebind_bundle(record)
        report = preflight_external_pilot(self.write_external(record), ROOT)
        self.assertEqual(report["pause_count"], 0)
        self.assertEqual(report["resolved_incident_count"], 0)

    def test_external_record_rejects_names_and_missing_human_start(self):
        record = self.external_record()
        record["roster"][0]["person_name"] = "Private Person"
        self.rebind_start(record); self.rebind_bundle(record)
        with self.assertRaisesRegex(ShadowPilotError, "不保存姓名"):
            preflight_external_pilot(self.write_external(record), ROOT)
        record = self.external_record()
        record["stage20_release"]["human_start_authorized"] = False
        with self.assertRaisesRegex(ShadowPilotError, "人工 Pilot 启动授权"):
            preflight_external_pilot(self.write_external(record), ROOT)

    def test_prepare_and_cli_outputs(self):
        prepare_external_pack(self.output, load_json(EXTERNAL_TEMPLATE))
        self.assertTrue((self.output / "external-shadow-pilot.json").is_file())
        self.assertTrue((self.output / "daily-gates.csv").is_file())
        report = run_demo(self.output / "demo", check=True)
        self.assertEqual(report["external_sent_count"], 0)
        result = subprocess.run([
            sys.executable, str(ROOT / "stage21.py"), "demo", "--check-baseline",
            "--output", str(self.output / "cli")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("发送 0；写入 0", result.stdout)


if __name__ == "__main__":
    unittest.main()
