"""Qihang-specific local review experience backed by the shared scoped store."""
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import secrets
from urllib.parse import parse_qs, quote, unquote, urlparse

from fde_platform.core.platform.tenant_store import TenantStore


def serve(db_path, tenant_domains, reviewers, port=8769):
    people = {x['actor_id']: x['role'] for x in reviewers}
    csrf = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def html(self, body, status=200):
            page = ('<!doctype html><html lang="zh"><meta charset="utf-8">'
                    '<title>启航模拟售后审核</title><style>body{font:16px system-ui;max-width:980px;'
                    'margin:2rem auto;line-height:1.5}pre{white-space:pre-wrap;background:#f5f5f5;padding:1rem}'
                    'a{margin-right:1rem}button{margin:.3rem}</style><body>'
                    '<h1>启航设备 · 模拟售后审核</h1><p>本地角色切换仅供教学；不发送维修指导或派工。</p>'
                    + body + '</body></html>').encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(page)))
            self.end_headers()
            self.wfile.write(page)

        def actor(self):
            actor_id = parse_qs(urlparse(self.path).query).get('user', ['zhou'])[0]
            if actor_id not in people:
                raise ValueError('未知教学用户')
            return actor_id, people[actor_id]

        def do_GET(self):
            try:
                actor_id, role = self.actor()
            except ValueError as exc:
                return self.html(escape(str(exc)), 400)
            store = TenantStore(db_path, tenant_domains)
            try:
                scope = store.scope('qihang-training', 'after_sales')
                path = urlparse(self.path).path
                if path == '/':
                    links = ' '.join(f'<a href="/?user={quote(user)}">{escape(user)}</a>' for user in people)
                    tasks = [x for x in scope.list('review_task') if
                             (x['assignee_id'], x['assignee_role']) == (actor_id, role)]
                    items = ''.join(f'<li><a href="/item/{quote(x["task_id"])}?user={quote(actor_id)}">'
                                    f'{escape(x["case_id"])} · {escape(x["risk_level"])}</a></li>' for x in tasks)
                    return self.html(f'<p>当前：{escape(actor_id)}；切换：{links}</p><ul>{items}</ul>')
                if not path.startswith('/item/'):
                    return self.html('未找到', 404)
                task_id = unquote(path.removeprefix('/item/'))
                task = scope.get('review_task', task_id)
                if task is None or (task['assignee_id'], task['assignee_role']) != (actor_id, role):
                    return self.html('任务不存在或无权查看', 404)
                p = task['payload']
                sections = [f'<h2>{escape(task["case_id"])} · {escape(task["risk_level"])}</h2>',
                    f'<p>设备：{escape(str(p["device_model"]))}；序列号：{escape(str(p["serial_number"]))}；'
                    f'报警：{escape(str(p["error_code"]))}；当前压力：{escape(str(p["pressure_bar"]))} bar</p>',
                    '<h3>最近维修</h3><pre>' + escape(str(p['maintenance_summary'] or '无可确认记录')) + '</pre>',
                    '<h3>风险与下一步内部建议</h3><pre>' + escape(json.dumps(
                        {'warnings': p['warnings'], 'options': p['options'], 'evidence': task['evidence']},
                        ensure_ascii=False, indent=2)) + '</pre>']
                if not scope.feedback(task_id):
                    actions = ('resolve', 'edit', 'reject', 'escalate') if role == 'engineer' else (
                        'approve', 'edit', 'reject', 'escalate')
                    buttons = ''.join(f'<button name="action" value="{action}">{action}</button>' for action in actions)
                    sections.append(f'<form method="post" action="/item/{quote(task_id)}?user={quote(actor_id)}">'
                        f'<input type="hidden" name="csrf" value="{csrf}">'
                        '<label>审核原因 <input name="reason" size="60"></label><p>' + buttons + '</p></form>')
                sections.append('<h3>追加式审核记录</h3><pre>' +
                                escape(json.dumps(scope.feedback(task_id), ensure_ascii=False, indent=2)) + '</pre>')
                return self.html(f'<a href="/?user={quote(actor_id)}">返回队列</a>' + ''.join(sections))
            finally:
                store.close()

        def do_POST(self):
            try:
                actor_id, role = self.actor()
            except ValueError as exc:
                return self.html(escape(str(exc)), 400)
            path = urlparse(self.path).path
            if not path.startswith('/item/'):
                return self.html('无效操作', 403)
            size = int(self.headers.get('Content-Length', '0'))
            if size < 0 or size > 16384:
                return self.html('请求大小无效', 413)
            form = parse_qs(self.rfile.read(size).decode(), keep_blank_values=True)
            field = lambda key: form.get(key, [''])[0]
            if field('csrf') != csrf:
                return self.html('CSRF token 无效', 403)
            task_id = unquote(path.removeprefix('/item/'))
            store = TenantStore(db_path, tenant_domains)
            try:
                scope = store.scope('qihang-training', 'after_sales')
                scope.review(task_id, actor_id, role, field('action'), field('reason'))
            except ValueError as exc:
                return self.html(escape(str(exc)), 400)
            finally:
                store.close()
            self.send_response(303)
            self.send_header('Location', f'/item/{quote(task_id)}?user={quote(actor_id)}')
            self.end_headers()

    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f'启航售后审核：http://127.0.0.1:{server.server_port}/?user=zhou', flush=True)
    server.serve_forever()
