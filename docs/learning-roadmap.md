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

## Stage 5：Product Search、Rule Engine 与 Recommendation

从已审核 InquiryRecord 加载 Stage 3 权威技术字段与 Stage 5 明示模拟扩展，经硬筛、受控规则、代理排序生成暂定候选和工程师升级。24 条合成 Golden Draft 用于计算 Candidate Recall@5、Top-3 Acceptance、安全违规和升级误差；本机页面练习 Approve/Choose Another/Escalate。原稿中的 100 条历史案例及业务改善数值并非真实证据。见 [Stage 5 入口](../stages/05-product-recommendation/README.md)。

## Stage 6：Customer Context、Enterprise Knowledge 与 Reply Draft

把具体客户历史与一般企业知识分流：前者依赖身份确认及最近相关已完成订单，后者依赖有版本、有状态、有生效日的文档检索。结构化 Claim 先经过证据和审批政策，再由租户风格生成可审核邮件草稿；知识缺口弃答并回流治理。12 条身份/订单、50 条知识检索和 10 条草稿案例均为教学合成，真实销售接受率尚无数据。见 [Stage 6 入口](../stages/06-context-knowledge-reply/README.md)。

## Stage 7：Pilot Deployment、Human Workflow 与 Adoption

用 10 个工作日、3 位虚构销售和 1 位工程师的合成活动，演练受控范围、假设前测、按角色审核、工程师升级、脱敏追踪、四层仪表盘、故障降级、数据版本发布门和复盘决策。12 个流程案例中有 3 个仅进入 Shadow；180 条活动事件用于练习分母和分群，并不代表真实用户行为。真实 Pilot Gate 仍为 `NOT_EVALUATED`。见 [Stage 7 入口](../stages/07-pilot-operations/README.md)。

## Stage 8：第二客户与产品化

通过虚构启航设备售后服务观察，逐层区分真正稳定的 Core 契约、外贸/售后各自的 Schema、规则、风险和 UI，以及客户特定数据与配置。实现租户作用域存储、售后 10 条合成案例、海川适配、危险建议人工审核和“维修历史已取到但未进入排序”的故障重放；交付产品化债务、评估层级、复用指标与 Product Thesis V1。没有真实第二客户 Pilot，见 [Stage 8 入口](../stages/08-productization/README.md)。

完成基础演练后，从[双案例纵向交付](../stages/08-productization/vertical/README.md)的模拟电话与邮件输入开始，亲自进行建单、证据核对、人工改写、结果登记和工时记录。两条案例能验证共享契约的可运行性；交付时间收益要等真人分阶段记录，不能由脚本速度推算。

## Stage 9：交付强化

在[Stage 9 手册](../stages/09-hardening/README.md)中练习两人独立标注与裁决、模拟邮箱/CRM/CMMS 的超时与版本更新、售后安全签核和产品曲线适用门、本地签名身份及租户作用域迁移、可选模型端点对比和试点运营复盘。结果仍是合成控制验证；缺少真实系统授权、独立标注和现场试点时，决策保持 `ITERATE_IN_SIMULATION`。

## 后续路线

| 阶段 | 要回答的问题 | 可能产物 |
|---|---|---|
| 后续：真实受控试点 | 合成演练如何转为有授权的现场证据？ | 来源签核、权限/安全审查、真实前测、有限用户试点与退出判断 |
| 后续：技术战略与组合 | 哪个 Domain 和客户群值得投入？ | 真实交付成本、买方证据、技术债容量与取舍记录 |

更远阶段只是学习路线建议，不预先承诺阶段编号、技术栈或范围。

## 每轮学习的共同方法

先独立完成模板，再对照参考结果；记录哪些判断来自证据、哪些来自经验。让同伴追问“证据在哪里”“怎样推翻这个结论”“缺少的数据是否会改变决策”。在下轮更新资料时保留决策变更的原因。
