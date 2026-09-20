# 四层仪表盘、指标口径与 Trace 字典

`pilot-events.jsonl` 是 10 天 × 3 人 × 每人每日 6 条的**合成行为脚本**。每行有 `synthetic_training_event` 标识，仪表盘的比较基线来自 `hypothetical_pre_pilot_baseline`。两者均不能用于证明节省时间或现场可用性。`pilot-dashboard.json` 保存完整分群，Markdown 只展示关键列。

| 层 | 指标与计算口径 | 注意 |
|---|---|---|
| Business | 合格询盘处理时间/首次响应时间取中位数；工程师咨询次数÷10 天 | 假设前测使用同角色×复杂度组合，仍非真实对照 |
| Product | DAU = 当天至少完成一次辅助的不同销售数；辅助率 = `assisted / eligible`；**复杂询盘采用率** = `assisted ∧ eligible ∧ complex / eligible ∧ complex`；草稿接受或小改 = `accept/minor_edit / 已审核辅助草稿`；放弃 = `abandoned / attempted` | 不能用总使用率催促简单询盘强制用 AI |
| AI | 抽取纠错 = `extraction_corrected / assisted`；Top-3 接受 = `top3_accepted / 有候选反馈的辅助询盘`；严重规则违规计数 | 工程师升级召回、无证据主张率因没有独立现场标签为 N/A，不能填 0 |
| System | 成功率/集成错误率以 `attempted` 为分母；P95 是有延迟记录的尝试的 nearest-rank 值；观察到的 API 成本÷尝试数 | 此处无付费调用，$0 是**离线观察值**，不预测部署成本 |

始终切 `user_id`、`experience`、`complexity`、`customer_type`、`week`；缺分母则给 `null/N/A`。`eligible` 由范围规则定义，不能事后为了好看改分母。若真实试点收集反馈，还需独立判定正确升级/应升级、无证据主张、重大人工修改，记录标注者及一致性。

## 端到端 Trace

`python3 stage7.py trace --case P7-003` 返回 `trace_id`、询盘案例 ID、负责人、模式、状态、输入摘要、版本表、依赖降级、总本机耗时、观察到的 API 成本和每个 Stage 的 Span。Span 存开始/结束时间、耗时、`ok/skipped/degraded/failed`、输入/输出引用与安全元数据：

| Stage | 保留的元数据 |
|---|---|
| ingestion / extraction | 工作项 ID、离线模型与 prompt 版本、token/API 成本 |
| customer_resolution / order_context | 身份状态、脱敏客户引用、订单来源 ID 与版本 |
| field_provenance | 显式当前值/历史值等来源类型 |
| product_recommendation | 候选 SKU、代理分数、触发规则、规则/排序/产品数据版本 |
| knowledge_retrieval | 意图、文档/片段 ID、相关分、地区/SKU 过滤条件、知识版本 |
| reply_generation | Claim 类型、证据引用、风格/政策版本与草稿状态 |
| human review | SQLite 中追加式事件，读 Trace 时拼入动作、角色、覆盖分类和时间 |

Trace 不保存原始邮件正文、草稿正文、价格或折扣；本地 `pilot-artifacts/` 会保存**虚构案例**的完整处理产物，供教学调试。真实系统还需保留期限、访问审计、数据最小化与删除流程。`total_offline_latency_ms` 是本地代码耗时；180 条活动的 `latency_ms` 是另行造出的体验脚本，二者不能混成同一套生产性能测量。`P7-009`～`P7-012` 的 degraded Span 可用于核对回退路径。

## 计算与重新生成

```bash
python3 scripts/build_stage7_pilot_fixture.py
python3 stage7.py demo --output outputs/my-stage7-run
python3 stage7.py dashboard --output outputs/my-stage7-run
python3 stage7.py eval --check-baseline --output outputs/my-stage7-run
```

生成脚本是确定性的。修改事件后若结构不再是 180 条/10 天，计算器会拒绝此教学样本；要设计别的真实试点，先另建数据契约和基线，而非直接改写本案例的回归期望。
