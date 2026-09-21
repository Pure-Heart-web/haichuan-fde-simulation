# 模型发布、Canary 与回滚 Runbook

## 职责分离

| 角色 | 证据 | 允许的动作 |
|---|---|---|
| Model Owner | 模型/提示版本、Schema、成本上限 | 签核候选版本 |
| Evaluation Owner | 冻结集、指标、差异和失败类型 | 产生评估报告，不改发布状态 |
| AI Safety Owner | 攻防集、输入/输出门和剩余风险 | 签核安全版本 |
| Release Manager | 双签和机器可读门 | 激活合成 Canary |
| Operator | 延迟、失败、成本、熔断和隔离事件 | 立即回退 baseline |

## 发布前

1. 填写 `templates/model-change-request.md`，明确候选版本、数据范围、预期收益和停止条件。
2. 检查 `model-registry.json` 的 Prompt SHA-256 和两个签核的 `content_sha256` 对应同一内容。
3. 运行 `python3 stage12.py demo --check-baseline`，保留六份报告和两份遥测文件。
4. 确认遥测不含正文、Prompt、输出、邮箱、电话或 secret canary。
5. 确认对外动作为 0，然后由 Model Owner 和 AI Safety Owner 分别签核。

## Canary 观测

本演练使用 `work_item.id` 的 SHA-256 bucket 做稳定分流，同一案例重放不会随机切换路由。观测指标包括：

- candidate / baseline / fallback / blocked 路由数；
- 调用延迟、单案成本、输入门与输出门拒绝数；
- 字段正确率、证据覆盖、人工修改和弃答；
- 供应方超时、熔断状态和 baseline 回退数。

## Stop 与 rollback

以下任一情况立即切回 baseline，由 Operator 写入原因：

- 危险动作、跨租户访问、直接标识符或秘密出现一次；
- 准确率低于发布门，证据引用错误，或安全评估不再全通过；
- 成本超限，或连续两次供应方故障打开熔断；
- 审核队列或专家负担超过已批准运营容量。

回滚后保留事件链和关联报告，禁止删改历史条目。修复后必须使用新的注册表哈希重新双签。

## 真实环境差距

真实切换时需用经授权的客户黄金集替代合成集，将签核接入企业身份与变更系统，将遥测接入生产告警，并在真实值班中演练回滚。本地 JSONL 事件链不是企业不可篡改日志。
