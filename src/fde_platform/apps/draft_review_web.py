"""Loopback-only reply draft review with evidence and knowledge gap feedback."""
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import secrets
from urllib.parse import parse_qs, quote, unquote, urlparse

from fde_platform.domains.foreign_trade.reply.store import DraftStore


def serve(db_path, port=8767):
    csrf = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def respond(self, body, status=200):
            html = ('<!doctype html><html lang="zh"><meta charset="utf-8"><title>Stage 6 草稿审核</title>'
                    '<style>body{font:16px system-ui;max-width:1000px;margin:2rem auto;line-height:1.5}'
                    'pre{white-space:pre-wrap;background:#f5f5f5;padding:1rem}textarea{width:100%;min-height:9rem}'
                    'label{display:block;margin:.6rem 0}table{border-collapse:collapse;width:100%}'
                    'td,th{border:1px solid #ddd;padding:.5rem}</style><body><a href="/">队列</a>'
                    '<h1>Stage 6 回复草稿审核</h1><p>仅教学模拟；本页面没有邮件发送或 CRM 写入功能。</p>'
                    + body + '</body></html>').encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def do_GET(self):
            store = DraftStore(db_path)
            try:
                path = urlparse(self.path).path
                if path == '/':
                    rows = ''.join(f'<tr><td><a href="/item/{quote(x["case_id"])}">{escape(x["case_id"])}</a></td>'
                                   f'<td>{escape(x["draft_status"])}</td><td>{escape(x["latest_action"] or "待审核")}</td></tr>'
                                   for x in store.list_items())
                    return self.respond('<table><tr><th>案例</th><th>状态</th><th>最近动作</th></tr>' + rows + '</table>')
                if not path.startswith('/item/'):
                    return self.respond('未找到', 404)
                case_id = unquote(path.removeprefix('/item/'))
                row = store.get(case_id)
                if row is None:
                    return self.respond('案例不存在', 404)
                artifact = row['artifact']
                draft = artifact['draft']
                refs = {'identity': artifact['identity'], 'previous_order': artifact['previous_order'],
                        'resolved_fields': artifact['resolved_fields'],
                        'knowledge_evidence': artifact['knowledge_evidence'],
                        'recommendation': artifact['recommendation']}
                gap_rows = ''.join('<tr><td>' + escape(g['intent']) + '</td><td>' + escape(g['status']) +
                                   '</td><td>' + escape(g['owner']) + '</td></tr>' for g in store.gaps(case_id))
                body = (f'<h2>{escape(case_id)}</h2><p>状态：{escape(draft["status"])}；审核角色：'
                        f'{escape(draft["required_reviewer"])}；身份：{escape(artifact["identity"]["status"])}</p>'
                        f'<h3>回复草稿</h3><pre>{escape(draft["subject"])}\n\n{escape(draft["body"])}</pre>'
                        f'<details><summary>查看内容计划、Claim 与证据</summary><pre>{escape(json.dumps({"plan": draft["content_plan"], "claims": draft["claims"], "sources": refs}, ensure_ascii=False, indent=2))}</pre></details>'
                        f'<h3>知识缺口</h3><table><tr><th>问题</th><th>状态</th><th>负责人</th></tr>{gap_rows}</table>'
                        f'<form method="post"><input type="hidden" name="csrf" value="{csrf}">'
                        '<input type="hidden" name="kind" value="review">'
                        '<label>审核人 <input name="reviewer" required></label>'
                        '<label>角色 <select name="reviewer_role"><option>sales</option><option>engineer</option></select></label>'
                        '<label>修改正文（选择 minor/major edit 时填写；改写后需重新验证）'
                        f'<textarea name="edited_body">{escape(draft["body"])}</textarea></label>'
                        '<label>原因/意见 <input name="comment"></label>'
                        '<button name="action" value="approve">批准原草稿</button>'
                        '<button name="action" value="minor_edit">小修改</button>'
                        '<button name="action" value="major_edit">大修改</button>'
                        '<button name="action" value="reject">拒绝</button>'
                        '<button name="action" value="escalate">升级</button></form>'
                        f'<form method="post"><input type="hidden" name="csrf" value="{csrf}">'
                        '<input type="hidden" name="kind" value="gap">'
                        '<label>缺口意图 <input name="intent" placeholder="atex"></label>'
                        '<label>知识负责人 <input name="owner"></label>'
                        '<label>人工确认答案 <input name="human_answer"></label>'
                        '<button>提交知识治理</button></form>'
                        f'<h3>审核事件</h3><pre>{escape(json.dumps(store.reviews(case_id), ensure_ascii=False, indent=2))}</pre>')
                return self.respond(body)
            finally:
                store.close()

        def do_POST(self):
            path = urlparse(self.path).path
            if not path.startswith('/item/'):
                return self.respond('未找到', 404)
            size = int(self.headers.get('Content-Length', '0'))
            if size > 32768:
                return self.respond('请求过大', 413)
            data = parse_qs(self.rfile.read(size).decode(), keep_blank_values=True)
            val = lambda key: data.get(key, [''])[0]
            if val('csrf') != csrf:
                return self.respond('CSRF token 无效', 403)
            store = DraftStore(db_path)
            try:
                case_id = unquote(path.removeprefix('/item/'))
                if val('kind') == 'gap':
                    store.confirm_gap(case_id, val('intent'), val('owner'), val('human_answer'))
                elif val('kind') == 'review':
                    edited = val('edited_body') if val('action') in ('minor_edit', 'major_edit') else None
                    store.review(case_id, val('action'), val('reviewer'), val('reviewer_role'),
                                 val('comment'), edited)
                else:
                    raise ValueError('无效操作类型')
            except ValueError as exc:
                return self.respond(escape(str(exc)), 400)
            finally:
                store.close()
            self.send_response(303)
            self.send_header('Location', path)
            self.end_headers()

    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f'草稿审核页面：http://127.0.0.1:{server.server_port}/', flush=True)
    server.serve_forever()
