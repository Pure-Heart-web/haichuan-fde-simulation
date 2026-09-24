# Paid Discovery SOW Term Sheet

> 供业务、交付、法务和采购共同形成正式 SOW 的工作底稿。正式文本、客户信息和签字必须进入获批合同系统。

## 1. Parties and purpose

- Provider legal entity: `[contract system reference]`
- Customer legal entity: `[contract system reference]`
- Business Sponsor / Acceptance Owner: `[role references]`
- Purpose: 在四周内形成是否进入有限 Shadow Pilot 的共同决策和证据，不承诺生产上线或自动化业务结果。

## 2. Scope and deliverables

| ID | Deliverable | Acceptance evidence | Customer owner |
|---|---|---|---|
| D1 | Problem、Scope、RACI | 双方确认的流程、in/out scope、角色 | Sponsor |
| D2 | Baseline 与成功测量计划 | 冻结分母、取样和 Stop/Iterate/Pilot 门槛 | Process Owner |
| D3 | 数据、安全与 IP 决策包 | 数据类别、权威源、保留、访问、DPA 决议 | Data/Security Owner |
| D4 | Pilot 与集成计划 | 环境、Connector、身份、人工审核、回退 | IT Owner |
| D5 | Business Case | 成本、客户投入、单位经济、敏感性分析 | Sponsor |
| D6 | Pilot 建议 | 证据、限制、风险、依赖和下一 Gate | Sponsor |

Out of scope：生产部署、自动外发/写入、24×7 SLA、真实泵选型或维修判断、未列明 Domain/语言、未批准数据迁移及第三方费用。

## 3. Work plan and dependencies

- Period: `[effective date]` 至 `[end date]`
- Weekly cadence: 工作会议、RAID Review、Sponsor Checkpoint、最终验收。
- Customer commitments: Process Owner 每周 2 小时；Sponsor 每周 30 分钟；按期提供脱敏样本、现行流程、专家、IT/安全/采购决策。
- Provider commitments: Engagement、FDE、Security/Data 和必要工程角色；按周报告范围、风险、成本和依赖。
- 客户依赖延期时，双方通过 Change Control 调整日期或范围，不默认为 Provider 延误。

## 4. Acceptance and change control

交付物按上表逐项接受、附条件接受或拒绝；拒绝必须引用未达到的合同标准。客户在 `[N]` 个工作日内反馈。任何新增集成、数据、Domain、自动动作或成果承诺都需书面 Change Request，列明费用、时间、安全与验收影响。

## 5. Fees and payment

- Fixed fee: `CNY [amount]` plus applicable tax；Stage 17 教学参考为 CNY 120,000，正式价格须经授权审批。
- Milestone 1: `[percent]%` at Kickoff；Milestone 2: `[percent]%` at acceptance。
- Payment term / PO / invoice requirements: `[finance and procurement decision]`
- 付款义务、税务和暂停权以正式合同为准。

## 6. Data, security and AI boundaries

- 默认合成或脱敏数据、只读访问、最小权限、人工审核和待发送区；
- 未知工况、证据冲突、高风险建议、跨租户请求和提示注入必须弃答或升级；
- 数据位置、保留/删除、子处理方、模型使用和训练限制由 DPA/安全附件决定；
- Discovery Acceptance 不授权 Shadow、生产或外部发送。

## 7. Governance and exit

双方列明 Sponsor、Delivery Lead、Security/Data、Procurement/Legal、Acceptance 与 Stop Owner。最终 Steering Decision 为 Stop、补充 Discovery 或准备独立 Pilot SOW。终止、知识产权、保密、责任限制、保证和争议解决由正式 MSA/SOW 规定。

## 8. Execution references

- MSA/terms ID and version: `[external reference]`
- SOW ID and version: `[external reference]`
- DPA/security decision: `[external reference]`
- PO/equivalent authorization: `[external reference]`
- Authorized signatory records: `[external references]`
