import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fde_stage3.audit import AuditError, report_stage2, report_stage3

SOURCE = ROOT / 'stages/03-data-boundary/data'


class StageAuditTests(unittest.TestCase):
    def test_stage2_and_stage3_references_are_consistent(self):
        self.assertEqual(report_stage2(ROOT)['deliverable_count'], 6)
        result = report_stage3(ROOT)
        self.assertEqual(result['status'], 'DESIGN_READY_FOR_REVIEW')
        self.assertEqual(result['counts']['golden_categories'],
                         {'normal': 10, 'history': 3, 'complex': 5, 'failure': 2})
        self.assertEqual(result['detected_product_conflict_fields'],
                         ['flow_max', 'flow_min', 'head_max', 'head_min', 'material'])
        self.assertIn('真实预测输出与 Release Gate 实测', result['unresolved'])

    def test_sensitive_data_cannot_be_sent_to_model_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / 'data'
            shutil.copytree(SOURCE, copied)
            path = copied / 'manifest.json'
            doc = json.loads(path.read_text())
            next(x for x in doc['sources'] if x['id'] == 'SRC-DISC')['model_context'] = 'approved_extract_only'
            path.write_text(json.dumps(doc), encoding='utf-8')
            with self.assertRaisesRegex(AuditError, '高敏感'):
                report_stage3(ROOT, copied)

    def test_broken_mail_pair_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / 'data'
            shutil.copytree(SOURCE, copied)
            path = copied / 'golden.json'
            doc = json.loads(path.read_text())
            doc['cases'][0]['reply_path'] = 'bundle/replies/reply_002.eml'
            path.write_text(json.dumps(doc), encoding='utf-8')
            with self.assertRaisesRegex(AuditError, '配对错误'):
                report_stage3(ROOT, copied)

    def test_unapproved_final_candidate_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / 'data'
            shutil.copytree(SOURCE, copied)
            path = copied / 'golden.json'
            doc = json.loads(path.read_text())
            doc['cases'][0]['preferred_candidate'] = 'CP90'
            path.write_text(json.dumps(doc), encoding='utf-8')
            with self.assertRaisesRegex(AuditError, '最终型号'):
                report_stage3(ROOT, copied)

    def test_provisional_customer_identity_stays_manual(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / 'data'
            shutil.copytree(SOURCE, copied)
            path = copied / 'identity.json'
            doc = json.loads(path.read_text())
            doc['entities'][0]['autolink_allowed'] = True
            path.write_text(json.dumps(doc), encoding='utf-8')
            with self.assertRaisesRegex(AuditError, '自动关联'):
                report_stage3(ROOT, copied)

    def test_product_conflict_must_name_all_differing_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / 'data'
            shutil.copytree(SOURCE, copied)
            path = copied / 'conflicts.json'
            doc = json.loads(path.read_text())
            doc[0]['fields'].remove('material')
            path.write_text(json.dumps(doc), encoding='utf-8')
            with self.assertRaisesRegex(AuditError, 'material'):
                report_stage3(ROOT, copied)

    def test_all_stages_cli_runs_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run([sys.executable, str(ROOT / 'stage_pipeline.py'), 'all',
                                  '--output-root', tmp], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue((Path(tmp) / 'stage-01/metrics.json').is_file())
            self.assertEqual(json.loads((Path(tmp) / 'stage-03/audit.json').read_text())['status'],
                             'DESIGN_READY_FOR_REVIEW')


if __name__ == '__main__':
    unittest.main()
