"""Local-only Stage 5 human review page; never sends customer communications."""
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse
import secrets

from fde_platform.domains.foreign_trade.recommendation.store import RecommendationStore


def serve(db_path, port=8766):
    csrf = secrets.token_urlsafe(24)

    class Handler(BaseHTTPRequestHandler):
        def respond(self, body, status=200):
            data = ('<!doctype html><html lang="zh"><meta charset="utf-8"><title>Stage 5 审核</title>'
                    '<style>body{font:16px system-ui;max-width:960px;margin:2rem auto;line-height:1.5}'
                    'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:.5rem}'
                    'pre{white-space:pre-wrap;background:#f5f5f5;padding:1rem}label{display:block;margin:.5rem 0}'
                    'button{margin:.5rem}</style><body><a href="/">队列</a><h1>Stage 5 产品候选审核</h1>'
                    '<p>所有建议为教学模拟；人工审核后仍不构成客户报价或最终工程选型。</p>' + body + '</body></html>').encode()
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            store = RecommendationStore(db_path)
            try:
                path = urlparse(self.path).path
                if path == '/':
                    rows = ''.join(f'<tr><td><a href="/item/{quote(x["work_item_id"])}">{escape(x["work_item_id"])}</a></td>'
                                   f'<td>{escape(x["result"]["status"])}</td><td>{escape(x["result"]["required_reviewer"])}</td>'
                                   f'<td>{escape(x["latest_action"] or "待审核")}</td></tr>' for x in store.list_items())
                    return self.respond('<table><tr><th>任务</th><th>状态</th><th>审核角色</th><th>最近动作</th></tr>' + rows + '</table>')
                if not path.startswith('/item/'):
                    return self.respond('未找到', 404)
                key = unquote(path.removeprefix('/item/'))
                item = store.get_item(key)
                if item is None:
                    return self.respond('任务不存在', 404)
                import json
                result = item['result']
                candidates = ''.join('<tr><td>' + escape(c['sku']) + '</td><td>' + str(c['score']) +
                  '</td><td>' + escape(json.dumps(c['evidence'], ensure_ascii=False)) + '</td><td>' +
                  escape(', '.join(c['warnings'])) + '</td></tr>' for c in result['candidates'])
                choices = ''.join(f'<option value="{escape(c["sku"])}">{escape(c["sku"])}</option>' for c in result['candidates'])
                history = escape(json.dumps(store.reviews(key), ensure_ascii=False, indent=2))
                body = (f'<h2>{escape(key)}</h2><p>来源：{escape(item["origin"])}；状态：{escape(result["status"])}；'
                        f'要求审核：{escape(result["required_reviewer"])}</p>'
                        f'<details><summary>查看原始结构化询盘</summary><pre>{escape(json.dumps(item["inquiry"], ensure_ascii=False, indent=2))}</pre></details>'
                        '<h3>候选与来源</h3><table><tr><th>SKU</th><th>排序分</th><th>证据</th><th>警告</th></tr>'
                        + candidates + '</table>'
                        f'<p>警告：{escape(", ".join(result["warnings"]) or "无")}；缺口：{escape(", ".join(result["missing_information"]) or "无")}</p>'
                        f'<details><summary>查看规则命中与排除明细</summary><pre>{escape(json.dumps({k: result[k] for k in ("triggered_rules", "rejected_candidates")}, ensure_ascii=False, indent=2))}</pre></details>'
                        f'<form method="post"><input type="hidden" name="csrf" value="{csrf}">'
                        '<label>审核人 <input name="reviewer" required></label>'
                        '<label>角色 <select name="reviewer_role"><option>sales</option><option>engineer</option></select></label>'
                        f'<label>候选 <select name="chosen_sku"><option value="">无</option>{choices}</select></label>'
                        '<label>原因 <textarea name="reason"></textarea></label>'
                        '<button name="action" value="approve">批准暂列首位</button>'
                        '<button name="action" value="choose_another">选择其他候选</button>'
                        '<button name="action" value="escalate">升级</button></form>'
                        f'<h3>追加式审核记录</h3><pre>{history}</pre>')
                return self.respond(body)
            finally:
                store.close()

        def do_POST(self):
            path = urlparse(self.path).path
            if not path.startswith('/item/'):
                return self.respond('未找到', 404)
            size = int(self.headers.get('Content-Length', '0'))
            if size > 16384:
                return self.respond('请求过大', 413)
            data = parse_qs(self.rfile.read(size).decode(), keep_blank_values=True)
            val = lambda key: data.get(key, [''])[0]
            if val('csrf') != csrf:
                return self.respond('CSRF token 无效', 403)
            store = RecommendationStore(db_path)
            try:
                store.review(unquote(path.removeprefix('/item/')), val('action'), val('reviewer'),
                             val('reviewer_role'), val('chosen_sku') or None, val('reason'))
            except ValueError as exc:
                return self.respond(escape(str(exc)), 400)
            finally:
                store.close()
            self.send_response(303)
            self.send_header('Location', path)
            self.end_headers()

    server = HTTPServer(('127.0.0.1', port), Handler)
    print(f'审核页面：http://127.0.0.1:{server.server_port}/', flush=True)
    server.serve_forever()
