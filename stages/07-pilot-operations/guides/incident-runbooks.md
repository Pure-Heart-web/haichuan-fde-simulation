# 故障、降级与回退 Runbook

每次事件先定范围与风险：记录发现时间、受影响案例/用户、Trace ID、最近代码/数据/规则/知识版本变更、当前错误率/延迟和是否存在已被人使用的错误建议。先阻断危险输出，再比较好坏版本的同一案例，保留未改写的审核与决策记录。此处所有事故均为**模拟注入**。

| 故障 | 识别与隔离 | 安全降级 | 恢复条件 |
|---|---|---|---|
| 草稿/LLM 不可用 (`P7-012`) | `reply_generation=degraded`，草稿为空；查看依赖健康 | 禁止批准空草稿，转人工原流程；保留已知事实与缺口 | 服务恢复、端到端回归与销售复核通过 |
| 产品数据不可用 (`P7-011`) | `product_recommendation=degraded`，无候选；检查数据版本 | 不猜型号，创建工程师任务；销售只作人工澄清 | 权威目录恢复、数据门与推荐回归通过 |
| CRM 超时 (`P7-009`) | `order_context=degraded`；看超时率与该 Span | 跳过历史订单，明确需人工核实；不把缓存猜测当客户事实 | CRM 恢复，身份/历史订单引用重查；实际系统应有超时、有限重试、缓存策略 |
| 知识不可用 (`P7-010`) | `knowledge_retrieval=degraded`，证据列表为空 | 保修/认证等政策性主张弃答或请人工确认 | 已批准文档可检索、引用回归通过 |
| 关键错误推荐 | 按 Trace 定位 SKU/规则/数据版本，冻结受影响候选 | 暂停该规则或回退上个批准数据版本，通知审核负责人复核已处理任务 | 根因修复、独立黄金集与高风险复测、负责人签核 |

## 演练 A：材质别名导致候选丢失

运行 `python3 stage7.py incident` 后查看 `outputs/stage-07/product-incident.json`。模拟坏候选 v13 把 `SS316` 写成未映射的 `Stainless Steel 316`，`validate_product_candidate` 在**发布前**拦截 `unmapped_material:CP90`。现场若已发布，先回退 v12 并冻结受影响 SKU；追溯近一次数据变更和同条件 Trace，确认这属于数据契约/规范化，不把它归咎于模型。修复版 v13 通过当前简化校验也只得到 `READY_FOR_SIMULATED_APPROVAL`，**没有发布**。

教学发布链是 `Upload → Schema → Canonicalization → Quality → Diff → Eval → Approve → Publish`。本仓库实际实现了候选状态、SKU/范围/别名/缺失旧 SKU 校验和差异摘要；`Eval/Approve/Publish` 仍由人工流程文字和现有离线回归代表，**没有真正的生产发布器或完整数据评估器**。真实数据门应再核查单位、材质兼容、字段来源、版本签名和高风险回归。

## 演练 B：延迟从 3.8 秒升到 12.4 秒

查看 `outputs/stage-07/latency-incident.md` 与 `data/latency-incident.json`，8.1 秒集中在 `crm_context`。先看 CRM 可用性与超时，设置时限并跳过非必需历史上下文；草稿标明需人工核对。更换模型不能修复该瓶颈。若真实用户正在使用，还要记录 P50/P95、成功率、尝试放弃和依赖错误，按角色与询盘类型切开。

## 事故会与事后动作

负责人记录：影响面、触发条件、版本差异、止损时间、是否有错误对外发送、根因类别（Data/Context/Retrieval/Rule/Model/Integration/Workflow/Human）、永久修复、回归案例、复发监测和决定人。此仓库发送数恒为 0，不能拿模拟事故证明生产恢复能力。每周将审核 `override` 分类与合成故障分布合并，选一项有明确假设与验收指标的改动。
