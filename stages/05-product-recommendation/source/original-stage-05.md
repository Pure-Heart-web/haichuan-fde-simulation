# 海川工业泵 AI 询盘项目

## Stage 5：Product Search、Rule Engine、Recommendation 与专家知识工程

---

# 1. Stage 5 的核心目标

Sprint 1 已经解决：

```text
Email
↓
Structured Extraction
↓
InquiryRecord
```

现在要回答下一件真正有业务价值的问题：

> **给定一个结构化询盘，系统能不能找到合理的产品候选，并知道什么时候必须让工程师介入？**

注意目标不是：

> AI 自动选出最终型号。

而是：

```text
InquiryRecord
↓
Candidate Search
↓
Rule Validation
↓
Ranking
↓
Recommendation
↓
Engineer Escalation
↓
Human Review
```

---

# 2. 技术负责人首先明确 Scope

## Sprint 2 做

* ProductRecord
* 产品数据清洗
* Candidate Search
* Domain Rule Engine
* Candidate Ranking
* Recommendation
* Engineer Escalation
* Product Matching Eval

## Sprint 2 不做

* 自动最终报价
* 自动确认非标产品
* 自动 CAD / 性能曲线复杂计算
* 全产品线支持
* 自动对客户承诺型号
* Fine-tuning

第一版只支持：

> **标准离心泵产品线。**

---

# 3. 为什么不能直接用 RAG 选产品？

Engineer A 提出：

> 产品目录全部放向量库，直接问模型推荐型号不就行了？

技术负责人要求团队拿一个真实案例验证。

询盘：

```text
Flow: 85 m³/h
Head: 38m
Medium: seawater
Temperature: 42°C
```

RAG 搜出：

```text
CP80
CP90
CP100
```

因为三个型号文档都出现：

* centrifugal pump
* 80–100 m³/h
* 30–45m

模型可能挑 CP80。

但陈工说：

> CP80 不建议，工作点太靠边，而且普通版本材质不适合海水。

问题出现了。

RAG 解决的是：

> 找相关资料。

它不能天然保证：

> 满足所有工程约束。

因此技术负责人做出 ADR：

```text
Product recommendation
≠
Document retrieval
```

---

# 4. 重新建模：产品匹配其实有四层

```text
Layer 1
Hard Eligibility

↓

Layer 2
Domain Constraints

↓

Layer 3
Ranking

↓

Layer 4
Human Judgment
```

---

# 5. Layer 1：Hard Eligibility

回答：

> 这个产品在物理参数上能不能进入候选集合？

例如：

```text
flow_min <= requested_flow <= flow_max

head_min <= requested_head <= head_max

status == active
```

这一层应该：

```text
Database + deterministic code
```

不是 LLM。

---

# 6. Layer 2：Domain Constraints

回答：

> 参数虽然符合，但有没有行业规则让它不能用？

例如：

```text
medium = seawater
→ cast iron 不允许
```

或者：

```text
temperature >= 80°C
→ standard seal 不允许直接推荐
```

这一层：

```text
Rule Engine
```

---

# 7. Layer 3：Ranking

多个产品都满足时：

> 哪个更合适？

这里可能考虑：

```text
工作点距离最佳区间
标准配置优先
常用型号优先
库存情况
商业偏好
历史成功案例
```

这部分可以混合：

```text
Code
+
Rules
+
统计/排序算法
```

必要时 LLM 负责解释，但不直接决定硬排序。

---

# 8. Layer 4：Human Judgment

以下情况直接升级：

```text
特殊介质
高温
客户参数不完整
性能边界
多个候选难区分
非标准应用
历史失败案例
```

最终：

```text
Engineer Review
```

---

# 9. ProductRecord V1

技术负责人先要求团队定义数据合同。

```python
class ProductRecord(BaseModel):
    sku: str
    product_family: str

    flow_min_m3h: float
    flow_max_m3h: float

    head_min_m: float
    head_max_m: float

    material: str

    temperature_min_c: float | None
    temperature_max_c: float | None

    motor_power_kw: float | None

    supported_frequency_hz: list[int]

    status: str

    source_version: str
```

重点不是字段多。

重点是：

> 每个字段必须知道 Source of Truth。

---

# 10. 数据清洗第一次爆雷

Engineer C 导入产品表。

发现：

```text
Material:

SS316
316SS
SUS316
Stainless 316
Stainless Steel
CI
Cast Iron
```

如果直接入库：

规则：

```text
material != cast_iron
```

根本不可靠。

因此增加：

# Canonicalization Layer

---

# 11. Canonical Material Model

例如：

```text
raw:
316SS

canonical:
SS316
```

```text
raw:
SUS316

canonical:
SS316
```

```text
raw:
CI

canonical:
CAST_IRON
```

保留：

```text
raw_value
canonical_value
mapping_version
```

---

# 12. 技术负责人学到一个重要事实

生产 AI 系统里很多关键工作不是：

> 调模型。

而是：

```text
Ontology
Canonicalization
Entity Resolution
Data Quality
```

这些东西通常比 Prompt 更决定结果。

---

# 13. 第二个数据问题：参数范围重叠

产品库：

| SKU   | Flow   | Head  |
| ----- | ------ | ----- |
| CP80  | 70–90  | 30–40 |
| CP90  | 80–105 | 32–45 |
| CP100 | 90–120 | 35–50 |

输入：

```text
85 m³/h
38m
```

CP80 和 CP90 都符合。

如果只是 SQL：

```text
2 candidates
```

不能解决。

---

# 14. 陈工第一次知识访谈

你把这条案例给陈工：

> CP80 和 CP90 都满足，为什么你选 CP90？

陈工：

> CP80 工作点太靠右。

Engineer A：

> 什么叫太靠右？

陈工打开性能曲线。

> 最佳工作区域在中间附近。
>
> 长期在边缘运行效率、稳定性都差一些。

---

# 15. 技术负责人不要立刻写 Prompt

应该问：

> 这个判断能不能计算？

陈工：

> 可以，粗略可以。

于是产生一个更好的模型：

```text
Operating Point Score
```

例如非常简化地：

```text
requested_flow 距离推荐流量中心越近
score 越高
```

未来如果拿到真实性能曲线，可以升级。

---

# 16. Candidate Score V1

第一版可以简单：

```text
score =
flow_fit_score
+
head_fit_score
+
preferred_range_score
+
standard_configuration_score
```

注意：

这里的权重必须：

> 来自业务假设 + Eval 验证。

不能随便拍脑袋后当真理。

---

# 17. Rule Engine 设计开始

Engineer A：

> 规则直接写 Python if 就行。

短期当然能做。

例如：

```python
if inquiry.medium == "seawater":
    reject_cast_iron()
```

第一个规则没问题。

但是预计会出现：

```text
20
50
100
```

条规则。

技术负责人需要开始考虑：

> 哪些规则应该数据化？

---

# 18. Rule V1 数据模型

```python
class Rule(BaseModel):
    id: str
    domain: str
    version: str

    condition: dict

    action: dict

    severity: str

    owner: str

    status: str
```

例如：

```yaml
id: PUMP_MATERIAL_001

when:
  medium_category: seawater

then:
  exclude_materials:
    - CAST_IRON

severity: critical

owner: technical_department

status: active
```

---

# 19. 第二条规则

```yaml
id: HIGH_TEMP_001

when:
  temperature_c:
    gte: 80

then:
  require_engineer_review: true
  warning:
    "High temperature may require special seal/material configuration"

severity: high
```

---

# 20. 技术负责人要避免另一个坑

不要一开始造一个：

> “万能 DSL Rule Platform”。

第一版只支持项目真正需要的几种 Operator：

```text
equals
in
gte
lte
exists
```

以及动作：

```text
exclude_candidate
add_warning
require_review
add_requirement
```

够了。

原则：

> Rule Engine 也应该从实际规则长出来。

---

# 21. Rule Registry

所有规则必须有：

```text
id
description
owner
version
effective_date
source
severity
status
```

特别重要的是：

```text
owner
```

因为规则不是工程师发明的。

业务 Owner 应该是：

```text
Technical Department
```

---

# 22. Rule Governance

新规则流程：

```text
Failure / Expert Interview
↓
Candidate Rule
↓
Technical Verification
↓
Rule Test
↓
Activate
```

不能：

```text
微信群里看到一句话
↓
直接上线
```

---

# 23. 第一批 Rule 提取

团队跟陈工开 1 小时访谈。

整理：

### R001

海水：

```text
排除 CAST_IRON
```

### R002

温度 >= 80°C：

```text
Engineer Review
```

### R003

介质未知：

```text
不得给最终产品推荐
要求补充介质
```

### R004

候选工作点靠性能边缘：

```text
增加 warning
可能要求工程审核
```

### R005

非标准电压：

```text
Engineer / electrical review
```

---

# 24. 现在完整 Candidate Pipeline

```text
InquiryRecord
↓
Critical Field Check
↓
Hard Product Filter
↓
Rule Evaluation
↓
Remove Invalid Candidates
↓
Ranking
↓
Risk Evaluation
↓
Recommendation
```

---

# 25. 伪代码结构

```python
async def recommend_products(inquiry):

    eligibility = validate_required_fields(inquiry)

    if not eligibility.can_search:
        return recommendation_for_clarification(...)

    candidates = product_repository.search(
        flow=inquiry.flow_m3h,
        head=inquiry.head_m,
    )

    evaluated = rule_engine.evaluate(
        inquiry=inquiry,
        candidates=candidates,
    )

    ranked = rank_candidates(
        inquiry,
        evaluated.valid_candidates,
    )

    return build_recommendation(
        inquiry,
        ranked,
        evaluated,
    )
```

注意这里：

> 没有 Agent 必须出现。

---

# 26. Recommendation 数据结构升级

```python
class Recommendation(BaseModel):

    inquiry_id: str

    candidates: list[CandidateResult]

    preferred_candidate_id: str | None

    missing_information: list[str]

    warnings: list[str]

    triggered_rules: list[str]

    risk_level: str

    requires_engineer_review: bool

    evidence: list[EvidenceRef]
```

---

# 27. Evidence 特别重要

例如：

```text
推荐 CP90
```

不能只告诉销售：

> AI 推荐 CP90。

应该显示：

```text
为什么：

✓ Flow 85 在推荐范围内
✓ Head 38 在范围内
✓ SS316 满足海水材质规则
✓ 工作点优于 CP80

Triggered Rules:
PUMP_MATERIAL_001

Source:
Product Master v2026.09
```

这会直接影响：

# User Trust

---

# 28. 技术负责人必须建立“解释不是模型自由发挥”的原则

推荐依据必须先由系统形成结构化证据：

```text
matched_conditions
rules
scores
sources
```

LLM 可以把它写成人话。

但不能自己创造依据。

---

# 29. Engineer Escalation Policy

现在一个非常重要的问题：

> 什么情况下必须找陈工？

先不让 AI 自己“感觉”。

定义第一版 Policy。

---

## Auto Sales Review

例如：

```text
所有 critical fields 完整
+
存在明确候选
+
没有 high severity rule
+
Top1 score 显著高于 Top2
```

进入：

```text
Sales Review
```

---

## Engineer Review

以下任意成立：

```text
特殊介质
高温
critical missing field
多个候选接近
critical rule
非标准配置
低置信度
```

进入：

```text
Engineer Review
```

---

# 30. 技术负责人在这里真正控制的是“自动化边界”

系统目标不是：

> 最大化自动化率。

而是：

> 在错误成本允许范围内最大化有效自动化。

这个差别非常重要。

---

# 31. Product Matching Golden Dataset

现在不能只看 Extraction Eval。

需要建立：

```text
100 条历史询盘
```

由陈工人工标：

```text
acceptable candidates
preferred candidate
required rules
engineer review required?
```

---

# 32. 一个关键 Eval 设计问题

有时候不是只有一个正确 SKU。

例如：

```text
CP90
CP100
```

都合理。

所以不能只用：

```text
Exact Match Accuracy
```

而应该用：

### Candidate Recall

正确候选是否进入 Top-K？

### Top-K Accuracy

人工认可产品是否出现在 Top 3？

### Unsafe Recommendation Rate

有没有出现明确不允许产品？

### Escalation Recall

该找工程师的案例有没有升级？

---

# 33. 建议关键指标

```text
Candidate Recall@5
Top-3 Acceptance
Critical Rule Violation Rate
Engineer Escalation Recall
False Escalation Rate
```

这里：

```text
Critical Rule Violation Rate
```

应当接近：

```text
0
```

---

# 34. 第一次跑 Eval

100 条历史案例：

```text
Candidate Recall@5:
94%

Top-3 accepted:
82%

Critical Rule Violation:
0%

Engineer Escalation Recall:
91%

False Escalation:
42%
```

看起来不错？

不完全。

---

# 35. 技术负责人注意到 False Escalation 很高

意思是：

系统很安全。

但：

> 什么都丢给陈工。

那么项目没有业务价值。

因为客户最初的痛点之一就是：

```text
工程师被打扰太多
```

所以安全不是唯一指标。

---

# 36. 这形成一个经典优化问题

```text
减少工程师升级
```

和：

```text
避免错误自动处理
```

之间存在 Trade-off。

技术负责人必须明确：

> 这是业务风险取舍，不只是模型调参。

---

# 37. 第二次专家 Review

抽 20 个 False Escalation。

发现：

12 个都是：

```text
标准淡水应用
标准温度
标准电压
候选明确
```

为什么升级？

Rule：

```text
if application is null:
    engineer_review = true
```

太保守。

陈工：

> 普通清水项目 application 不写也没关系。

于是 Rule 改成：

```text
如果 medium = water
且其他关键参数完整
application 缺失不强制升级
```

---

# 38. 第二次 Eval

```text
Engineer Escalation Recall:
91% → 94%

False Escalation:
42% → 24%
```

非常好的改进。

注意：

> 没换模型。

---

# 39. 第一次 Recommendation UI

Engineer B 做页面：

```text
Inquiry Summary

Flow: 85
Head: 38
Medium: Seawater
Temperature: 42
```

下面：

```text
Recommended

CP90
Score: 0.89

Why:
- Flow compatible
- Head compatible
- SS316 suitable for seawater
- Preferred operating range

Warnings:
None
```

其他候选：

```text
CP80
Rejected

Reason:
Operating point near edge
```

```text
CP100
Score: 0.68
```

底部：

```text
[Approve]
[Choose another]
[Escalate to Engineer]
```

---

# 40. Linda 第一次测试

Linda：

> 这个比之前好很多，因为我知道它为什么推荐。

这句话对技术负责人很重要。

说明：

> Explainability 不是为了漂亮，而是直接影响 Adoption。

---

# 41. 但 Linda 提出新需求

> 能不能直接告诉我“推荐哪个”，别显示这么多技术细节？

技术负责人不能简单：

> 好。

因为对 Linda 这种资深销售可以。

新人呢？

工程师呢？

所以做：

# Progressive Disclosure

默认：

```text
推荐：CP90
```

点击：

```text
查看原因
```

再展示规则与证据。

---

# 42. User Experience 和 Risk Model 开始结合

不同角色显示不同信息：

### Senior Sales

简洁建议。

### Junior Sales

更多解释。

### Engineer

完整规则、数据、来源。

这开始形成：

```text
Role-aware Review UI
```

---

# 43. 一个新的错误出现

询盘：

```text
Flow: 90
Head: 40
Medium: seawater
```

系统：

```text
CP90
```

陈工：

> 不行，CP90 在这个点太边缘了，我会选 CP100。

团队查看 ranking。

发现：

```text
flow_fit
head_fit
```

只是线性计算。

不够。

---

# 44. 技术负责人怎么判断？

有三个选项：

### A

改 Prompt。

没意义。

### B

继续调 ranking 权重。

可能。

### C

获取更真实性能曲线。

更根本，但投入更高。

技术负责人查看错误频率。

100 条里：

```text
6 条来自性能边缘判断。
```

当前 Pilot：

先选择：

> 改进简单 Operating Point Score。

同时建立：

```text
Technical Debt:
真实性能曲线建模
```

而不是立即做复杂曲线数字化。

---

# 45. 这是很典型的工程判断

不是：

> 最好的技术方案是什么？

而是：

> 当前阶段值得做到哪一步？

---

# 46. Technical Investment Record

### Current Problem

6% 案例 ranking 不理想。

### Short-term Fix

更合理的 preferred operating range。

### Long-term

性能曲线数字化。

### Trigger

如果：

```text
Top-3 不足目标
或
产品自动推荐成为核心收入能力
```

再投资。

---

# 47. AI 在 Recommendation 层应该干什么？

现在技术负责人正式明确：

LLM 可以负责：

### 1. 解释

把：

```text
rule R001
score 0.89
```

转换成用户可读语言。

### 2. 弱语义判断

例如：

客户描述：

> used in marine cooling loop

推断：

```text
application = marine cooling
```

### 3. Follow-up question generation

根据：

```text
missing_fields
```

生成自然语言追问。

---

# 48. LLM 不负责

```text
最终硬约束
价格计算
库存事实
产品存在性
critical safety rule
最终 SKU 承诺
```

---

# 49. 新的代码库结构

```text
core/
├── rules/
│   ├── engine.py
│   ├── models.py
│   └── operators.py
│
├── recommendation/
│   ├── models.py
│   └── builder.py
│
└── ranking/
    └── interfaces.py
```

Domain：

```text
domains/
└── foreign_trade/
    ├── products/
    │   ├── schema.py
    │   ├── search.py
    │   └── ranking.py
    │
    └── rules/
        ├── material.yaml
        ├── temperature.yaml
        └── escalation.yaml
```

Tenant：

```text
tenants/
└── haichuan/
    ├── product_mappings.yaml
    └── product_preferences.yaml
```

---

# 50. 技术负责人检查边界

例如：

```text
CP90 preferred over CP80
```

如果原因是：

> 泵行业技术特性。

属于：

```text
Domain
```

如果原因是：

> 海川现在库存很多 CP90，希望优先卖。

属于：

```text
Tenant / Commercial Policy
```

这两个必须分开。

否则技术规则会被商业策略污染。

---

# 51. Sprint 2 Production Review

最终指标：

```text
Candidate Recall@5:
97%

Top-3 Acceptance:
91%

Critical Rule Violation:
0%

Engineer Escalation Recall:
96%

False Escalation:
21%

Median Review Time:
42 sec
```

示例数字仅用于这个模拟 Pilot。

---

# 52. 业务指标开始出现变化

Linda 团队测试：

复杂标准询盘：

之前：

```text
约 15–30 分钟
```

现在：

```text
AI 预处理 + Review：
约 4–8 分钟
```

特别是新人效果明显。

---

# 53. 但技术负责人不能现在宣布“成功”

还需要回答：

> 工程师被打扰真的少了吗？

因此下一阶段 Pilot 开始记录：

```text
engineer_escalation_count
reason
resolution
```

只有真实使用以后才能知道。

---

# 54. Stage 5 主要技术决策总结

到现在已经形成：

### Decision 1

产品匹配不使用纯 RAG。

### Decision 2

产品事实进入结构化 Product DB。

### Decision 3

硬约束进入 Rule Engine。

### Decision 4

Ranking 与 Eligibility 分离。

### Decision 5

Recommendation 必须带 Evidence。

### Decision 6

最终产品选择仍 Human-in-the-loop。

### Decision 7

Engineer Escalation 本身也是需要优化的产品能力。

### Decision 8

技术规则与商业偏好分离。

---

# 55. 技术负责人这一阶段真正训练的能力

表面项目是在：

> “做产品推荐。”

实际上负责人练的是：

```text
Knowledge Engineering
Data Modeling
Rule Governance
Deterministic vs Probabilistic Design
Ranking
Risk Policy
Human Escalation
Evaluation Design
Technical Debt Judgment
Explainability
Domain / Tenant Separation
```

---

# 56. Stage 5 Exit Criteria

```text
[x] ProductRecord

[x] Product Data Canonicalization

[x] Candidate Search

[x] Rule Engine V1

[x] Rule Registry

[x] Ranking V1

[x] Recommendation

[x] Evidence Model

[x] Engineer Escalation Policy

[x] Matching Golden Dataset

[x] Product Matching Eval

[x] Review UI

[x] Failure Analysis

[x] Technical Debt Register
```

---

# 57. 下一阶段：Stage 6

接下来系统已经可以：

```text
理解询盘
+
找到产品
+
应用规则
+
给出建议
```

下一步进入：

# Context Retrieval + Knowledge Retrieval + Reply Generation

这会解决两个非常真实的问题：

```text
“same as previous order”
```

以及：

```text
“Do you provide CE?”
“What's your warranty?”
“What's your lead time?”
```

Stage 6 会重点训练技术负责人如何正确区分：

```text
Customer Context
vs
Enterprise Knowledge
```

以及为什么：

```text
CRM / ERP
≠
Vector DB
```

同时会加入：

* Customer Entity Resolution
* Order History
* Knowledge Document Governance
* Hybrid Retrieval
* Citation / Evidence
* Reply Generator
* Knowledge Hallucination Eval

这一阶段会把系统从“选型工具”推进成真正能辅助销售完成一整个询盘回复的 Copilot。
