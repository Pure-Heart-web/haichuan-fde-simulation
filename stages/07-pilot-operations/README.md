# Stage 7：受控 Pilot、人工工作流与运营演练

本阶段把 Stage 4–6 的离线切片接成一个**仅供教学的试点重放**：限定范围 → 运行 12 个询盘案例 → 生成脱敏 Trace 与角色审核任务 → 计算 10 个工作日、180 条合成活动的分群指标 → 注入依赖故障 → 演练产品数据发布门和事故复盘。原稿描述的“真实 Pilot”“Production Failure”“Expand”在本仓库**没有发生**；可执行结论是 `ITERATE_SIMULATION_ONLY`，真实试点发布门为 `NOT_EVALUATED`。

## 从仓库根目录运行

Python 3.10+，无需第三方包、账号、API Key 或网络：

```bash
python3 stage7.py demo
python3 stage7.py eval --check-baseline
python3 stage7.py trace --case P7-003
python3 stage7.py incident
python3 stage7.py review
```

页面地址为 `http://127.0.0.1:8768/?user=linda`；可切换 `mike`、`anna`、`chen`、`admin`。用户切换只模拟角色视图，**不是登录鉴权**，页面只绑定本机。先运行 `demo`，用 Ctrl+C 停止页面。`stage7.py dashboard` 可根据当前 SQLite 审核事件重新计算仪表盘；`python3 stage_pipeline.py all` 连续执行 Stage 1–7。

建议打开 `outputs/stage-07/pilot-status.json`、`pilot-dashboard.md`/`.json`、`pilot-artifacts/`、`shadow-artifacts/`、`product-incident.md`、`latency-incident.md` 和 `pilot.sqlite3`。输出目录不纳入版本管理。重复运行会保留既有审核事件；如果要重新开始练习，请使用新的 `--output outputs/my-stage7-run`，不要依赖旧队列重置。

## 建议练习路径

1. 读 [试点计划与角色流程](guides/pilot-plan-and-workflow.md)，先填[观察与审核记录模板](templates/pilot-review-notebook.md)，再对照下列案例。
2. `P7-001` 看普通销售草稿；`P7-002` 看 Mike 的展开证据与陈工前置审核；`P7-003` 看历史客户、订单来源和知识引用；`P7-004` 看户外工况升级。
3. `P7-006`～`P7-008` 看高温、化工 ATEX、非目标产品系列如何只进 Shadow；销售审核队列不出现它们。
4. `P7-009`～`P7-012` 分别看 CRM、知识、产品数据、草稿不可用时的人工兜底；失败字段必须保持未知，不能伪装成已验证值。
5. 在页面上先以 `mike` 打开 `P7-002-SALES` 尝试批准，观察工程师前置任务；切到 `chen` 处理 `P7-002-ENG`，再返回 Mike。覆盖时必须选原因分类并写解释。
6. 按[指标与 Trace 字典](guides/metrics-and-observability.md)核对分母、版本、证据和成本。按[故障与回退 Runbook](guides/incident-runbooks.md)重放两个事故，再读[周复盘与决策](deliverables/pilot-review-and-decision.md)。

## 文件与代码地图

| 路径 | 作用 |
|---|---|
| `source/original-stage-07.md` | 用户提供的阶段原文，保留供对照 |
| `data/pilot-config.json`、`baseline.json` | 虚构角色、范围与**假设前测** |
| `data/pilot-scenarios.jsonl`、`pilot-events.jsonl` | 12 个流程案例、180 条合成活动；后者由 `scripts/build_stage7_pilot_fixture.py` 重建 |
| `data/product-v12.json`、`product-v13-*.json` | 材质映射缺口的坏候选与修复候选，均不会发布 |
| `data/regression-baseline.json` | 教学回归预期，不是现场 KPI 门槛 |
| `stage7.py` | demo / trace / dashboard / incident / review / eval CLI |
| `src/fde_platform/core/pilot/` | 可复用 Trace、ReviewTask SQLite、指标、数据发布门 |
| `src/fde_platform/domains/foreign_trade/pilot/` | 泵询盘范围、故障注入、任务分派 |
| `src/fde_platform/apps/pilot_review_web.py` | 本机教学审核页面 |

此切片不接收真实邮件，不调用外部模型，不修改 CRM，不发送邮件，不给最终型号或价格承诺。真实上线前仍需授权数据、独立标注、身份与权限系统、审计保留策略、发布审批和现场前测。[ADR-011–015](deliverables/adr-011-015.md)记录了这些边界。
