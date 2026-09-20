# 海川工业泵 AI 询盘项目

## Stage 2：Discovery 实战、Problem Brief、As-Is Workflow 与 Decision Map

---

# 1. Discovery Meeting 正式开始

参与人：

* 王总：老板
* Linda：外贸销售主管
* 陈工：技术经理
* 你：创业团队负责人 / Lead FDE
* Engineer A：旁听并记录技术信息

你的目标不是卖方案。

本轮只做四件事：

```text
观察真实流程
↓
找到决策节点
↓
找到证据和未知
↓
形成第一版问题模型
```

---

# 2. 第一轮：先看真实询盘

你：

> Linda，我们先不聊 AI 怎么做。
>
> 能不能找昨天一封比较典型的询盘，从你收到邮件开始，完整操作一遍？

Linda：

> 可以。

她打开一封邮件。

---

## Inquiry #017

```text
Subject:
Pump Inquiry for Cooling Water Project

Dear Linda,

We need centrifugal pumps for our cooling water system.

Capacity: 85 m3/h
Head: 38m
Quantity: 6 sets

Water temperature around 42°C.

Please quote CIF Jebel Ali.

Motor: 380V / 50Hz.

Regards,
Ahmed
Al Noor Engineering
UAE
```

---

# 3. Linda 开始操作

Linda：

> 第一眼我先看客户是不是靠谱。

你：

> “靠谱”具体怎么判断？

Linda：

> 公司邮箱、公司名字、国家、有没有项目、参数写得全不全。

王总插话：

> 其实国家也很重要，有些地区垃圾询盘特别多。

Linda：

> 但不能完全这么看，有些真的客户也用 Gmail。

---

# 4. 技术负责人此时怎么记录？

不要直接记录：

> 判断客户价值 = 国家 + 邮箱。

应该分四类。

---

## Fact

Linda 确实会在正式处理前进行一次客户有效性判断。

---

## Claim

王总认为：

> 某些国家垃圾询盘比例更高。

目前没有数据验证。

---

## Hypothesis

Lead qualification 可能是一个独立 Decision Point。

---

## Unknown

到底有哪些字段最能预测有效询盘？

是否有历史成交数据验证？

---

这是非常重要的技术负责人习惯：

> 客户说的话不是自动变成业务规则。

---

# 5. 继续 Workflow

Linda：

> 这个客户看起来正常。
>
> 接下来我会把参数记录下来。

她打开 Excel：

```text
Customer Inquiry Tracking.xlsx
```

字段：

```text
Company
Country
Contact
Product
Flow
Head
Qty
Voltage
Frequency
Medium
Temperature
Destination
Status
```

你：

> 这些字段每封都填吗？

Linda：

> 尽量填。
>
> 但客户经常不给全。

你：

> 不全怎么办？

Linda：

> 有些缺了没关系，有些必须问。

---

# 6. 出现第二个 Decision Point

你：

> 哪些属于“必须问”？

Linda：

> 要看产品。

你：

> 比如这个询盘呢？

Linda：

> Flow、Head 都有。
>
> 水温 42 度也没问题。
>
> 电压也有。
>
> 但是具体什么水没写得特别清楚。

陈工：

> 还得知道是不是普通淡水，有没有腐蚀性。

Linda：

> 对，这个我可能会先问一句。

---

此时问题已经不是：

```text
“提取字段”
```

而是：

```text
“判断哪些字段在当前场景是必需的”
```

这是两个完全不同的系统能力。

---

# 7. 技术负责人应该捕捉什么？

这里至少出现三个层次：

### Extraction

客户写了什么？

例如：

```text
flow = 85
head = 38
temperature = 42
```

### Completeness

当前任务还缺什么？

### Domain Requirement

为什么这个字段在这个场景下必须知道？

例如：

```text
medium properties
```

可能决定材质和型号。

因此以后系统不能只是：

```text
Email → JSON
```

还需要：

```text
JSON
↓
Domain Rules
↓
Missing Critical Information
```

---

# 8. Linda 开始查产品

她打开：

```text
Pump Selection.xlsx
```

输入：

```text
Flow: 85
Head: 38
```

出现三个型号：

```text
CP80
CP90
CP100
```

Linda：

> CP80 理论上也可以，但比较靠性能曲线边缘。
>
> 我一般更倾向 CP90。

你：

> 这个“更倾向”写在哪里？

Linda：

> 没写。
>
> 做久了就知道。

---

这里出现了第一个重要：

# Tacit Knowledge

```text
“不要只满足参数边界，还要考虑工作点是否处于合理区域。”
```

产品数据库解决不了这个问题。

普通 RAG 也未必能可靠解决。

它可能需要：

* 技术规则
* 性能曲线数据
* 专家经验结构化

---

# 9. 你继续追问

你：

> 如果一个新人看到 CP80、CP90、CP100 三个型号，他会怎么选？

Linda：

> 问陈工。

陈工：

> 基本会问我。

你：

> 你怎么决定？

陈工：

> 先看工作点。
>
> 再看介质。
>
> 温度。
>
> 材质。
>
> 电机要求。
>
> 有时候还要看客户行业。

你：

> “行业”为什么影响？

陈工：

> 食品、化工、普通工业完全不一样。
>
> 参数一样，材料和密封要求也可能不同。

---

# 10. Problem 深了一层

原先我们以为：

```text
产品选择
=
Flow + Head
```

现在发现：

```text
产品选择
=
Hydraulic Parameters
+
Medium
+
Temperature
+
Application
+
Material
+
Motor
+
Industry Constraints
+
Expert Judgment
```

所以技术负责人应该马上调整自己的技术假设。

---

# 11. 错误示范

如果前一天已经写好了：

```text
SELECT *
FROM products
WHERE flow_min <= flow
AND flow_max >= flow
AND head_min <= head
AND head_max >= head
```

现在不能硬说：

> SQL 产品匹配已经解决 80%。

证据已经推翻了这个假设。

成熟技术负责人必须允许：

> **业务事实改变架构。**

---

# 12. 继续：工程师什么时候介入？

你：

> Linda，最近一天大概有多少次需要问陈工？

Linda：

> 我自己少一点。
>
> 新人很多。

王总：

> 一天几十次吧。

陈工：

> 没那么夸张。

Linda 笑：

> 你可能已经习惯了。

---

现在出现组织访谈中很常见的问题：

> 三个人给出的数字不一致。

---

# 13. 技术负责人怎么处理？

错误：

```text
老板说几十次
→ 写进 Problem Brief
```

也不能：

```text
陈工说没那么多
→ 判断老板夸张
```

正确记录：

### Claim A

王总：

> 每日几十次。

### Claim B

陈工：

> 没有几十次。

### Unknown

工程师咨询实际发生频率。

### Verification Plan

下一周：

* 统计微信群 / 工单 / 邮件
* 让工程师简单打标签
* 抽样记录 3 个工作日

---

# 14. 这是 FDE 非常重要的能力

> 不解决“谁说得对”，而是设计验证方法。

---

# 15. 继续问时间

你：

> Linda，这封询盘如果今天没有我在旁边，你大概要多久处理？

Linda：

> 15 分钟左右吧。

你：

> 为什么？

Linda：

> 这个比较标准。

你：

> 如果新人？

Linda：

> 可能 30 分钟，也可能先放着。

---

这里出现一个新的业务问题：

```text
并不仅仅是单次处理时间。
```

还有：

```text
Queue Delay
```

复杂询盘可能因为销售不会处理而被延后。

这会直接影响：

```text
First Response Time
```

---

# 16. 技术负责人应该追问

你：

> “先放着”通常多久？

Linda：

> 可能等陈工有空。
>
> 有时候当天，有时候第二天。

这意味着：

客户体验上的主要问题可能不是：

```text
10 分钟 vs 5 分钟
```

而是：

```text
复杂询盘
2 小时
vs
24 小时
```

这比原来想象的 ROI 更大。

---

# 17. 王总提出一个新诉求

王总：

> 所以我才说最好 AI 直接回复。
>
> 这样客户一分钟就能收到。

---

技术负责人不能立刻同意。

你：

> 我理解您希望缩短响应时间。
>
> 但我们需要区分：
>
> “一分钟告诉客户已经收到”
>
> 和
>
> “一分钟给出正确选型和报价”
>
> 这两件事情风险完全不同。

王总：

> 这个倒是。

---

# 18. 这里得到一个重要 Product Insight

响应可以分层：

### Level 1

自动确认：

```text
已收到您的询盘。
```

低风险。

### Level 2

自动补问：

```text
还缺介质类型。
```

中低风险。

### Level 3

产品建议：

需要审核。

### Level 4

正式报价：

高风险。

这就是：

# Automation Ladder

而不是：

```text
自动 / 不自动
```

二选一。

---

# 19. 开始问错误成本

你：

> 陈工，过去有没有因为选型错误造成损失？

陈工：

> 有过。

> 去年一个项目客户给的工况信息不完整，销售报得太快。
>
> 最后泵材质不合适。

你：

> 后果是什么？

陈工：

> 换货。
>
> 运费我们承担了一部分。

王总：

> 那单亏了不少。

你：

> 大概数量级？

王总：

> 几万块。

---

# 20. 这条信息改变什么？

说明：

```text
Recommendation Error Cost
=
High
```

因此 V1 不应该：

```text
AI → Final Product Decision
```

应该：

```text
AI
↓
Candidate + Evidence + Warning
↓
Human Review
```

---

# 21. 继续问数据来源

你：

> 陈工，如果系统要帮 Linda 减少找你的次数，我们要知道你现在到底参考什么东西。

陈工：

> 产品目录。
>
> 性能曲线。
>
> Excel。
>
> 有些特殊经验就是自己知道。

Linda：

> 历史报价也会看。
>
> 特别是老客户。

王总：

> ERP 里面也有订单。

你：

> 哪一个是真正的 Source of Truth？

三个人沉默几秒。

陈工：

> 产品参数还是技术部最新 Excel 为准。

Linda：

> 但我们平时经常用 PDF。

陈工：

> PDF 有些旧。

---

这就是典型企业数据现实：

```text
“公司有资料”
≠
“公司有可靠知识库”
```

---

# 22. 技术负责人马上记录一个新风险

## Knowledge Governance Risk

存在：

```text
旧 PDF
新 Excel
历史报价
工程师经验
```

之间的版本冲突。

因此未来做 RAG 之前，先要解决：

```text
Source of Truth
Version
Effective Date
Owner
```

否则 RAG 只会：

> 更快地把错误资料找出来。

---

# 23. Discovery Meeting 第一阶段结束

现在你已经有足够信息做第一版建模。

不是做最终系统。

而是：

# Problem Brief V1

---

# 24. Problem Brief V1

## Customer

宁波海川流体设备有限公司

---

## Primary Users

主要：

* 外贸销售

次要：

* 技术工程师

管理利益相关者：

* 王总

---

## Observed Problem

销售处理复杂技术询盘时，需要依赖产品资料、历史客户信息以及技术工程师经验。

其中：

* 新销售依赖尤其明显；
* 部分复杂询盘会因为等待工程师而延迟到当天晚些时候甚至第二天；
* 技术工程师承担大量重复性咨询；
* 产品知识分散于 PDF、Excel、历史订单和人员经验中。

---

## Evidence

目前已经观察到：

1. 一条标准询盘由熟练销售处理约 15 分钟。
2. 新销售处理同类询盘可能达到约 30 分钟。
3. 复杂询盘可能因等待技术确认延后处理。
4. 产品选择并非只依赖 Flow / Head。
5. 历史上存在由于工况信息不足和选型问题造成换货损失的案例。
6. 产品资料存在新旧版本并存问题。

注意：

工程师每日咨询次数目前仍未验证。

---

# 25. Root Cause Hypotheses V1

当前主要假设：

### H1

技术知识没有以销售可直接调用的形式存在。

### H2

产品资料虽然存在，但缺少统一 Source of Truth。

### H3

新销售缺少经验，因此需要频繁升级给工程师。

### H4

复杂询盘处理延迟主要发生在技术判断，而不是邮件撰写本身。

### H5

客户历史 Context 对部分询盘非常重要。

---

# 26. Business Impact

当前可能造成：

```text
销售处理产能下降

首次回复延迟

工程师频繁被打断

新人培训周期较长

错误选型商业风险
```

---

# 27. Success Metrics V1

当前先定义候选指标：

### Business

```text
复杂询盘首次处理时间
```

### Workflow

```text
需要工程师升级的询盘比例
```

### Product

```text
销售使用 AI 建议后的任务完成时间
```

### AI

```text
Critical Field Extraction Accuracy

Missing Critical Information Recall

Top-K Product Candidate Accuracy

Rule Violation Rate
```

---

# 28. Non-goals V1

第一阶段暂不：

```text
自动最终选型

自动正式报价

无审核自动发送技术结论

替代工程师

支持所有产品线
```

---

# 29. As-Is Workflow V1

现在把真实流程画出来。

```text
Customer Inquiry
       ↓
Sales opens email
       ↓
Lead validity judgment
       ↓
Requirement extraction
       ↓
Missing information judgment
       ↓
Customer history lookup（部分场景）
       ↓
Product candidate search
       ↓
Technical / application judgment
       ↓
┌─────────────────────┐
│ Need Engineer?      │
└──────────┬──────────┘
      Yes  │   No
           │
     Engineer review
           │
           ↓
      Product decision
           ↓
       Price lookup
           ↓
      Quote calculation
           ↓
       Reply drafting
           ↓
          Send
```

---

# 30. Bottleneck Map

### B1：Requirement Normalization

客户写法不统一。

例如：

```text
85 cubic meters/hour
85 m3/h
85CMH
```

---

### B2：Missing Information

销售需要知道：

> 现在缺的信息是否影响选型？

---

### B3：Product Candidate Search

不是简单关键词搜索。

需要参数和工况。

---

### B4：Technical Judgment

大量经验集中在工程师。

---

### B5：Knowledge Fragmentation

```text
PDF
Excel
ERP
历史订单
专家经验
```

之间不统一。

---

### B6：Queue Delay

复杂询盘因为需要工程确认而等待。

---

# 31. Decision Map V1

现在单独把最关键的判断拆出来。

---

## Decision 1：是否为有效询盘？

### Owner

Sales

### Inputs

* 公司信息
* 邮箱
* 国家
* 产品描述
* 项目描述
* 数量

### 状态

部分经验化。

### Error Cost

中。

### Automation Potential

AI Suggestion。

暂不自动 Reject。

---

# 32. Decision 2：信息是否足够？

### Owner

Sales / Engineer

### Inputs

* 产品类型
* Flow
* Head
* Medium
* Temperature
* Voltage
* Application

### 状态

依赖产品和场景。

### Error Cost

高。

### Automation Potential

较高。

非常适合：

```text
AI Extraction
+
Domain Rules
```

---

# 33. Decision 3：候选产品有哪些？

### Owner

Sales / Engineer

### Inputs

```text
Hydraulic Parameters
Application
Medium
Temperature
Material
Motor
```

### 状态

部分结构化、部分经验。

### Error Cost

高。

### Automation Potential

适合：

```text
Structured Search
+
Rules
+
AI Explanation
```

不适合纯 LLM 自由生成。

---

# 34. Decision 4：是否需要工程师？

### Owner

目前是销售自己判断。

### Possible Rules

例如：

```text
Non-standard application
Special material
Critical temperature
Multiple ambiguous candidates
Missing critical parameters
```

### Automation Potential

高。

可以成为系统非常有价值的一层：

> AI 不一定替代工程师，但可以判断什么时候真的需要工程师。

---

# 35. Decision 5：是否可以正式报价？

### Owner

Sales / Manager

### Dependencies

```text
Product Confirmed
Price Available
Customer Policy
Discount Permission
Shipping
```

### Error Cost

高。

### V1

不自动执行。

---

# 36. 技术负责人现在应该看到什么？

到这里，项目方向已经和客户最初说的完全不同。

最初：

```text
AI 外贸业务员
```

现在第一阶段真正值得做的可能是：

```text
Technical Inquiry Copilot
```

核心能力：

```text
询盘结构化
+
缺失信息判断
+
客户 Context
+
产品候选
+
技术规则
+
是否需要工程师
+
回复 Draft
```

---

# 37. MVP Candidate V1

第一版 Pilot 可以定义成：

```text
Email
↓
Structured Extraction
↓
Critical Missing Field Check
↓
Customer Context
↓
Candidate Product Search
↓
Rule Validation
↓
Recommendation + Evidence
↓
Sales Review
↓
Reply Draft
```

重点：

> Recommendation，而不是 Decision。

---

# 38. 这时候仍然不能立即开发

下一步还差：

```text
Data Inventory
+
Golden Dataset
+
AI Boundary Matrix
```

特别是必须验证：

### 产品数据够不够结构化？

### 历史订单能不能关联客户？

### 陈工的经验规则能不能提取出来？

### 哪些知识资料是真正有效版本？

否则架构仍然建立在猜测上。

---

# 39. Stage 2 Exit Criteria

完成以下内容后才进入技术设计：

```text
[x] Problem Brief V1

[x] As-Is Workflow V1

[x] Decision Map V1

[x] Bottleneck Map

[x] Non-goals V1

[ ] Data Inventory

[ ] Knowledge Source of Truth

[ ] Golden Dataset Sample

[ ] AI Boundary Matrix

[ ] Pilot Scope Final
```

---

# 40. 下一阶段：Stage 3

下一步正式进入：

# Data Discovery + AI Boundary Design

我们会向客户要第一批真实材料：

```text
20 条历史询盘
产品 Excel
产品 PDF
10 个历史订单
10 个技术咨询案例
5 个错误/特殊案例
```

然后技术负责人带团队逐个判断：

```text
这是 Data？
Context？
Knowledge？
Rule？
Tacit Knowledge？
```

再把每一个 Workflow 节点分配给：

```text
LLM
Database
Search
Rule Engine
Code
Human
```

到这一步，才真正具备设计代码库和 MVP 技术架构的条件。
