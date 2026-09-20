import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))

from stage8 import tenant_domains
from stage8_vertical import DATA, inbound_events, prepare, report
from fde_platform.core.platform.effort import EffortLog
from fde_platform.core.platform.episode import EpisodeJournal
from fde_platform.core.platform.tenant_store import TenantStore


class VerticalSliceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.output = Path(self.temp.name)
        self.store = TenantStore(self.output / 'platform.sqlite3', tenant_domains())

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def journal(self, tenant):
        return EpisodeJournal(self.store.scope(tenant, tenant_domains()[tenant]))

    def test_both_domains_share_review_contract_and_preserve_evidence(self):
        stats = prepare(self.store, self.output)
        self.assertEqual(stats, {'newly_received': 2, 'duplicate_events_in_fixture': 1})
        reviews = json.loads((DATA / 'scripted-reviews.json').read_text())['reviews']
        outcomes = json.loads((DATA / 'outcomes.json').read_text())['outcomes']
        for item in reviews:
            journal = self.journal(item['tenant_id'])
            episode = journal.list()[0]
            self.assertEqual(episode['state'], 'pending_review')
            self.assertIsNotNone(journal.session.get('case_record', episode['case_record_id']))
            with self.assertRaisesRegex(ValueError, '先完成'):
                journal.close(episode['episode_id'], next(x for x in outcomes if x['case_id'] == item['case_id']))
            with self.assertRaisesRegex(ValueError, '无权'):
                journal.record_edit(episode['episode_id'], actor_id='intruder',
                                    actor_role=item['actor_role'], edited_action='人工修改', reason='测试')
            self.assertEqual(len(journal.session.feedback(episode['review_task_id'])), 0)
            journal.record_edit(episode['episode_id'], actor_id=item['actor_id'],
                                actor_role=item['actor_role'], edited_action=item['edited_action'],
                                reason=item['reason'])
            outcome = next(x for x in outcomes if x['case_id'] == item['case_id'])
            journal.close(episode['episode_id'], outcome)
            self.assertEqual([x['event_type'] for x in journal.events(episode['episode_id'])],
                ['inbound_received', 'case_created', 'proposal_ready', 'human_edited', 'outcome_recorded'])
            self.assertEqual(len(journal.session.feedback(episode['review_task_id'])), 1)
        result = report(self.store, self.output)
        self.assertEqual(result['closed_count'], 2)
        self.assertTrue(result['shared_event_sequence'])
        by_case = {x['case_id']: x for x in result['episodes']}
        self.assertIn('WO-QH-110', by_case['QH-001']['evidence_refs'])
        self.assertIn('S6-ORD-002', by_case['P7-003']['evidence_refs'])
        self.assertEqual(by_case['QH-001']['top_option'], 'review_maintenance_work_order')
        self.assertEqual(by_case['P7-003']['top_option'], 'CP90')
        self.assertIsNone(self.journal('haichuan-training').get(by_case['QH-001']['episode_id']))
        self.assertEqual(result['human_effort']['comparison_status'], 'INSUFFICIENT_LOGGED_HUMAN_EFFORT')
        self.assertFalse(result['delivery_time_savings_proven'])

    def test_duplicate_and_changed_metadata_are_rejected(self):
        prepare(self.store, self.output)
        event = inbound_events()[0]
        journal = self.journal(event['tenant_id'])
        original = journal.list()[0]
        duplicate, created = journal.receive(event)
        self.assertFalse(created)
        self.assertEqual(original['episode_id'], duplicate['episode_id'])
        self.assertEqual(len(journal.events(original['episode_id'])), 3)
        changed = dict(event, as_of='2026-09-22')
        with self.assertRaisesRegex(ValueError, '内容已改变'):
            journal.receive(changed)
        with self.assertRaisesRegex(ValueError, '租户不匹配'):
            self.journal('haichuan-training').receive(event)

    def test_feedback_and_episode_event_rollback_together(self):
        prepare(self.store, self.output)
        journal = self.journal('qihang-training')
        episode = journal.list()[0]
        with patch.object(journal, '_append', side_effect=RuntimeError('disk failure')):
            with self.assertRaisesRegex(RuntimeError, 'disk failure'):
                journal.record_edit(episode['episode_id'], actor_id='engineer-chen',
                                    actor_role='engineer', edited_action='人工修改', reason='测试回滚')
        self.assertEqual(journal.get(episode['episode_id'])['state'], 'pending_review')
        self.assertEqual(journal.session.feedback(episode['review_task_id']), [])
        self.assertEqual(len(journal.events(episode['episode_id'])), 3)

    def test_outcome_requires_scoped_and_chronological_source(self):
        prepare(self.store, self.output)
        journal = self.journal('qihang-training')
        episode = journal.list()[0]
        journal.record_edit(episode['episode_id'], actor_id='engineer-chen',
                            actor_role='engineer', edited_action='人工修改', reason='测试')
        outcome = json.loads((DATA / 'outcomes.json').read_text())['outcomes'][0]
        with self.assertRaisesRegex(ValueError, '租户或案例'):
            journal.close(episode['episode_id'], dict(outcome, tenant_id='haichuan-training'))
        with self.assertRaisesRegex(ValueError, '早于输入'):
            journal.close(episode['episode_id'], dict(outcome, recorded_at='2026-09-20T10:00:00+08:00'))
        self.assertEqual(journal.get(episode['episode_id'])['state'], 'reviewed')

    def test_cli_demo_is_idempotent_and_effort_is_operator_recorded(self):
        cli_output = self.output / 'cli'
        for _ in range(2):
            run = subprocess.run([sys.executable, str(ROOT / 'stage8_vertical.py'), 'demo',
                                  '--check-baseline', '--output', str(cli_output)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
        report_data = json.loads((cli_output / 'episode-report.json').read_text())
        self.assertEqual([len(x['events']) for x in report_data['episodes']], [5, 5])
        effort = EffortLog(cli_output / 'delivery-effort.jsonl')
        started = effort.start(domain='after_sales', phase='integration', actor='learner',
                               activity='检查模拟接入')
        self.assertIn(started['activity_id'], effort.summary()['open_activity_ids'])
        effort.stop(started['activity_id'])
        self.assertEqual(len(effort.summary()['completed']), 1)
        self.assertEqual(effort.summary()['comparison_status'], 'INSUFFICIENT_LOGGED_HUMAN_EFFORT')
        other = effort.start(domain='foreign_trade', phase='integration', actor='learner',
                             activity='检查模拟邮件接入')
        effort.stop(other['activity_id'])
        self.assertEqual(effort.summary()['comparison_status'], 'DESCRIPTIVE_ONLY')
        self.assertFalse(effort.summary()['causal_savings_proven'])


if __name__ == '__main__':
    unittest.main()
