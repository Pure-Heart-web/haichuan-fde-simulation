#!/usr/bin/env python3
"""Loopback-only stand-in for the Stage 9 model adapter contract; no LLM calls."""
import argparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from fde_platform.core.ingestion import from_text
from fde_platform.domains.foreign_trade.baseline import RegexBaselineProvider


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/extract':
            self.send_error(404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 100_000:
                raise ValueError('invalid request size')
            request = json.loads(self.rfile.read(length))
            if request.get('protocol') != 'fde-extract-v1':
                raise ValueError('unsupported protocol')
            item = request['work_item']
            work = from_text(item['body'], source_id=item['source_id'])
            output = json.loads(RegexBaselineProvider().complete(work, request['prompt_version']))
            data = json.dumps({'output': output, 'cost_usd': 0.0,
                               'mode': 'deterministic_stand_in_not_a_model'},
                              ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            self.send_error(400, str(exc))

    def log_message(self, fmt, *args):
        pass


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8810)
    args = parser.parse_args()
    HTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
