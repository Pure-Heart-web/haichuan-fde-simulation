# 海川工业泵 AI 询盘项目

## Stage 3：Data Discovery、Knowledge Governance 与 AI Boundary Design

---

# 1. 客户第一次交付数据

Discovery 完成后，你向客户提出第一批数据需求。

要求不要太大。

第一批只要：

```text
20 条历史询盘
20 条对应销售回复
10 个成交订单
5 个失败/特殊案例
产品 Excel
产品目录 PDF
FAQ
部分技术咨询记录
```

目的不是训练模型。

而是先回答：

> 我们到底拥有什么数据？

---

# 2. 客户实际给你的东西

两天以后 Linda 发来一个压缩包：

```text
Haichuan_Pilot_Data_v1/

├── inquiries/
│   ├── inquiry_001.eml
│   ├── inquiry_002.eml
│   ├── ...
│   └── inquiry_020.eml
│
├── replies/
│   ├── reply_001.eml
│   ├── ...
│
├── products/
│   ├── Pump_Catalog_2024.pdf
│   ├── Pump_Catalog_2025.pdf
│   ├── Pump_Selection_NEW.xlsx
│   ├── Product_Master_Final.xlsx
│   └── Product_Master_Final_v2.xlsx
│
├── orders/
│   └── historical_orders.xlsx
│
├── pricing/
│   ├── Quote_2025.xlsx
│   └── Special_Discount.xlsx
│
├── training/
│   └── Sales_Training.pptx
│
└── tech_chat/
    └── tech_group_export.txt
```

你的工程师 A 看完说：

> 数据不少啊，直接建知识库应该很快。

---

# 3. 技术负责人第一反应应该是什么？

不是：

> 开始 embedding。

而是：

> **哪一个文件是真的？**

因为文件名已经释放出危险信号：

```text
NEW
Final
Final_v2
2024
2025
```

说明数据治理可能很差。

---

# 4. 第一次 Data Review Meeting

你把 Linda 和陈工叫进会议。

你：

> 这几个产品表，哪一个现在销售应该使用？

Linda：

> 我一般用 Product_Master_Final_v2。

陈工：

> 不对，技术参数应该以 Pump_Selection_NEW 为准。

Linda：

> 但那个没有价格。

陈工：

> 价格本来就不能看那个。

你：

> 那 Pump Catalog 2025 呢？

陈工：

> 部分型号已经改过。

---

# 5. 第一条重大结论

客户所谓：

> “我们有完整产品资料。”

实际上是：

```text
多个来源
+
不同用途
+
不同版本
+
不同 Owner
```

所以第一项技术工作不是 RAG。

而是：

# Source of Truth Mapping

---

# 6. 建立 Data Inventory V1

| 数据源                          | 类型               | 用途     | Owner | 当前可信度            |
| ---------------------------- | ---------------- | ------ | ----- | ---------------- |
| Pump_Selection_NEW.xlsx      | Product Data     | 技术选型   | 技术部   | High             |
| Product_Master_Final_v2.xlsx | Commercial Data  | 销售信息   | 销售部   | Medium           |
| Catalog 2025 PDF             | Knowledge        | 对外产品资料 | 市场/技术 | Medium           |
| historical_orders.xlsx       | Context          | 客户历史   | 销售/财务 | Medium           |
| Quote_2025.xlsx              | Pricing Data     | 标准报价   | 销售    | Medium           |
| Special_Discount.xlsx        | Sensitive Policy | 特殊价格   | 管理层   | High sensitivity |
| Training PPT                 | Knowledge        | 新人培训   | 销售    | Medium           |
| Tech Chat                    | Tacit Knowledge  | 工程经验   | 技术部   | Low structure    |

---

# 7. 技术负责人必须明确五类东西

后续系统设计中，不要把所有数据都叫：

> “Knowledge”。

至少分成五类。

---

# A. Structured Data

结构化事实。

例如：

```text
SKU
Flow Range
Head Range
Material
Power
Voltage
Status
```

适合：

```text
Database
SQL
Filter
Validation
```

---

# B. Context

当前客户、设备、订单过去发生了什么。

例如：

```text
ABC Marine
2025-03
P120
20 units
Brazil
```

适合：

```text
CRM
ERP
Context Provider
```

---

# C. Knowledge

公司普遍适用的文档知识。

例如：

```text
Warranty Policy
Installation Guide
FAQ
Certification
```

适合：

```text
Knowledge Retrieval / RAG
```

---

# D. Rules

确定性约束。

例如：

```text
seawater
→ cast iron forbidden
```

适合：

```text
Rule Engine
```

---

# E. Tacit Knowledge

专家脑中的经验。

例如陈工说：

> CP80 参数虽然能覆盖，但工作点太靠边，不建议长期运行。

这不是简单文档知识。

需要：

```text
采访
↓
结构化
↓
验证
↓
转成 Rule / Guideline
```

---

# 8. 客户数据里出现第一个真实坑

Engineer C 检查产品 Excel。

发现：

```text
CP90

Flow:
80-100

Head:
35-42

Material:
SS316
```

另一个文件：

```text
CP90

Flow:
75-95

Head:
32-40

Material:
SS304
```

团队问：

> 哪个是真的？

---

# 9. 技术负责人不能自己猜

正确动作：

创建：

```text
Data Conflict D-001
```

内容：

```text
Entity:
CP90

Conflict:
Flow range
Head range
Material

Sources:
Pump_Selection_NEW.xlsx
Product_Master_Final_v2.xlsx

Decision Owner:
Technical Department

Status:
Pending
```

---

然后让陈工确认。

陈工：

> Pump_Selection_NEW 是新的。

于是正式定义：

```text
Technical Product Source of Truth
=
Pump_Selection_NEW.xlsx
```

---

# 10. Source of Truth Register

技术负责人现在应该建立：

| Domain                       | Source of Truth            |
| ---------------------------- | -------------------------- |
| Technical product parameters | Pump_Selection_NEW         |
| Customer history             | ERP / confirmed order data |
| Warranty                     | Current Warranty Policy    |
| Standard pricing             | Quote table                |
| Special discounts            | Approval system / manager  |
| Certifications               | Certification repository   |

以后 AI 输出任何事实：

应该能够追溯到这里。

---

# 11. 第二个坑：历史订单脏数据

打开：

```text
historical_orders.xlsx
```

发现客户名字：

```text
ABC Marine
ABC Marine Ltd
ABC MARINE
ABC-Marine BV
```

其实可能是同一客户。

而系统以后要解决：

> same as previous order

那么如果 Customer Identity 做不好：

Context Retrieval 一定失败。

---

# 12. 技术负责人判断

这不是：

```text
LLM 问题
```

而是：

# Entity Resolution

需要建立：

```text
Customer
↓
Canonical Customer ID
↓
Aliases
↓
Orders
```

例如：

```text
customer_id:
CUST_00128

canonical_name:
ABC Marine BV

aliases:
- ABC Marine
- ABC MARINE
- ABC-Marine BV
```

---

# 13. 新的共享能力出现

团队可以开始考虑：

```text
core/entities/
```

而不是在 Prompt 里面说：

> “请识别这些是不是同一个客户。”

因为：

客户身份是基础业务实体。

---

# 14. 第三个坑：技术聊天记录

打开：

```text
tech_group_export.txt
```

里面有：

> Linda：
> 海水项目 CP100 可以吗？

> 陈工：
> 普通版本不行，要 SS316。

另一段：

> Mike：
> 90度热水用 CP90？

> 陈工：
> 不建议，密封需要换，先找我确认。

Engineer A：

> 这些直接进向量库很有价值。

---

# 15. 技术负责人要阻止

原因：

聊天记录是：

```text
非正式
无版本
上下文不完整
可能过期
```

不能直接成为权威知识。

---

# 16. Tacit Knowledge Extraction

正确流程：

```text
Chat / Expert Interview
↓
Candidate Rule
↓
Engineer Verification
↓
Rule Registry
```

例如：

---

## Candidate Rule R-001

```text
Condition:
medium = seawater

Constraint:
cast iron prohibited

Preferred:
SS316 or approved corrosion-resistant material

Owner:
Technical Department

Status:
Verified
```

---

## Candidate Rule R-002

```text
Condition:
temperature >= 80°C

Action:
Engineer review required

Reason:
Seal / material configuration may require modification

Status:
Verified
```

---

这时候聊天记录只是：

> 发现规则的来源。

不是：

> 生产系统里的直接事实来源。

---

# 17. 第四个坑：报价数据

Engineer B：

> 我们可以顺便把报价接进去。

打开：

```text
Special_Discount.xlsx
```

看到：

```text
Customer
SKU
Special Price
Reason
Approved By
```

里面包含大量客户特价。

---

# 18. 技术负责人要做 Security Classification

至少：

```text
Public
Internal
Confidential
Highly Sensitive
```

例如：

| 数据     | 分类               |
| ------ | ---------------- |
| 对外产品目录 | Public           |
| 技术参数   | Internal         |
| CRM    | Confidential     |
| 标准价格   | Confidential     |
| 客户特价   | Highly Sensitive |

V1：

```text
Special Discount
```

完全不进入生成模型上下文。

报价也暂不在 Pilot Scope。

---

# 19. AI Boundary Design 正式开始

现在我们已经基本知道数据形态。

开始把 Workflow 中每一个任务分配给正确机制。

---

# 20. Task 1：读取邮件

目标：

把：

```text
Dear Sir...
Flow 80 m3...
```

变成标准输入。

机制：

```text
Email Adapter
+
Parser
```

不是 LLM 核心任务。

输出：

```text
WorkItem
```

---

# 21. Task 2：询盘字段提取

例如：

```text
Flow = 85 m3/h
Head = 38m
Temperature = 42C
```

机制：

```text
LLM Structured Extraction
+
Schema Validation
```

适合 AI。

原因：

客户表达高度非结构化。

---

# 22. Task 3：单位标准化

例如：

```text
85 CMH
85 m³/h
1416 L/min
```

统一：

```text
85 m3/h
```

机制：

```text
Deterministic Code
```

不是让 LLM 每次计算。

---

# 23. Task 4：关键字段缺失判断

机制：

```text
Domain Rules
+
Structured Data
```

例如：

```text
if product_type == centrifugal_pump
and medium is None:

    request_medium = True
```

必要时结合 AI 理解上下文。

但最终规则应该尽可能确定。

---

# 24. Task 5：Customer Context

例如：

客户写：

> same as previous order

机制：

```text
Entity Resolution
↓
Customer Context Provider
↓
Order DB
```

不是 RAG。

---

# 25. Task 6：产品候选搜索

机制：

```text
Structured Product Database
+
Filter / Ranking
```

第一层：

硬过滤：

```text
flow
head
status
```

第二层：

Domain Rules：

```text
medium
temperature
material
```

第三层：

Ranking：

```text
preferred operating point
commercial preference
```

---

# 26. Task 7：知识问答

例如：

> Do you provide CE?

机制：

```text
Knowledge Retrieval
+
LLM Generation
```

适合 RAG。

---

# 27. Task 8：产品推荐解释

系统已经有：

```text
Candidates
Rules
Context
```

LLM 可以生成：

```text
P90 is recommended because...
```

但它只能解释已有候选。

不能：

> 自由发明型号。

---

# 28. Task 9：最终型号确认

V1：

```text
Human
```

角色：

```text
Sales
or
Engineer
```

根据风险升级。

---

# 29. Task 10：回复 Draft

机制：

```text
LLM
```

输入：

```text
Structured Inquiry
Missing Information
Approved Candidate
Knowledge
```

输出：

```text
Reply Draft
```

必须：

```text
Human Review
```

---

# 30. AI Boundary Matrix V1

| Task                | Primary Mechanism      | Human Review        |
| ------------------- | ---------------------- | ------------------- |
| Email parsing       | Code                   | No                  |
| Field extraction    | LLM + Schema           | Exception           |
| Unit normalization  | Code                   | No                  |
| Missing field check | Rules                  | No                  |
| Customer identity   | DB + Entity Resolution | Exception           |
| Customer history    | Context Provider       | No                  |
| Product filtering   | DB                     | No                  |
| Product constraints | Rules                  | No                  |
| Candidate ranking   | Code / Rules           | Yes                 |
| Knowledge retrieval | Search / RAG           | Yes where sensitive |
| Explanation         | LLM                    | Yes                 |
| Final selection     | Human                  | Yes                 |
| Pricing             | Out of Scope           | Yes                 |
| Reply generation    | LLM                    | Yes                 |
| Send                | Human                  | Yes                 |

---

# 31. 现在出现第一版技术架构

```text
                Email
                  ↓
            Ingestion Adapter
                  ↓
               WorkItem
                  ↓
        Structured Extraction
                  ↓
          Unit Normalization
                  ↓
           Inquiry Record
             ↙        ↘
 Customer Context    Knowledge
      ↓                 ↓
 Product Search      Retrieval
      ↓                 ↓
        Domain Rule Engine
               ↓
        Candidate Ranking
               ↓
         Recommendation
               ↓
           Human Review
               ↓
          Reply Generator
               ↓
           Human Send
```

---

# 32. 这时候技术负责人开始分团队任务

4 人团队：

---

## 你：Tech Lead / FDE

负责：

```text
Domain Schema
Architecture
AI Boundary
客户技术规则访谈
Eval Definition
PR / Architecture Review
```

注意：

你不需要写最多代码。

---

## Engineer A：AI / Backend

负责：

```text
Extraction
LLM Gateway
Knowledge Retrieval
Reply Generator
```

---

## Engineer B：Product / Full-stack

负责：

```text
Review UI
User Workflow
Feedback UI
```

---

## Engineer C：Data / Integration

负责：

```text
Product Data
Customer Identity
Order Context
Normalization
Data Quality
```

---

# 33. 技术负责人现在如何控制开发？

不能说：

> 大家先各自写。

先定义 Data Contracts。

---

# 34. WorkItem V1

```text
WorkItem

id
tenant_id
source_type
source_id

sender
subject
body

attachments

received_at
```

---

# 35. InquiryRecord V1

```text
InquiryRecord

customer_name
customer_id

country

product_type

quantity

flow_m3h
head_m

medium
temperature_c

voltage
frequency

application

destination_port

missing_fields

extraction_confidence
```

---

# 36. ProductCandidate V1

```text
ProductCandidate

sku

match_score

matched_conditions

warnings

rule_results

requires_engineer_review
```

---

# 37. Recommendation V1

```text
Recommendation

inquiry_id

candidate_products

preferred_candidate

reasoning_summary

missing_information

risk_level

required_reviewer

evidence
```

---

# 38. ReviewTask V1

```text
ReviewTask

work_item_id

recommendation_id

review_type

assignee_role

status

decision

edits

comment
```

---

# 39. 为什么 Data Contract 特别重要？

因为以后：

```text
模型换了
RAG 换了
数据库换了
```

只要：

```text
InquiryRecord
Recommendation
```

契约稳定，

系统其他部分不需要跟着全部重写。

---

# 40. 进入 Golden Dataset 建设

现在从客户 20 条历史询盘里选：

```text
10 个正常案例
5 个复杂案例
3 个历史客户案例
2 个失败案例
```

组成：

# Eval Dataset V0

---

# 41. Example Case E-001

Input：

```text
Need centrifugal pump.

Flow 85m3/h
Head 38m

Water around 42C.
6pcs.
```

Expected Extraction：

```text
flow_m3h = 85
head_m = 38
temperature_c = 42
quantity = 6
```

Expected Missing：

```text
medium detail
```

Expected Candidate：

```text
P90
```

Expected Action：

```text
Request medium clarification
```

---

# 42. Example Case E-002

Input：

```text
Same as last order.
Need 20 pcs.
```

Expected：

```text
Customer resolved
↓
previous order retrieved
↓
previous SKU candidate
```

不应该：

```text
直接要求 Flow / Head
```

---

# 43. Example Case E-003

Input：

```text
Seawater
Flow 90
Head 40
```

Expected Rule：

```text
cast iron prohibited
```

Rule Violation：

必须为：

```text
0
```

这是 Critical Eval。

---

# 44. 技术负责人此时要设第一版 Release Gate

例如：

### Extraction

关键字段准确率：

```text
>= 95%
```

Pilot 后再提高。

---

### Critical Rules

```text
Rule violation = 0
```

---

### Product Candidate

Top-3：

```text
>= 90%
```

---

### Human Review

所有正式产品推荐：

```text
100% Review
```

---

这些数字只是当前 Pilot 假设，不是行业标准。

后续根据真实 Dataset 调整。

---

# 45. 现在团队第一次具备“可以开始 Build”的条件

因为我们已经拥有：

```text
Problem Brief
Workflow
Decision Map
Data Inventory
Source of Truth
AI Boundary
Architecture V0
Data Contracts
Golden Dataset V0
Release Gate
```

这时候才正式进入工程开发。

---

# 46. Stage 3 Exit Criteria

```text
[x] Data Inventory V1

[x] Data Classification

[x] Source of Truth Register

[x] Context / Knowledge / Rules 分离

[x] Tacit Knowledge Handling

[x] AI Boundary Matrix

[x] Architecture V0

[x] Core Data Contracts

[x] Golden Dataset V0

[x] Release Gate V0
```

---

# 47. 下一阶段：Stage 4

接下来进入真正的：

# Build Sprint 1

目标不是一次做完整系统。

第一 Sprint 只完成：

```text
Email
↓
WorkItem
↓
Structured Extraction
↓
Normalization
↓
InquiryRecord
↓
Simple Review UI
```

然后拿真实 20 条询盘跑。

我们会模拟：

* 团队如何拆 Jira / GitHub Issues
* 技术负责人怎么主持 Design Review
* AI Coding 怎么参与
* PR 怎么审
* 第一个 Extraction 为什么会失败
* 怎么建立 Eval CI
* 怎么决定是否换模型
* 代码库到底怎么落成 `core / domains / tenants / evals`

这一阶段开始真正进入“代码与工程管理”层。
