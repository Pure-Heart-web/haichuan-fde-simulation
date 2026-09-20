"""Local-only human review UI with original text, edits, approval and feedback."""
from dataclasses import fields
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, unquote
import secrets

from ..core.store import Store
from ..domains.foreign_trade.schema import InquiryRecord

EDITABLE = [
    ('company_name', 'Company', 'text'), ('country', 'Country', 'text'),
    ('product_type', 'Product type', 'text'), ('application', 'Application', 'text'),
    ('quantity', 'Quantity', 'int'), ('flow_m3h', 'Flow (m³/h)', 'float'),
    ('head_m', 'Head (m)', 'float'), ('medium_category', 'Medium category', 'text'),
    ('medium_description', 'Medium description', 'text'),
    ('temperature_c', 'Temperature (°C)', 'float'), ('voltage_v', 'Voltage (V)', 'int'),
    ('frequency_hz', 'Frequency (Hz)', 'int'), ('destination_port', 'Destination port', 'text'),
]


def html_page(title, content):
    return f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>body{{font:16px system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 18px;color:#18202a;background:#f6f8fa}}a{{color:#115c9d}}main{{background:white;padding:24px;border-radius:12px;box-shadow:0 2px 12px #0001}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}pre{{white-space:pre-wrap;background:#f2f4f6;padding:16px;border-radius:8px;overflow:auto}}label{{display:block;margin:10px 0}}input,textarea{{font:inherit;padding:8px;border:1px solid #aab3bd;border-radius:6px;box-sizing:border-box}}label input{{width:100%}}textarea{{width:100%;height:80px}}button{{padding:10px 16px;margin-right:10px;border:0;border-radius:6px;color:white;background:#115c9d;cursor:pointer}}button[value=reject]{{background:#9f3a32}}button[value=edit]{{background:#6a4caa}}.warn{{background:#fff4d7;padding:10px}}@media(max-width:700px){{.grid{{grid-template-columns:1fr}}}}</style><main>{content}</main></html>'''


def record_from_form(original, params, work_item_id):
    base = dict(original or InquiryRecord(work_item_id).to_dict())
    for name, label, kind in EDITABLE:
        raw = params.get(name, [''])[0].strip()
        if not raw:
            base[name] = None
        elif kind == 'text':
            base[name] = raw
        elif kind == 'int':
            if not raw.isdigit() or int(raw) <= 0:
                raise ValueError(f'{label} 必须为正整数')
            base[name] = int(raw)
        else:
            try:
                number = float(raw)
            except ValueError:
                raise ValueError(f'{label} 必须是数字') from None
            if not -273.15 <= number <= 1_000_000 or (name != 'temperature_c' and number <= 0):
                raise ValueError(f'{label} 超出可接受范围')
            base[name] = number
    # Human review owns the corrected field values; prior evidence is kept only for unchanged fields.
    allowed = {f.name for f in fields(InquiryRecord)}
    if base.get('medium_description') and base['medium_description'] != 'water':
        base['missing_fields'] = [x for x in base.get('missing_fields', []) if x != 'medium_detail']
    for field_name in ('flow_m3h', 'head_m'):
        if base.get(field_name) is not None:
            base['missing_fields'] = [x for x in base.get('missing_fields', []) if x != field_name]
    return InquiryRecord(**{k: v for k, v in base.items() if k in allowed}).to_dict()


def make_handler(store, csrf_token):
    class ReviewHandler(BaseHTTPRequestHandler):
        def _send(self, content, status=200):
            body = html_page('海川询盘复核 · 教学演练', content).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/':
                items = store.list_items()
                rows = ''.join(f'<li><a href="/item/{escape(x["id"])}">{escape(x["source_id"])} · {escape(x["id"])}</a> — 抽取 {escape(x["status"])}；审核 {escape(x["review_status"] or "待处理")}</li>' for x in items)
                self._send('<h1>询盘人工复核</h1><p class="warn">本地教学演练。所有样本为合成邮件，不连接生产邮箱。</p><ul>' + rows + '</ul>')
                return
            if not self.path.startswith('/item/'):
                self._send('<h1>页面不存在</h1>', 404)
                return
            work_id = unquote(self.path[len('/item/'):])
            item = store.get_item(work_id)
            if item is None:
                self._send('<h1>任务不存在</h1>', 404)
                return
            record = item['model_record'] or InquiryRecord(work_id).to_dict()
            form = ''.join(f'<label>{escape(label)}<input name="{escape(name)}" value="{escape(str(record.get(name) if record.get(name) is not None else ""))}"></label>' for name, label, _ in EDITABLE)
            warnings = ', '.join((item['model_record'] or {}).get('warnings', []))
            content = f'<p><a href="/">← 返回列表</a></p><h1>{escape(item["work_item"]["source_id"])} · 审核字段</h1>'
            content += '<p class="warn">抽取结果仅供审核；页面不会报价、推荐产品或发送邮件。</p>'
            if item['status'] == 'failed':
                content += f'<p class="warn">抽取失败：{escape(item["result"].get("error") or "未知错误")}。请修改或拒绝。</p>'
            if warnings:
                content += f'<p class="warn">警告：{escape(warnings)}</p>'
            content += '<div class="grid"><section><h2>原始邮件</h2><pre>' + escape(item['work_item']['body']) + '</pre>'
            content += '<h3>来源</h3><pre>' + escape(item['work_item']['sender'] + '\n' + item['work_item']['subject']) + '</pre></section>'
            content += f'<section><h2>提取与更正</h2><form method="post" action="/item/{escape(work_id)}"><input type="hidden" name="csrf" value="{escape(csrf_token)}">{form}'
            content += '<label>审核者<input name="reviewer" required></label><label>说明<textarea name="comment"></textarea></label>'
            content += '<button name="action" value="approve">批准原结果</button><button name="action" value="edit">保存更正</button><button name="action" value="reject">拒绝</button></form></section></div>'
            history = store.reviews(work_id)
            if history:
                content += '<h2>审核历史</h2><ul>' + ''.join(f'<li>{escape(x["created_at"])} · {escape(x["reviewer"])} · {escape(x["action"])} · {len(x["feedback"])} 个字段更正</li>' for x in history) + '</ul>'
            self._send(content)

        def do_POST(self):
            if not self.path.startswith('/item/'):
                self._send('<h1>页面不存在</h1>', 404)
                return
            size = int(self.headers.get('Content-Length', '0'))
            if size <= 0 or size > 100_000:
                self._send('<h1>请求大小无效</h1>', 413)
                return
            params = parse_qs(self.rfile.read(size).decode('utf-8'), keep_blank_values=True)
            if params.get('csrf', [''])[0] != csrf_token:
                self._send('<h1>表单令牌无效</h1>', 403)
                return
            work_id = unquote(self.path[len('/item/'):])
            item = store.get_item(work_id)
            if item is None:
                self._send('<h1>任务不存在</h1>', 404)
                return
            action = params.get('action', [''])[0]
            reviewer = params.get('reviewer', [''])[0]
            comment = params.get('comment', [''])[0]
            try:
                corrected = record_from_form(item['model_record'], params, work_id) if action == 'edit' else None
                store.review(work_id, action, reviewer, corrected, comment)
            except ValueError as exc:
                self._send('<h1>无法保存审核</h1><p>' + escape(str(exc)) + '</p><a href="/item/' + escape(work_id) + '">返回</a>', 400)
                return
            self.send_response(303)
            self.send_header('Location', '/item/' + work_id)
            self.end_headers()

    return ReviewHandler


def serve(db_path, host='127.0.0.1', port=8765):
    if host != '127.0.0.1':
        raise ValueError('教学审核页面只允许绑定 127.0.0.1')
    store = Store(db_path)
    token = secrets.token_urlsafe(24)
    server = HTTPServer((host, port), make_handler(store, token))
    print(f'审核页面：http://{host}:{server.server_port}/（Ctrl+C 退出）', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('审核页面已停止。', flush=True)
    finally:
        server.server_close()
        store.close()
