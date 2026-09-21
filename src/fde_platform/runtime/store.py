"""SQLite reference runtime with durable jobs, reviews and a transactional outbox."""
import hashlib
import json
import sqlite3
import threading

from fde_platform.core.models import utc_now
from fde_platform.onboarding.privacy import contains_direct_identifier

SCHEMA_VERSION = 1


class RuntimeStore:
    def __init__(self, path, tenant_id, domain):
        self.path = str(path)
        self.tenant_id, self.domain = tenant_id, domain
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        version = self.conn.execute('PRAGMA user_version').fetchone()[0]
        if version > SCHEMA_VERSION:
            raise ValueError('运行库版本高于当前代码，禁止降级打开')
        if version == 0:
            self._migrate_v1()
        elif version != SCHEMA_VERSION:
            raise ValueError('运行库迁移不完整')

    def _migrate_v1(self):
        with self.conn:
            self.conn.executescript('''
              CREATE TABLE migration_history (
                version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL
              );
              CREATE TABLE inbox (
                tenant_id TEXT NOT NULL, domain TEXT NOT NULL, event_id TEXT NOT NULL,
                source_id TEXT NOT NULL, source_version INTEGER NOT NULL,
                case_id TEXT NOT NULL, digest TEXT NOT NULL, payload_json TEXT NOT NULL,
                state TEXT NOT NULL, attempt_count INTEGER NOT NULL DEFAULT 0,
                available_tick INTEGER NOT NULL DEFAULT 0, locked_by TEXT,
                locked_tick INTEGER, last_error TEXT, superseded INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, domain, event_id),
                UNIQUE (tenant_id, domain, source_id, source_version)
              );
              CREATE TABLE cases (
                tenant_id TEXT NOT NULL, domain TEXT NOT NULL, case_id TEXT NOT NULL,
                source_id TEXT NOT NULL, source_version INTEGER NOT NULL,
                route TEXT NOT NULL, assignee_id TEXT NOT NULL, assignee_role TEXT NOT NULL,
                artifact_json TEXT NOT NULL, state TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, domain, case_id)
              );
              CREATE TABLE reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL,
                domain TEXT NOT NULL, case_id TEXT NOT NULL, actor_id TEXT NOT NULL,
                actor_role TEXT NOT NULL, action TEXT NOT NULL, reason TEXT NOT NULL,
                created_at TEXT NOT NULL
              );
              CREATE TABLE outbox (
                tenant_id TEXT NOT NULL, domain TEXT NOT NULL, message_id TEXT NOT NULL,
                case_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                payload_json TEXT NOT NULL, state TEXT NOT NULL,
                reviewer_id TEXT NOT NULL, approver_id TEXT,
                attempt_count INTEGER NOT NULL DEFAULT 0,
                available_tick INTEGER NOT NULL DEFAULT 0, last_error TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, domain, message_id),
                UNIQUE (tenant_id, domain, case_id),
                UNIQUE (tenant_id, domain, idempotency_key)
              );
              CREATE TABLE delivery_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL,
                domain TEXT NOT NULL, message_id TEXT NOT NULL, attempt INTEGER NOT NULL,
                result TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
              );
              CREATE TABLE audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT NOT NULL,
                actor_id TEXT NOT NULL, action TEXT NOT NULL, object_id TEXT NOT NULL,
                allowed INTEGER NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL
              );
              CREATE TABLE incidents (
                incident_id TEXT PRIMARY KEY, kind TEXT NOT NULL, object_id TEXT NOT NULL,
                state TEXT NOT NULL, detail TEXT NOT NULL, opened_at TEXT NOT NULL,
                resolved_at TEXT
              );
            ''')
            self.conn.execute('INSERT INTO migration_history VALUES (?,?)',
                              (SCHEMA_VERSION, utc_now()))
            self.conn.execute(f'PRAGMA user_version={SCHEMA_VERSION}')

    def close(self):
        with self.lock:
            self.conn.close()

    def _scope(self, tenant_id):
        if tenant_id != self.tenant_id:
            raise ValueError('禁止跨租户访问 Delivery Room')

    def _audit(self, tenant_id, actor_id, action, object_id, allowed, detail=''):
        self.conn.execute('''INSERT INTO audit
            (tenant_id,actor_id,action,object_id,allowed,detail,created_at)
            VALUES (?,?,?,?,?,?,?)''',
            (tenant_id, actor_id, action, object_id, int(allowed), detail, utc_now()))

    def accept(self, event):
        self._scope(event['tenant_id'])
        if event['domain'] != self.domain:
            raise ValueError('Domain 与运行时不匹配')
        if contains_direct_identifier(event):
            raise ValueError('运行时拒绝直接邮箱或电话号码')
        canonical = json.dumps(event, ensure_ascii=False, sort_keys=True,
                               separators=(',', ':'))
        digest = hashlib.sha256(canonical.encode()).hexdigest()
        now = utc_now()
        with self.lock, self.conn:
            old = self.conn.execute('''SELECT digest FROM inbox WHERE tenant_id=?
                AND domain=? AND event_id=?''',
                (self.tenant_id, self.domain, event['event_id'])).fetchone()
            if old:
                if old['digest'] != digest:
                    raise ValueError('同一 event_id 的净化内容发生变化')
                self._audit(self.tenant_id, 'connector', 'duplicate_event',
                            event['event_id'], True)
                return 'duplicate'
            prior = self.conn.execute('''SELECT MAX(source_version) AS version FROM inbox
                WHERE tenant_id=? AND domain=? AND source_id=?''',
                (self.tenant_id, self.domain, event['source_id'])).fetchone()['version']
            expected = 1 if prior is None else prior + 1
            if event['source_version'] != expected:
                raise ValueError(f'来源版本必须连续：期望 {expected}')
            if prior is not None:
                self.conn.execute('''UPDATE inbox SET superseded=1,updated_at=?
                    WHERE tenant_id=? AND domain=? AND source_id=?''',
                    (now, self.tenant_id, self.domain, event['source_id']))
            self.conn.execute('''INSERT INTO inbox
                (tenant_id,domain,event_id,source_id,source_version,case_id,digest,payload_json,
                 state,attempt_count,available_tick,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (self.tenant_id, self.domain, event['event_id'], event['source_id'],
                 event['source_version'], event['case_id'], digest, canonical, 'queued',
                 0, 0, now, now))
            self._audit(self.tenant_id, 'connector', 'accept_event', event['event_id'], True,
                        'updated' if prior is not None else 'created')
            return 'updated' if prior is not None else 'created'

    def claim_job(self, worker_id, tick):
        with self.lock:
            self.conn.execute('BEGIN IMMEDIATE')
            try:
                row = self.conn.execute('''SELECT * FROM inbox WHERE tenant_id=? AND domain=?
                    AND state IN ('queued','retry') AND available_tick<=?
                    ORDER BY created_at,event_id LIMIT 1''',
                    (self.tenant_id, self.domain, tick)).fetchone()
                if not row:
                    self.conn.commit()
                    return None
                changed = self.conn.execute('''UPDATE inbox SET state='processing',locked_by=?,
                    locked_tick=?,attempt_count=attempt_count+1,updated_at=?
                    WHERE tenant_id=? AND domain=? AND event_id=? AND state IN ('queued','retry')''',
                    (worker_id, tick, utc_now(), self.tenant_id, self.domain,
                     row['event_id'])).rowcount
                if changed != 1:
                    self.conn.rollback()
                    return None
                self.conn.commit()
                item = dict(self.conn.execute('''SELECT * FROM inbox WHERE tenant_id=?
                    AND domain=? AND event_id=?''',
                    (self.tenant_id, self.domain, row['event_id'])).fetchone())
                item['payload'] = json.loads(item.pop('payload_json'))
                return item
            except Exception:
                self.conn.rollback()
                raise

    def recover_leases(self, tick, lease_ticks=3):
        with self.lock, self.conn:
            rows = self.conn.execute('''SELECT event_id FROM inbox WHERE tenant_id=?
                AND domain=? AND state='processing' AND locked_tick<=?''',
                (self.tenant_id, self.domain, tick - lease_ticks)).fetchall()
            for row in rows:
                self.conn.execute('''UPDATE inbox SET state='retry',locked_by=NULL,
                    locked_tick=NULL,available_tick=?,last_error='worker_lease_expired',updated_at=?
                    WHERE tenant_id=? AND domain=? AND event_id=?''',
                    (tick, utc_now(), self.tenant_id, self.domain, row['event_id']))
                self._audit(self.tenant_id, 'runtime', 'recover_worker_lease',
                            row['event_id'], True)
            return len(rows)

    def complete_job(self, event_id, artifact):
        if contains_direct_identifier(artifact):
            raise ValueError('案例产物含直接标识符')
        now = utc_now()
        payload = json.dumps(artifact, ensure_ascii=False, sort_keys=True)
        with self.lock, self.conn:
            job = self.conn.execute('''SELECT * FROM inbox WHERE tenant_id=? AND domain=?
                AND event_id=? AND state='processing' ''',
                (self.tenant_id, self.domain, event_id)).fetchone()
            if not job:
                raise ValueError('待完成 Worker Job 不存在')
            old = self.conn.execute('''SELECT source_version FROM cases WHERE tenant_id=?
                AND domain=? AND case_id=?''',
                (self.tenant_id, self.domain, job['case_id'])).fetchone()
            if old and old['source_version'] >= job['source_version']:
                raise ValueError('案例来源版本没有前进')
            if old:
                self.conn.execute('''UPDATE cases SET source_version=?,route=?,assignee_id=?,
                    assignee_role=?,artifact_json=?,state='pending_review',updated_at=?
                    WHERE tenant_id=? AND domain=? AND case_id=?''',
                    (job['source_version'], artifact['route'], artifact['assignee_id'],
                     artifact['assignee_role'], payload, now, self.tenant_id,
                     self.domain, job['case_id']))
                self.conn.execute('''DELETE FROM reviews WHERE tenant_id=? AND domain=?
                    AND case_id=?''', (self.tenant_id, self.domain, job['case_id']))
                self.conn.execute('''DELETE FROM outbox WHERE tenant_id=? AND domain=?
                    AND case_id=? AND state!='delivered' ''',
                    (self.tenant_id, self.domain, job['case_id']))
            else:
                self.conn.execute('''INSERT INTO cases VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                    (self.tenant_id, self.domain, job['case_id'], job['source_id'],
                     job['source_version'], artifact['route'], artifact['assignee_id'],
                     artifact['assignee_role'], payload, 'pending_review', now))
            self.conn.execute('''UPDATE inbox SET state='done',locked_by=NULL,locked_tick=NULL,
                last_error=NULL,updated_at=? WHERE tenant_id=? AND domain=? AND event_id=?''',
                (now, self.tenant_id, self.domain, event_id))
            self._audit(self.tenant_id, 'worker', 'complete_job', event_id, True,
                        artifact['route'])

    def fail_job(self, event_id, error, tick, max_attempts=3):
        with self.lock, self.conn:
            row = self.conn.execute('''SELECT attempt_count FROM inbox WHERE tenant_id=?
                AND domain=? AND event_id=? AND state='processing' ''',
                (self.tenant_id, self.domain, event_id)).fetchone()
            if not row:
                raise ValueError('失败 Job 不存在')
            dead = row['attempt_count'] >= max_attempts
            state = 'dead' if dead else 'retry'
            available = tick if dead else tick + 2 ** row['attempt_count']
            self.conn.execute('''UPDATE inbox SET state=?,available_tick=?,locked_by=NULL,
                locked_tick=NULL,last_error=?,updated_at=? WHERE tenant_id=? AND domain=?
                AND event_id=?''', (state, available, str(error)[:300], utc_now(),
                self.tenant_id, self.domain, event_id))
            self._audit(self.tenant_id, 'worker', f'job_{state}', event_id, True,
                        str(error)[:120])
            if dead:
                self._open_incident('worker_dead_letter', event_id, str(error))
            return state

    def _open_incident(self, kind, object_id, detail):
        incident_id = hashlib.sha256(f'{kind}|{object_id}'.encode()).hexdigest()[:16]
        self.conn.execute('''INSERT OR IGNORE INTO incidents
            (incident_id,kind,object_id,state,detail,opened_at) VALUES (?,?,?,?,?,?)''',
            (incident_id, kind, object_id, 'open', str(detail)[:300], utc_now()))
        return incident_id

    def cases(self, tenant_id, actor_id):
        allowed = tenant_id == self.tenant_id
        with self.lock, self.conn:
            self._audit(tenant_id, actor_id, 'list_cases', '*', allowed)
            if not allowed:
                raise ValueError('禁止跨租户访问 Delivery Room')
            rows = self.conn.execute('''SELECT * FROM cases WHERE tenant_id=? AND domain=?
                ORDER BY case_id''', (self.tenant_id, self.domain)).fetchall()
            return [self._case(row) for row in rows]

    def case(self, tenant_id, case_id, actor_id):
        allowed = tenant_id == self.tenant_id
        with self.lock, self.conn:
            self._audit(tenant_id, actor_id, 'read_case', case_id, allowed)
            if not allowed:
                raise ValueError('禁止跨租户访问 Delivery Room')
            row = self.conn.execute('''SELECT * FROM cases WHERE tenant_id=? AND domain=?
                AND case_id=?''', (self.tenant_id, self.domain, case_id)).fetchone()
            return self._case(row) if row else None

    @staticmethod
    def _case(row):
        item = dict(row)
        item['artifact'] = json.loads(item.pop('artifact_json'))
        return item

    def review(self, tenant_id, case_id, claims, action, reason):
        if tenant_id != claims['tenant_id']:
            raise ValueError('身份租户与请求不匹配')
        item = self.case(tenant_id, case_id, claims['sub'])
        if not item or (claims['sub'], claims['role']) != (
                item['assignee_id'], item['assignee_role']):
            raise ValueError('当前身份不是案例负责人')
        if item['state'] != 'pending_review':
            raise ValueError('案例不在待审核状态')
        if action not in ('accept', 'edit', 'escalate', 'reject') or not reason.strip():
            raise ValueError('审核动作或理由无效')
        if contains_direct_identifier(reason):
            raise ValueError('审核理由不得包含直接邮箱或电话号码')
        now = utc_now()
        with self.lock, self.conn:
            self.conn.execute('''INSERT INTO reviews
                (tenant_id,domain,case_id,actor_id,actor_role,action,reason,created_at)
                VALUES (?,?,?,?,?,?,?,?)''',
                (self.tenant_id, self.domain, case_id, claims['sub'], claims['role'],
                 action, reason.strip(), now))
            next_state = 'reviewed_no_delivery'
            message_id = None
            if action in ('accept', 'edit') and item['route'] != 'quarantine':
                message_id = 'MSG-' + hashlib.sha256(
                    f'{self.tenant_id}|{case_id}|{item["source_version"]}'.encode()).hexdigest()[:16]
                payload = {'mode': 'synthetic_mock_delivery', 'case_id': case_id,
                    'source_version': item['source_version'],
                    'decision': 'reviewed_internal_result',
                    'content': '模拟客户回执：内部审核完成；此消息只允许投递到本机 Mock Sink。'}
                self.conn.execute('''INSERT INTO outbox
                    (tenant_id,domain,message_id,case_id,idempotency_key,payload_json,state,
                     reviewer_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (self.tenant_id, self.domain, message_id, case_id, message_id,
                     json.dumps(payload, ensure_ascii=False, sort_keys=True),
                     'pending_approval', claims['sub'], now, now))
                next_state = 'awaiting_release_approval'
            self.conn.execute('''UPDATE cases SET state=?,updated_at=? WHERE tenant_id=?
                AND domain=? AND case_id=?''',
                (next_state, now, self.tenant_id, self.domain, case_id))
            self._audit(self.tenant_id, claims['sub'], 'review_case', case_id, True, action)
            return {'case_id': case_id, 'state': next_state, 'message_id': message_id}

    def approve_message(self, tenant_id, message_id, claims):
        self._scope(tenant_id)
        if claims['tenant_id'] != tenant_id or claims['role'] != 'release_manager':
            raise ValueError('只有当前租户 Release Manager 可以批准 Outbox')
        with self.lock, self.conn:
            row = self.conn.execute('''SELECT * FROM outbox WHERE tenant_id=? AND domain=?
                AND message_id=?''', (self.tenant_id, self.domain, message_id)).fetchone()
            if not row or row['state'] != 'pending_approval':
                raise ValueError('Outbox 消息不存在或不待批准')
            if row['reviewer_id'] == claims['sub']:
                raise ValueError('审核人与发布批准人必须分离')
            self.conn.execute('''UPDATE outbox SET state='ready',approver_id=?,updated_at=?
                WHERE tenant_id=? AND domain=? AND message_id=?''',
                (claims['sub'], utc_now(), self.tenant_id, self.domain, message_id))
            self._audit(self.tenant_id, claims['sub'], 'approve_outbox', message_id, True)
            return True

    def ready_messages(self, tick):
        with self.lock:
            rows = self.conn.execute('''SELECT * FROM outbox WHERE tenant_id=? AND domain=?
                AND state IN ('ready','retry') AND available_tick<=? ORDER BY message_id''',
                (self.tenant_id, self.domain, tick)).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item['payload'] = json.loads(item.pop('payload_json'))
                result.append(item)
            return result

    def delivery_result(self, message_id, success, detail, tick, max_attempts=3):
        with self.lock, self.conn:
            row = self.conn.execute('''SELECT attempt_count,case_id FROM outbox WHERE tenant_id=?
                AND domain=? AND message_id=? AND state IN ('ready','retry')''',
                (self.tenant_id, self.domain, message_id)).fetchone()
            if not row:
                raise ValueError('待投递 Outbox 消息不存在')
            attempt = row['attempt_count'] + 1
            if success:
                state, available, error = 'delivered', tick, None
            elif attempt >= max_attempts:
                state, available, error = 'dead', tick, str(detail)[:300]
            else:
                state, available, error = 'retry', tick + 2 ** attempt, str(detail)[:300]
            self.conn.execute('''UPDATE outbox SET state=?,attempt_count=?,available_tick=?,
                last_error=?,updated_at=? WHERE tenant_id=? AND domain=? AND message_id=?''',
                (state, attempt, available, error, utc_now(), self.tenant_id,
                 self.domain, message_id))
            self.conn.execute('''INSERT INTO delivery_attempts
                (tenant_id,domain,message_id,attempt,result,detail,created_at)
                VALUES (?,?,?,?,?,?,?)''',
                (self.tenant_id, self.domain, message_id, attempt, state,
                 str(detail)[:300], utc_now()))
            if state == 'delivered':
                self.conn.execute('''UPDATE cases SET state='mock_delivered',updated_at=?
                    WHERE tenant_id=? AND domain=? AND case_id=?''',
                    (utc_now(), self.tenant_id, self.domain, row['case_id']))
            elif state == 'dead':
                self.conn.execute('''UPDATE cases SET state='delivery_failed',updated_at=?
                    WHERE tenant_id=? AND domain=? AND case_id=?''',
                    (utc_now(), self.tenant_id, self.domain, row['case_id']))
                self._open_incident('outbox_dead_letter', message_id, detail)
            self._audit(self.tenant_id, 'dispatcher', f'outbox_{state}', message_id,
                        True, str(detail)[:120])
            return state

    def outbox(self):
        with self.lock:
            return [dict(x) for x in self.conn.execute('''SELECT message_id,case_id,state,
                reviewer_id,approver_id,attempt_count,last_error FROM outbox
                WHERE tenant_id=? AND domain=? ORDER BY message_id''',
                (self.tenant_id, self.domain))]

    def trace(self, tenant_id, case_id, actor_id):
        item = self.case(tenant_id, case_id, actor_id)
        if not item:
            raise ValueError('案例不存在')
        with self.lock:
            source = [dict(x) for x in self.conn.execute('''SELECT event_id,source_id,
                source_version,state,attempt_count,last_error,superseded,created_at,updated_at
                FROM inbox WHERE tenant_id=? AND domain=? AND case_id=? ORDER BY source_version''',
                (self.tenant_id, self.domain, case_id))]
            reviews = [dict(x) for x in self.conn.execute('''SELECT actor_id,actor_role,action,
                reason,created_at FROM reviews WHERE tenant_id=? AND domain=? AND case_id=?
                ORDER BY id''', (self.tenant_id, self.domain, case_id))]
            messages = [dict(x) for x in self.conn.execute('''SELECT message_id,state,
                reviewer_id,approver_id,attempt_count,last_error,created_at,updated_at FROM outbox
                WHERE tenant_id=? AND domain=? AND case_id=?''',
                (self.tenant_id, self.domain, case_id))]
            attempts = [dict(x) for x in self.conn.execute('''SELECT d.message_id,d.attempt,
                d.result,d.detail,d.created_at FROM delivery_attempts d JOIN outbox o
                ON o.message_id=d.message_id WHERE o.tenant_id=? AND o.domain=? AND o.case_id=?
                ORDER BY d.id''', (self.tenant_id, self.domain, case_id))]
            return {'tenant_id': tenant_id, 'case_id': case_id, 'source_events': source,
                    'case': item, 'reviews': reviews, 'outbox': messages,
                    'delivery_attempts': attempts}

    def metrics(self):
        with self.lock:
            def histogram(table, field):
                return {row[field]: row['n'] for row in self.conn.execute(
                    f'''SELECT {field},COUNT(*) n FROM {table} WHERE tenant_id=? AND domain=?
                        GROUP BY {field}''', (self.tenant_id, self.domain))}
            attempts = self.conn.execute('''SELECT COUNT(*) n FROM delivery_attempts
                WHERE tenant_id=? AND domain=?''', (self.tenant_id, self.domain)).fetchone()['n']
            reviews = self.conn.execute('''SELECT COUNT(*) n FROM reviews WHERE tenant_id=?
                AND domain=?''', (self.tenant_id, self.domain)).fetchone()['n']
            incidents = [dict(x) for x in self.conn.execute(
                'SELECT * FROM incidents ORDER BY opened_at,incident_id')]
            worker_attempts = self.conn.execute('''SELECT COALESCE(SUM(attempt_count),0) n
                FROM inbox WHERE tenant_id=? AND domain=?''',
                (self.tenant_id, self.domain)).fetchone()['n']
            unapproved = self.conn.execute('''SELECT COUNT(*) n FROM outbox WHERE tenant_id=?
                AND domain=? AND state='delivered' AND approver_id IS NULL''',
                (self.tenant_id, self.domain)).fetchone()['n']
            return {'schema_version': SCHEMA_VERSION, 'inbox': histogram('inbox', 'state'),
                    'cases': histogram('cases', 'state'), 'outbox': histogram('outbox', 'state'),
                    'review_count': reviews, 'delivery_attempt_count': attempts,
                    'worker_attempt_count': worker_attempts,
                    'unapproved_deliveries': unapproved, 'incidents': incidents}

    def privacy_scan(self):
        with self.lock:
            values = []
            values.extend(row['payload_json'] for row in self.conn.execute(
                'SELECT payload_json FROM inbox WHERE tenant_id=? AND domain=?',
                (self.tenant_id, self.domain)))
            values.extend(row['artifact_json'] for row in self.conn.execute(
                'SELECT artifact_json FROM cases WHERE tenant_id=? AND domain=?',
                (self.tenant_id, self.domain)))
            values.extend(row['payload_json'] for row in self.conn.execute(
                'SELECT payload_json FROM outbox WHERE tenant_id=? AND domain=?',
                (self.tenant_id, self.domain)))
            values.extend(row['reason'] for row in self.conn.execute(
                'SELECT reason FROM reviews WHERE tenant_id=? AND domain=?',
                (self.tenant_id, self.domain)))
            values.extend(row['detail'] for row in self.conn.execute(
                'SELECT detail FROM audit WHERE tenant_id=?', (self.tenant_id,)))
            values.extend(row['detail'] for row in self.conn.execute(
                'SELECT detail FROM delivery_attempts WHERE tenant_id=? AND domain=?',
                (self.tenant_id, self.domain)))
            values.extend(row['detail'] for row in self.conn.execute(
                'SELECT detail FROM incidents'))
            return {'scanned_rows': len(values),
                    'rows_with_direct_identifier': sum(contains_direct_identifier(x)
                                                       for x in values)}

    def resolve_incident(self, incident_id, detail):
        with self.lock, self.conn:
            changed = self.conn.execute('''UPDATE incidents SET state='resolved',detail=?,
                resolved_at=? WHERE incident_id=? AND state='open' ''',
                (detail, utc_now(), incident_id)).rowcount
            return changed == 1

    def requeue_dead_event(self, tenant_id, event_id, claims, reason):
        self._scope(tenant_id)
        if claims['tenant_id'] != tenant_id or claims['role'] != 'operator':
            raise ValueError('只有当前租户 Operator 可以重放 Dead Letter')
        if not reason.strip() or contains_direct_identifier(reason):
            raise ValueError('重放必须提供不含直接标识符的理由')
        with self.lock, self.conn:
            changed = self.conn.execute('''UPDATE inbox SET state='retry',attempt_count=0,
                available_tick=0,last_error=NULL,locked_by=NULL,locked_tick=NULL,updated_at=?
                WHERE tenant_id=? AND domain=? AND event_id=? AND state='dead' ''',
                (utc_now(), self.tenant_id, self.domain, event_id)).rowcount
            if changed != 1:
                raise ValueError('Worker Dead Letter 不存在')
            self.conn.execute('''UPDATE incidents SET state='resolved',detail=?,resolved_at=?
                WHERE kind='worker_dead_letter' AND object_id=? AND state='open' ''',
                ('approved_requeue: ' + reason.strip(), utc_now(), event_id))
            self._audit(self.tenant_id, claims['sub'], 'requeue_dead_event', event_id,
                        True, reason.strip())
            return True

    def requeue_dead_message(self, tenant_id, message_id, claims, reason):
        self._scope(tenant_id)
        if claims['tenant_id'] != tenant_id or claims['role'] != 'operator':
            raise ValueError('只有当前租户 Operator 可以重放 Dead Letter')
        if not reason.strip() or contains_direct_identifier(reason):
            raise ValueError('重放必须提供不含直接标识符的理由')
        with self.lock, self.conn:
            changed = self.conn.execute('''UPDATE outbox SET state='retry',attempt_count=0,
                available_tick=0,last_error=NULL,updated_at=? WHERE tenant_id=? AND domain=?
                AND message_id=? AND state='dead' AND approver_id IS NOT NULL''',
                (utc_now(), self.tenant_id, self.domain, message_id)).rowcount
            if changed != 1:
                raise ValueError('已批准的 Outbox Dead Letter 不存在')
            self.conn.execute('''UPDATE incidents SET state='resolved',detail=?,resolved_at=?
                WHERE kind='outbox_dead_letter' AND object_id=? AND state='open' ''',
                ('approved_requeue: ' + reason.strip(), utc_now(), message_id))
            self._audit(self.tenant_id, claims['sub'], 'requeue_dead_message', message_id,
                        True, reason.strip())
            return True
