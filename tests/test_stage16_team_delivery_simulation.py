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

from stage16 import BASELINE, REFERENCE, SCENARIO, check_baseline, run_demo
from fde_platform.simulation import SimulationError, load_json, prepare_simulation, score_submission


class TeamDeliverySimulationTests(unittest.TestCase):
    def setUp(self):
        self.scenario = load_json(SCENARIO)
        self.submission = load_json(REFERENCE)
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_reference_team_and_every_member_meet_supervised_standard(self):
        report = score_submission(self.scenario, self.submission)
        self.assertTrue(check_baseline(report))
        self.assertEqual(report["final_score"], 93)
        self.assertEqual(report["technically_responsible_count"], 6)
        self.assertTrue(all(row["readiness"] == "TECHNICALLY_RESPONSIBLE"
                            for row in report["individual_readiness"].values()))
        self.assertFalse(report["real_customer_data_used"])
        self.assertEqual(report["external_customer_actions"], 0)

    def test_critical_control_failure_caps_team_and_individual_readiness(self):
        changed = copy.deepcopy(self.submission)
        changed["control_results"][1]["status"] = "failed"
        report = score_submission(self.scenario, changed)
        self.assertEqual(report["raw_score"], 93)
        self.assertEqual(report["final_score"], 59)
        self.assertEqual(report["status"], "TEAM_NOT_READY_CRITICAL_CONTROL_FAILURE")
        self.assertEqual(report["technically_responsible_count"], 0)

    def test_team_score_cannot_hide_missing_individual_responsibility_evidence(self):
        changed = copy.deepcopy(self.submission)
        changed["individual_contributions"] = [row for row in changed["individual_contributions"]
            if not (row["member_id"] == "M03" and row["type"] == "operational_action")]
        report = score_submission(self.scenario, changed)
        self.assertEqual(report["final_score"], 93)
        self.assertEqual(report["individual_readiness"]["M03"]["readiness"],
                         "SUPERVISED_PRACTICE_REQUIRED")
        self.assertIn("operational_action",
                      report["individual_readiness"]["M03"]["missing_contribution_types"])
        self.assertEqual(report["status"], "TEAM_ITERATE_BEFORE_CUSTOMER_DELIVERY")

    def test_every_role_artifact_and_independent_review_is_required(self):
        missing_role = copy.deepcopy(self.submission)
        missing_role["members"][5]["roles"] = []
        with self.assertRaisesRegex(SimulationError, "未分配交付角色"):
            score_submission(self.scenario, missing_role)
        self_review = copy.deepcopy(self.submission)
        self_review["artifacts"][0]["reviewers"] = ["M01"]
        with self.assertRaisesRegex(SimulationError, "另一成员审阅"):
            score_submission(self.scenario, self_review)
        missing_artifact = copy.deepcopy(self.submission)
        missing_artifact["artifacts"].pop()
        with self.assertRaisesRegex(SimulationError, "缺少交付物"):
            score_submission(self.scenario, missing_artifact)

    def test_prepare_separates_participant_and_facilitator_information(self):
        manifest = prepare_simulation(ROOT / "stages/16-team-delivery-simulation", self.output)
        self.assertEqual(manifest["status"], "TEAM_SIMULATION_PACK_READY")
        participant = self.output / "participant-pack"
        facilitator = self.output / "facilitator-pack"
        self.assertTrue((participant / "public-brief.md").is_file())
        self.assertTrue((participant / "role-fde-technical-lead.md").is_file())
        self.assertFalse((participant / "injects.json").exists())
        self.assertTrue((facilitator / "injects.json").is_file())
        self.assertTrue((facilitator / "reference-submission.json").is_file())

    def test_assessment_must_reference_real_delivery_evidence(self):
        changed = copy.deepcopy(self.submission)
        changed["assessments"][0]["evidence_refs"] = ["EV-NOT-REAL"]
        with self.assertRaisesRegex(SimulationError, "不存在的证据"):
            score_submission(self.scenario, changed)

    def test_individual_accountability_requires_two_external_assessors(self):
        changed = copy.deepcopy(self.submission)
        changed["members"][0]["accountability_assessors"] = ["M01", "facilitator-business"]
        with self.assertRaisesRegex(SimulationError, "两名非本人评委"):
            score_submission(self.scenario, changed)

    def test_cli_demo_and_outputs(self):
        result = subprocess.run([sys.executable, str(ROOT / "stage16.py"), "demo",
            "--check-baseline", "--output", str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("技术负责就绪 6/6", result.stdout)
        self.assertTrue((self.output / "team-score.md").is_file())
        self.assertTrue((self.output / "simulation-pack/pack-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
