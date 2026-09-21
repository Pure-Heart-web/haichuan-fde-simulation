# Stage 13：Design Partner Pilot Readiness & Operator Workbench

这一阶段把 Stage 11 的 Delivery Room 和 Stage 12 的 Model Lab 组合成一次现场交付前演练。团队要在同一轮中完成授权核对、身份认证、租户隔离、人工审核、双人发布、班次交接、SLO 评审和紧急回退。

所有人员、数据、签核和事故仍为教学合成。PostgreSQL 只提供 RLS DDL 契约，没有对真实数据库执行；OIDC 是本地 HS256 训练 issuer，不是企业 SSO；遥测是无正文的 OTLP-shaped JSONL，没有发送到真实 Collector。

## 一键演练

```bash
python3 stage13.py demo --check-baseline
python3 -m unittest tests.test_stage13_pilot_readiness -v
```

报告位于 `outputs/stage-13/`：

- `stage13-report.json` / `.md`：现场准备判定、限制和下一个 Gate。
- `field-operations.jsonl`：班次、交接、事故、停止和回退的哈希链。
- `otel-spans.jsonl`：只含低基数元数据的 OTLP-shaped 教学 span。
- `delivery-room/`：Stage 11 入站、Worker、审核、Outbox 和事故证据。
- `model-lab/`：Stage 12 评估、安全门、Canary、熔断和回退证据。
- `identity/`：本机训练 issuer 密钥和账户 code，权限为 `0600`，不纳入 Git。

## 可选 PostgreSQL RLS 容器练习

默认报告只检查 SQL 契约，不声称执行过 PostgreSQL。本机 Docker 可用时，可额外运行真实 PostgreSQL 16 的租户读写隔离测试：

```bash
docker compose -f stages/13-pilot-readiness/infra/docker-compose.postgres.yml up \
  --abort-on-container-exit --exit-code-from rls-check
docker compose -f stages/13-pilot-readiness/infra/docker-compose.postgres.yml down -v
```

`rls-check` 先用 `tenant-a` 写入一条记录，再验证 `tenant-b` 无法读取，且在 `tenant-a` 上下文中写入 `tenant-b` 会被 RLS `WITH CHECK` 拒绝。该容器使用明示训练密码，不可复用于其他环境。

## 人工工作台

第一个终端：

```bash
python3 stage13.py serve --output outputs/my-stage13-workbench
```

第二个终端读取训练 code，再用与任务匹配的角色登录：

```bash
cat outputs/my-stage13-workbench/identity/training-oidc-codes.json
python3 stage13.py login \
  --output outputs/my-stage13-workbench \
  --actor dp-engineer-wu \
  --code '<training-code>'
```

打开 `http://127.0.0.1:8783/`，粘贴 token。工作台可查看角色队列、Trace、审核、升级、双人批准、Worker 和 Dispatcher。令牌只留在页面内存；重新加载页面后需重新粘贴。

## 文件地图

```text
data/pilot-authorization-bundle.json  四方签核的合成授权包
data/shift-plan.json                  三个 Operator 班次与一个 Auditor 评审
infra/postgresql-rls.sql              租户行级安全迁移契约
infra/docker-compose.postgres.yml     可选 PostgreSQL 16 运行时测试
infra/verify-rls.sh                   跨租户读写负向测试
guides/operator-runbook.md            开班、交接、Stop 和回退步骤
guides/real-customer-cutover.md       真实客户外置包与切换门
templates/pilot-charter.md            Pilot 范围和指标冻结模板
templates/shift-handoff.md            班次交接模板
templates/customer-uat.md             客户 UAT 模板
deliverables/stage13-review.md        本次合成演练的评审记录
```

## 完成标准

- 授权包明确禁止内嵌客户记录、Git 存储和客户系统写入，四个不同角色签核同一内容哈希。
- 训练 OIDC 对 issuer、audience、tenant、role、expiry 和 revocation 都有正向与负向测试。
- PostgreSQL DDL 为六张表开启并强制 RLS，每表有租户 Policy；报告不把静态校验写成运行时证据。
- 工作台覆盖队列、Trace、审核、升级、发布和运行动作。
- 三个 Operator 班次有完整交接；候选模型事故经过宣告、Stop、恢复 baseline 和关闭。
- SLO 门、安全门和回滚门全部通过；真实客户数据、用户和动作保持为 0。

NIST AI RMF 建议明确人机监督责任、在接近部署条件下评估、持续监测和保留停用机制；本阶段将这些要求映射为可运行的教学门。参考 [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)。
