# 海川工业泵 AI 询盘项目

## Stage 4：Build Sprint 1 —— 从设计进入真实工程开发

---

# 1. Sprint 1 到底要完成什么？

前面已经确认整个长期 Workflow：

```text
Email
↓
Extraction
↓
Context
↓
Knowledge
↓
Rules
↓
Recommendation
↓
Human Review
↓
Reply
```

但是 Sprint 1 **绝对不全部实现**。

第一 Sprint 只验证最底层的一条能力：

> **客户邮件能否稳定地转换为可靠、可验证的结构化 InquiryRecord？**

因此 Sprint 1 Scope：

```text
Email / Raw Text
↓
Ingestion
↓
WorkItem
↓
Structured Extraction
↓
Normalization
↓
Validation
↓
InquiryRecord
↓
Simple Review UI
↓
Feedback
↓
Eval
```

明确不做：

```text
Product Recommendation
RAG
Customer History
Pricing
Auto Reply
Auto Send
```

---

# 2. 为什么技术负责人要这么切？

因为后面所有能力：

```text
产品搜索
规则
推荐
报价
```

都建立在一个假设上：

> **系统正确理解了客户到底说了什么。**

如果 Extraction 都不可靠，后面越复杂，错误只会被放大。

所以技术负责人应该坚持：

> 先验证最基础的数据合同，再继续叠加智能。

---

# 3. Sprint Duration

假设团队：

* 你：Tech Lead / FDE Lead
* Engineer A：AI / Backend
* Engineer B：Full-stack
* Engineer C：Data / Integration

Sprint 长度：

**10 个工作日。**

目标不是“Feature Complete”。

目标是：

> **第 10 天能够拿 100 条真实风格询盘跑完整 Eval，并让销售真实审核结果。**

---

# 4. Sprint Planning

技术负责人第一件事不是：

> 大家开始写。

而是把 Sprint Goal 写清楚。

---

## Sprint Goal

> 将非结构化外贸询盘稳定转换为标准 InquiryRecord，并建立第一个可持续 Regression Eval 流程。

---

## Success Criteria

### Functional

能够处理：

```text
纯文本邮件
HTML 邮件
常见邮件签名
英文询盘
简单中英文混合
```

---

### AI

关键字段：

```text
product_type
quantity
flow
head
medium
temperature
voltage
frequency
destination
```

在 Pilot Dataset 上达到预设基线。

---

### Engineering

必须有：

```text
typed schema
validation
logging
prompt version
model version
eval CI
```

---

### Product

销售可以：

```text
查看原邮件
查看提取结果
修改错误字段
提交反馈
```

---

# 5. Sprint Issue Breakdown

技术负责人开始拆 Issue。

不要按照：

```text
“做 AI”
“做前端”
“做后端”
```

这样拆。

要按系统能力和 Contract 拆。

---

# Epic A：Domain Schema

Owner：

Tech Lead + Engineer A

---

## ISSUE A1：定义 InquiryRecord V1

输出：

```text
domains/foreign_trade/schemas/inquiry.py
```

例如：

```python
class InquiryRecord(BaseModel):
    customer_name: str | None
    company_name: str | None
    country: str | None

    product_type: str | None
    quantity: int | None

    flow_m3h: float | None
    head_m: float | None
    medium: str | None
    temperature_c: float | None

    voltage_v: int | None
    frequency_hz: int | None

    destination_port: str | None

    missing_fields: list[str]
```

---

## Acceptance Criteria

不是：

> “代码写好了。”

而是：

```text
[ ] 每个字段有业务定义
[ ] 每个单位有 canonical representation
[ ] optional / required 逻辑明确
[ ] 可序列化
[ ] 有 schema test
```

---

# Epic B：Ingestion

Owner：

Engineer C

---

## ISSUE B1：Raw Email → WorkItem

实现：

```text
core/ingestion/
```

输入：

```text
.eml
text
HTML
```

输出统一：

```python
WorkItem(
    id=...,
    tenant_id=...,
    sender=...,
    subject=...,
    body=...,
    received_at=...
)
```

---

## 技术负责人重点

不要让 Extraction 模块自己解析邮件。

否则以后：

```text
Gmail
Outlook
Web Form
WhatsApp
```

都会污染 AI 逻辑。

边界必须是：

```text
External Source
↓
Adapter
↓
WorkItem
```

---

# Epic C：Structured Extraction

Owner：

Engineer A

---

## ISSUE C1：Extraction Engine

路径：

```text
core/extraction/
```

职责：

```text
WorkItem
+
Schema
+
Domain Instructions
↓
StructuredRecord
```

---

接口类似：

```python
async def extract(
    work_item: WorkItem,
    schema: type[T],
    config: ExtractionConfig
) -> ExtractionResult[T]:
    ...
```

注意：

`core/extraction` 不应该知道：

```text
flow
head
pump
```

这些属于 Domain。

---

# 6. 技术负责人第一次 Architecture Review

Engineer A 提出：

> 我直接写一个 `extract_pump_email()` 会比较快。

技术负责人应该怎么回答？

不是：

> 不行，我们要优雅。

而是问：

> 如果第二个 Domain 是售后工单，这个函数还能复用什么？

于是改为：

```text
core:
Generic Extraction Engine

domain:
foreign_trade schema + instructions
```

---

这就是：

> 为已经非常明确的共享能力建立边界。

不是提前造万能平台。

---

# 7. Epic D：Normalization

Owner：

Engineer C

---

客户可能写：

```text
85 m3/h
85 m³/h
85 CMH
1416 L/min
```

系统统一：

```text
flow_m3h = 85
```

温度：

```text
42C
42°C
107.6F
```

统一：

```text
temperature_c = 42
```

---

# 为什么不用 LLM 做？

因为单位转换：

```text
规则明确
可测试
可确定
```

所以：

```text
Deterministic Code
```

---

这也是技术负责人要不断强化的边界：

> **能确定性解决的问题，不要因为 LLM 方便就交给模型。**

---

# Epic E：Validation

Owner：

Engineer A + Tech Lead

---

例如模型输出：

```text
flow_m3h = -85
```

显然错误。

或者：

```text
frequency_hz = 380
voltage_v = 50
```

很可能把：

```text
380V / 50Hz
```

解析反了。

所以 Extraction 后：

```text
LLM
↓
Schema Validation
↓
Domain Validation
```

---

例如：

```python
if flow_m3h is not None and flow_m3h <= 0:
    error(...)
```

以及：

```python
if frequency_hz not in {50, 60}:
    warning(...)
```

注意：

这不是说全世界频率一定只有 50/60。

而是：

> 根据当前业务数据建立可维护的 validation policy。

---

# 8. Epic F：Review UI

Owner：

Engineer B

---

第一版 UI 只需要三个区域。

左侧：

```text
原始邮件
```

右侧：

```text
结构化字段
```

底部：

```text
Approve
Edit
Reject
```

例如：

```text
Flow
[ 85 ]

Head
[ 38 ]

Medium
[ Water ]

Temperature
[ 42 ]

[Correct] [Needs Fix]
```

---

# 技术负责人必须阻止什么？

Engineer B：

> 要不要做漂亮 Dashboard、客户列表、Analytics？

回答：

> 暂时不做。

原因：

当前 Sprint 的业务问题不是：

> 用户缺 Dashboard。

而是：

> Extraction 是否可靠。

---

# 9. Feedback Data Design

用户修改：

```text
medium:
water
→
cooling water
```

不要只覆盖数据库。

必须保留：

```text
model_output
human_corrected_output
```

形成：

```python
FeedbackEvent(
    stage="extraction",
    field="medium",
    expected="cooling water",
    actual="water",
    feedback_type="corrected"
)
```

以后这就是：

```text
Golden Dataset
```

的重要来源。

---

# 10. Repo 第一次正式落地

现在代码库可以变成：

```text
fde-platform/

├── apps/
│   ├── api/
│   └── review-web/
│
├── core/
│   ├── models/
│   ├── ingestion/
│   ├── extraction/
│   ├── normalization/
│   ├── feedback/
│   └── observability/
│
├── domains/
│   └── foreign_trade/
│       ├── schemas/
│       ├── extraction/
│       ├── validation/
│       └── prompts/
│
├── tenants/
│   └── haichuan/
│       └── config.yaml
│
├── integrations/
│   └── llm/
│
├── evals/
│   ├── datasets/
│   ├── graders/
│   └── reports/
│
├── tests/
│
└── docs/
    └── adr/
```

---

# 11. 技术负责人要控制 Dependency Direction

推荐：

```text
apps
 ↓
domains
 ↓
core
```

以及：

```text
integrations
→ 实现 core 定义的接口
```

不能变成：

```text
core
→ foreign_trade
→ haichuan
```

否则 Core 不再 Core。

---

# 12. 第一个 Prompt 怎么管理？

不要：

```text
prompt = """
...
"""
```

散落在代码里。

第一版至少：

```text
domains/
  foreign_trade/
    prompts/
      inquiry_extraction_v1.md
```

同时每一次请求记录：

```text
prompt_version = inquiry_extraction_v1
```

---

# 13. AI Coding 怎么参与 Sprint？

这是技术负责人非常现实的一部分。

你自己几个月没大量写生产代码，也完全可以使用 AI Coding Agent。

适合交给 AI：

```text
生成 Pydantic schema 初稿
FastAPI boilerplate
测试样例
单位转换测试
数据库 migration
UI 表单基础代码
API client
代码解释
PR first-pass review
```

---

# 14. 但技术负责人不能把什么交出去？

例如：

```text
模块边界
Data Contract
字段语义
错误策略
Eval Gate
AI / Code 边界
Review 权限
```

AI 可以提出建议。

最终判断必须由技术负责人掌握。

---

# 15. 一个 AI Coding 实际流程

Engineer A：

> 我要实现 extraction engine。

不是直接说：

> AI 帮我写。

而应该先人工定义：

```text
Responsibility:
Structured extraction only.

Input:
WorkItem + schema + config.

Output:
ExtractionResult.

Must not:
query CRM
search products
send email
```

然后把这份 Contract 交给 Coding Agent。

这样 AI 生成代码的质量会明显更稳定。

---

# 16. 技术负责人的第一份 PR Template

每个关键 PR 要填写：

```text
Problem

Why this change exists

Scope

Architecture boundary

Input / Output

Eval impact

Risks

Rollback
```

---

# 17. PR #21：Extraction Engine

Engineer A 提交。

内容：

```text
Added LLM-based inquiry extraction.
```

技术负责人 Review。

---

## Review Question 1

> LLM 输出无法解析怎么办？

Engineer A：

> Retry。

你继续：

> Retry 几次？
> 第二次还是失败怎么办？
> 用户看到什么？
> 是否记录原始模型输出？

---

最终设计：

```text
Attempt 1
↓
Structured parse failure
↓
Retry once
↓
Still failure
↓
ExtractionFailed
↓
Human Review
```

同时记录：

```text
trace_id
model
prompt_version
raw_output
error
```

---

# 18. Review Question 2

Engineer A 在 Prompt 里写：

> Convert all units to metric units.

技术负责人：

> 为什么单位转换要让 LLM 做？

最后移出 Prompt。

改成：

```text
LLM extracts value + raw unit
↓
Normalization layer
```

这是很典型的 Tech Lead Review。

---

# 19. Review Question 3

Engineer A：

```python
if product == "pump":
    ...
```

写在 `core/extraction`。

技术负责人：

> 这个判断属于 Core 还是 Domain？

移动到：

```text
domains/foreign_trade
```

---

# 20. Day 4：第一次跑 20 条 Golden Dataset

结果：

| Field        | Accuracy |
| ------------ | -------: |
| Quantity     |     100% |
| Flow         |      95% |
| Head         |      95% |
| Temperature  |      90% |
| Voltage      |      85% |
| Frequency    |      85% |
| Medium       |      70% |
| Product Type |      95% |

团队第一反应：

> Medium 不行，Prompt 要调。

技术负责人：

> 先看错误案例。

---

# 21. Failure Review #1

失败案例：

### Case F-001

Email：

```text
Cooling water circulation pump.
```

模型输出：

```text
medium = water
```

Golden：

```text
medium = cooling water
```

---

### Case F-002

Email：

```text
Pump for seawater desalination plant.
```

模型：

```text
medium = seawater
```

正确。

---

### Case F-003

Email：

```text
For chemical washing line.
Fluid information attached.
```

附件没处理。

模型：

```text
medium = null
```

---

# 22. 技术负责人发现问题不能简单归为“Medium Extraction 差”

实际上两个完全不同 Failure：

```text
F-001:
Ontology / Normalization ambiguity

F-003:
Attachment ingestion missing
```

所以不能用一个 Prompt Fix 处理所有错误。

---

# 23. 第一次 Failure Taxonomy

团队建立：

```text
Extraction / Semantic
Extraction / Attachment Missing
Normalization
Schema
Input Quality
Model
```

---

# 24. 技术负责人判断下一步

F-001：

需要讨论：

> medium 字段到底需要多细？

如果业务真正需要的是：

```text
water
seawater
chemical
oil
other
```

那么 Golden Label：

```text
cooling water
```

可能过细。

这时候问题甚至可能不是模型。

而是：

# Schema Design

---

# 25. 和陈工确认

你：

> 陈工，对选型来说，普通 cooling water 和普通 water 是否需要区别？

陈工：

> 大部分情况不需要。
>
> 真正重要的是有没有腐蚀性、固体颗粒、温度这些。

于是团队发现：

原 Schema：

```text
medium: free text
```

设计可能不够好。

改成：

```text
medium_category
medium_description
```

例如：

```text
medium_category = water
medium_description = cooling water
```

---

# 26. 这是非常关键的一次技术负责人行为

模型效果不好。

最终解决方案不是：

```text
换模型
改 Prompt
```

而是：

```text
重新设计 Domain Model
```

这就是技术判断能力。

---

# 27. Day 5：工程师提出换模型

Engineer A：

> 新模型 Benchmark 更高，要不要直接升级？

技术负责人：

> 当前错误中有多少明确是模型能力造成？

统计：

```text
20 cases

semantic/model errors: 2
schema/ontology: 3
attachments: 2
normalization: 1
```

结论：

模型不是当前主要瓶颈。

决定：

```text
暂不换。
```

这是典型的：

# Technology Investment Judgment

---

# 28. Day 6：附件问题出现

真实询盘：

```text
Please find technical requirements attached.
```

附件：

```text
requirements.xlsx
```

里面才有：

```text
Flow
Head
Medium
```

当前系统完全没处理。

---

# 团队讨论

Engineer C：

> 那我们要做完整 PDF/Excel ingestion。

技术负责人：

> Sprint Goal 是什么？

目前：

```text
验证 text-based extraction pipeline。
```

于是决定：

Sprint 1：

```text
只支持附件存在检测
+
提示 Requires Attachment Processing
```

Sprint 2 再做附件。

这就是：

> Scope Control。

---

# 29. Day 7：Eval CI

现在开始把 Eval 放进 CI。

每次修改：

```text
prompt
schema
normalizer
model
```

自动运行：

```text
evals/datasets/inquiry_v0.jsonl
```

输出：

```text
critical_fields_accuracy
field_accuracy
parse_failure_rate
latency
cost
```

---

例如：

```text
PR #38

Before:
critical accuracy 91%

After:
critical accuracy 96%

Parse failures:
2% → 1%

P95 latency:
2.1s → 2.4s

Cost:
+4%
```

这样技术负责人 Review 才有证据。

---

# 30. Release Gate

Sprint 1 最终规定：

```text
Critical fields >= 95%

Parse failure < 2%

No known critical schema violation

100% failed extraction routed to review

Eval regression <= agreed threshold
```

注意：

这不是行业标准。

只是当前 Pilot Gate。

---

# 31. Day 8：第一次真实销售测试

Linda 打开 Review UI。

第一条：

```text
Flow: 85
Head: 38
Medium: Water
Temperature: 42
```

Linda 修改：

```text
Product type:
centrifugal pump
→ cooling water centrifugal pump
```

Engineer A：

> 模型还是不够准。

你：

> Linda，为什么要改这个？

Linda：

> 因为我习惯这样写，方便后面找产品。

---

# 32. 技术负责人发现新的问题

这不一定是 Extraction Accuracy。

可能是：

# User Mental Model vs System Schema

系统需要的：

```text
product_type = centrifugal_pump
application = cooling_water
```

用户习惯：

```text
product = cooling water centrifugal pump
```

因此不能为了迎合 UI，把 Schema 搞乱。

解决：

UI 可以组合显示：

```text
Cooling Water / Centrifugal Pump
```

底层仍然保持：

```text
product_type
application
```

---

# 33. 这是技术负责人另一个重要职责

区分：

```text
Display Model
```

和：

```text
Domain Model
```

不能因为用户喜欢一种展示方式，就直接破坏底层数据模型。

---

# 34. Day 9：Sprint Review 前指标

现在扩大到：

```text
100 条询盘
```

结果示例：

| Metric                  | Result |
| ----------------------- | -----: |
| Critical field accuracy |  96.8% |
| Parse success           |    99% |
| Quantity accuracy       |    99% |
| Flow accuracy           |    98% |
| Head accuracy           |    97% |
| Medium category         |    94% |
| Voltage/Frequency       |    96% |
| Human correction rate   |    18% |

---

# 35. 但是技术负责人不能只看 Accuracy

还要看：

```text
P95 latency: 2.8s

Cost / inquiry: $0.018

Review completion:
median 21 sec
```

以及：

> 哪些错误仍然属于 High Risk？

---

# 36. Remaining Critical Failures

发现：

3 个案例：

```text
380V / 60Hz
```

模型有一次把：

```text
frequency = 50
```

错误补全成了常见值。

这是严重问题。

因为客户没有写 50。

---

# 37. Root Cause

Prompt 中有一句：

> Fill common industrial defaults where reasonable.

这是 Engineer A 为了减少空字段加进去的。

---

# 38. 技术负责人判断

立刻删除。

原则升级：

> **Extraction 层只允许提取和明确推断，不允许业务默认值静默进入事实字段。**

如果需要默认值：

应该：

```text
extracted_value = null

suggested_default = 50

source = system_default
```

必须分开。

---

# 39. 这个事故产生一条重要 ADR

### ADR-005

**Never silently convert inferred/default values into extracted facts.**

原因：

```text
Fact
≠
Inference
≠
Default
```

未来数据模型可以支持：

```text
value
source
confidence
```

---

# 40. Sprint 1 Review

第 10 天团队 Demo。

不是只演示漂亮页面。

技术负责人按照下面顺序汇报。

---

## A. Goal

我们验证：

> 非结构化询盘是否能够可靠转换为标准 InquiryRecord。

---

## B. What We Built

```text
Ingestion
Extraction
Normalization
Validation
Review
Feedback
Eval CI
```

---

## C. What We Did Not Build

```text
Product Search
RAG
Pricing
Auto Reply
Attachments
```

---

## D. Results

```text
Critical Extraction Accuracy:
96.8%

Human Correction:
18%

P95:
2.8s
```

---

## E. Major Learnings

### Learning 1

`medium` 问题部分来自 Schema，而非模型。

### Learning 2

附件是重要输入来源，但不是 Sprint 1 Scope。

### Learning 3

事实与推断必须分开。

### Learning 4

用户展示模型与底层 Domain Model 不应该混为一体。

---

# 41. Sprint 1 技术资产

真正有价值的不是页面。

而是已经沉淀：

```text
WorkItem
InquiryRecord
Extraction Engine
Normalization Layer
Validation Layer
FeedbackEvent
Eval Dataset
Eval CI
Prompt Versioning
Observability
```

其中多个以后可以复用。

---

# 42. Tech Lead Sprint Retro

技术负责人自己做复盘。

---

## 做对了什么？

### 1.

没有一开始做整个 Agent。

### 2.

Data Contract 先行。

### 3.

Eval 从 Sprint 1 就存在。

### 4.

没有因为错误立即换模型。

### 5.

及时修正了 Domain Schema。

---

## 做错了什么？

例如：

### 1.

一开始忽略附件场景。

### 2.

Prompt 里加入“common defaults”风险过高。

### 3.

Golden Dataset 初始样本不够覆盖复杂邮件。

---

# 43. Sprint 2 Should We Build What?

现在不能凭兴趣决定。

看当前业务链路：

```text
Extraction
✅

下一瓶颈：
如何从 InquiryRecord 找到正确产品候选？
```

因此 Sprint 2 Candidate：

# Product Search + Domain Rules

流程：

```text
InquiryRecord
↓
Product Data
↓
Candidate Filtering
↓
Domain Rules
↓
Candidate Ranking
↓
Human Review
```

---

# 44. Sprint 2 前还需要完成的东西

不能直接编码。

必须先：

```text
清洗 Product Master

定义 ProductRecord

整理 10～20 条技术 Rules

建立 Product Matching Golden Dataset

定义 Top-K Eval

定义 Engineer Escalation Policy
```

---

# 45. Stage 4 Exit Criteria

```text
[x] Sprint Goal 明确

[x] Repo 边界稳定

[x] WorkItem

[x] InquiryRecord

[x] Generic Extraction Engine

[x] Normalization

[x] Validation

[x] Simple Human Review

[x] Feedback Event

[x] Golden Dataset

[x] Eval CI

[x] Prompt Versioning

[x] Observability

[x] 第一轮 Failure Review

[x] 至少一个 ADR 来自真实失败
```

---

# 46. 技术负责人这一阶段真正训练的能力

表面上团队完成的是：

> “邮件抽取。”

实际上技术负责人训练的是：

```text
Scope Control
Architecture Boundary
Data Contract
AI Boundary
PR Review
Failure Diagnosis
Eval-driven Development
Technical Investment Judgment
User / Domain Model Separation
AI Coding Governance
```

这就是为什么一个好的技术负责人即使没有亲自写掉大部分生产代码，也仍然可以非常深入地控制工程质量。

他的工作不是：

> 每一行都自己实现。

而是持续保证：

```text
正确的问题
↓
正确的边界
↓
正确的数据模型
↓
正确的实现方式
↓
正确的验证方法
```

---

# 47. 下一阶段：Stage 5

接下来正式进入：

## Product Search + Rule Engine + Recommendation

这是项目第一次开始碰真正困难的“专家知识”。

我们会遇到：

```text
产品 Excel 数据脏
性能范围重叠
Flow/Head 只是部分条件
海水材质规则
高温密封规则
工作点边缘问题
新人 vs 陈工的选择不同
```

然后技术负责人必须决定：

```text
哪些放数据库？
哪些是规则？
哪些需要算法 Ranking？
哪些交给 LLM？
哪些仍然必须让陈工 Review？
```

同时第一次建立：

```text
ProductRecord
Rule DSL
Candidate Search
Recommendation
Top-K Eval
Engineer Escalation
```

这一阶段会真正展示 **“AI + 传统工程 + 专家知识”如何组合成生产系统**。
