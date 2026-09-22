# Stage 14：Integration Lab & Authorized Shadow Pilot Preflight

Stage 14 把 Stage 13 的现场准备契约升级为可重放的集成实验室。它首先用 Delivery Room 中的实际死信和事故阻断顶层 Gate，再经过 Operator 重放、人工复核、发布批准和 Mock 投递将 Gate 恢复。同一轮中还演练两种只读 Connector、OIDC Discovery/JWKS 轮换、遥测脱敏、合成 Shadow 观察和可携带证据包。

所有输入、账户、Connector 和 Shadow 用户仍是教学合成。默认外部证据清单的八项均为 `false`，因此程序只能给出 `INTEGRATION_LAB_READY_FOR_AUTHORIZED_SHADOW_REVIEW`，不会宣称真实客户 Shadow 已通过。

## 一键演练

```bash
python3 stage14.py demo --check-baseline
python3 -m unittest tests.test_stage14_integration_shadow -v
python3 stage14.py verify-evidence
```

结果位于 `outputs/stage-14/`：

- `stage14-report.json` / `.md`：集成实验室总结和真实 Shadow Gate。
- `operational-gates.json`：事故处置前后的跨层 Gate。
- `remediation-report.json`：死信重放、复核、批准和重投结果。
- `connector-report.json`：分页、游标、限流、重复、更新、字段漂移、撤权和只读边界。
- `identity-lab-report.json`：Discovery、MFA claim、Group Mapping、Key Rotation 和停用证据。
- `collector-export.jsonl`：脱敏后的教学 span。
- `shadow-observation-report.json`：12 个合成影子案例的人工行为与时间。
- `evidence-manifest.json`：只包含相对路径的 SHA-256 证据清单。

## 可选 PostgreSQL 运行练习

```bash
docker compose \
  -f stages/14-integration-shadow/infra/docker-compose.integration.yml \
  up --abort-on-container-exit --exit-code-from postgres-runtime-check
docker compose \
  -f stages/14-integration-shadow/infra/docker-compose.integration.yml down -v
```

该练习在真实 PostgreSQL 16 容器中加载 Stage 13 RLS Schema，再用两个事务模拟连接池复用，验证 `SET LOCAL app.tenant_id` 不会将 tenant-a 状态泄漏给 tenant-b。默认 `stage14-report.json` 仍保持 `postgres_runtime_executed: false`；只有真实执行且保存外部证据后才能改变客户 Gate。

## 真实 Shadow 预检

复制 `data/external-evidence.example.json` 到 Git 之外，由负责人基于真实证据填写：

```bash
python3 stage14.py preflight \
  --external-evidence /approved-mount/design-partner/shadow-evidence.json
```

八项必备证据是：授权、外置数据挂载、PostgreSQL 运行、企业 OIDC、Connector Sandbox、OTLP 后端、客户 UAT 和值班演练。Shadow 阶段必须保持客户系统写入关闭，真实记录不得进入 Git。

## 完成标准

- 顶层 Gate 对底层死信和未解决事故保持 fail-closed。
- 事故在获批重放后进入 `recovering`，只有实际处理成功才进入 `resolved`。
- 邮箱与 CMMS Connector 演练为只读，写入、撤权后访问与 Schema Drift 全部被拒绝。
- OIDC Lab 验证标准元数据形状、MFA、Group Mapping、Key Rotation 和组停用，但不冒充企业 SSO。
- Collector 在导出前删除 Prompt、Body、Content、Model Output 和 Tool Arguments。
- 证据包可在不同根目录下校验，任何文件被改动都会失效。
- 真实客户数据、真实用户和客户系统动作均为 0。

运行手册见 [Authorized Shadow Runbook](guides/authorized-shadow-runbook.md)，证据评审见 [Stage 14 Review](deliverables/stage14-review.md)。
