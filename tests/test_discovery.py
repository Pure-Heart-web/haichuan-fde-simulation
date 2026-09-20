import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fde_discovery.core import DataError, gate, load, metrics, validate
from fde_discovery.report import render

INPUT = ROOT / 'stages/01-discovery/data/simulation.json'


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.data = load(INPUT)

    def test_hand_calculated_baseline(self):
        m = metrics(self.data)
        self.assertEqual(m['sales_active_minutes']['total'], 202)
        self.assertAlmostEqual(m['sales_active_minutes']['mean'], 202 / 6)
        self.assertEqual(m['complex_active_minutes']['mean'], 51)
        self.assertAlmostEqual(m['simple_active_minutes']['mean'], 49 / 3)
        self.assertEqual(m['complex_step_mean_minutes']['selection'], 15)
        self.assertEqual(m['engineer_total_minutes'], 56)
        self.assertEqual(m['escalation_ratio'], 0.5)
        self.assertIsNone(m['engineer_daily_consultations'])
        self.assertEqual(m['first_reply_minutes']['mean'], 560 / 6)
        self.assertEqual(m['first_reply_minutes']['p90'], 165)

    def test_training_gate_never_approves_real_work(self):
        self.assertEqual(gate(self.data)['status'], 'SIMULATION_READY')
        self.data['mode'] = 'real'
        with self.assertRaisesRegex(DataError, '模拟证据'):
            validate(self.data, INPUT.parent)
        for source in self.data['sources']:
            source['origin'] = 'real'
        validate(self.data, INPUT.parent)
        self.assertEqual(gate(self.data)['status'], 'REAL_REVIEW_REQUIRED')

    def test_missing_role_and_unconfirmed_cost_block_gate(self):
        self.data['interviews'] = self.data['interviews'][:2]
        self.data['checks']['error_cost']['confirmed'] = False
        validate(self.data, INPUT.parent)
        g = gate(self.data)
        self.assertEqual(g['status'], 'NEEDS_MORE_DISCOVERY')
        self.assertEqual(sum(not row['passed'] for row in g['checks']), 2)

    def test_empty_observations_produce_gap_not_zero_average(self):
        self.data['observations'] = []
        validate(self.data, INPUT.parent)
        m = metrics(self.data)
        self.assertIsNone(m['sales_active_minutes']['mean'])
        self.assertIsNone(m['escalation_ratio'])
        self.assertFalse(gate(self.data)['complete'])

    def test_no_complex_cases_blocks_bottleneck_confirmation(self):
        self.data['observations'] = self.data['observations'][:3]
        self.assertIsNone(metrics(self.data)['complex_active_minutes']['mean'])
        self.assertFalse(gate(self.data)['complete'])

    def test_invalid_observation_variants(self):
        changes = [
            lambda o: o['steps'].pop('quote'),
            lambda o: o['steps'].update(quote=-1),
            lambda o: o['steps'].update(quote=float('nan')),
            lambda o: o['steps'].update(quote=True),
            lambda o: o['steps'].update(quote=1000),
            lambda o: o.update(source_id='missing'),
            lambda o: o.update(first_reply_at='2026-09-14T08:00:00+08:00'),
            lambda o: o.update(first_reply_at='2026-09-14T09:25:00'),
            lambda o: o.update(engineer_minutes=5),
            lambda o: o.update(escalated=True, escalation_reason=''),
        ]
        for change in changes:
            with self.subTest(change=change):
                d = copy.deepcopy(self.data)
                change(d['observations'][0])
                with self.assertRaises(DataError):
                    validate(d, INPUT.parent)

    def test_duplicate_case_and_source_ids_rejected(self):
        for key in ('observations', 'sources'):
            with self.subTest(key=key):
                d = copy.deepcopy(self.data)
                d[key].append(copy.deepcopy(d[key][0]))
                with self.assertRaises(DataError):
                    validate(d, INPUT.parent)

    def test_missing_file_and_unsupported_confirmation_rejected(self):
        self.data['sources'][0]['path'] = 'not-found.md'
        with self.assertRaises(DataError):
            validate(self.data, INPUT.parent)
        self.data = load(INPUT)
        self.data['checks']['error_cost']['source_ids'] = []
        with self.assertRaises(DataError):
            validate(self.data, INPUT.parent)

    def test_unknown_information_does_not_require_fake_evidence(self):
        self.data['assessment']['evidence'].append(dict(type='Unknown', text='尚需核查', source_ids=[]))
        validate(self.data, INPUT.parent)

    def test_timezone_offsets_represent_same_elapsed_duration(self):
        self.data['observations'][0]['received_at'] = '2026-09-14T01:00:00+00:00'
        validate(self.data, INPUT.parent)
        self.assertAlmostEqual(metrics(self.data)['first_reply_minutes']['mean'], 560 / 6)

    def test_report_has_six_deliverables_and_evidence_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            render(self.data, INPUT, tmp)
            out = Path(tmp)
            self.assertEqual(len(list(out.glob('0*.md'))), 6)
            saved = json.loads((out / 'metrics.json').read_text())
            self.assertEqual(saved['gate']['status'], 'SIMULATION_READY')
            for file in out.glob('*.md'):
                self.assertIn('模拟数据', file.read_text())
            self.assertIn('session-notes.md', (out / 'evidence-index.md').read_text())

    def test_cli_failure_does_not_create_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'invalid.json'
            path.write_text('{broken', encoding='utf-8')
            output = Path(tmp) / 'report'
            run = subprocess.run([sys.executable, str(ROOT / 'run.py'), 'analyze', '--input', str(path), '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertFalse(output.exists())

    def test_cli_gap_generates_report_and_returns_three(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.data['interviews'] = []
            for source in self.data['sources']:
                source['path'] = str(INPUT.parent / source['path'])
            path = Path(tmp) / 'partial.json'
            path.write_text(json.dumps(self.data), encoding='utf-8')
            output = Path(tmp) / 'report'
            run = subprocess.run([sys.executable, str(ROOT / 'run.py'), 'analyze', '--input', str(path), '--output', str(output)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 3, run.stderr)
            self.assertTrue((output / 'exit-review.md').exists())


if __name__ == '__main__':
    unittest.main()
