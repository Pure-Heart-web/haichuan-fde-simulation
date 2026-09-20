# AI / FDE 创业实战

## Stage 8：第二客户进入、Productization 与 Shared Platform

---

# 1. 一个危险但令人兴奋的时刻

海川 Pilot 已经跑起来。

团队只有 4 个人。

这时销售带来第二个客户：

> 苏州启航压缩设备有限公司

简称：

**启航设备**

主要产品：

* 工业空压机
* 冷干机
* 储气罐
* 空气处理设备

企业规模：

约 200 人。

售后工程师：

12 人。

客服：

6 人。

全国存在大量已安装设备。

---

客户负责人张总说：

> 我们售后每天收到大量电话和微信。
>
> 很多问题其实非常重复。
>
> 我希望做一个 AI 售后工程师。
>
> 客户描述故障以后，AI 直接告诉他怎么修。
>
> 最好以后简单故障都不用找我们工程师。

---

# 2. 你的第一反应是什么？

如果经历过前面七个 Stage，现在不应该想：

```text
“我们已经有 AI 平台了，
改一下 Prompt 应该就可以。”
```

也不能走另一个极端：

```text
“这是完全不同的行业，
重新开发一套。”
```

正确问题应该是：

> **哪些问题真的一样，哪些只是表面相似？**

---

# 3. 第二客户为什么如此重要？

第一客户阶段，你可以凭想象定义：

```text
Core
Domain
Tenant
```

第二客户到来以后：

这些抽象第一次接受现实检验。

你会发现三种情况：

```text
① 原来真的可以复用

② 看起来相似，其实不应该复用

③ 第一客户时根本没意识到这是通用能力
```

因此：

> 第二客户是 Productization 的第一场真正考试。

---

# 4. 不要立即复制海川系统

团队召开 90 分钟 Discovery。

要求启航的一线客服真实演示一条售后请求。

客户来电：

> 我们的 QH-75 空压机今天突然 E37 报警。
>
> 压力一直上不去，大概只有 5 bar。
>
> 平时是 8 bar。
>
> 机器还有一点异响。
>
> 昨天刚做过保养。

客服小周开始处理。

---

# 5. 售后真实 Workflow

小周：

> 我先问机器型号和序列号。

然后：

```text
确认设备
↓
查设备档案
↓
查最近维修记录
↓
记录故障码
↓
问运行情况
↓
查手册
↓
判断能不能远程指导
↓
不确定就问工程师
↓
必要时派工
```

---

# 6. 初步 Workflow

整理后：

```text
Service Request
      ↓
Device Identification
      ↓
Symptom Extraction
      ↓
Asset Context
      ↓
Fault Code Lookup
      ↓
Knowledge Retrieval
      ↓
Diagnostic Rules
      ↓
Recommendation
      ↓
Risk Evaluation
      ↓
Engineer Review
      ↓
Remote Guidance / Dispatch
```

团队里有人说：

> 这不是跟外贸一模一样吗？

确实很像。

但先别急。

---

# 7. 对比海川 Workflow

海川：

```text
Inquiry
↓
Customer Identification
↓
Requirement Extraction
↓
Customer Context
↓
Product Search
↓
Knowledge
↓
Rules
↓
Recommendation
↓
Sales / Engineer Review
```

启航：

```text
Service Request
↓
Device Identification
↓
Symptom Extraction
↓
Asset Context
↓
Fault Search
↓
Knowledge
↓
Rules
↓
Recommendation
↓
Engineer Review
```

结构上非常接近。

所以我们得到第一个 Productization Hypothesis：

> 两个 Domain 可能共享同一套 AI Workflow primitives。

注意：

仍然只是 Hypothesis。

---

# 8. 开始逐层检验

不要讨论：

> “整个平台能不能共享？”

要一个模块一个模块检查。

---

# 9. Ingestion

海川输入：

```text
Email
Web Form
```

启航输入：

```text
客服录入
售后工单
微信转录
电话转写
```

表面不同。

但进入系统以后都可以变成：

```text
WorkItem
```

例如：

```python
class WorkItem:
    id
    tenant_id
    domain

    source_type
    source_id

    raw_content
    attachments

    actor_id
    created_at
```

因此：

# Ingestion Contract 可以进入 Core

而：

```text
EmailAdapter
TicketAdapter
CallTranscriptAdapter
```

属于 Integrations。

---

# 10. Extraction Engine

海川抽：

```text
flow
head
medium
quantity
```

售后抽：

```text
device_model
serial_number
error_code
pressure
symptoms
runtime_hours
maintenance_recency
```

字段完全不同。

但是运行过程：

```text
Raw Content
+
Schema
+
Instructions
↓
Structured Object
```

完全一样。

因此：

# Extraction Runtime = Core

而：

```text
InquirySchema
ServiceCaseSchema
```

属于 Domain。

---

# 11. 一个非常重要的 Productization 判断

错误抽象：

```python
def extract_pump_email(...)
```

难复用。

正确抽象：

```python
extract(
    work_item,
    schema,
    domain_config
)
```

第二客户第一次证明：

前面的 Schema-driven Extraction 是正确投资。

---

# 12. Context Retrieval

海川：

```text
Customer Context
Previous Orders
```

启航：

```text
Asset Context
Maintenance History
Previous Faults
Installed Components
```

业务对象不同。

但是模式一致：

```text
entity_id
↓
retrieve relevant historical context
```

因此：

```text
ContextProvider
```

可以进入 Core。

---

# 13. ContextProvider Core Interface

例如：

```python
class ContextProvider(Protocol):

    async def get_context(
        self,
        entity_ref,
        context_request
    ) -> list[ContextItem]:
        ...
```

海川实现：

```text
CustomerOrderContextProvider
```

启航：

```text
AssetMaintenanceContextProvider
```

这样共享的是：

> **接口与执行模型。**

不是强迫所有 Context 长得一样。

---

# 14. Knowledge Retrieval

海川：

```text
产品手册
FAQ
保修政策
认证
```

启航：

```text
维修手册
故障码手册
SOP
维修案例
安全指南
```

两者都需要：

```text
版本
Owner
Status
Effective Date
Metadata
Retrieval
Evidence
```

所以：

# Knowledge Runtime = Core

但是：

```text
Knowledge Corpus
Metadata Schema Extensions
Retrieval Filter Policy
```

仍然可以 Domain / Tenant 化。

---

# 15. Rule Engine

海川规则：

```text
seawater
→ exclude cast iron
```

启航规则：

```text
E37
+
discharge temperature > threshold
→ stop machine
→ engineer escalation
```

内容完全不同。

执行模式：

```text
condition
↓
action
↓
severity
↓
evidence
```

高度一致。

因此：

# Rule Runtime = Core

# Rule Set = Domain / Tenant

---

# 16. Recommendation

海川：

```text
产品候选
```

启航：

```text
诊断步骤 / 下一行动
```

开始出现差异。

如果 Core 定义成：

```python
ProductRecommendation
```

无法复用。

所以需要提升一个抽象层次。

---

# 17. Recommendation V2

更通用：

```python
class Recommendation:
    actions
    options
    warnings

    evidence

    risk_level
    confidence

    requires_review
```

外贸：

```text
option:
CP90

action:
request medium confirmation
```

售后：

```text
action:
check intake filter

warning:
do not continue running if temperature exceeds X
```

---

# 18. 这是第二客户推动出的新 Core

第一客户阶段：

```text
Recommendation ≈ 产品推荐
```

第二客户以后：

```text
Recommendation = 下一步建议 / 决策辅助结果
```

这是一种健康抽象。

为什么？

因为：

> 它来自两个真实 Workflow 的重复。

不是第一天架构会议想象出来的。

---

# 19. Human Review

海川：

```text
Sales Review
Engineer Review
```

启航：

```text
Support Review
Engineer Review
Dispatch Approval
```

底层动作仍然是：

```text
Approve
Edit
Reject
Escalate
```

因此：

# ReviewTask 明确进入 Core

---

# 20. Feedback

海川：

```text
销售修改产品候选
修改邮件
工程师 override
```

启航：

```text
工程师修改诊断
标记建议无效
维修完成后记录真实原因
```

本质都是：

```text
system_output
vs
human / real-world outcome
```

所以：

# FeedbackEvent = Core

---

# 21. Eval

海川：

```text
Extraction Accuracy
Candidate Recall
Rule Violation
Draft Acceptance
```

启航：

```text
Extraction Accuracy
Diagnosis Top-K
Unsafe Advice Rate
Engineer Acceptance
Resolution Rate
```

指标不同。

但是：

```text
Dataset
Pipeline Version
Runner
Graders
Regression
Report
```

运行基础设施一致。

因此：

# Eval Runtime = Core

# Eval Scenario / Metrics = Domain

---

# 22. 第一次 Core / Domain / Tenant Mapping

现在可以画出：

```text
                  Shared Core
────────────────────────────────────
WorkItem
Workflow Runtime
Extraction Engine
Context Interface
Knowledge Runtime
Rule Engine
Recommendation Contract
ReviewTask
FeedbackEvent
Eval Runtime
Observability
Auth / Audit
────────────────────────────────────
             ↓                 ↓
   Foreign Trade Domain   After-sales Domain
             ↓                 ↓
       Haichuan Tenant     Qihang Tenant
```

---

# 23. Productization 不是“把代码搬到 core”

这里非常容易犯错。

工程师可能：

> 这段代码两个项目都用到了，搬 Core。

不够。

真正需要问五个问题：

```text
1. 语义真的相同吗？

2. 生命周期真的相同吗？

3. 两个 Domain 会不会以不同速度演化？

4. 抽象后的接口是否自然？

5. 第三个 Domain 可能继续使用吗？
```

---

# 24. 一个不应该共享的例子

海川有：

```text
Product Candidate Ranking
```

启航有：

```text
Fault Diagnosis Ranking
```

都叫 Ranking。

是不是应该：

```text
core/ranking/
```

？

暂时未必。

因为：

海川考虑：

```text
flow
head
operating point
commercial preference
```

启航考虑：

```text
symptom likelihood
fault code
asset history
risk
```

除了名字，都不太一样。

因此：

```text
ForeignTradeRanking
AfterSalesDiagnosisRanking
```

暂时留在 Domain。

---

# 25. 抽象真正的原则

不是：

> 两份代码长得像。

而是：

> **两份代码表达的是同一个稳定概念。**

这一点技术负责人必须守住。

---

# 26. 第二客户暴露第一客户的技术债

启航开始接入后发现：

海川项目的 `core` 里存在：

```python
if field_name == "medium":
```

还有：

```python
if recommendation.candidate_products:
```

这说明：

Domain 泄漏到 Core。

---

# 27. Productization Refactor

立即建立：

```text
Productization Debt
```

例如：

### PD-001

`core/extraction` 出现泵字段语义。

解决：

由 Domain Validator 接管。

---

### PD-002

Recommendation 假设存在 product candidates。

解决：

改为通用：

```text
options
actions
warnings
```

---

### PD-003

Review UI 假设 Reviewer 是 Sales。

解决：

Role-driven ReviewTask。

---

# 28. 不要大爆炸重构

团队很容易产生：

> 第二客户来了，我们花一个月把平台彻底重构好。

危险。

因为：

你仍然不知道第三个客户是什么样。

更合理：

```text
New Customer Delivery
+
Incremental Productization
```

同步进行。

---

# 29. Productization Budget

例如团队每个 Sprint：

```text
60% 第二客户业务交付

25% 已验证 Core 抽取

15% 技术债 / Eval / Infra
```

比例不是标准答案。

关键是：

> Productization 必须有明确预算，否则客户项目会永远吞掉全部时间。

---

# 30. 启航 MVP Discovery

继续业务拆解。

一条售后请求：

```text
Machine:
QH-75

Serial:
QH7519238

Alarm:
E37

Pressure:
5 bar

Normal:
8 bar

Symptom:
abnormal noise

Maintenance:
yesterday
```

---

# 31. ServiceCase Schema

```python
class ServiceCase:

    device_model
    serial_number

    error_codes

    symptoms

    current_pressure
    normal_pressure

    temperature

    runtime_hours

    recent_maintenance

    urgency

    missing_fields
```

这完全可以复用：

```text
Core Extraction Runtime
```

只换：

```text
Schema + Instructions
```

---

# 32. Asset Context

根据 serial：

```text
QH7519238
```

查：

```text
设备型号
安装日期
客户
历史工单
上次保养
更换配件
```

这正好验证：

```text
ContextProvider
```

是否真的是好抽象。

---

# 33. 第一次 Context 接入失败

海川接口写成：

```python
get_customer_history(customer_id)
```

显然无法支持设备。

说明此前抽象层次不够。

于是重构为：

```python
get_context(entity_ref, context_request)
```

其中：

```text
entity_type:
customer
asset
order
```

这就是：

> 第二客户推动 Core 成熟。

---

# 34. Knowledge

启航上传：

```text
Equipment_Manual_2025.pdf
Fault_Code_Manual.xlsx
Service_SOP.docx
Old_Service_Manual_2021.pdf
Engineer_FAQ.xlsx
```

你立刻认识到熟悉的问题：

```text
Old
New
FAQ
Excel
Manual
```

所以海川阶段建立的：

```text
version
status
effective_date
owner
```

全部直接复用。

这是真正的 Product Asset。

---

# 35. Rule 示例

技术工程师说：

> E37 本身不一定严重。
>
> 但如果伴随高温和异响，就不要让客户继续运行。

整理后：

```yaml
id: SERVICE_E37_003

when:
  error_code: E37
  symptoms:
    contains: abnormal_noise
  temperature_c:
    gte: 95

then:
  actions:
    - stop_machine
    - escalate_engineer

severity: critical
```

Rule Engine 完全复用。

规则内容不复用。

---

# 36. 一个重要安全差异

海川错误产品建议可能造成：

```text
商业损失
换货
客户体验问题
```

启航错误维修建议可能造成：

```text
设备损坏
人身安全
生产停机
```

因此虽然技术结构相似：

# Risk Policy 不能完全共享。

---

# 37. Domain-specific Risk Policy

After-sales Domain：

例如：

```text
High-risk maintenance
→ AI 不允许直接指导
```

或者：

```text
Electrical cabinet
Pressure vessel
High temperature
Unknown mechanical noise
```

强制工程师。

---

# 38. 这告诉技术负责人一个重要边界

可以共享：

```text
Policy Engine / Review Mechanism
```

但不能共享：

```text
具体风险政策
```

结构共享，内容分离。

---

# 39. Shared Core + Domain Pack

现在正式形成产品模型：

```text
FDE Platform
=
Shared Core
+
Domain Pack
+
Tenant Config
+
Integrations
```

---

# 40. Shared Core

包括：

```text
WorkItem

Workflow Runtime

Extraction Runtime

Context Interface

Knowledge Runtime

Rule Runtime

Recommendation Contract

Review Workflow

Feedback System

Eval Runtime

Observability

Auth

Audit
```

---

# 41. Foreign Trade Domain Pack

包括：

```text
InquirySchema

ProductSchema

Foreign Trade Ontology

Product Search

Pump Rules

Product Ranking

Inquiry Metrics

Reply Content Policy
```

---

# 42. After-sales Domain Pack

包括：

```text
ServiceCaseSchema

AssetSchema

Fault Ontology

Diagnosis Logic

Safety Rules

Service Escalation

After-sales Metrics

Service Response Policy
```

---

# 43. Haichuan Tenant

包括：

```text
Product Mapping

Customer Mapping

Approved Knowledge Sources

Commercial Preference

Permissions

Reply Style

CRM / ERP Integration Config
```

---

# 44. Qihang Tenant

包括：

```text
Equipment Mapping

Fault Code Mapping

Service Policies

Engineer Routing

Knowledge Sources

CMMS / ERP Integration

Permissions
```

---

# 45. 判断是否平台化的黄金测试

给第三个假想 Domain：

> 招聘筛选。

Workflow：

```text
Resume
↓
Extraction
↓
Candidate Context
↓
Job Knowledge
↓
Rules
↓
Recommendation
↓
Human Review
```

如果：

```text
Extraction Runtime
Context Interface
Knowledge
Rules
Review
Feedback
Eval
```

依然说得通，

说明这些 Core 抽象很可能确实稳定。

---

# 46. 但不能因此做万能低代码平台

Founder 最容易在此处兴奋：

> 我们是不是可以做一个“所有行业的 AI Workflow Platform”？

先不要。

因为客户真正购买的是：

> **问题解决能力。**

不是：

> 抽象层数量。

---

# 47. 产品化有两个维度

## Engineering Productization

减少：

```text
重复开发
部署成本
测试成本
维护成本
```

---

## Market Productization

回答：

```text
谁愿意买？

为什么买？

购买理由是否重复？

ROI 是否类似？

销售过程是否可重复？
```

只有第一项，没有第二项：

你可能只是造了一个内部平台。

---

# 48. 第二客户后的市场学习

海川痛点：

```text
少数专家知识
→
大量销售重复依赖
```

启航痛点：

```text
少数售后专家知识
→
大量客服重复依赖
```

开始出现更高层的共同模式：

> **专家知识无法规模化。**

这可能比：

> “外贸 AI”

更接近真正的 Product Thesis。

---

# 49. Product Thesis V1

初步可以表达成：

> 为工业设备企业，把分散在文档、历史记录和专家脑中的技术知识嵌入一线销售和售后工作流，让大量重复判断由系统辅助完成，把专家时间集中在真正复杂的问题上。

注意：

这仍然需要更多客户验证。

但已经比：

> “做 AI Agent 平台”

具体很多。

---

# 50. 从 Feature 到 Capability

第一个客户容易看 Feature：

```text
邮件抽取
产品推荐
回复生成
```

第二客户以后应该开始看 Capability：

```text
Structured Understanding

Entity Context

Knowledge Grounding

Rule-based Decision Support

Human Review

Feedback Learning

Evaluation
```

Capability 才是产品工程的真正积木。

---

# 51. Productization Metrics

技术负责人开始新增一组指标。

不只看客户业务指标。

还要看：

# Reuse Metrics

---

## Time to First Demo

海川：

例如：

```text
10 天
```

启航：

如果 Core 有效：

```text
4 天
```

---

## Shared Code Ratio

不要机械追求数字。

但可以观察：

```text
Core runtime
```

是否无需修改即可支持新客户。

---

## New Domain Changes to Core

这是很重要的指标。

如果每个客户都需要：

```text
大量修改 Core
```

说明 Core 不稳定。

---

## Tenant-specific Code

如果不断增长：

```text
if tenant == ...
```

说明配置边界失败。

---

# 52. 一个更好的指标

# Customer-specific Branch Count

理想趋势：

```text
↓
```

如果：

客户 1：

```text
5
```

客户 2：

```text
16
```

客户 3：

```text
35
```

你正在滑向：

> 项目制软件公司。

---

# 53. Delivery Speed

记录：

```text
Discovery → Demo

Demo → Pilot

Pilot → Production
```

每个新客户是否缩短？

这比代码复用率更有商业意义。

---

# 54. Productization Review Meeting

每完成一个客户阶段，团队开 60 分钟 Review。

固定问：

```text
这次重新做了什么？

为什么没复用？

什么真正重复了？

哪些差异是 Domain？

哪些差异只是 Tenant？

哪个 Core abstraction 被证明错误？

什么现在值得抽？

什么还应该继续等？
```

---

# 55. 一个重要例子：Approval

海川需要：

```text
Sales Approval
Engineer Approval
```

启航需要：

```text
Engineer Approval
Dispatch Approval
```

未来报价还需要：

```text
Manager Approval
```

因此发现：

```text
Approval Workflow
```

可能是 Core。

---

# 56. 但不要立刻做 BPM 平台

第一版只支持：

```text
single reviewer
role routing
approve
reject
edit
escalate
```

如果未来真实出现：

```text
多级审批
并行审批
条件审批
```

再扩展。

---

# 57. Configuration vs Code

团队开始讨论：

> 哪些客户差异放配置？

推荐判断：

如果差异：

```text
明确
稳定
有限
业务人员可理解
```

适合配置。

---

例如：

```yaml
review_policy:
  high_risk:
    reviewer_role: engineer
```

合理。

---

但如果你做：

```yaml
entire_business_logic:
  step_1:
    ...
```

最终是在 YAML 里重新发明编程语言。

危险。

---

# 58. Rule / Config / Code 的边界

## Config

简单差异：

```text
阈值
Feature flag
Source mapping
角色
展示方式
```

---

## Rule

业务可解释的条件约束：

```text
如果 X，则 Y
```

---

## Code

复杂算法、执行逻辑、数据操作。

---

## LLM

不确定自然语言理解和生成。

不要为了“平台化”全部配置化。

---

# 59. Multi-tenant Data Isolation

第二客户来了以后，一个此前不紧迫的问题变得关键：

> 客户 A 的数据绝对不能进入客户 B。

所有主要数据：

```text
WorkItem
Context
Knowledge
Rule
Trace
Eval
Feedback
```

必须拥有：

```text
tenant_id
```

并在存储层和查询层真正执行隔离。

---

# 60. Knowledge Retrieval 也必须 Tenant-aware

不能：

```text
search all docs
↓
prompt filter
```

必须先：

```text
tenant scope
↓
domain scope
↓
permission
↓
metadata
↓
retrieval
```

这是系统边界，不是 Prompt 规则。

---

# 61. Eval 也需要多层结构

开始组织为：

```text
evals/
├── core/
│   ├── structured_output/
│   └── workflow/
│
├── domains/
│   ├── foreign_trade/
│   └── after_sales/
│
└── tenants/
    ├── haichuan/
    └── qihang/
```

---

# 62. 为什么 Tenant Eval 仍然重要？

例如相同售后 Domain：

客户 A：

```text
设备型号体系不同
```

客户 B：

```text
规则不同
```

所以：

Domain Eval 证明：

> 通用售后能力没坏。

Tenant Eval 证明：

> 这个客户部署没坏。

---

# 63. Platform Release 变复杂了

以前：

```text
改完 → 海川 Eval → 上线
```

现在：

```text
Core Change
↓
Core Tests
↓
Foreign Trade Regression
↓
After-sales Regression
↓
Haichuan Eval
↓
Qihang Eval
↓
Release
```

这就是产品化带来的真实成本。

---

# 64. 不要只看到复用收益

Shared Core 同样产生：

```text
耦合
Regression Surface
版本管理
Migration
```

所以：

> 并不是代码越共享越好。

核心标准：

> 总系统复杂度是否下降？

---

# 65. 一个典型错误

为了复用：

团队把所有 Schema 统一成：

```python
data: dict[str, Any]
```

于是任何 Domain 都能跑。

看起来超级通用。

但代价：

```text
类型安全消失
Contract 不明确
Eval 更难
IDE 无帮助
错误推迟到 runtime
```

这是：

# Fake Generalization

---

# 66. 更好的设计

Core 提供：

```text
generic runtime
```

Domain 提供：

```text
strong typed schema
```

例如：

```python
ExtractionEngine[T]
```

而不是：

```python
EverythingDict
```

---

# 67. 第二客户第一次 Build Sprint

因为 Shared Core 已存在，

启航 Sprint 1 不再需要重写：

```text
Ingestion Runtime
Extraction Runtime
ReviewTask
Feedback
Tracing
Eval Harness
```

只需要新增：

```text
ServiceCase Schema
Ticket Adapter
Asset Context Adapter
After-sales Rules
Domain Eval Dataset
Review UI domain view
```

---

# 68. Delivery 时间对比

海川第一版：

```text
Discovery:
5 days

First usable extraction demo:
10 days

Pilot:
~4 weeks
```

启航：

假设：

```text
Discovery:
4 days

First usable demo:
4 days

Pilot:
2–3 weeks
```

再次强调：

这里是模拟数据。

真正重要的是：

> 是否存在明显的学习曲线。

---

# 69. 如果第二客户还是和第一客户一样慢呢？

这并不一定说明平台失败。

先看时间花在哪里。

可能：

```text
80% 时间仍然花在：
业务 Discovery
数据清洗
专家规则整理
```

这可能本来就是 FDE 项目的主要成本。

---

# 70. 于是产品化方向可能不是“完全消灭服务”

而是：

> **把不可避免的人力投入集中在真正的领域知识获取，而不是重复造基础设施。**

这是更现实的目标。

---

# 71. Productization Funnel

每个客户的东西按下面路径判断：

```text
Customer-specific Fix
↓
Repeated Pattern?
   ↓
  No → Tenant
   ↓ Yes
Domain Pattern?
   ↓
  Yes → Domain Capability
   ↓
Cross-domain Stable Pattern?
   ↓
  Yes → Shared Core Candidate
```

最后一步一定要慢。

---

# 72. 三次规则

团队可以使用一个启发式规则：

> 如果一个抽象只出现 1 次，先别抽。

> 出现 2 次，可以设计接口。

> 出现 3 次且变化模式类似，再考虑稳定平台能力。

不是硬规则。

但对创业团队非常有帮助。

---

# 73. 防止平台团队吞噬创业团队

此时工程师很容易兴奋于：

```text
Workflow Engine
Plugin System
Rule DSL
Generic UI
Multi-tenant Control Plane
```

技术负责人必须持续问：

> 这能让下一个客户更快获得价值吗？

如果不能：

暂缓。

---

# 74. FDE Platform Roadmap

根据两个客户的真实证据，现在 Roadmap 可以分三层。

---

## P0：已验证 Core

```text
WorkItem
Extraction
Context
Knowledge
Rules
Review
Feedback
Eval
Observability
```

---

## P1：正在形成

```text
Workflow Runtime
Approval
Domain Package Contract
Tenant Configuration
Data Deployment
```

---

## P2：暂不投资

```text
Visual Workflow Builder
Universal Agent Runtime
Generic Rule UI
Marketplace
Complex Plugin SDK
```

直到客户需求真正出现。

---

# 75. 产品 Roadmap 不应该按技术组件排

不要写：

```text
Q1 Vector DB
Q2 Agent
Q3 Graph
```

更好的：

```text
Goal 1:
新 Domain 从 Discovery 到 Demo < 1 周

Goal 2:
客户数据更新不产生未检测 Regression

Goal 3:
高风险输出 100% 可追踪

Goal 4:
第二客户 Pilot 业务价值成立
```

再由这些目标决定技术投入。

---

# 76. 商业模型也开始受到影响

第一客户可能按照：

```text
Pilot Fee
+
Customization
```

收费。

随着产品化：

可以逐步形成：

```text
Platform Subscription
+
Domain Module
+
Integration
+
Deployment / Services
```

但技术负责人需要理解：

产品化不是只影响代码。

它会逐渐影响：

```text
销售
定价
实施
支持
版本
SLA
```

---

# 77. Founder-FDE 的新问题

现在你开始面对资源分配：

当前有：

```text
海川：
正在扩张 Pilot

启航：
正在实施

潜在客户 C：
希望下周 Demo
```

团队仍然只有 4 人。

这时最大的技术风险可能已经不是模型。

而是：

> **团队注意力碎片化。**

---

# 78. 客户组合管理

建议明确：

```text
Primary Pilot:
启航

Production Customer:
海川

Discovery:
Customer C

其他:
保持关系
```

不要三个都进入重 Build。

---

# 79. 为什么这也是技术负责人职责？

因为每增加一个活跃客户：

都会增加：

```text
Integration Surface
Data Surface
Eval Surface
Support Load
Context Switching
```

所以：

> 销售 Pipeline 也是技术容量问题。

---

# 80. 第二客户的第一个重大 Failure

启航上线 Shadow Mode 后：

系统根据：

```text
E37
+
低压力
```

推荐：

> 检查进气过滤器。

工程师说：

> 这个建议一般没错，但这个设备昨天刚做过保养，第一优先应该检查维护过程中是否装配异常。

---

# 81. 系统哪里错了？

Extraction：

正确。

Knowledge：

正确。

Rules：

正确。

模型：

也没有明显错误。

缺的是：

```text
Asset Context
```

虽然已经查询了维修历史，

但 Ranking 没使用：

```text
recent_maintenance
```

---

# 82. 这形成一个新的 Pattern

海川曾经有：

```text
same as previous order
```

启航出现：

```text
recent maintenance
```

共同本质：

> **历史 Context 不只是拿来展示，它需要真正影响当前决策。**

这是一个可能的 Shared Capability：

```text
Context-aware Decision Inputs
```

但是否抽象进 Core？

暂时不急。

先记录重复。

---

# 83. 这是 Productization 最健康的方式

不是：

```text
看到 Pattern
→ 立即建框架
```

而是：

```text
看到 Pattern
→ 记录
→ 第二次验证
→ 第三次稳定
→ 抽象
```

---

# 84. 第二个重大 Failure：Review UI

启航工程师说：

> 这个页面太像销售系统。

因为从海川复制了：

```text
Candidate
Approve
Reply Draft
```

但售后工程师真正关心：

```text
设备信息
历史维修
风险
排查步骤
```

因此：

# Review Engine 共享

但是：

# Review Experience 应该 Domain-specific

---

# 85. 共享 Backend ≠ 共享 UI

技术负责人应该避免：

> 为了平台化，把所有用户都塞进同一个万能 Review 页面。

更好的：

```text
Shared Review Contract
+
Domain Review Renderer
```

---

# 86. Core / Domain Boundary 最终版本

到第二客户结束后，大致形成：

## Shared Core

```text
Execution
Contracts
Policies Framework
Observability
Evaluation Infrastructure
Review Workflow
```

## Domain

```text
Schemas
Ontology
Decision Logic
Risk Policy
Ranking
UX
Metrics
```

## Tenant

```text
Data
Mappings
Thresholds
Integrations
Permissions
Style
Local Policies
```

---

# 87. Productization Decision Log 示例

## Capability

Extraction Runtime

### Evidence

海川 + 启航均使用。

### Difference

Schema 不同。

### Decision

Shared Core。

---

## Capability

Candidate Ranking

### Evidence

两个项目都有类似名称。

### Difference

语义完全不同。

### Decision

Keep Domain-specific。

---

## Capability

ReviewTask

### Evidence

两个项目均需要审批和修改。

### Decision

Shared Core。

---

## Capability

Review UI

### Evidence

两个 Domain 用户需求差异明显。

### Decision

Shared framework + Domain renderer。

---

# 88. Productization Scorecard

每一个候选能力可以按五项检查：

| 维度                  | 问题           |
| ------------------- | ------------ |
| Frequency           | 是否反复出现？      |
| Semantic Similarity | 真的是同一概念吗？    |
| Stability           | 是否已经稳定？      |
| Reuse Value         | 抽象后能明显节省时间吗？ |
| Complexity Cost     | 会增加多少复杂度？    |

不要机械打总分。

重点是迫使团队把取舍讲清楚。

---

# 89. Stage 8 Pilot 结束后的公司资产

两个客户之后，公司已经不仅有代码。

还有：

```text
Discovery Method

Problem Brief

Workflow Modeling

AI Boundary Framework

Shared Contracts

Domain Package Pattern

Data Governance

Rule Governance

Eval Framework

Pilot Process

Incident Process

Productization Review
```

这套东西本身就是：

# Delivery IP

---

# 90. 为什么 Delivery IP 很重要？

因为创业团队的壁垒未必一开始就是：

> 一个不可复制的模型。

也可能是：

> **把一个陌生工业 Workflow 在 2～3 周内可靠 AI 化的能力。**

如果这件事情别人需要三个月，你需要三周：

它本身就是竞争优势。

---

# 91. 现在重新看 FDE 的含义

最开始：

```text
FDE =
去客户现场写代码
```

现在更准确：

```text
FDE =
Discovery
+
Domain Modeling
+
Data Engineering
+
AI System Design
+
Workflow Integration
+
Evaluation
+
Production
+
Product Learning
```

代码只是其中一部分。

---

# 92. Founder-FDE 的关键升级

第一个客户时：

你问：

> 怎么把项目做成功？

第二个客户以后：

你必须同时问：

> 怎么让这个项目成功？

和：

> 这次交付会不会让第三个客户更快？

这两个问题必须同时存在。

---

# 93. Stage 8 最终系统架构

```text
                    Applications
        ┌──────────────┴──────────────┐
        │                             │
 Foreign Trade UI              After-sales UI
        │                             │
        └──────────────┬──────────────┘
                       ↓
                 Domain Packs
        ┌──────────────┴──────────────┐
        │                             │
 Foreign Trade                  After-sales
 Schema                         Schema
 Rules                          Rules
 Ranking                        Diagnosis
 Risk Policy                    Safety Policy
 Metrics                        Metrics
        └──────────────┬──────────────┘
                       ↓
                  Shared Core
────────────────────────────────────────────
WorkItem
Workflow Runtime
Extraction
Context
Knowledge
Rule Engine
Recommendation
ReviewTask
Feedback
Evaluation
Observability
Auth / Audit
────────────────────────────────────────────
                       ↓
                  Integrations
        CRM / ERP / CMMS / Email / LLM
                       ↓
                  Tenant Config
          Haichuan       Qihang
```

---

# 94. Stage 8 Exit Criteria

```text
[x] 第二客户完成 Discovery

[x] 第二 Domain Workflow 建模

[x] Shared / Domain / Tenant 逐层评审

[x] Core 抽象经第二客户验证

[x] 第一批错误抽象被重构

[x] Productization Debt 建立

[x] Multi-tenant 数据边界明确

[x] Domain-specific Risk Policy

[x] Domain-specific Eval

[x] Domain-specific Review UX

[x] Productization Review

[x] Delivery Speed Metrics

[x] Product Thesis V1
```

---

# 95. 到这里第一轮完整 FDE 生命周期结束

我们已经从：

```text
客户一句：
“我要 AI 外贸业务员”
```

走完：

```text
Discovery
↓
Problem Framing
↓
Workflow Modeling
↓
Data Discovery
↓
AI Boundary
↓
Build Sprint
↓
Product Search
↓
Rules
↓
Context / Knowledge
↓
Generation
↓
Production Pilot
↓
Failure Analysis
↓
Second Customer
↓
Productization
```

这实际上就是一套完整的：

# Founder-FDE Operating Loop

---

# 96. 但创业公司的下一阶段更难

现在公司已经拥有：

```text
两个真实客户
一套 Shared Core
两个 Domain Pack
大量真实 Failure
初步 Product Thesis
```

下一个问题不再只是：

> 系统怎么做？

而是：

# 公司该往哪里下注？

例如现在出现四个机会：

```text
A：
继续深挖外贸销售

B：
继续深挖工业售后

C：
做通用工业企业 AI Platform

D：
接更多定制项目赚现金
```

与此同时：

```text
只有 4～6 名工程师
```

这是从：

> 技术负责人

继续升级到：

> Founder / CTO 技术战略负责人

必须面对的问题。

---

# 97. 下一阶段：Stage 9

下一阶段应该进入：

# Technical Strategy & Portfolio Management

我们不再只模拟单项目。

而是模拟你作为创业团队负责人面对：

```text
多个客户
多个产品方向
有限工程师
技术债
现金流压力
平台投入
产品化机会
新模型 / Agent 技术变化
```

你要决定：

```text
什么客户接？

什么客户不接？

什么需求做？

什么需求拒绝？

什么时候抽象？

什么时候重构？

什么时候招聘？

什么时候继续 Founder Coding？

什么时候建立专门 Platform Team？

哪个 Domain 应该成为真正主航道？
```

这才是技术负责人训练从：

```text
Project Leadership
```

进入：

```text
Company-level Technical Leadership
```

的下一步。
