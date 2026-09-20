"""Local teaching UI; user selector is not production authentication."""
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import secrets
from urllib.parse import parse_qs, quote, unquote, urlparse

from fde_platform.core.pilot.store import PilotStore


def serve(db_path, users, port=8768):
    people = {x['user_id']: x for x in users}
    people['admin'] = {'user_id': 'admin', 'role': 'admin', 'experience': 'admin'}
    csrf = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def respond(self, body, status=200):
            raw = ('<!doctype html><html lang="zh"><meta charset="utf-8"><title>Stage 7 Pilot 审核</title>'
                   '<style>body{font:16px system-ui;max-width:1000px;margin:2rem auto;line-height:1.5}'
                   'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:.5rem}'
                   'pre{white-space:pre-wrap;background:#f5f5f5;padding:1rem}label{display:block;margin:.6rem 0}'
                   '</style><body><h1>Stage 7 模拟 Pilot 审核队列</h1>'
                   '<p>角色选择只用于本地教学；没有真实登录、邮件发送或生产权限。</p>' + body + '</body></html>').encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def actor(self):
            user = parse_qs(urlparse(self.path).query).get('user', ['linda'])[0]
            if user not in people:
                raise ValueError('未知教学用户')
            return people[user]

        def do_GET(self):
            try:
                actor = self.actor()
            except ValueError as exc:
                return self.respond(escape(str(exc)), 400)
            user = actor['user_id']
            links = ' '.join(f'<a href="/?user={quote(key)}">{escape(key)}</a>' for key in people)
            store = PilotStore(db_path)
            try:
                path = urlparse(self.path).path
                if path == '/':
                    tasks = store.list_tasks(actor_id=user, role=actor['role'])
                    rows = ''.join(f'<tr><td><a href="/item/{quote(x["task_id"])}?user={quote(user)}">'
                                   f'{escape(x["task_id"])}</a></td><td>{escape(x["type"])}</td>'
                                   f'<td>{escape(x["status"])}</td></tr>' for x in tasks)
                    return self.respond(f'<p>当前用户：{escape(user)}。切换：{links}</p>'
                                        '<table><tr><th>任务</th><th>类型</th><th>状态</th></tr>' + rows + '</table>')
                if not path.startswith('/item/'):
                    return self.respond('未找到', 404)
                task_id = unquote(path.removeprefix('/item/'))
                task = store.get_task(task_id)
                if task is None or (actor['role'] != 'admin' and
                    (task['assignee_id'], task['assignee_role']) != (user, actor['role'])):
                    return self.respond('任务不存在或无权查看', 404)
                payload = task['payload']
                summary = (f'<h2>{escape(task_id)}</h2><p>状态：{escape(task["status"])}；'
                           f'风险：{escape(task["risk_level"])}；前置审核：'
                           f'{escape(task["prerequisite_task_id"] or "无")}</p>'
                           f'<p>候选：{escape(", ".join(payload.get("candidate_skus") or []) or "无")}；'
                           f'警告：{escape(", ".join(payload.get("warnings") or []) or "无")}</p>')
                if task['type'] == 'sales_draft':
                    summary += f'<h3>草稿</h3><pre>{escape(payload.get("draft_body") or "草稿服务不可用：转人工处理")}</pre>'
                else:
                    summary += f'<h3>工程师需回答的问题</h3><p>{escape(payload.get("question", ""))}</p>'
                open_attr = ' open' if actor['role'] in ('engineer', 'admin') or actor['experience'] == 'junior' else ''
                summary += (f'<details{open_attr}><summary>证据、规则与版本</summary><pre>'
                            f'{escape(json.dumps({"payload": payload, "evidence": task["evidence"]}, ensure_ascii=False, indent=2))}</pre></details>')
                if actor['role'] != 'admin' and task['status'] == 'pending':
                    actions = ('approve', 'edit', 'reject', 'escalate') if task['type'] == 'sales_draft' else (
                        'resolve', 'override', 'escalate')
                    buttons = ''.join(f'<button name="action" value="{a}">{a}</button>' for a in actions)
                    summary += (f'<form method="post" action="/item/{quote(task_id)}?user={quote(user)}">'
                                f'<input type="hidden" name="csrf" value="{csrf}">'
                                '<label>原因/备注 <input name="comment"></label>'
                                '<label>工程师覆盖分类 <select name="override_category">'
                                '<option value="">无</option><option>commercial_preference</option>'
                                '<option>missing_rule</option><option>bad_ranking</option>'
                                '<option>data_error</option><option>user_preference</option></select></label>'
                                + buttons + '</form>')
                summary += f'<h3>追加式决定</h3><pre>{escape(json.dumps(store.events(task_id), ensure_ascii=False, indent=2))}</pre>'
                return self.respond(f'<p><a href="/?user={quote(user)}">返回队列</a></p>' + summary)
            finally:
                store.close()

        def do_POST(self):
            try:
                actor = self.actor()
            except ValueError as exc:
                return self.respond(escape(str(exc)), 400)
            path = urlparse(self.path).path
            if not path.startswith('/item/') or actor['role'] == 'admin':
                return self.respond('无效操作', 403)
            size = int(self.headers.get('Content-Length', '0'))
            if size > 16384:
                return self.respond('请求过大', 413)
            form = parse_qs(self.rfile.read(size).decode(), keep_blank_values=True)
            val = lambda key: form.get(key, [''])[0]
            if val('csrf') != csrf:
                return self.respond('CSRF token 无效', 403)
            task_id = unquote(path.removeprefix('/item/'))
            store = PilotStore(db_path)
            try:
                store.review(task_id, actor['user_id'], actor['role'], val('action'),
                             val('comment'), val('override_category') or None)
            except ValueError as exc:
                return self.respond(escape(str(exc)), 400)
            finally:
                store.close()
            self.send_response(303)
            self.send_header('Location', f'/item/{quote(task_id)}?user={quote(actor["user_id"])}')
            self.end_headers()

    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f'Pilot 审核页面：http://127.0.0.1:{server.server_port}/?user=linda', flush=True)
    server.serve_forever()
