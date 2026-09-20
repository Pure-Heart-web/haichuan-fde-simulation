# 学习路线与阶段边界

## Stage 1：机会识别与 Discovery

要学会将“做一个 AI 外贸业务员”拆成待验证的问题，观察真实工作，区分 Fact / Claim / Hypothesis / Unknown，建立指标，并明确人为审核边界。

输入：客户诉求与初步访谈。输出：Problem Brief V1、As-Is Workflow、Decision Map、Data / Knowledge Inventory V0、Baseline Metrics、Open Questions。通过本阶段后才讨论 MVP。

原稿保留在 `stages/01-discovery/source/`。本次细化包括：证据编号、可执行会议日程、计时口径、合成练习数据、指标计算、退出条件证据表。原稿中“已有事实”缺少原始观察附件，因此在真实项目中应暂作为前期访谈线索；此处不将它们直接升级为已验证结论。

## Stage 2：Discovery 实战与问题建模

用 Inquiry #017 复盘客户有效性判断、需求缺口、选型候选、专家升级与等待；交付 Problem Brief、As-Is Workflow、Bottleneck Map、Decision Map、Pilot 候选与 Non-goals。保留计时、咨询频率、错误金额等访谈主张的待验证状态。见 [Stage 2 入口](../stages/02-discovery/README.md)。

## Stage 3：数据发现与 AI 边界

审查 20 对合成邮件与回复、订单、产品表冲突、目录和聊天摘录；按业务域指定权威来源，处理身份歧义、规则候选和敏感数据。交付 Data Inventory、Source of Truth、AI Boundary、架构、数据契约、Golden Dataset V0、Release Gate V0。见 [Stage 3 入口](../stages/03-data-boundary/README.md)。

## Stage 4：Build Sprint 1

实现 Email/Text/HTML → WorkItem → 提取 → 规范化/校验 → InquiryRecord → 本地人工审核和反馈 → 合成评估。可替换抽取接口目前用离线正则基线演练，未接真实模型；100 条合成集用于回归练习，真实 Pilot Gate 尚未评估。见 [Stage 4 入口](../stages/04-build-sprint-1/README.md)。

## Stage 5：Product Search、Rule Engine 与 Recommendation（本次新增）

从已审核 InquiryRecord 加载 Stage 3 权威技术字段与 Stage 5 明示模拟扩展，经硬筛、受控规则、代理排序生成暂定候选和工程师升级。24 条合成 Golden Draft 用于计算 Candidate Recall@5、Top-3 Acceptance、安全违规和升级误差；本机页面练习 Approve/Choose Another/Escalate。原稿中的 100 条历史案例及业务改善数值并非真实证据。见 [Stage 5 入口](../stages/05-product-recommendation/README.md)。

## 后续路线

| 阶段 | 要回答的问题 | 可能产物 |
|---|---|---|
| 后续：扩展与集成 | 如何加入客户上下文和业务系统？ | 引用、权限、审核和集成测试 |
| 后续：试点与运营 | 是否创造价值，谁负责运行？ | 试点对照、监控、回退、运行手册、培训与交接 |

更远阶段只是学习路线建议，不预先承诺阶段编号、技术栈或范围。

## 每轮学习的共同方法

先独立完成模板，再对照参考结果；记录哪些判断来自证据、哪些来自经验。让同伴追问“证据在哪里”“怎样推翻这个结论”“缺少的数据是否会改变决策”。在下轮更新资料时保留决策变更的原因。
