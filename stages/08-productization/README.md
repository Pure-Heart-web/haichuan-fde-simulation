# Stage 8：第二客户、产品化与 Shared Platform

这一阶段把虚构的**启航设备售后**作为第二个 Domain：10 条合成客服工单经共享 `WorkItem` 和 JSON 抽取运行时、资产上下文接口、租户先行的知识检索与规则运行时，形成仅供内部审核的下一步建议；另将海川一条 Stage 7 询盘通过显式适配器写入同一平台契约。两个租户的数据在查询时先限定 `tenant_id + domain`，启航的工程师页面显示设备、最近维修、风险与排查选项。**这不是两个真实客户的现场部署**：真实 Pilot Gate 均为 `NOT_EVALUATED`，没有客户维修指导、派工、外部模型调用或生产鉴权。

## 运行

从仓库根目录使用 Python 3.10+，无需依赖、API Key 和网络：

```bash
python3 stage8.py demo
python3 stage8.py eval --check-baseline
python3 stage8.py trace --case QH-001
python3 stage8.py trace --tenant haichuan-training --case P7-001
python3 stage8.py incident
python3 stage8.py review
```

`review` 在 `http://127.0.0.1:8769/?user=zhou` 启动启航专用本机审核页，可切换 `engineer-chen`。角色选择**不是身份认证**。输出在 `outputs/stage-08/`：`service-artifacts/`、`haichuan-bridge.json`、`stage8-eval.md`、`shadow-incident.md`、`platform-status.json` 和 SQLite 队列。重复 demo 保留审核事件；更改源数据后请用新的 `--output outputs/my-stage8-run`。`python3 stage_pipeline.py all` 串联 Stage 1–8。

新增的[双 Domain 纵向演练](vertical/README.md)从 `QH-001` 电话转写和 `P7-003` 邮件开始，走模拟建单、证据化内部建议、人工改写与独立合成结果记录。运行 `python3 stage8_vertical.py demo --check-baseline`；或者按手册使用 `prepare`、`queue`、`review`、`close` 逐步演练。它使用独立的 `outputs/stage-08-vertical/`，也已纳入 `stage_pipeline.py all`。

## 练习顺序

1. 阅读[启航 Discovery 与安全边界](guides/discovery-and-safety.md)，先在[观察模板](templates/second-customer-notebook.md)写自己的 Problem Brief、流程和信息缺口。
2. 运行 `demo`。看 `QH-001` 的 E37、低压力、异响和昨日保养；`QH-002` 的 98°C 触发关键安全规则；`QH-004` 的未知序列号无法恢复资产历史；`QH-003` 是低风险、仍需客服审核的对照。
3. 运行 `incident`，对比“已取到维修历史却没用于排序”和修正后的第一建议；详见[合成故障复盘](deliverables/shadow-failure-review.md)。
4. 以 `zhou` 和 `engineer-chen` 浏览各自队列。高风险任务不能批准远程指导，工程师可留下技术复核事件；所有动作只更新本机追加式审核记录。
5. 阅读[Core / Domain / Tenant 边界](guides/platform-boundaries.md)与[隔离、评估和发布门](guides/tenancy-eval-release.md)，用测试里的越权场景检验“共享”是否真的安全。
6. 对照[产品化 Review、债务与 Thesis](deliverables/productization-review.md)，讨论哪些能力已经值得共享，哪些仅是名字相似。

## 代码与资料

| 位置 | 内容 |
|---|---|
| `source/original-stage-08.md` | 用户提供的原稿，原样保留 |
| `data/` | 虚构租户、资产、手册片段、售后规则、10 条有标签工单与回归预期 |
| `src/fde_platform/core/platform/` | 有类型的通用建议/上下文/反馈契约、规则执行、先租户后检索、作用域存储 |
| `src/fde_platform/domains/after_sales/` | 售后 Schema、离线抽取 Provider、资产 Adapter、风险与排序、流程 |
| `src/fde_platform/domains/foreign_trade/platform/` | 海川已有流程向共享契约的显式适配器；产品排序仍留在外贸 Domain |
| `src/fde_platform/apps/service_review_web.py` | 启航设备视角的本机审核页，后台使用共享审核契约 |
| `tests/test_stage8_productization.py` | 租户隔离、安全路由、上下文排序回归、页面权限及幂等重放 |
| `vertical/`、`stage8_vertical.py`、`tests/test_stage8_vertical_slice.py` | 双案例输入、模拟接入、事件链、人工审核与结果回填、回归测试 |

脚本的 10/10 Top-1 和 50/50 字段命中来自自造样本，只说明演练路径可复现，不说明维修准确率或现场安全。真实接入要补 CMMS/工单适配、来源签核、账号与权限、独立标注、专家流程、事故与责任边界、真实基线以及安全评审。
