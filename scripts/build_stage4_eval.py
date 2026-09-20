#!/usr/bin/env python3
"""Build 100 independent-looking but fully synthetic, deterministic eval cases."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'stages/04-build-sprint-1/data/inquiry_eval_v0.jsonl'
FIELDS = ('product_type', 'quantity', 'flow_m3h', 'head_m', 'medium_category',
          'temperature_c', 'voltage_v', 'frequency_hz', 'destination_port')


def label(**values):
    return {field: values.get(field) for field in FIELDS}


def build():
    cases = []
    media = [('freshwater', 'water'), ('cooling water', 'water'), ('seawater', 'seawater'),
             ('wastewater', 'wastewater'), ('chemical', 'chemical')]
    for i in range(50):
        medium, category = media[i % len(media)]
        flow, head, quantity = 50 + i, 20 + i % 17, 2 + i % 7
        temp = 20 + i % 30
        freq = 50 if i % 3 else 60
        if i < 40:
            body = f'Need centrifugal pump for {medium}. Flow {flow} m3/h, Head {head} m, {temp} C, {quantity} pcs, 380V/{freq}Hz. Quote CIF Jebel Ali.'
            if 30 <= i < 35:
                body = body.replace(f'Flow {flow} m3/h, Head {head} m',
                                    f'Operating capacity: {flow} cubic meters per hour, total dynamic head of {head} metres')
            if 35 <= i < 40:
                body = body.replace(f'{temp} C, {quantity} pcs',
                                    f'operating temp. {temp} degrees Celsius, need {quantity} machines')
        else:
            cn = {'freshwater': '淡水', 'cooling water': '冷却水', 'seawater': '海水', 'wastewater': '污水', 'chemical': '化工液体'}[medium]
            body = f'离心泵 inquiry, 介质{cn}, 流量 {flow} m³/h, 扬程 {head} m, 温度 {temp}°C, 数量 {quantity} 台, 380V/{freq}Hz, 目的港 Jebel Ali。'
        cases.append({'group': 'standard_or_mixed', 'format': 'text', 'body': body, 'attachments': [],
                      'expected': label(product_type='centrifugal_pump', quantity=quantity,
                                        flow_m3h=flow, head_m=head, medium_category=category,
                                        temperature_c=temp, voltage_v=380, frequency_hz=freq,
                                        destination_port='Jebel Ali')})
    for i in range(20):
        medium, category = media[i % len(media)]
        flow = 60 + i
        head = 25 + i % 10
        quantity = 1 + i % 5
        if i % 2 == 0:
            flow_part = f'{flow * 1000 / 60:.4f} L/min'
            expected_flow = round(round(flow * 1000 / 60, 4) * .06, 4)
        else:
            flow_part = f'{flow} CMH'
            expected_flow = flow
        if i % 3 == 0:
            temp_part = '107.6 F'
        else:
            temp_part = '42°C'
        if i < 5:
            flow_part = flow_part.replace('L/min', 'liters per minute').replace('CMH', 'cubic meters per hour')
            temp_part = temp_part.replace(' F', ' degrees Fahrenheit').replace('°C', ' degrees Celsius')
        cases.append({'group': 'unit_conversion', 'format': 'text',
                      'body': f'Centrifugal pump for {medium}: capacity {flow_part}; head {head} m; {temp_part}; {quantity} units; 400 V / 50 Hz. CIF Jebel Ali.',
                      'attachments': [],
                      'expected': label(product_type='centrifugal_pump', quantity=quantity,
                                        flow_m3h=expected_flow, head_m=head, medium_category=category,
                                        temperature_c=42, voltage_v=400, frequency_hz=50,
                                        destination_port='Jebel Ali')})
    for i in range(15):
        body = f'Centrifugal pump for freshwater. Flow {70+i} m3/h, 35 m head, 3 pcs, 380V/50Hz, 30 C. CIF Jebel Ali.'
        expected = label(product_type='centrifugal_pump', quantity=3, flow_m3h=70+i, head_m=35,
                         medium_category='water', temperature_c=30, voltage_v=380,
                         frequency_hz=50, destination_port='Jebel Ali')
        if i < 5:
            body = body.replace('35 m head, ', '')
            expected['head_m'] = None
        elif i < 10:
            body = body.replace('380V/50Hz, ', '')
            expected['voltage_v'] = None
            expected['frequency_hz'] = None
        else:
            body = body.replace('3 pcs, ', '')
            expected['quantity'] = None
        if i < 5:
            body = body.replace('Flow ', 'Rated flow ')
        cases.append({'group': 'missing_field', 'format': 'text', 'body': body,
                      'attachments': [], 'expected': expected})
    for i in range(10):
        flow, head = 80 + i, 35 + i % 5
        html = f'<html><body><p>Centrifugal pump for cooling water.</p><div>Flow <b>{flow} m3/h</b>, Head <b>{head} m</b>, 42°C, 6 pcs, 380V/50Hz.</div><p>CIF Jebel Ali.</p><script>flow 999 m3/h</script></body></html>'
        cases.append({'group': 'html', 'format': 'html', 'body': html, 'attachments': [],
                      'expected': label(product_type='centrifugal_pump', quantity=6, flow_m3h=flow,
                                        head_m=head, medium_category='water', temperature_c=42,
                                        voltage_v=380, frequency_hz=50, destination_port='Jebel Ali')})
    for i in range(5):
        cases.append({'group': 'attachment_placeholder', 'format': 'text',
                      'body': 'Please find pump technical requirements attached. We need your review.',
                      'attachments': [{'filename': f'requirements_{i+1}.xlsx', 'content_type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}],
                      'expected': label(product_type='pump'),
                      'expected_missing': ['attachment_processing_required']})
    assert len(cases) == 100
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open('w', encoding='utf-8') as handle:
        for index, case in enumerate(cases, 1):
            handle.write(json.dumps({'id': f'S4-{index:03}', 'mode': 'simulation', **case}, ensure_ascii=False) + '\n')
    print(f'已生成 {len(cases)} 条合成评估样本：{OUT}')


if __name__ == '__main__':
    build()
