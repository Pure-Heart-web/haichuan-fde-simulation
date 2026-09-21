#!/usr/bin/env python3
"""Run the local API and localhost Mock Sink together for Docker or workshops."""
import argparse
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading

from stage11 import PLAN, build_runtime, prepare, read, run_worker
from stage11_mock_server import MockState, handler_for
from fde_platform.runtime.api import serve
from fde_platform.runtime.worker import (DeliveryWorker, LocalHttpSink,
                                          OutboxDispatcher)


def main():
    parser = argparse.ArgumentParser(description='Stage 11 本地双服务启动器')
    parser.add_argument('--output', type=Path, default=Path('outputs/stage-11'))
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8781)
    parser.add_argument('--mock-port', type=int, default=8782)
    args = parser.parse_args()
    output = args.output.resolve()
    db = output / 'delivery-room.sqlite3'
    if not db.exists():
        prepare(output)
        run_worker(output)
    mock = ThreadingHTTPServer(('127.0.0.1', args.mock_port), handler_for(
        MockState(output / 'mock-deliveries.json', 'stage11-local-secret')))
    thread = threading.Thread(target=mock.serve_forever, daemon=True)
    thread.start()
    manifest, broker, credentials, store, service = build_runtime(output)
    plan = read(PLAN)
    worker = DeliveryWorker(store, service.components, fault_plan=plan['worker']['faults'])
    sink = LocalHttpSink(f'http://127.0.0.1:{args.mock_port}/deliveries',
                         'stage11-local-mock-token')
    dispatcher = OutboxDispatcher(store, sink)
    try:
        serve(service, worker, dispatcher, host=args.host, port=args.port)
    finally:
        mock.shutdown()
        mock.server_close()
        store.close()


if __name__ == '__main__':
    main()
