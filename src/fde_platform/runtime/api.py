"""Small authenticated HTTP API for the Stage 11 local delivery room."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
from urllib.parse import parse_qs, urlparse


def handler_for(service, worker, dispatcher, console_html=None):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'FDEDeliveryRoom/1'

        def log_message(self, fmt, *args):
            # Avoid logging request bodies or credentials in the training runtime.
            return

        def _json(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self, value):
            body = value.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _body(self):
            length = int(self.headers.get('Content-Length', '0'))
            if length > 1_000_000:
                raise ValueError('请求体超过 1 MB')
            value = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(value, dict):
                raise ValueError('JSON 请求体必须是对象')
            return value

        def _bearer(self):
            value = self.headers.get('Authorization', '')
            if not value.startswith('Bearer '):
                raise ValueError('缺少 Bearer 身份令牌')
            return value[7:]

        def do_GET(self):
            try:
                parsed = urlparse(self.path)
                if parsed.path == '/':
                    return self._html(console_html or CONSOLE_HTML)
                if parsed.path == '/health':
                    return self._json(200, {'status': 'ok', 'mode': 'local_training_runtime'})
                if parsed.path == '/v1/cases':
                    return self._json(200, {'cases': service.cases(self._bearer())})
                if parsed.path.startswith('/v1/traces/'):
                    case_id = parsed.path.rsplit('/', 1)[-1]
                    return self._json(200, service.trace(self._bearer(), case_id))
                if parsed.path == '/v1/metrics':
                    service.require_role(self._bearer(), 'operator', 'auditor', 'release_manager')
                    return self._json(200, service.store.metrics())
                return self._json(404, {'error': 'not_found'})
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                self._json(403, {'error': str(exc)})

        def do_POST(self):
            try:
                parsed = urlparse(self.path)
                body = self._body()
                if parsed.path == '/v1/events':
                    result = service.accept(body, self.headers.get('X-Service-Token', ''))
                    return self._json(202, result)
                if parsed.path == '/v1/worker/tick':
                    service.require_role(self._bearer(), 'operator')
                    tick = int(body.get('tick', 0))
                    return self._json(200, worker.once(tick) or {'state': 'idle'})
                if parsed.path == '/v1/dispatcher/tick':
                    service.require_role(self._bearer(), 'operator')
                    tick = int(body.get('tick', 0))
                    return self._json(200, dispatcher.once(tick) or {'state': 'idle'})
                if parsed.path.startswith('/v1/cases/') and parsed.path.endswith('/reviews'):
                    case_id = parsed.path.split('/')[3]
                    return self._json(200, service.review(self._bearer(), case_id,
                        body.get('action'), body.get('reason', '')))
                if parsed.path.startswith('/v1/outbox/') and parsed.path.endswith('/approve'):
                    message_id = parsed.path.split('/')[3]
                    service.approve(self._bearer(), message_id)
                    return self._json(200, {'message_id': message_id, 'state': 'ready'})
                if parsed.path.startswith('/v1/dead-letters/events/') and parsed.path.endswith('/requeue'):
                    event_id = parsed.path.split('/')[4]
                    service.requeue_event(self._bearer(), event_id, body.get('reason', ''))
                    return self._json(200, {'event_id': event_id, 'state': 'retry'})
                if parsed.path.startswith('/v1/dead-letters/messages/') and parsed.path.endswith('/requeue'):
                    message_id = parsed.path.split('/')[4]
                    service.requeue_message(self._bearer(), message_id, body.get('reason', ''))
                    return self._json(200, {'message_id': message_id, 'state': 'retry'})
                return self._json(404, {'error': 'not_found'})
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                self._json(400, {'error': str(exc)})

    return Handler


CONSOLE_HTML = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>Stage 11 Delivery Room</title><style>
body{font:15px system-ui;max-width:1100px;margin:32px auto;padding:0 16px;background:#f6f7f9;color:#18202a}
button,input{padding:8px;margin:4px}pre{background:#111827;color:#d1fae5;padding:16px;overflow:auto;min-height:240px}
.card{background:white;padding:18px;border-radius:10px;box-shadow:0 1px 5px #ccd;margin:12px 0}</style></head>
<body><h1>Stage 11 Delivery Room</h1><p>本机教学控制台。令牌只保存在当前浏览器内存。</p>
<div class="card"><input id="token" size="80" placeholder="Bearer token（只粘贴令牌本体）">
<button onclick="load('/v1/cases')">审核队列</button><button onclick="load('/v1/metrics')">运行指标</button></div>
<pre id="result">等待查询</pre><script>
async function load(path){const r=await fetch(path,{headers:{Authorization:'Bearer '+document.querySelector('#token').value}});
document.querySelector('#result').textContent=JSON.stringify(await r.json(),null,2)}</script></body></html>'''


def serve(service, worker, dispatcher, host='127.0.0.1', port=8781, auto_run=True,
          console_html=None):
    server = ThreadingHTTPServer((host, port), handler_for(
        service, worker, dispatcher, console_html=console_html))
    print(f'Stage 11 Delivery Room API: http://{host}:{port}（仅本机教学）')
    stop = threading.Event()
    def background():
        tick = 0
        while not stop.wait(1):
            worker.once(tick)
            dispatcher.once(tick)
            tick += 1
    thread = threading.Thread(target=background, daemon=True)
    if auto_run:
        thread.start()
    try:
        server.serve_forever()
    finally:
        stop.set()
        if auto_run:
            thread.join(timeout=2)
        server.server_close()
