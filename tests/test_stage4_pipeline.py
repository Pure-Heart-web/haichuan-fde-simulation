import json
from email.message import EmailMessage
from pathlib import Path
import re
import select
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fde_platform.core.extraction import extract
from fde_platform.core.ingestion import from_eml, from_text
from fde_platform.core.models import ExtractionConfig
from fde_platform.core.store import Store
from fde_platform.domains.foreign_trade.normalization import DomainValidationError, normalize_flow, normalize_temperature, to_record
from fde_platform.evals.runner import evaluate
from fde_platform.pipeline import process


class SprintOneTests(unittest.TestCase):
    def test_html_email_and_attachment_detection(self):
        msg = EmailMessage()
        msg['From'] = 'buyer@example.com'
        msg['To'] = 'sales@example.com'
        msg['Subject'] = 'Cooling pump'
        msg['Date'] = 'Mon, 14 Sep 2026 09:00:00 +0800'
        msg.set_content('<html><body><p>Flow 85 m3/h, Head 38m.</p><script>Flow 999 m3/h</script></body></html>', subtype='html')
        msg.add_attachment(b'not parsed', maintype='application', subtype='octet-stream', filename='requirements.xlsx')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'sample.eml'
            path.write_bytes(msg.as_bytes())
            work = from_eml(path)
        self.assertEqual(work.body_format, 'html')
        self.assertIn('Flow 85 m3/h', work.body)
        self.assertNotIn('999', work.body)
        self.assertEqual(work.attachments[0]['filename'], 'requirements.xlsx')
        result, record = process(work)
        self.assertEqual(result.status, 'extracted')
        self.assertEqual(record.flow_m3h, 85)
        self.assertIn('attachment_processing_required', record.missing_fields)

    def test_units_and_no_silent_default(self):
        self.assertEqual(normalize_flow(1416, 'L/min'), 84.96)
        self.assertEqual(normalize_flow(85, 'm³/h'), 85)
        self.assertEqual(normalize_temperature(107.6, '°F'), 42)
        work = from_text('Centrifugal pump, Flow 85 m3/h, Head 38m, 380V/60Hz.', source_id='T1')
        _, record = process(work)
        self.assertEqual(record.frequency_hz, 60)
        self.assertEqual(record.evidence['frequency_hz']['text'], '60Hz')
        _, missing_frequency = process(from_text('Centrifugal pump, 380V, Flow 85 m3/h.', source_id='T2'))
        self.assertIsNone(missing_frequency.frequency_hz)
        self.assertIsNone(work.received_at)

    def test_missing_email_date_stays_unknown(self):
        msg = EmailMessage()
        msg['From'] = 'buyer@example.com'
        msg['Subject'] = 'Pump'
        msg.set_content('Need 2 pcs centrifugal pump.')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'undated.eml'
            path.write_bytes(msg.as_bytes())
            work = from_eml(path)
        self.assertIsNone(work.received_at)

    def test_chinese_english_and_evidence_offsets(self):
        work = from_text('离心泵 inquiry, 介质冷却水, 流量 85 m³/h, 扬程 38 m, 数量 6 台, 380V/50Hz, 目的港 Jebel Ali。', source_id='ZH1')
        result, record = process(work)
        self.assertEqual(result.status, 'extracted')
        self.assertEqual(record.product_type, 'centrifugal_pump')
        self.assertEqual(record.medium_category, 'water')
        self.assertEqual(record.quantity, 6)
        self.assertEqual(record.destination_port, 'Jebel Ali')
        for evidence in record.evidence.values():
            self.assertEqual(work.body[evidence['start']:evidence['end']], evidence['text'])

    def test_retry_once_then_failed_or_success(self):
        class Provider:
            model_version = 'fake-v1'
            def __init__(self, values):
                self.values = list(values)
            def complete(self, work_item, prompt_version):
                return self.values.pop(0)
        work = from_text('Need pump', source_id='R1')
        config = ExtractionConfig('prompt-v1', 'fake-v1')
        success = extract(work, Provider(['broken', '{}']), config)
        self.assertEqual((success.status, success.attempts), ('extracted', 2))
        failure = extract(work, Provider(['broken', 'still broken']), config)
        self.assertEqual((failure.status, failure.attempts), ('failed', 2))
        self.assertEqual(len(failure.raw_outputs), 2)
        self.assertTrue(failure.trace_id)

        class TimeoutProvider:
            model_version = 'timeout-v1'
            def complete(self, work_item, prompt_version):
                raise TimeoutError('provider timeout')
        timeout = extract(work, TimeoutProvider(), config)
        self.assertEqual(timeout.status, 'failed')
        self.assertEqual(timeout.attempts, 2)
        self.assertIn('provider timeout', timeout.error)

    def test_invalid_value_and_false_evidence_route_to_review(self):
        class Provider:
            model_version = 'invalid-v1'
            def __init__(self, field):
                self.field = field
            def complete(self, work_item, prompt_version):
                return json.dumps({'flow': self.field})
        work = from_text('Flow 85 m3/h', source_id='BAD1')
        for field in [
            {'value': -85, 'unit': 'm3/h', 'text': 'Flow 85 m3/h', 'start': 0, 'end': 12},
            {'value': 85, 'unit': 'm3/h', 'text': 'wrong', 'start': 0, 'end': 5},
        ]:
            with self.subTest(field=field):
                result, record = process(work, Provider(field))
                self.assertEqual(result.status, 'failed')
                self.assertIsNone(record)

    def test_feedback_preserves_original_and_marks_human_source(self):
        work = from_text('Need centrifugal pump for water. Flow 85 m3/h, Head 38m, 2 pcs.', source_id='F1')
        result, record = process(work)
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'reviews.sqlite3')
            store.save_extraction(work, result, record)
            corrected = record.to_dict()
            corrected['medium_description'] = 'cooling water'
            feedback = store.review(work.id, 'edit', 'Linda', corrected, '客户补充工况')
            self.assertEqual(len(feedback), 1)
            saved = store.get_item(work.id)
            self.assertEqual(saved['model_record']['medium_description'], 'water')
            event = store.reviews(work.id)[0]
            self.assertEqual(event['corrected_record']['medium_description'], 'cooling water')
            self.assertEqual(event['corrected_record']['evidence']['medium_description']['origin'], 'human_review')
            self.assertEqual(event['feedback'][0]['field'], 'medium_description')
            self.assertEqual(len(event['corrected_record']['missing_fields']), 0)
            store.close()

    def test_failed_extraction_requires_human_edit_or_reject(self):
        work = from_text('Need pump', source_id='FAIL')
        class Provider:
            model_version = 'fake'
            def complete(self, work_item, prompt_version):
                return '{broken'
        result, record = process(work, Provider())
        self.assertEqual(result.status, 'failed')
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'reviews.sqlite3')
            store.save_extraction(work, result, record)
            with self.assertRaisesRegex(ValueError, '不能直接批准'):
                store.review(work.id, 'approve', 'Linda', None)
            store.review(work.id, 'reject', 'Linda', None, '信息不足')
            self.assertEqual(store.reviews(work.id)[0]['action'], 'reject')
            store.close()

    def test_synthetic_eval_and_regression_check(self):
        result = evaluate(ROOT / 'stages/04-build-sprint-1/data/inquiry_eval_v0.jsonl')
        self.assertEqual(result['case_count'], 100)
        self.assertAlmostEqual(result['critical_field_accuracy'], 0.9888888888888889)
        self.assertEqual(result['parse_failure_rate'], 0)
        self.assertEqual(result['per_field']['flow_m3h']['accuracy'], 1.0)
        self.assertEqual(result['per_field']['temperature_c']['accuracy'], 1.0)
        self.assertTrue(result['offline_thresholds_met'])
        with tempfile.TemporaryDirectory() as tmp:
            run = subprocess.run([sys.executable, str(ROOT / 'stage4.py'), 'eval',
                                  '--output', tmp, '--check-baseline'], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)

    def test_review_page_get_and_post(self):
        work = from_text('Need centrifugal pump for water. Flow 85 m3/h, Head 38m, 2 pcs.', source_id='WEB1')
        result, record = process(work)
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / 'review.sqlite3')
            store.save_extraction(work, result, record)
            store.close()
            proc = subprocess.Popen([sys.executable, str(ROOT / 'stage4.py'), 'review',
                                     '--output', tmp, '--port', '0'], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            try:
                ready, _, _ = select.select([proc.stdout], [], [], 5)
                self.assertTrue(ready, '审核服务未启动')
                line = proc.stdout.readline()
                found = re.search(r':(\d+)/', line)
                if not found and proc.poll() is not None:
                    stderr = proc.stderr.read()
                    if 'Operation not permitted' in stderr:
                        self.skipTest('当前沙盒禁止本地监听；在普通本机/CI 环境可运行 HTTP 测试')
                    self.fail(stderr or '审核服务启动失败')
                self.assertIsNotNone(found, line)
                port = int(found.group(1))
                url = f'http://127.0.0.1:{port}/item/{work.id}'
                html = urlopen(url, timeout=5).read().decode()
                self.assertIn('原始邮件', html)
                self.assertIn('Flow 85 m3/h', html)
                token = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
                data = {'csrf': token, 'action': 'edit', 'reviewer': 'Linda', 'comment': 'test',
                        'medium_description': 'cooling water'}
                for name in ('company_name', 'country', 'product_type', 'application', 'quantity',
                             'flow_m3h', 'head_m', 'medium_category', 'temperature_c', 'voltage_v',
                             'frequency_hz', 'destination_port'):
                    value = record.to_dict().get(name)
                    data[name] = '' if value is None else str(value)
                urlopen(Request(url, data=urlencode(data).encode()), timeout=5).read()
            finally:
                proc.terminate()
                proc.wait(timeout=5)
                proc.stdout.close()
                proc.stderr.close()
            store = Store(Path(tmp) / 'review.sqlite3')
            self.assertEqual(store.reviews(work.id)[0]['feedback'][0]['field'], 'medium_description')
            store.close()


if __name__ == '__main__':
    unittest.main()
