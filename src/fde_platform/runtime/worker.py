"""Bounded-retry worker and localhost-only transactional outbox dispatcher."""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener

from fde_platform.onboarding.shadow import process_shadow


class DeliveryWorker:
    def __init__(self, store, components, *, worker_id='worker-1', fault_plan=None):
        self.store, self.components, self.worker_id = store, components, worker_id
        self.fault_plan = dict(fault_plan or {})

    def once(self, tick):
        job = self.store.claim_job(self.worker_id, tick)
        if not job:
            return None
        event_id = job['event_id']
        attempt = job['attempt_count']
        try:
            mode = self.fault_plan.get(event_id)
            if mode == 'timeout_once' and attempt == 1:
                raise TimeoutError('simulated_connector_context_timeout')
            if mode == 'permanent_schema_drift':
                raise ValueError('simulated_unmapped_required_field')
            artifact = process_shadow(job['payload'], self.components)
            self.store.complete_job(event_id, artifact)
            return {'event_id': event_id, 'state': 'done', 'attempt': attempt,
                    'case_id': job['case_id'], 'route': artifact['route']}
        except (OSError, TimeoutError, ValueError, KeyError, TypeError) as exc:
            state = self.store.fail_job(event_id, exc, tick)
            return {'event_id': event_id, 'state': state, 'attempt': attempt,
                    'error': str(exc)}

    def drain(self, *, start_tick=0, end_tick=32):
        results = []
        for tick in range(start_tick, end_tick + 1):
            while True:
                item = self.once(tick)
                if not item:
                    break
                results.append(item)
        return results


class RecordingMockSink:
    """Durable-process substitute for the localhost HTTP sink used in tests/demo."""
    mode = 'synthetic_recording_mock_sink'

    def __init__(self, fault_plan=None):
        self.fault_plan = dict(fault_plan or {})
        self.attempts, self.deliveries = {}, {}

    def deliver(self, message):
        key = message['idempotency_key']
        attempt = self.attempts.get(key, 0) + 1
        self.attempts[key] = attempt
        mode = self.fault_plan.get(key)
        if mode == 'retry_once' and attempt == 1:
            raise RuntimeError('mock_sink_429_rate_limited')
        if mode == 'permanent_failure':
            raise RuntimeError('mock_sink_503_unavailable')
        duplicate = key in self.deliveries
        self.deliveries.setdefault(key, message['payload'])
        return {'status': 'duplicate' if duplicate else 'accepted',
                'mock_delivery': True, 'idempotency_key': key}


class LocalHttpSink:
    """HTTP adapter that refuses non-loopback endpoints and carries idempotency keys."""
    mode = 'localhost_http_mock_sink'

    def __init__(self, endpoint, bearer_token, opener=None):
        parsed = urlparse(endpoint)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost'):
            raise ValueError('Stage 11 只允许投递到本机 HTTP Mock Sink')
        self.endpoint, self.token = endpoint, bearer_token
        self.opener = opener or build_opener()

    def deliver(self, message):
        body = json.dumps(message['payload'], ensure_ascii=False).encode()
        request = Request(self.endpoint, data=body, method='POST', headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.token}',
            'Idempotency-Key': message['idempotency_key'],
        })
        try:
            with self.opener.open(request, timeout=3) as response:
                result = json.loads(response.read(100_000))
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f'localhost_mock_delivery_failed: {exc}') from exc
        if result.get('mock_delivery') is not True:
            raise RuntimeError('本机 Sink 未返回 mock_delivery 标记')
        return result


def fetch_local_mock_token(token_endpoint, client_secret, opener=None):
    parsed = urlparse(token_endpoint)
    if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost'):
        raise ValueError('Stage 11 OAuth 演练只允许本机端点')
    request = Request(token_endpoint, data=b'{}', method='POST', headers={
        'Content-Type': 'application/json', 'X-Client-Secret': client_secret})
    try:
        with (opener or build_opener()).open(request, timeout=3) as response:
            value = json.loads(response.read(100_000))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f'localhost_mock_oauth_failed: {exc}') from exc
    if value.get('token_type') != 'Bearer' or not value.get('access_token'):
        raise RuntimeError('本机 OAuth 响应不完整')
    return value['access_token']


class OutboxDispatcher:
    def __init__(self, store, sink):
        self.store, self.sink = store, sink

    def once(self, tick):
        ready = self.store.ready_messages(tick)
        if not ready:
            return None
        message = ready[0]
        try:
            result = self.sink.deliver(message)
            state = self.store.delivery_result(message['message_id'], True,
                                                json.dumps(result, sort_keys=True), tick)
        except (OSError, RuntimeError, ValueError) as exc:
            state = self.store.delivery_result(message['message_id'], False, str(exc), tick)
        return {'message_id': message['message_id'], 'state': state}

    def drain(self, *, start_tick=0, end_tick=32):
        results = []
        for tick in range(start_tick, end_tick + 1):
            while True:
                item = self.once(tick)
                if not item:
                    break
                results.append(item)
        return results
