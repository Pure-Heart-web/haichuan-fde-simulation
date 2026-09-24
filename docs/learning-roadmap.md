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

## Stage 10：客户接入与受控 Shadow Pilot

用虚构设计合作客户练习授权清单、只读 Connector、入库前脱敏、幂等和版本更新、角色审核、提示注入隔离与保留期删除。共享 Core 直接复用，客户差异留在薄适配层。本地数据面拒绝真实客户模式，真实切换必须另外满足授权证据、生产存储、企业身份、外部凭据和现场运营门。见 [Stage 10 手册](../stages/10-customer-onboarding/README.md)。

## Stage 11：Production-like Delivery Room

把合成客户接入升级为长期服务形态：认证 API、持久化 Inbox、Worker 租约和退避、版本更新重开、角色审核、第二人发布、事务性 Outbox、本机 Mock Sink、Trace、指标、Dead Letter 与事故复盘。36 个案例和五个班次仍是脚本合成；SQLite 与本地身份只用于教学。见 [Stage 11 手册](../stages/11-delivery-room/README.md)。

## Stage 12：Model Evaluation, Safety & Canary

把候选模型放在 Model Gateway 后面，使用冻结的 100 条抽取集和 24 条独立攻防集判定发布门，再对 Stage 11 的 36 个工单执行稳定的 25% Canary。练习输入/输出策略、证据绑定、数据最小化遥测、成本门、超时熔断、双签和回滚。候选模型仍为本地 stand-in，未验证真实 LLM 或客户数据。见 [Stage 12 手册](../stages/12-model-safety-canary/README.md)。

## Stage 13：Design Partner Pilot Readiness & Operator Workbench

把 Delivery Room 和 Model Lab 放入同一次现场交付前演练：四方签核授权包、训练 OIDC 契约、PostgreSQL RLS DDL、统一人工工作台、三个 Operator 班次、Auditor 评审、SLO 和候选模型紧急回退。静态 DDL、本地 issuer 和 OTLP-shaped JSONL 保留明确限制，不被写成生产证据。见 [Stage 13 手册](../stages/13-pilot-readiness/README.md)。

## Stage 14：Integration Lab & Authorized Shadow Pilot Preflight

用底层 Delivery Room 的实际死信和事故重算顶层 Gate，演练 `open -> recovering -> resolved` 恢复语义、邮箱/CMMS 只读 Connector、OIDC Discovery 与 Key Rotation、遥测导出前脱敏、合成 Shadow 观察和可携带证据包。八项真实客户外部证据默认均为缺失，因此决策保持 `ITERATE_BEFORE_REAL_SHADOW`。见 [Stage 14 手册](../stages/14-integration-shadow/README.md)。

## Stage 15：Commercial Delivery Room

把技术阶段放入完整商务路径：机会资格、付费 Discovery、双方行动计划、合同/数据/安全尽调、阶段报价、授权 Shadow、商业验收、生产移交、续约和扩容。机器校验 A–F Gate、证据状态、付款比例和合成边界，防止把技术演示写成签约、把意向金额写成收入或把 Pilot 验收写成生产授权。当前海川案例只达到“可提交付费 Discovery 方案”，已签约金额和真实收入均为 0。见 [Stage 15 手册](../stages/15-commercial-delivery/README.md)。

## Stage 16：Team Commercial Delivery Capstone

6 名参与者分别承担 Engagement、FDE 技术、AI 评估、平台集成、安全数据和工作流采用责任，在六轮中处理资格、签约、数据越界、知识冲突、Connector 异常、模型安全失败、人员绕过、跨租户事故、范围膨胀、验收分母和对外宣传压力。团队评分与个人责任证据分开；关键控制失败封顶，团队高分不能掩盖成员没有 Own、Review、Decision、Ops、客户解释或复盘经历。见 [Stage 16 手册](../stages/16-team-delivery-simulation/README.md)。

## Stage 17：Paid Discovery Delivery & Acceptance

在不篡改真实商机状态的前提下，创建明确标记为反事实教学分支的合成 Discovery 合同，演练合同内容摘要、RACI、客户/FDE 依赖、六项可验收交付物、Change Control、冻结指标、三方验收、角色成本、模拟开票条件和下一 Gate。任何交付物或合同变更都会使已有签核失效；合成分支强制真实合同、发票、回款、客户批准、数据和用户为 0。见 [Stage 17 手册](../stages/17-paid-discovery-delivery/README.md)。

## Stage 18：Design Partner Acquisition & Contracting

把 Stage 17 的报价和交付物用于真实商机之前，先用合成候选训练 ICP、Sponsor 资格、付费意愿、预算、采购、数据安全 Owner 和客户投入判断。真实客户的合同、联系人、PO 和签字文件保存在仓库外权威系统；代码只校验十项证据和三方 Release 的引用、状态、角色和日期，并明确不能验证法律效力。见 [Stage 18 手册](../stages/18-design-partner-contracting/README.md)。

## Stage 19：Live Paid Discovery Execution

在 Stage 18 的人工合同释放之后运行四周现场工作：八类会议/观察、客户事实与 FDE 推断/假设分离、五项基线冻结、依赖和变更、真实工时成本，以及六项交付物的验收准备。真实 manifest 仍在仓库外，客户数值和个人信息只保存在权威系统；机器预检不会代替客户验收或授权 Pilot。见 [Stage 19 手册](../stages/19-live-discovery-execution/README.md)。

## Stage 20：Customer Acceptance & Pilot Investment

把六项交付物逐项绑定内容摘要和合同标准，演练附条件接受、整改、最终接受、Discovery 开票释放与五方 Steering。Business Case 必须分开事实和假设；选择 Pilot 后还需独立 SOW、六类成功指标和十项 Mobilization 条件。参考分支选择 Pilot 但保持未授权，真实记录只在仓库外预检。见 [Stage 20 手册](../stages/20-acceptance-investment/README.md)。

## Stage 21：Controlled Shadow Pilot Operations

把 Stage 20 的启动条件落实到有限用户、有限案例和无外部副作用的 Shadow Pilot：五方人工授权绑定范围，Roster 与五类运行版本逐案校验，Daily Gate 控制开班，真实演练一次 Pause、Remediation 和 Resume。三十个合成案例记录七类人工决定、审核时间、专家负担和成本，六项指标与 Evidence Bundle 内容绑定。仓库外真实记录通过预检后仍只能进入人工 Pilot 验收和生产决策。见 [Stage 21 手册](../stages/21-shadow-pilot-operations/README.md)。

## 后续路线

| 阶段 | 要回答的问题 | 可能产物 |
|---|---|---|
| 后续：Pilot 验收与生产决策 | Stage 21 的有限 Shadow 证据是否足以停止、迭代、扩围或进入生产评估？ | 客户验收、缺陷与风险关闭、生产 SLO、安全评审、容量与成本、上线和回退计划、人工生产授权 |
| 后续：技术战略与组合 | 哪个 Domain 和客户群值得投入？ | 真实交付成本、买方证据、技术债容量与取舍记录 |

更远阶段只是学习路线建议，不预先承诺阶段编号、技术栈或范围。

## 每轮学习的共同方法

先独立完成模板，再对照参考结果；记录哪些判断来自证据、哪些来自经验。让同伴追问“证据在哪里”“怎样推翻这个结论”“缺少的数据是否会改变决策”。在下轮更新资料时保留决策变更的原因。
