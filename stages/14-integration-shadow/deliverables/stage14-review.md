# Stage 14 评审记录

## 已验证

- 顶层 Gate 不再使用独立脚本的“事故已关闭”声明，而是直接读取 Delivery Room 死信和事故状态。
- 获批重放只将事故改为 `recovering`；Worker 或 Dispatcher 成功后才改为 `resolved`。
- 邮箱和 CMMS 教学 Connector 完成分页、游标、429 重试、重复、更新、Schema Drift、撤权和禁止写入演练。
- OIDC Lab 完成 Discovery、PKCE 能力声明、MFA claim、Group Mapping、两把 Key 轮换和停用演练。
- 遥测管道在导出前删除原文及直接标识符，证据清单使用相对路径和 SHA-256。

## 仍未验证

- 真实生产 PostgreSQL 迁移、长连接池、备份恢复和迁移回滚。
- 客户企业 OIDC/JWKS、真实 MFA 和账户撤销延迟。
- 真实邮箱、CRM/CMMS Sandbox 的 Scope、限流和供应商故障行为。
- 真实 OTLP Collector 与后端的权限、保留期和删除证据。
- 客户 UAT、真人采用、专家负担、实际工时和业务价值。

## 决策

`ITERATE_BEFORE_REAL_SHADOW`。允许继续收集客户外部证据和运行 Integration Lab，不允许客户系统写入、自动发送或真实维修动作。
