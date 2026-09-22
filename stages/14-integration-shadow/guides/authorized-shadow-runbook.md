# Authorized Shadow Pilot Runbook

## 1. 启动前

1. 冻结用户、场景、数据源、指标口径、停止条件和试点结束日期。
2. 核对外置授权包哈希，禁止将客户记录和 Secret 复制到仓库。
3. 使用客户测试租户验证 OIDC、撤权、MFA 和角色映射。
4. 运行 PostgreSQL RLS、连接池复用、备份恢复和跨租户负向测试。
5. Connector 仅申请必需读取 Scope，验证限流、补数、乱序、重复、附件和凭据撤销。
6. 证明 OTLP 管道不导出原文、Prompt、Model Output 和 Tool Arguments。

## 2. 运行边界

- AI 只生成内部建议；客户邮件、CRM/CMMS 和设备控制系统均不得被写入。
- 每个案例保留系统原始建议、人工修改、审核理由、证据版本和最终人工决定。
- 值班人每班检查 Inbox 积压、Dead Letter、未批准 Outbox、数据泄漏、模型安全和 Connector 健康。
- 出现跨租户访问、未批准动作、危险建议、直接标识符泄漏或无法回退时立即 Stop。

## 3. 事故恢复

1. 声明事故并冻结相关 Worker、Connector 或模型路由。
2. 保留脱敏 Trace、影响范围、上次成功游标和当前版本。
3. Operator 提交重放原因；事故进入 `recovering`，不得提前关闭。
4. 重放后重新审核，需投递的内部结果再次由 Release Manager 批准。
5. 只有处理或 Mock 投递成功后才将事故改为 `resolved`，然后重算顶层 Gate。

## 4. 结束决策

- `STOP`：安全边界失效、客户撤回授权或无法恢复。
- `ITERATE`：安全边界有效，但字段、证据、用户采用或专家负担未达门槛。
- `EXPAND`：预先冻结的质量、安全、效率、采用和运营门槛全部达成，且客户责任人签核新范围。
