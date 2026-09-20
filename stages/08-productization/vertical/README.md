# QH-001 / P7-003：双 Domain 纵向交付演练

这份练习从**模拟外部输入**开始，而不是从已整理好的案例对象开始。启航 `QH-001` 的电话转写产生售后工单，读取设备与昨日保养 `WO-QH-110`，形成带手册、规则、维修记录引用的内部建议；工程师修改后，另录入一条虚构 CMMS 现场复核结论。海川 `P7-003` 从邮件产生询盘，经既有产品/订单/知识流程形成暂定 `CP90` 候选，由销售修改并录入虚构 CRM 澄清记录。两条路都使用 Core 的租户作用域存储、案例事件日志、审核反馈与结果契约。没有真实电话系统、CRM/CMMS 连接或对外发送。

## 先跑完整回放

在仓库根目录运行 Python 3.10+：

```bash
python3 stage8_vertical.py demo --check-baseline --output outputs/my-vertical-demo
```

查看 `outputs/my-vertical-demo/episode-report.md`，再打开同目录的 `episode-report.json` 与 `artifacts/`。报告应显示两条 `closed`、一条重复电话输入、两条相同的五步事件序列，以及 `delivery_time_savings_proven: false`。再运行一次相同命令，事件数仍应各为五条。

## 自己扮演审核人

用一个**新目录**运行以下命令；`prepare` 只走到待审核，后续动作由你逐个触发。

```bash
python3 stage8_vertical.py prepare --output outputs/my-vertical-workshop
python3 stage8_vertical.py queue --tenant qihang-training --output outputs/my-vertical-workshop
python3 stage8_vertical.py queue --tenant haichuan-training --output outputs/my-vertical-workshop
```

在报告与 `artifacts/qihang-training/QH-001.json` 中核对输入文本、序列号、`E37`、压力/异响、`WO-QH-110`、手册版本和第一建议。审核命令必须提供真实的**修改后内容**和原因；教学环境下 `engineer-chen` 只是预置角色 ID，不是登录认证。

```bash
python3 stage8_vertical.py review --tenant qihang-training --case QH-001 --actor-id engineer-chen --actor-role engineer --edited-action '先核对 WO-QH-110，再由工程师现场复核装配情况' --reason '昨日保养改变排查优先级' --output outputs/my-vertical-workshop
python3 stage8_vertical.py close --tenant qihang-training --case QH-001 --outcome-id SIM-CMMS-QH-001-CLOSE --output outputs/my-vertical-workshop
```

海川使用**同一个 `review` / `close` 契约**，但销售 Domain 的候选、知识来源和审批角色不同：

```bash
python3 stage8_vertical.py review --tenant haichuan-training --case P7-003 --actor-id anna --actor-role sales --edited-action '暂保留 CP90；先核对电气参数、现场工况和 CE 文件适用范围' --reason '历史订单不能替代本次确认' --output outputs/my-vertical-workshop
python3 stage8_vertical.py close --tenant haichuan-training --case P7-003 --outcome-id SIM-CRM-P7-003-CONFIRM --output outputs/my-vertical-workshop
python3 stage8_vertical.py report --output outputs/my-vertical-workshop
python3 stage8_vertical.py eval --check-baseline --output outputs/my-vertical-workshop
```

`close` 只接受本目录 `outcomes.json` 中与租户、案例、结果类型和时间对应的**合成**结果。它不证明工程师真的到场或客户真的确认了配置。先 `close` 后 `review`、用 `zhou` 审核工程师任务、把启航结果写到海川租户，都应失败且不留下半条审核事件。

## 输入、输出与责任边界

| 环节 | 可检查的资料/产物 | 当前实现与真实接入缺口 |
|---|---|---|
| 采集 | `inbound-events.jsonl` → `inbound_received` | 电话转写、邮件均为固定文本；真实环境需接入授权、转写质量、来源签名和重试队列 |
| 建单 | `TKT-QH-001` / `INQ-P7-003` → `case_created` | 模拟工单/询盘，无真实系统 ID 回写；同一来源 ID 更改内容或元数据时阻断，待人工核版 |
| 建议 | WorkItem、Trace、Recommendation → `proposal_ready` | 共享契约与租户作用域；启航用维修记录/规则，海川用订单/知识/产品；来源真实性需各自系统验证 |
| 审核 | ReviewTask、FeedbackEvent → `human_edited` | 记录修改前后与原因；角色白名单是模拟权限，没有企业 SSO/审计身份 |
| 结果 | 合成 CMMS/CRM 引用 → `outcome_recorded` | 与输入案例分离，保留来源 ID；不是独立现场验证，不能作维修准确率或产品收益证明 |

事件日志在本地 `platform.sqlite3` 的 `episodes`、`episode_events` 表中。原始输入文本不写入事件日志，但会进入租户作用域 WorkItem；现有 SQLite 文件仍含可读原文，所以真实客户数据必须先做保存期限、访问控制、脱敏与删除设计。`episode-report.json` 提供跨步骤索引，`artifacts/` 保留两条 Domain 的详细产物。程序不创建客户消息或派工。

## 检验“共享 Core 省时间”

这轮**证明了接口和状态流程能复用，尚未证明节省交付时间**。若团队实际练习，可为每个 Domain 记录 Discovery、接入、领域规则、审核流程、评估的真人工作时段：

```bash
python3 stage8_vertical.py effort-start --domain after_sales --phase integration --actor learner --activity '核对电话转写与工单映射' --output outputs/my-vertical-workshop
python3 stage8_vertical.py effort-stop --activity-id <上一命令返回的 activity_id> --output outputs/my-vertical-workshop
python3 stage8_vertical.py report --output outputs/my-vertical-workshop
```

另对 `foreign_trade` 逐项记录。`delivery-effort.jsonl` 保存开始/结束事件；只有两个 Domain 均有完整时段才给出描述性对比，仍不会标成因果节省。请把新 Domain 的**总集成时间、Core 改动、领域规则/数据清理时间、审核修改率和返工原因**放在同一张复盘表里；单次脚本运行时间不能替代 FDE 人工交付成本。

## 复盘问题

1. 启航“昨日保养”从哪个工单进入建议？如果 CMMS 同步晚一天，系统如何显示未知而非假设已保养？
2. 海川历史订单、CE 文档与本次工况之间，哪些只是候选证据？谁批准发给客户？
3. 相同事件契约下，哪些新增工作只写在售后/外贸 Domain，哪些迫使 Core 变化？把实际工时与代码变更一起记录。
4. 若电话转写纠错、工单重复、权限撤销或最终原因推翻初始建议，谁负责版本、撤回、重开与通知？当前演练对这些只做部分阻断，尚无生产工作流。

进一步判断见[纵向案例复盘](../deliverables/vertical-slice-review.md)。
