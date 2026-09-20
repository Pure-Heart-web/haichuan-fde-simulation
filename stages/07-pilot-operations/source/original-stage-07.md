# 海川工业泵 AI 询盘项目

## Stage 7：Pilot Deployment、Human Workflow、Observability 与 Adoption

---

# 1. Stage 7 的核心问题

到目前为止，系统已经能够：

```text id="w02ki3"
Email
↓
Extraction
↓
Customer Context
↓
Product Search
↓
Rule Engine
↓
Knowledge Retrieval
↓
Recommendation
↓
Reply Draft
```

技术指标也已经达到初步 Pilot 要求。

但是这还不能说明项目成功。

真正的问题变成：

> **销售在真实工作日里，会不会持续使用？**

以及：

> **出了错误，我们能不能知道为什么？**

因此 Stage 7 的目标是验证：

```text id="sv8e4l"
Technical Reliability
+
Workflow Fit
+
Human Trust
+
Business Value
```

---

# 2. Pilot 不是 Production Rollout

王总：

> 既然现在效果不错，直接给 8 个销售全部上线吧。

技术负责人不应该立刻答应。

第一阶段建议：

```text id="cd7dhs"
2～3 名销售
+
1 名技术工程师
+
2 周
```

先运行：

# Controlled Pilot

而不是：

# Company-wide Rollout

---

# 3. Pilot User Selection

选择三类用户最有价值。

## User A：Linda

资深销售。

作用：

> 判断 AI 建议与专家工作方式的差距。

---

## User B：Mike

入职 6 个月的新销售。

作用：

> 验证系统是否真的降低新人门槛。

---

## User C：Anna

中等经验销售。

作用：

> 防止系统只适合专家或新人。

---

Engineer Reviewer：

陈工。

作用：

> 审核复杂技术升级。

---

# 4. Pilot Scope

第一阶段只覆盖：

```text id="ok4621"
标准离心泵询盘
英文邮件
标准产品
已批准知识库内容
```

不覆盖：

```text id="7qlz9l"
特殊化工工况
极端高温
非标设计
自动报价
自动发信
```

---

# 5. Pilot Definition

## Duration

2 周。

---

## Users

3 名销售。

---

## Daily Volume

每人每天建议：

```text id="kpln9a"
5～15 条真实询盘
```

---

## Human Boundary

所有：

```text id="x39omh"
Product Recommendation
Reply Draft
```

必须经过人工 Review。

高风险案例：

```text id="w08x4f"
Engineer Review
```

---

# 6. 上线前先建立 Baseline

Pilot 最大错误之一：

> 上线以后才想起来要看效果。

上线前先记录：

---

## Sales Baseline

每类询盘：

```text id="pju1xn"
简单询盘处理时间

复杂询盘处理时间

首次响应时间

等待工程师时间
```

---

## Engineer Baseline

```text id="m63qfg"
每天销售咨询次数

每次咨询平均耗时

重复问题比例
```

---

## Quality Baseline

```text id="g1r52x"
错误选型

遗漏关键参数

回复重大修改率
```

没有 Before：

After 没意义。

---

# 7. Pilot Dashboard V1

技术负责人只需要四层指标。

---

## Layer 1：Business

```text id="c4jgoa"
Median Processing Time

First Response Time

Engineer Consultation Count
```

---

## Layer 2：Product

```text id="a8gy1y"
Daily Active Users

AI-Assisted Inquiry Rate

Draft Acceptance

Abandonment Rate
```

---

## Layer 3：AI

```text id="ims6kf"
Extraction Correction Rate

Top-3 Product Acceptance

Engineer Escalation Recall

Unsupported Claim Rate
```

---

## Layer 4：System

```text id="g8ip16"
Success Rate

P95 Latency

LLM Cost / Inquiry

Integration Error Rate
```

---

# 8. Pilot Workflow

理想情况下，销售不要打开：

> 一个完全独立的新 AI 网站。

最好嵌入已有 Workflow。

例如：

```text id="89dwba"
Email Inbox
↓
Open Inquiry
↓
AI Side Panel
↓
Review
↓
Copy / Send Reply
```

---

# 9. 为什么 Workflow Integration 很重要？

如果实际流程变成：

```text id="mut9hd"
邮箱
↓
复制邮件
↓
打开 AI 网站
↓
粘贴
↓
等待
↓
复制结果
↓
回邮箱
```

即使模型非常准：

用户也可能不用。

因为你增加了：

```text id="g23eqr"
Context Switching
+
Clicks
+
Copy/Paste
```

---

# 10. 第一次真实 Pilot

Day 1：

三名销售开始用。

技术指标：

```text id="j22s0f"
Extraction:
97%

Recommendation:
91%

Draft acceptance:
83%
```

团队很兴奋。

但 Day 3：

使用次数开始下降。

---

# 11. Usage 数据

Day 1：

```text id="3fwt07"
31 inquiries
```

Day 2：

```text id="r6q0ud"
28
```

Day 3：

```text id="jjgpf9"
17
```

Day 4：

```text id="iwowaj"
11
```

Engineer A：

> 是不是模型结果不够好？

技术负责人：

> 先观察用户。

---

# 12. User Observation

你坐在 Linda 旁边看她工作。

发现：

Linda 收到邮件以后：

```text id="8hxctq"
看邮件
↓
自己已经判断七八成
↓
打开 AI 系统
↓
等待约 4 秒
↓
再确认
```

Linda：

> 简单询盘我自己比它还快。

---

# 13. 重要发现

对于：

```text id="spqe3i"
简单询盘
```

AI 反而增加操作成本。

真正价值可能集中在：

```text id="bs70go"
复杂询盘
新人
历史客户
需要查资料
```

因此产品目标不应该是：

> 100% Inquiry AI Usage。

而应该是：

> **在真正高成本的任务里被使用。**

---

# 14. 技术负责人修改 Adoption Metric

原来：

```text id="1kiv31"
AI Usage Rate
```

改成：

```text id="qeut5d"
Eligible Complex Inquiry Adoption Rate
```

避免错误激励。

否则团队可能为了提高 Usage：

把 AI 强制塞进所有询盘。

---

# 15. Mike 的情况完全不同

新人 Mike：

> 我基本每封都愿意看一下。

原因：

> 我不确定自己的判断对不对。

这里出现重要 Product Insight：

# Value Is Role-dependent

对于专家：

```text id="vy17m0"
Speed
```

更重要。

对于新人：

```text id="sd2spx"
Confidence
+
Learning
```

更重要。

---

# 16. 产品设计开始 Role-aware

Linda：

默认只显示：

```text id="o0e9pm"
Recommendation
Warnings
```

Mike：

额外显示：

```text id="z9riym"
Why
Sources
Rule Explanation
```

陈工：

显示：

```text id="xc1ow0"
Full Technical Evidence
Triggered Rules
Raw Parameters
```

---

# 17. Engineer Escalation Workflow

当系统发现：

```text id="s5kgf7"
requires_engineer_review = true
```

不能只是显示：

> 请找工程师。

应该自动创建：

```text id="bt4cbz"
ReviewTask
```

例如：

```text id="sp8yha"
Inquiry:
INQ-1082

Reason:
High temperature

Candidate:
CP100

Triggered Rule:
HIGH_TEMP_001

Missing:
Seal configuration

Reviewer:
Technical Engineer
```

---

# 18. 工程师看到的不是整封邮件

而是：

```text id="76uw42"
必要上下文
+
系统候选
+
触发规则
+
具体问题
```

这样陈工的 Review 从：

> 重新理解整个询盘

变成：

> 回答一个明确技术问题。

这可能才是系统真正降低工程师负担的方式。

---

# 19. Engineer Escalation Metric

不要只测：

```text id="h6fdkg"
多少次升级
```

还要测：

```text id="8yzjlz"
Time to Review

Review Resolution Time

Repeated Escalation Rate

Engineer Override Rate
```

---

# 20. 生产 Observability 正式设计

现在系统必须能够回答：

> 为什么这封邮件当时推荐了 CP90？

因此每个 Inquiry 有：

```text id="i9t4av"
trace_id
```

例如：

```text id="b9ni58"
trace_01JK92...
```

---

# 21. Trace 结构

完整 Trace：

```text id="57c9ym"
WorkItem Received
↓
Extraction
↓
Normalization
↓
Customer Resolution
↓
Context Retrieval
↓
Product Search
↓
Rule Evaluation
↓
Ranking
↓
Knowledge Retrieval
↓
Reply Generation
↓
Human Review
```

---

# 22. 每个 Stage 至少记录

```text id="apn9bp"
start_time
end_time
status
input_reference
output_reference
version
error
```

---

# 23. AI Stage 额外记录

```text id="u170qn"
model
prompt_version
token_usage
latency
cost
structured_output_status
```

不要默认长期保存不必要的敏感原始模型输入；按数据治理和访问策略控制。

---

# 24. Retrieval Stage 记录

```text id="su39fu"
query
filters
document_ids
scores
selected_evidence
```

---

# 25. Rule Stage 记录

```text id="aqwh84"
rules_evaluated
rules_triggered
rules_failed
rule_version
```

---

# 26. Ranking Stage 记录

```text id="tfol60"
candidate_ids
scores
ranking_version
```

---

# 27. Review Stage 记录

```text id="jcr0r0"
reviewer
decision
edits
override
reason
```

---

# 28. 为什么这非常重要？

两周以后客户说：

> AI 上周给我推荐错了一个型号。

如果没有 Trace：

团队只能：

```text id="byet9n"
猜
```

有 Trace：

可以回答：

```text id="6bss2m"
Extraction 正确
Product DB 正确
Rule 没触发
原因是 medium mapping 缺失
```

才能真正修系统。

---

# 29. Production Failure #1

Pilot Day 5。

Linda：

> 今天系统突然不给产品推荐了。

Monitoring：

```text id="cz1v7z"
LLM healthy
Database healthy
API healthy
```

但是：

```text id="wcjqyg"
Recommendation success rate
92% → 48%
```

---

# 30. 技术负责人 Incident Flow

第一步：

# Scope

什么时候开始？

哪些请求受影响？

---

第二步：

# Recent Change

过去 24 小时改过什么？

发现：

Engineer C 昨晚更新产品数据。

---

第三步：

# Compare Trace

正常：

```text id="p14hrv"
material = SS316
```

异常：

```text id="smyc9t"
material = Stainless Steel 316
```

---

# 31. Root Cause

Normalization mapping 没更新。

所以 Rule Engine 不认识：

```text id="gfj8lh"
Stainless Steel 316
```

候选被错误过滤。

---

# 32. 这是什么问题？

不是：

```text id="ijj553"
LLM failure
```

不是：

```text id="1h55kk"
Rule logic failure
```

而是：

```text id="0zuyud"
Data Contract / Canonicalization Failure
```

---

# 33. Immediate Mitigation

回滚产品数据版本。

恢复：

```text id="xa9ysn"
Product Dataset v12
```

---

# 34. Permanent Fix

增加：

```text id="tz0r23"
Canonicalization coverage test
```

每次 Product Dataset 更新：

自动验证：

```text id="0ntpwz"
所有 material raw values
→ known canonical values
```

否则禁止发布。

---

# 35. 技术负责人要建立 Data Deployment Pipeline

现在客户 Excel 不能：

```text id="6yexjs"
上传
↓
直接覆盖 Production
```

应该：

```text id="0dk46m"
Upload
↓
Schema Validation
↓
Canonicalization
↓
Data Quality Check
↓
Diff Review
↓
Eval
↓
Approve
↓
Publish
```

---

# 36. 数据本身开始拥有 Version

例如：

```text id="fcjny9"
product_data_version:
2026-09-12-v13
```

每个 Recommendation Trace 都记录：

```text id="37m2m0"
product_data_version
```

否则历史结果无法复现。

---

# 37. Production Failure #2：Latency

Day 7。

用户反馈：

> 今天 AI 很慢。

Dashboard：

```text id="r0djjo"
P95 latency:
3.8s → 12.4s
```

Tracing 显示：

```text id="fax3xm"
Knowledge Retrieval:
0.7s

LLM:
2.3s

CRM Context:
8.1s
```

根因：

ERP API 很慢。

---

# 38. 技术负责人判断

不是：

> 换更快模型。

而是：

```text id="g3ir4m"
Context Integration Bottleneck
```

短期：

```text id="e3i3am"
timeout
+
fallback
+
cache
```

---

# 39. Graceful Degradation

如果 CRM 超时：

不要整个系统失败。

可以：

```text id="xpljj9"
Context unavailable
↓
continue without history
↓
show warning
```

例如：

> Customer history is temporarily unavailable. Please verify prior-order references manually.

---

# 40. 不同失败的降级策略

## LLM unavailable

```text id="dzj6h2"
Manual workflow
```

---

## Knowledge unavailable

```text id="osbnn8"
Do not answer knowledge claims
```

---

## CRM unavailable

```text id="wyq3p9"
Continue without customer context
+
warning
```

---

## Product DB unavailable

```text id="4a81r6"
No product recommendation
```

因为不能安全猜。

---

# 41. Availability 不等于 AI API Availability

整个 Copilot 依赖：

```text id="phlfbi"
LLM
CRM
ERP
Product DB
Knowledge
Rules
```

生产可靠性是整条链路的问题。

---

# 42. Cost Observability

每天记录：

```text id="5gw0ba"
Cost / Inquiry
```

例如：

```text id="v8ty25"
Extraction:
$0.006

Reply:
$0.009

Knowledge:
$0.002

Total:
$0.017
```

---

# 43. 技术负责人不要只问“API 贵不贵”

应该问：

> 单位业务任务成本占创造价值多少？

如果：

```text id="wh615y"
Cost = $0.02
```

能够减少：

```text id="w422gk"
10 分钟人工
```

通常更重要的是：

> 价值 / 成本。

而不是单独盯 Token。

---

# 44. 权限模型开始进入 Production

三个角色：

```text id="q53k9m"
Sales
Engineer
Admin
```

---

## Sales

可以：

```text id="7hlvh6"
查看自己负责询盘
Review Recommendation
修改 Draft
```

---

## Engineer

可以：

```text id="8omfoe"
处理技术 Review
查看完整技术证据
```

---

## Admin

可以：

```text id="qglgke"
管理规则
知识库
数据版本
```

---

# 45. 价格与敏感数据隔离

虽然客户未来想自动报价：

Stage 7 依然不应该因为：

> 技术上可以查数据库

就让所有模型 Context 得到：

```text id="u8257j"
Special Discount
Margin
Customer Special Price
```

权限和 Context 最小化原则：

> **模型只获得完成当前任务真正需要的数据。**

---

# 46. Human Review 不是一个按钮

技术负责人开始把 Review 分类：

```text id="ut1wh0"
Sales Review

Engineer Review

Manager Approval
```

未来自动报价也可以复用。

---

# 47. ReviewTask 通用模型

```text id="i98crh"
ReviewTask

type
risk_level
assignee_role
payload
evidence
status
decision
comment
created_at
completed_at
```

这开始真正成为：

```text id="fy7ba0"
Shared Core
```

因为售后项目也可以复用。

---

# 48. Pilot Week 1 Review

技术指标不错：

```text id="bzbtpa"
System success:
98.5%

P95:
4.2s

Unsupported claim:
1.2%
```

但业务指标：

```text id="l71d38"
Linda adoption:
38%

Mike adoption:
91%

Anna adoption:
67%
```

如果只看平均：

```text id="r5z127"
65%
```

你会漏掉最重要的信息。

---

# 49. 技术负责人应该 Segment Metrics

按：

```text id="4ix7si"
User Experience Level
Inquiry Complexity
Product Family
Customer Type
```

切开看。

得到：

---

## Senior Sales + Simple Inquiry

价值低。

---

## Junior Sales + Complex Inquiry

价值极高。

---

## Historical Customer Inquiry

价值高。

---

## Non-standard Inquiry

系统经常升级工程师。

---

# 50. Pilot Persona Refinement

因此 V1 真正 ICP 内用户场景可能是：

```text id="huxlds"
新人 / 中级销售
+
标准复杂询盘
+
重复技术知识较多
```

不是：

> 所有外贸销售的所有邮件。

这会影响未来产品定位。

---

# 51. Week 2：Product Workflow 改版

根据观察：

简单询盘：

默认不主动弹 AI。

复杂询盘：

系统根据：

```text id="qdi0cm"
missing fields
multiple candidates
knowledge lookup
historical reference
```

判断：

```text id="1ff0qz"
AI Assistance Recommended
```

销售一键打开。

---

# 52. 结果

Linda Adoption：

```text id="8gj1nj"
38% → 61%
```

但更重要：

复杂询盘 Adoption：

```text id="57mqqb"
84%
```

这是更有意义的指标。

---

# 53. 工程师指标

Before：

例如：

```text id="v65vli"
销售技术咨询：
平均 18 次 / day
```

Pilot Week 2：

```text id="2psma7"
11 次 / day
```

同时：

Engineer Review 的平均输入质量更高。

因为系统已经整理：

```text id="wfatpr"
需求
候选
规则
问题
```

---

# 54. 这才是业务价值链

系统不是：

> AI 替代陈工。

而是：

```text id="ur650y"
低价值重复咨询
↓
系统处理

复杂技术判断
↓
陈工集中处理
```

所以专家的单位时间价值提高了。

---

# 55. Pilot Failure Review Meeting

每周一固定：

```text id="o71bkg"
Top 10 failures
```

分类：

```text id="atof3y"
Data
Context
Retrieval
Rule
Model
Integration
Workflow
Human
```

---

# 56. 示例 Week 2 Failure 分布

```text id="w7ozd3"
Data:
4

Context:
3

Retrieval:
2

Rule:
6

Model:
2

Integration:
5

Workflow:
8
```

最大的：

```text id="x3rdkp"
Workflow
```

这再次提醒团队：

> AI 产品问题不一定主要发生在 AI。

---

# 57. 技术负责人的 Weekly Bet

不能解决所有问题。

选择：

### Bet 1

Inbox integration。

目标：

```text id="m2t2d2"
减少操作步骤。
```

---

### Bet 2

标准询盘 Escalation Rule 优化。

目标：

```text id="i8688q"
减少 False Escalation。
```

---

### Bet 3

Product data deployment validation。

目标：

```text id="x4xc9z"
防止数据更新导致 Regression。
```

---

明确不做：

```text id="h10wpi"
换新模型
GraphRAG
自动报价
Multi-Agent
```

---

# 58. Pilot 结束结果

模拟最终结果：

| 指标                       | Before | Pilot |
| ------------------------ | -----: | ----: |
| 标准复杂询盘处理                 | 18 min | 6 min |
| 新人复杂询盘处理                 | 31 min | 9 min |
| 技术咨询次数/日                 |     18 |    10 |
| Draft Accept/Minor Edit  |      — |   86% |
| Critical Rule Violation  |      — |     0 |
| Complex Inquiry Adoption |      — |   82% |

以上数字只是本案例的模拟 Pilot 结果。

---

# 59. 但还有一个非常重要的指标

# Override Analysis

销售 / 工程师什么时候不同意 AI？

例如：

```text id="9n4no2"
Recommendation Override:
14 cases
```

分类：

```text id="3b0d67"
Commercial Preference:
5

Missing Rule:
4

Bad Ranking:
2

Data Error:
2

User Preference:
1
```

---

# 60. 为什么 Override 是黄金数据？

因为它直接告诉团队：

> AI 和专家判断差在哪里。

下一阶段：

```text id="f9ifw3"
Override
↓
Failure Classification
↓
Rule / Data / Ranking Improvement
↓
Regression Eval
```

形成真正的学习闭环。

---

# 61. Shadow Mode

准备扩大范围前，可以对暂不支持的场景运行：

```text id="qgg3yq"
Shadow Mode
```

例如化工泵询盘。

系统：

```text id="g9tjqi"
生成结果
```

但：

```text id="hfh978"
不展示给销售
```

只与工程师真实判断比较。

这样可以先收集：

```text id="rtehgc"
Eval Data
```

再决定上线。

---

# 62. 为什么 Shadow Mode 非常适合 FDE？

因为新 Domain / 新 Workflow 往往：

```text id="p75ro3"
数据不足
+
风险较高
```

不需要：

> 要么不上，要么全上。

还有第三种：

> **先观察系统在真实环境里会做什么。**

---

# 63. Rollout Ladder

因此完整上线阶梯：

```text id="70z5wd"
Offline Eval
↓
Shadow Mode
↓
Internal Review
↓
Limited Pilot
↓
Broader Pilot
↓
Controlled Automation
```

这比：

```text id="o2fx7m"
Demo
↓
Production
```

健康得多。

---

# 64. 技术负责人本阶段必须建立 Runbook

例如：

## LLM Failure Runbook

---

## Product Data Failure Runbook

---

## CRM Outage Runbook

---

## Knowledge Retrieval Failure Runbook

---

## Critical Wrong Recommendation Runbook

---

这样事故发生时：

团队不是临时讨论“怎么办”。

---

# 65. Pilot Review 最终问题

不要只问：

> 客户满意吗？

应该回答：

### Business

真的节省时间了吗？

### User

谁在什么场景使用？

### AI

主要 Failure 在哪里？

### Risk

有没有重大错误？

### System

生产可靠性如何？

### Cost

单位任务成本如何？

### Learning

原来哪些假设错了？

---

# 66. Pilot Decision

四个可能：

```text id="5pr91a"
Stop

Iterate

Expand

Productize
```

海川当前结果：

# Expand + Begin Productization

原因：

```text id="8b0m5k"
真实用户持续使用
业务指标改善
风险可控
重复技术模式明确
```

但：

```text id="b71t8s"
自动报价
```

仍然没有足够证据进入范围。

---

# 67. Stage 7 的重要 ADR

建议增加：

### ADR-011

Pilot 先 Limited Rollout，不直接全员上线。

### ADR-012

所有 Recommendation 必须可追踪到数据 / 规则 /版本。

### ADR-013

数据版本与代码版本同样需要 Deployment Gate。

### ADR-014

External Dependency Failure 必须支持 Graceful Degradation。

### ADR-015

Adoption 以目标 Workflow 使用率衡量，不追求无差别 AI Usage。

---

# 68. 到这里技术负责人发生了什么变化？

最开始关心：

```text id="7yw07p"
模型准不准？
```

现在开始关心：

```text id="zr2cvn"
哪个用户？

哪个 Workflow？

为什么没用？

哪一层失败？

错误能否复现？

什么应该降级？

什么值得本周投入？
```

这就是从：

> AI Engineer

走向：

> Production AI / FDE Tech Lead

的重要变化。

---

# 69. Stage 7 Exit Criteria

```text id="w3ypwu"
[x] Pilot User Group

[x] Business Baseline

[x] Pilot Scope

[x] Role-aware Review

[x] Engineer Escalation

[x] End-to-end Trace

[x] Model / Prompt Versioning

[x] Data Versioning

[x] Rule Versioning

[x] Retrieval Evidence

[x] Cost Observability

[x] Graceful Degradation

[x] Incident Process

[x] Failure Review

[x] Adoption Segmentation

[x] Shadow Mode Strategy

[x] Pilot Review
```

---

# 70. 下一阶段：Stage 8

海川 Pilot 已经证明：

> 这不是一个只能 Demo 的 AI 功能。

现在真正困难的问题出现：

# 第二个客户来了。

例如：

**苏州启航压缩设备有限公司**

他们不是卖泵。

他们的问题是：

> AI 售后助手。

工作流：

```text id="uzh6ta"
Service Ticket
↓
Device Identification
↓
Symptom Extraction
↓
Asset History
↓
Knowledge
↓
Rules
↓
Diagnosis Recommendation
↓
Engineer Review
```

你会突然发现：

它和外贸系统非常像。

但又绝对不能简单复制代码。

因此 Stage 8 会正式进入：

# Productization

我们会逐模块判断：

```text id="zf97xp"
什么进入 Core？

什么留在 Foreign Trade Domain？

什么新建 After-sales Domain？

什么属于 Haichuan Tenant？

什么其实第一次抽象错了？
```

并真正执行一次：

```text id="6obgdu"
Customer Project
↓
Shared Platform
```

迁移。

这一步会检验前面所有架构决策是不是真的经得住第二个客户。
