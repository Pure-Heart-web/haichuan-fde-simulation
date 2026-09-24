# 复现与验收

1. 运行 `python3 run.py validate`，应显示 6 条观察、3 个访谈角色和输入校验通过。
2. 运行 `python3 run.py demo`，打开 `outputs/stage-01/README.md` 和六项交付物。
3. 核对 `05-baseline-metrics.md`：销售主动处理总计 202 分钟、均值 33.67 分钟；复杂样本均值 51 分钟，简单样本均值 16.33 分钟；升级 3/6；工程师总投入 56 分钟。
4. 核对复杂样本：产品选型平均 15 分钟、需求整理 12.33 分钟，报价 3.33 分钟。这支持进一步验证知识和需求整理瓶颈，但不能证明系统价值或全年节省。
5. 查看退出条件：应为 `SIMULATION_READY`。这只是练习场景已满足模拟证据要求。
6. 执行 `python3 -m unittest discover -s tests -v`，验证计算、证据检查和真实/模拟边界。

## 反事实练习

复制 `simulation.json` 到 `outputs/practice.json`，将副本中所有 `sources[].path` 改为 `../stages/01-discovery/data/session-notes.md`（来源路径相对于输入文件），再修改练习字段并运行：

```bash
python3 run.py analyze --input outputs/practice.json --output outputs/practice-report
```

| 修改 | 预期结果 |
|---|---|
| 删除工程师访谈记录 | 报告仍生成，角色条件失败，退出码 3 |
| 将 `checks.error_cost.confirmed` 改为 false | 错误成本条件失败，不可进入下一阶段演练 |
| 将某观察的 `source_id` 改为不存在的 ID | 数据无效，退出码 2，不生成新报告 |
| 将回复时间改为收件之前 | 数据无效，退出码 2 |
| 删除一个观察步骤 | 数据无效，不能用 0 悄悄替代缺失记录 |
| 仅把 `mode` 改成 real | 由于证据仍为 simulation，拒绝作为真实项目输入 |

如果运行失败，以终端的退出码和错误为准；目标文件夹可能保留上次成功生成的报告，不代表本轮成功。比较报告页头的数据集 ID 与生成时间。

## 接入新的演练数据

先写原始记录和证据编号，再改 JSON；不要为了通过检查补造证据。观察数不足或缺访谈等属于 Discovery 未完成，允许生成缺口报告。负数、时间错序、悬空引用、步骤漏记属于数据质量错误，先修复再分析。

真实项目需改用真实且授权的脱敏资料，逐项审阅 `assessment`、`decisions`、`questions` 和 `checks` 中人工填写的内容。工具仅检查结构与引用，不会验证证据是否真实、推断是否正确。`REAL_REVIEW_REQUIRED` 只表示可供负责人审阅，不是开工批准。

## Stage 7：试点运营演练

在仓库根目录执行 `python3 stage7.py demo` 和 `python3 stage7.py eval --check-baseline`，检查 `outputs/stage-07/pilot-status.json`：12 条 Trace、3 条 Shadow、180 条合成活动、坏数据候选 `BLOCKED`，真实 Pilot Gate 为 `NOT_EVALUATED`。再看 `pilot-dashboard.md` 的 90 条合格复杂询盘分母，不能把脚本生成的两周变化写成现场成效。

运行 `python3 stage7.py trace --case P7-009`，检查 CRM 降级；运行 `python3 stage7.py review`，在本机页面按 Linda/Mike/Chen 切换任务；运行 `python3 stage7.py incident` 查看产品别名和 CRM 延迟的故障重放。详细操作和反事实练习见 [Stage 7 入口](../stages/07-pilot-operations/README.md)。修改审核状态时使用独立的 `--output outputs/my-stage7-run`，避免旧队列影响练习。

## Stage 8：双客户产品化演练

运行 `python3 stage8.py demo`、`python3 stage8.py eval --check-baseline`，核对 `outputs/stage-08/platform-status.json` 的启航 10 条、海川适配 1 条、租户作用域通过、真实用户 0。用 `trace --case QH-001` 查看资产维修来源和安全规则；用 `trace --tenant haichuan-training --case QH-001` 应得到当前租户找不到该 Trace 的错误。`incident` 对比不用/使用维修历史时的排序。完整步骤、危险案例和边界见 [Stage 8 入口](../stages/08-productization/README.md)。

## Stage 8：双 Domain 纵向案例

运行 `python3 stage8_vertical.py demo --check-baseline`，核对 `outputs/stage-08-vertical/episode-report.md`：启航 `QH-001`、海川 `P7-003` 都应有五步完整事件链、一次重复输入被去重、零对外发送和零真实用户。若要自己审核，用独立目录执行 `prepare`、`queue`、`review`、`close`；完整命令和工时记录方式见[纵向演练手册](../stages/08-productization/vertical/README.md)。

## Stage 9：交付强化

运行 `python3 stage9.py demo --check-baseline`，核对 `outputs/stage-09/hardening-report.json`：原 Stage 4 合成字段门槛通过、10 条挑战案例/3 处分歧、2 条闭环/1 条更新待审、一次依赖重试、2 条 `pending_send`、实际发送 0。用新目录执行 `prepare`、`login`、`review`、`close`、`confirm` 可亲自重放；模型端点、真人标注、旧队列导出和运行门详见[Stage 9 手册](../stages/09-hardening/README.md)。

## Stage 10：客户接入与 Shadow Pilot

运行 `python3 stage10.py demo --check-baseline`，核对 `outputs/stage-10/stage10-report.json`：新增 5、更新 1、重复 1、拒绝 2；到期清理后保留 4 个已审核案例；对外副作用、真实客户数据和真实用户均为 0。运行 `python3 stage10.py readiness` 应为 `NOT_READY_FOR_REAL_CUSTOMER_DATA`，并明确列出生产数据面、企业身份、授权证据等缺口。手动审核、反事实练习和真实切换步骤见[Stage 10 手册](../stages/10-customer-onboarding/README.md)。

## Stage 11：Production-like Delivery Room

运行 `python3 stage11.py demo --check-baseline`，核对 `outputs/stage-11/stage11-report.json`：46 次入站、39 个完成版本事件、1 个 Worker Dead Letter、35 个已审核案例、26 次 Mock 投递和 1 个 Outbox Dead Letter。真实投递、未批准投递、跨租户成功和持久化直接标识符均为 0。手动审核、HTTP API、Docker、Runbook 和事故练习见[Stage 11 手册](../stages/11-delivery-room/README.md)。

## Stage 12：Model Evaluation, Safety & Canary

运行 `python3 stage12.py demo --check-baseline`，核对 `outputs/stage-12/stage12-report.json`：100 条抽取对比不应有准确率下降，24 条安全用例应全部符合预期，36 个 Canary 案例中 3 个在入模型前隔离。熔断演练应只调用故障 candidate 2 次，4 个请求全部回退 baseline；发布演练后的活跃路由应为 `baseline`。外部模型调用、客户侧动作和真实客户数据都应为 0。操作、反事实与发布边界见 [Stage 12 手册](../stages/12-model-safety-canary/README.md)。

## Stage 13：Design Partner Pilot Readiness

运行 `python3 stage13.py demo --check-baseline`，核对 `outputs/stage-13/stage13-report.json`：授权包、RLS 契约、5 个训练 OIDC 账户、7 项工作台动作、4 个班次视角、3 次交接、FieldOps 计划中的 1 个已解决事故和 SLO 门应通过。PostgreSQL 实际执行、企业 SSO、真实客户数据、客户动作和实际用户应明确为 `false` 或 0。Stage 11 Delivery Room 故意留下的两个底层死信不在该 FieldOps 计划 SLO 中；Stage 14 会暴露并修复这个跨层 Gate 缺口。浏览器工作台、班次练习和真实切换门见 [Stage 13 手册](../stages/13-pilot-readiness/README.md)。

## Stage 14：Integration Lab & Authorized Shadow Preflight

运行 `python3 stage14.py demo --check-baseline`，核对 `outputs/stage-14/operational-gates.json`：修复前应因 Inbox/Outbox 死信和两个未解决事故处于 `BLOCKED`；获批重放、人工复核、发布批准和 Mock 重投成功后才进入 `READY`。运行 `python3 stage14.py verify-evidence`验证相对路径证据清单；修改任一被绑定文件后校验应失败。

默认 `external-evidence.example.json` 的八项外部证据均为 `false`，因此 `real_shadow_gate.status` 必须是 `AUTHORIZED_SHADOW_NOT_READY`。可选 PostgreSQL 连接池 RLS 容器练习、外置证据预检及限制见 [Stage 14 手册](../stages/14-integration-shadow/README.md)。

## Stage 15：Commercial Delivery Room

运行 `python3 stage15.py demo --check-baseline`，核对 `outputs/stage-15/commercial-readiness.json`：机会只通过 Gate A，下一步为签署付费 Discovery；潜在四阶段教学报价为 CNY 1,480,000，已签约金额、真实合同和真实收入均为 0；Shadow 与生产 Gate 保持未通过。`invoice-plan.csv` 应有 10 个里程碑且合计等于四阶段金额。

复制交易档案到 `outputs/` 后修改：将 Gate B 设为 approved 但保留 draft/requested 证据应被拒绝；令任一阶段付款比例不等于 100% 应被拒绝；把合成指标填入 `customer_baseline` 应被拒绝；跳过 Gate B 直接批准 Gate C 应被拒绝。商务模板和完整演练方法见 [Stage 15 手册](../stages/15-commercial-delivery/README.md)。

## Stage 16：团队真实商业交付模拟

运行 `python3 stage16.py prepare --output outputs/my-team-capstone`，确认参与者包不含 `injects.json` 和参考提交，主持人包包含客户剧本、12 个事件注入和参考证据。运行 `python3 stage16.py demo --check-baseline`，参考团队应得 93/100，8 个关键控制全部通过，6/6 个成员具备模拟的 `TECHNICALLY_RESPONSIBLE` 证据。

反事实：把任一关键控制改为 failed，团队最终分应封顶 59 且个人全部不能 Ready；删除某成员的 `operational_action`，团队原始分仍为 93，但该成员应回到 `SUPERVISED_PRACTICE_REQUIRED`；让交付物 Owner 自己成为唯一 Reviewer，提交应被拒绝。完整组织方法、角色卡、答辩和评分见 [Stage 16 手册](../stages/16-team-delivery-simulation/README.md)。

## Stage 17：Paid Discovery Delivery & Acceptance

运行 `python3 stage17.py demo --check-baseline`，核对 `outputs/stage-17/stage17-report.json`：六项合成交付物全部接受；教学费用 CNY 120,000、成本 CNY 72,800、毛利率 39.33%；模拟开票条件满足 CNY 120,000，但真实合同、发票、回款、客户批准、数据、用户和外部动作均为 0；八项 Shadow 外部依赖保持 open。

复制 Stage 17 资料后修改任一交付物应使验收摘要失败；修改合同价格但不重新绑定签核应失败；将 Discovery 依赖改为 open 应阻断验收；把未批准 ERP/售后范围加入 delivered scope 应失败；允许事后修改指标分母或声明真实回款应失败。完整练习见 [Stage 17 手册](../stages/17-paid-discovery-delivery/README.md)。

## Stage 18：Design Partner Acquisition & Contracting

运行 `python3 stage18.py demo --check-baseline`，核对 `outputs/stage-18/stage18-report.json`：三个虚构候选中只有一个达到资格线；真实具名客户、外部签约证据、有效合同和回款均为 0，状态保持 `REAL_PAID_DISCOVERY_NOT_READY`。

运行 `python3 stage18.py prepare --output outputs/partner-private` 生成外部 manifest 和 Mutual Action Plan。将 manifest 移到仓库外受控目录并用权威系统引用填写后，运行 `python3 stage18.py preflight --manifest /secure/path/design-partner-manifest.json --as-of 2026-09-24`。仓库内路径、缺失/拒绝/过期证据、错误签约声明角色或缺少三方 Release 都应阻断；结构完整也只表示可进入人工合同真实性复核。完整练习见 [Stage 18 手册](../stages/18-design-partner-contracting/README.md)。
