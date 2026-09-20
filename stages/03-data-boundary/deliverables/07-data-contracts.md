# Core Data Contracts V1

示例对象位于 [`contract-examples.json`](../data/contract-examples.json)，可由 `stage_pipeline.py stage3` 校验基础字段、引用和边界。字段采用 JSON 风格；未得到的信息为 `null`，不能编造默认值。

| 对象 | 必需字段 | 关键不变量 |
|---|---|---|
| WorkItem | id, tenant_id, source_type, source_id, sender, subject, body, attachments, received_at | 唯一 ID；时间含时区；附件保留来源和权限 |
| InquiryRecord | work_item_id, customer_name, customer_id, product_type, quantity, flow_m3h, head_m, medium, temperature_c, voltage, frequency, application, destination_port, missing_fields, extraction_confidence, evidence | 数值单位固定；字段级原文引用；客户 ID 可空 |
| ProductCandidate | sku, match_score, matched_conditions, warnings, rule_results, requires_engineer_review, evidence | 只能引用实际产品库 SKU；冲突/候选规则不能视为通过 |
| Recommendation | id, inquiry_id, candidate_products, preferred_candidate, reasoning_summary, missing_information, risk_level, required_reviewer, evidence | preferred 可空；证据与风险必须可审；无审核不能作最终决定 |
| ReviewTask | id, work_item_id, recommendation_id, review_type, assignee_role, status, decision, edits, comment | `approved` 要有审核者和时间；发送独立于建议产生 |

`evidence` 应含 `source_id`、`source_version` 与片段/记录定位。模型输出需经过 Schema 校验、单位标准化、字段来源核查和规则检查后才能进入 ReviewTask。示例数据未实现真实抽取或系统接口；Stage 4 第一切片才开发 WorkItem → InquiryRecord 与简易 Review UI。
