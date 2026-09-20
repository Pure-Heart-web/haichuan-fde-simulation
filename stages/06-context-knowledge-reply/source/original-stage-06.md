# 海川工业泵 AI 询盘项目

## Stage 6：Customer Context、Enterprise Knowledge、Evidence 与 Reply Generation

---

# 1. Stage 6 的目标

前两个 Sprint 已经具备：

```text
Email
↓
Inquiry Extraction
↓
Product Search
↓
Rules
↓
Recommendation
↓
Human Review
```

但真实销售处理询盘，还经常需要回答两类完全不同的问题。

第一类：

> “Same as previous order.”

> “Can you offer the same configuration as last year?”

这是：

# Customer Context

---

第二类：

> “Do you provide CE?”

> “What's the warranty?”

> “Can this product be used outdoors?”

这是：

# Enterprise Knowledge

两者必须分开设计。

---

# 2. Context 和 Knowledge 到底有什么区别？

## Context

回答：

> **这个具体客户、订单、设备之前发生过什么？**

例如：

```text
Customer:
ABC Marine

Previous Order:
2025-03-12

Product:
CP90-SS316

Quantity:
20

Voltage:
380V / 50Hz
```

来源：

```text
CRM
ERP
Order DB
Customer DB
```

---

## Knowledge

回答：

> **公司一般如何处理这种情况？**

例如：

```text
CE certification:
Available for selected models

Warranty:
12 months from shipment

Standard lead time:
4–6 weeks
```

来源：

```text
Policy
Manual
FAQ
Certification Docs
SOP
```

---

# 3. 为什么不能全部扔进 Vector DB？

因为：

```text
客户上一单买什么
```

不是模糊语义搜索问题。

它本质是：

```text
customer_id
+
order history
```

应该查询确定性数据源。

如果用向量搜索：

可能召回：

```text
ABC Marine
ABC Industrial
Marine Pump Project
```

甚至错误历史。

---

所以技术负责人明确一条原则：

> **对象历史优先查询业务系统；一般知识才走 Knowledge Retrieval。**

---

# 4. Sprint 3 Scope

这一轮做：

```text
Customer Identity
Customer Context
Order History
Knowledge Ingestion
Knowledge Retrieval
Evidence
Reply Generation
Human Review
```

暂不做：

```text
自动发送
自动价格承诺
自动折扣
自动修改 CRM
长期自主 Follow-up Agent
```

---

# 5. 第一件事：Customer Identity

用户邮件：

```text
From:
john@abcmarine.com

Hi Linda,

Same as previous order.
Need 20 pcs.
```

系统首先必须知道：

> John 属于谁？

---

# 6. Customer Entity Model

建议：

```python
class CustomerEntity(BaseModel):
    customer_id: str

    canonical_name: str

    aliases: list[str]

    domains: list[str]

    contacts: list[str]

    country: str | None
```

例如：

```text
customer_id:
CUST_00128

canonical_name:
ABC Marine BV

aliases:
ABC Marine
ABC-Marine

domains:
abcmarine.com
```

---

# 7. Entity Resolution 顺序

不要一上来让 LLM 猜。

优先：

```text
1. Exact email match
↓
2. Email domain
↓
3. Existing CRM contact
↓
4. Alias matching
↓
5. Fuzzy / LLM-assisted matching
↓
6. Human confirmation
```

原则：

> **越确定的方法越靠前。**

---

# 8. 为什么 Identity 是高风险基础能力？

如果：

```text
ABC Marine
```

错误匹配成：

```text
ABC Marine Equipment
```

那么：

```text
历史订单
价格
联系方式
客户等级
```

都会错。

这类错误会污染整个下游系统。

所以技术负责人应该把：

```text
Entity Resolution
```

作为独立 Eval 能力。

---

# 9. Customer Context Provider

Core 定义接口：

```python
class ContextProvider(Protocol):

    async def retrieve(
        entity_id: str,
        context_types: list[str]
    ) -> list[ContextItem]:
        ...
```

海川实现：

```text
OrderContextProvider
CRMContextProvider
```

---

# 10. ContextItem

不要直接把 ERP 返回的一大坨 JSON 给 LLM。

统一成：

```python
class ContextItem(BaseModel):
    type: str
    entity_id: str

    data: dict

    source: str
    source_id: str

    timestamp: datetime | None
```

例如：

```text
type:
previous_order

data:
{
  sku: "CP90-SS316",
  quantity: 20,
  voltage: "380V",
  frequency: "50Hz"
}
```

---

# 11. “same as previous order” Pipeline

完整流程变成：

```text
Email
↓
Customer Identity
↓
Customer Context
↓
Previous Orders
↓
Reference Resolution
↓
InquiryRecord Enrichment
↓
Recommendation
```

注意：

不是直接把历史订单覆盖当前询盘。

应该区分：

```text
explicit_current_value
historical_reference
suggested_value
```

---

# 12. 一个关键数据模型

例如：

```python
class ResolvedField(BaseModel):
    value: Any

    source_type: str
    # explicit
    # historical
    # inferred
    # default

    source_ref: str | None

    confidence: float | None
```

客户明确写：

```text
380V
```

则：

```text
source_type = explicit
```

如果来自上一单：

```text
source_type = historical
```

不能混在一起。

---

# 13. 为什么这么做？

因为：

> 历史值不是事实上的当前值。

客户说：

> same as previous order

才允许使用。

客户没说：

不能偷偷把上一单参数当成这一单参数。

这是典型：

# Data Provenance

---

# 14. 第二部分：Knowledge Ingestion

客户资料：

```text
Warranty Policy
Product Manuals
Certification Files
FAQ
Shipping Policy
Lead Time Guide
```

这里才能进入 Knowledge Retrieval。

---

# 15. 文档进入知识库前必须做治理

每份文档至少带：

```text
document_id
title
version
status
effective_date
owner
document_type
product_family
region
language
```

例如：

```text
Warranty Policy

version:
2026.2

status:
active

effective_date:
2026-03-01

owner:
Sales Operations
```

---

# 16. Document Status

至少：

```text
draft
active
superseded
archived
```

Knowledge Retrieval 默认：

```text
status = active
```

否则早晚会把旧政策找回来。

---

# 17. 第一次 Knowledge Accident

系统中同时存在：

```text
Warranty Policy 2024
24 months
```

和：

```text
Warranty Policy 2026
12 months
```

客户问：

> What is your warranty?

如果只做 embedding similarity：

两份都很相关。

模型可能回答：

> 24 months.

---

# 18. 技术负责人正确诊断

这不是：

```text
embedding model 不够强
```

而是：

```text
Knowledge Governance
+
Metadata Filtering
```

正确 Pipeline：

```text
Query
↓
Domain / Product / Region Filter
↓
status = active
↓
effective_date validation
↓
Retrieval
↓
Reranking
```

然后再给 LLM。

---

# 19. Knowledge Retrieval V1

可以拆成：

```text
Query Understanding
↓
Metadata Filter
↓
Candidate Retrieval
↓
Reranking
↓
Evidence Selection
```

不必一开始做复杂 GraphRAG。

---

# 20. Hybrid Retrieval

例如客户问：

> CE certificate available for CP90?

这里：

```text
CE
CP90
```

都有非常强的关键词意义。

因此：

```text
BM25 / keyword
+
semantic retrieval
```

往往比纯 embedding 更合理。

技术负责人关注的不是：

> 哪种技术更潮。

而是：

> 哪种 retrieval 对当前 corpus 更有效。

---

# 21. Knowledge Result 数据结构

```python
class KnowledgeEvidence(BaseModel):
    document_id: str
    chunk_id: str

    title: str
    text: str

    version: str
    effective_date: date | None

    source_type: str

    relevance_score: float
```

---

# 22. Evidence-first Generation

系统不能：

```text
Question
↓
LLM
↓
Answer
```

应该：

```text
Question
↓
Evidence
↓
Supported Answer
```

Reply Generator 的输入应该明确带：

```text
Inquiry
Context
Approved Recommendation
Knowledge Evidence
Missing Information
```

---

# 23. Reply Generator Contract

例如：

```python
class ReplyDraftInput(BaseModel):
    inquiry: InquiryRecord

    customer_context: list[ContextItem]

    recommendation: Recommendation | None

    knowledge_evidence: list[KnowledgeEvidence]

    missing_information: list[str]

    approved_facts: dict
```

输出：

```python
class ReplyDraft(BaseModel):
    subject: str
    body: str

    claims: list[GeneratedClaim]

    requires_review: bool
```

---

# 24. Generated Claim

这是生产系统非常值得做的一层。

例如：

邮件生成：

> Our standard warranty is 12 months.

系统内部同时记录：

```text
claim:
"Standard warranty is 12 months"

source:
Warranty Policy 2026.2

confidence:
high
```

这让你以后可以做：

```text
Claim Verification
```

---

# 25. 为什么 Reply Generation 不应该只是 Prompt？

如果 Prompt：

> 请根据以上资料写专业邮件。

模型很可能：

* 补充不存在信息
* 自动承诺交期
* 自动补价格
* 混淆历史订单

所以技术负责人应该定义：

# Allowed Claim Policy

---

# 26. Claim Categories

例如：

## Safe

```text
Thank you for your inquiry.
```

模型自由生成。

---

## Evidence Required

```text
Warranty
Certification
Lead time
Product capability
```

必须有 Evidence。

---

## Approval Required

```text
Final product model
Delivery commitment
Commercial terms
```

必须有人审核。

---

## Forbidden in V1

```text
Final price
Special discount
Contract commitment
```

没有授权不能生成。

---

# 27. Reply Policy Engine

可以简单定义：

```text
claim_type
→
required_source
→
approval_policy
```

例如：

```yaml
warranty:
  evidence_required: true
  reviewer: sales

final_product:
  evidence_required: true
  reviewer: engineer_or_sales

price:
  allowed: false
```

这比：

> “Prompt 里提醒不要乱说。”

可靠得多。

---

# 28. 第一次 Reply Demo

Inquiry：

```text
Need CP90 same as last order.
20 pcs.

Do you provide CE?
What is warranty?
```

系统得到：

Customer Context：

```text
Previous order:
CP90-SS316
20 pcs
380V / 50Hz
```

Knowledge：

```text
CE:
Available for CP90 EU configuration

Warranty:
12 months
```

---

# 29. AI 生成 Draft

例如：

```text
Dear John,

Thank you for your inquiry.

Based on your reference to the previous order, we found your last purchase of CP90-SS316, 20 units.

CE certification is available for the applicable CP90 configuration.

Our current standard warranty is 12 months from shipment.

Before preparing the formal quotation, please confirm whether the electrical configuration remains 380V / 50Hz.

Best regards,
Linda
```

注意：

它没有说：

> 本次一定也是 380V / 50Hz。

而是：

> 上一单是这样，请确认。

---

# 30. 这体现 Context 的正确使用方式

历史 Context 用于：

```text
减少重复沟通
提供建议
恢复上下文
```

而不是：

```text
把历史事实偷偷当当前事实
```

---

# 31. Linda 的 Review

Linda：

> 这个就很接近我自己写的了。

但她指出：

> 老客户我通常不会写 “we found your last purchase”，太机器人了。

这进入：

# Style Layer

---

# 32. 技术负责人不要把 Style 和 Facts 混在一起

Reply Generation 可以分：

```text
Content Plan
↓
Style Realization
```

第一层决定：

```text
必须说什么
不能说什么
```

第二层决定：

```text
怎么说
```

---

# 33. Content Plan

例如：

```text
1. Acknowledge inquiry

2. Reference prior order indirectly

3. Confirm candidate configuration

4. Answer CE

5. Answer warranty

6. Ask voltage/frequency confirmation

7. Do not quote price
```

然后 Style Generator：

```text
professional
concise
existing_customer
```

---

# 34. 这比直接 Prompt 写邮件更稳

因为：

```text
事实控制
```

和：

```text
语言风格
```

被分开。

以后客户 B 想要更正式语气：

不用改业务逻辑。

---

# 35. Tenant Style Config

例如：

```yaml
reply_style:
  tone: concise_professional
  greeting: first_name
  existing_customer_reference: subtle
  max_paragraphs: 5
```

这属于：

```text
Tenant
```

不是 Core。

---

# 36. 第一轮 Knowledge Eval

建立 50 个 FAQ / Knowledge Cases。

例如：

```text
Q:
Warranty?

Expected source:
Warranty Policy 2026.2

Expected answer:
12 months
```

---

# 37. Retrieval 指标

至少：

```text
Recall@5

Correct Source@1

Outdated Document Retrieval Rate

Unsupported Answer Rate
```

其中：

```text
Outdated Document Retrieval Rate
```

非常重要。

---

# 38. Reply Eval

不能只测：

> 邮件好不好看。

拆成：

### Fact Accuracy

是否事实正确。

### Evidence Coverage

重要 Claim 是否有证据。

### Unsupported Claim Rate

有没有凭空新增事实。

### Human Acceptance

销售是否接受。

### Edit Rate

销售改多少。

---

# 39. 第一轮结果

示例：

```text
Correct Source@1:
88%

Unsupported Claim Rate:
7%

Draft Accept / Minor Edit:
72%

Major Edit:
18%

Reject:
10%
```

---

# 40. Unsupported Claim Failure

例如系统写：

> Delivery can be arranged within 4 weeks.

但当前 Evidence 只有：

```text
Typical lead time:
4–6 weeks
```

而且库存未知。

这是典型：

```text
LLM 把 general knowledge
↓
变成了 specific commitment
```

---

# 41. 技术负责人怎么修？

错误方式：

> Prompt 加一句“谨慎一点”。

更好的：

把：

```text
lead_time
```

定义成：

```text
commercial_commitment
```

需要：

```text
specific operational source
or
human approval
```

如果只有 FAQ：

模型只能说：

> Typical lead time is 4–6 weeks, subject to final production confirmation.

---

# 42. Knowledge 和 Operational Fact 再次分离

例如：

```text
Typical lead time:
Knowledge
```

而：

```text
This order can ship in 4 weeks:
Operational Fact
```

来源可能是：

```text
ERP
Production Planning
```

不能混。

---

# 43. 这时 Context Layer 扩展

以后可以增加：

```text
Inventory Context
Production Context
Quote Context
```

但 Sprint 3 暂时不做。

技术债/路线图记录即可。

---

# 44. 第二个失败：知识源缺失

客户问：

> Do you have ATEX certification?

系统没找到资料。

模型仍然说：

> Yes, available upon request.

这是严重问题。

---

# 45. 技术负责人必须建立 Abstention

如果 Evidence 不足：

系统应该：

```text
I couldn't verify ATEX availability from the current approved documentation.
```

内部 Review UI：

```text
Knowledge gap
→ Human confirmation required
```

---

# 46. 生产 AI 很重要的能力不是“总能回答”

而是：

> **知道什么时候不应该回答。**

这叫：

```text
Abstention / Escalation
```

---

# 47. Knowledge Gap Feedback

如果销售最终确认：

> CP90 确实有 ATEX。

不要只改邮件。

应该创建：

```text
KnowledgeGapEvent
```

例如：

```text
query:
ATEX for CP90

result:
missing

human_answer:
available for EX configuration

owner:
technical documentation team
```

然后进入知识治理流程。

---

# 48. 这样 Feedback 不再只是“模型调优”

它甚至推动：

> 企业知识本身变完整。

这是 FDE 很有价值的一层。

---

# 49. Context Failure Case

用户：

```text
Same as last order.
```

系统找到：

```text
2 个历史订单
```

一个 CP90。

一个 CP100。

“last order” 应该是最近订单。

但当前 API 返回无排序列表。

模型选择错了。

---

# 50. 根因

不是模型。

而是：

```text
Context Provider contract 不明确
```

应该要求：

```text
previous_order
```

语义明确：

> most recent completed relevant order。

---

# 51. Data Contract Upgrade

```python
class PreviousOrderContext(BaseModel):
    order_id: str
    order_date: date
    status: str

    items: list[OrderItem]

    relevance_reason: str
```

并由 Provider：

```text
排序
过滤取消订单
确认 customer_id
```

而不是留给模型处理业务数据库语义。

---

# 52. 技术负责人这阶段重点 Review

每个 Retrieval PR 应该问：

### 1.

这是 Context 还是 Knowledge？

### 2.

真正的 Source of Truth 在哪？

### 3.

是否存在版本问题？

### 4.

是否允许模型在无证据时回答？

### 5.

返回结果有没有 Provenance？

### 6.

低置信度怎么办？

---

# 53. Repository 进一步演化

```text
core/
├── context/
│   ├── interfaces.py
│   ├── models.py
│   └── resolution.py
│
├── knowledge/
│   ├── models.py
│   ├── retrieval.py
│   └── evidence.py
│
├── generation/
│   ├── planning.py
│   ├── claims.py
│   └── generation.py
│
└── policy/
    └── claims.py
```

---

Domain：

```text
domains/foreign_trade/
├── context/
├── knowledge/
├── reply/
│   ├── content_policy.yaml
│   └── prompt/
```

---

Tenant：

```text
tenants/haichuan/
├── knowledge_sources.yaml
├── reply_style.yaml
└── context_mapping.yaml
```

---

# 54. 完整的销售 Copilot Workflow V1

现在系统已经发展成：

```text
Email
↓
Ingestion
↓
Extraction
↓
Normalization
↓
Customer Identity
↓
Customer Context
↓
Product Search
↓
Rules
↓
Recommendation
↓
Knowledge Retrieval
↓
Content Plan
↓
Reply Generation
↓
Human Review
↓
Feedback
```

已经非常接近真实生产系统。

---

# 55. 但技术负责人要特别注意 Orchestration

此时很容易有人提出：

> 现在模块好多，做 Agent 吧。

先判断：

流程是否仍然基本固定？

当前：

```text
Extract
→ Context
→ Product
→ Knowledge
→ Generate
```

大部分确定。

所以依然可以：

```text
Explicit Workflow
```

不需要完全自主 Agent。

---

# 56. 哪里开始可能适合 Agent？

例如客户邮件非常复杂：

```text
“Please quote the same pump we bought for Dubai,
but this one will be used in a chemical plant.
Also compare with another model and advise whether ATEX is necessary.”
```

这时候下一步可能动态变化：

```text
查历史订单
查产品
查化工规则
查认证
补问客户
```

这类复杂长尾任务未来可以引入：

```text
bounded agent
```

但必须围绕：

```text
approved tools
policy
budget
human review
```

运行。

---

# 57. Stage 6 Pilot Metrics

技术负责人现在需要看三层指标。

## Context

```text
Customer Resolution Accuracy

Previous Order Resolution Accuracy

Wrong Customer Context Rate
```

---

## Knowledge

```text
Correct Source@1

Recall@5

Outdated Source Rate

Knowledge Gap Rate
```

---

## Generation

```text
Unsupported Claim Rate

Fact Accuracy

Draft Acceptance Rate

Human Edit Rate
```

---

# 58. 示例 Pilot 结果

经过迭代：

```text
Customer Resolution:
98%

Previous Order Resolution:
96%

Correct Knowledge Source@1:
94%

Outdated Document Rate:
0.5%

Unsupported Claim Rate:
1.8%

Draft Accept / Minor Edit:
84%
```

这里只是模拟结果，不是行业标准。

---

# 59. 业务指标第一次开始形成完整闭环

标准复杂询盘：

Before：

```text
15–30 min
```

After：

```text
3–7 min review
```

部分重复 FAQ：

Before：

```text
销售查资料 / 问同事
```

After：

```text
直接获得有来源的 Draft
```

工程师升级也开始下降。

---

# 60. 但技术负责人真正关心的是：

> **是不是减少了正确的人工，而不是单纯减少人工？**

例如：

低风险 FAQ：

应该大幅减少人工搜索。

高风险技术选型：

仍然保留 Review。

这才是健康自动化。

---

# 61. Stage 6 重要 ADR

到这一阶段建议至少沉淀：

### ADR-006

Context 和 Knowledge 分离。

### ADR-007

Historical values 不得静默覆盖 current facts。

### ADR-008

高风险 Claim 必须有 Evidence / Approval。

### ADR-009

无 Evidence 时允许 Abstain。

### ADR-010

Content Planning 与 Style Generation 分离。

---

# 62. 技术负责人这一阶段真正训练的能力

表面是：

> “做 RAG 和邮件生成。”

实际上是：

```text
Entity Resolution
Context Modeling
Knowledge Governance
Retrieval Architecture
Data Provenance
Claim Policy
Hallucination Control
Abstention
Evidence-backed Generation
Human Trust
Workflow Orchestration
```

这也是为什么一个生产级 FDE 项目越来越不像：

> “一个 Prompt 工程项目”。

而越来越像：

> **企业数据 + 决策规则 + AI 能力组成的软件系统。**

---

# 63. Stage 6 Exit Criteria

```text
[x] Customer Entity Model

[x] Entity Resolution

[x] Context Provider

[x] Order History Retrieval

[x] Knowledge Document Governance

[x] Metadata Filtering

[x] Knowledge Retrieval

[x] Evidence Model

[x] Claim Policy

[x] Reply Content Plan

[x] Reply Generator

[x] Abstention

[x] Knowledge Gap Feedback

[x] Context Eval

[x] Retrieval Eval

[x] Generation Eval
```

---

# 64. 下一阶段：Stage 7

系统现在已经可以完成：

```text
询盘理解
+
客户历史恢复
+
产品候选
+
技术规则
+
企业知识问答
+
回复 Draft
```

下一步就进入真正的：

# Pilot Deployment + Human Workflow + Observability

核心问题会从：

> “技术能不能工作？”

变成：

> **“真实销售为什么用 / 为什么不用？”**

Stage 7 会模拟：

* 邮箱接入
* Sales Review Queue
* Engineer Escalation
* Role / Permission
* Trace / Logging
* Cost / Latency
* Production Failure
* Shadow Mode
* Adoption
* Pilot Metrics
* Incident Response

以及一个非常重要的问题：

> **系统技术指标很好，但 Linda 团队只用了三天就不愿用了，技术负责人该怎么办？**

这一步会进入真正的生产 FDE。
