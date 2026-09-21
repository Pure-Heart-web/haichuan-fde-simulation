# API 与运行时架构

## 端点

| 方法 | 路径 | 身份 | 用途 |
|---|---|---|---|
| `GET` | `/health` | 无 | 本机健康检查，不返回业务数据 |
| `POST` | `/v1/events` | `X-Service-Token` | Connector 提交原始事件；净化后才持久化 |
| `GET` | `/v1/cases` | Bearer | 当前租户审核队列 |
| `GET` | `/v1/traces/{case}` | Bearer | 来源、案例、审核、Outbox 与投递尝试 |
| `POST` | `/v1/cases/{case}/reviews` | Bearer + assignee | 记录 accept/edit/escalate/reject |
| `POST` | `/v1/outbox/{message}/approve` | Bearer + release_manager | 第二人批准 |
| `POST` | `/v1/dead-letters/events/{id}/requeue` | Bearer + operator | 修复并批准后重放 Worker Dead Letter |
| `POST` | `/v1/dead-letters/messages/{id}/requeue` | Bearer + operator | 对账并批准后用原 Key 重放 Outbox Dead Letter |
| `POST` | `/v1/worker/tick` | Bearer | 教学用单步 Worker |
| `POST` | `/v1/dispatcher/tick` | Bearer | 教学用单步 Dispatcher |
| `GET` | `/v1/metrics` | Bearer | 队列、案例、投递与事故状态 |

请求体上限为 1 MB，API 日志不记录正文和令牌。运行时只能载入 `synthetic_design_partner` 清单；Dispatcher 只接受 `http://127.0.0.1` 或 `http://localhost`。

## 持久化语义

Inbox 使用 `(tenant, domain, event_id)` 幂等，用 `(tenant, domain, source_id, source_version)` 保证版本唯一。Worker 通过 `BEGIN IMMEDIATE` 抢占任务并记录租约；租约过期可恢复为 Retry。案例更新会重新打开审核，并删除尚未投递的旧版本 Outbox。

审核和 Outbox 在同一 SQLite 事务中写入，因此不会出现“审核成功但投递意图丢失”。投递使用稳定的 `Idempotency-Key`，Mock Sink 重复收到相同 Key 时返回 duplicate，不重复产生业务结果。

SQLite 适合便携教学。生产实现需要把 Store 接口迁移到获批数据库，并验证并发 Claim、隔离级别、备份恢复、迁移回滚和多副本 Worker。
