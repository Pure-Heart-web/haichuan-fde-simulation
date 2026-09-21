#!/usr/bin/env python3
"""Local-only OAuth and delivery sink used by the Stage 11 HTTP exercise."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading


class MockState:
    def __init__(self, output, client_secret):
        self.output, self.client_secret = Path(output), client_secret
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.lock, self.deliveries = threading.RLock(), {}
        if self.output.exists():
            self.deliveries = json.loads(self.output.read_text())

    def save(self):
        self.output.write_text(json.dumps(self.deliveries, ensure_ascii=False,
                                          indent=2) + '\n')


def handler_for(state):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'FDELocalMock/1'

        def log_message(self, fmt, *args):
            return

        def send_json(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/health':
                return self.send_json(200, {'status': 'ok', 'mock_only': True})
            if self.path == '/deliveries':
                if self.headers.get('Authorization') != 'Bearer stage11-local-mock-token':
                    return self.send_json(401, {'error': 'invalid_token'})
                with state.lock:
                    return self.send_json(200, {'deliveries': state.deliveries,
                                                'mock_only': True})
            self.send_json(404, {'error': 'not_found'})

        def do_POST(self):
            if self.path == '/oauth/token':
                if self.headers.get('X-Client-Secret') != state.client_secret:
                    return self.send_json(401, {'error': 'invalid_client'})
                return self.send_json(200, {'access_token': 'stage11-local-mock-token',
                                            'token_type': 'Bearer', 'expires_in': 300})
            if self.path != '/deliveries':
                return self.send_json(404, {'error': 'not_found'})
            if self.headers.get('Authorization') != 'Bearer stage11-local-mock-token':
                return self.send_json(401, {'error': 'invalid_token'})
            key = self.headers.get('Idempotency-Key', '')
            if not key:
                return self.send_json(400, {'error': 'missing_idempotency_key'})
            length = int(self.headers.get('Content-Length', 0))
            if length > 100_000:
                return self.send_json(413, {'error': 'too_large'})
            try:
                payload = json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                return self.send_json(400, {'error': 'invalid_json'})
            with state.lock:
                duplicate = key in state.deliveries
                state.deliveries.setdefault(key, payload)
                state.save()
            self.send_json(200, {'status': 'duplicate' if duplicate else 'accepted',
                                 'mock_delivery': True, 'idempotency_key': key})

    return Handler


def main():
    parser = argparse.ArgumentParser(description='Stage 11 本机模拟客户端点')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8782)
    parser.add_argument('--output', type=Path, default=Path('outputs/stage-11/mock-deliveries.json'))
    parser.add_argument('--client-secret', default='stage11-local-secret')
    args = parser.parse_args()
    if args.host not in ('127.0.0.1', 'localhost'):
        parser.error('模拟服务只允许绑定本机')
    server = ThreadingHTTPServer((args.host, args.port),
                                 handler_for(MockState(args.output, args.client_secret)))
    print(f'Stage 11 Mock Sink: http://{args.host}:{args.port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
