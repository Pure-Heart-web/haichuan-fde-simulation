# Stage 6 来源与流程手册

## 1. 对象历史与一般知识分流

客户历史由 `customer_id` 查询，不走相似文档搜索。身份先查精确邮箱，再查非公共域名，再查精确别名；多个候选、联系人与公司名冲突、仅模糊相似都进入人工确认，不能解锁订单。`previous_order` 固定为该客户在查询时间之前、**已完成**且**标准离心泵产品线相关**的最近一单；取消订单和其他产品线不参与，最近日期并列则人工确认。Stage 3 的 `SRC-ORD` 缺时间戳且身份暂定，本阶段使用另列的 `ST6-ORD` 合成样本，不修改 Stage 3 治理决定。

只有邮件明确说“same as previous/last order”等表达，编排才读取上一单。本次明确值在 `ResolvedField` 标为 `explicit_current`；历史值标为 `historical_reference`，保留订单 ID。即使客户引用上一单，历史 380V/50Hz 也只进入确认问题，不静默写入 InquiryRecord。本次写 400V/60Hz 时，草稿指出差异并请客户确认。Stage 5 的推荐仍为暂定，未经该阶段人工审核的候选不进入最终型号 Claim。

## 2. 知识入库和检索

`knowledge-documents.json` 中每份文档有 ID、标题、版本、状态、生效日、负责人、文档类型、产品线、地区、语言及 chunk。V1 先过滤 `status=active`、`effective_date<=as_of`、产品线、地区和 SKU，然后对符合条件的 chunk 做简单关键词排序。没有 embedding、向量库或 GraphRAG；这是一条可检查的离线基线。`WARRANTY-2024` 标为 superseded（24 个月），`WARRANTY-2026` 才是当前模拟有效版本（12 个月）；未来生效的 2027 文件即使状态 active 也被日期过滤。ATEX 只有 draft，不能作为证据。`as_of` 只用于当前状态和生效日过滤，V1 **不重建历史状态快照**；旧日期查询无有效来源时返回缺口。

`KnowledgeEvidence` 保留 document/chunk ID、版本、生效日、owner、原文和相关分数。文档结果是一般政策或技术说明；典型交期不能升级成具体订单交期。若没有适用证据，草稿输出待确认用语并创建 KnowledgeGapEvent。审核人填写答案后仅进入 `pending_governance`，不会自动生成 active 文档。

## 3. Claim → 内容计划 → 风格

Claim Policy 在 `tenants/haichuan/claim-policy.json`。普通致谢可无证据；历史订单、保修、认证、典型交期和户外适用判断必须引用源。典型交期必须包含 `subject to production confirmation`；最终型号需要有效审批引用，V1 不自动生成。具体交货承诺、价格、折扣、合同承诺在 V1 禁止。校验器先审查结构化 Claim，随后才把允许的 Claim 按内容计划写成英文正文。租户风格只决定称呼、语气与段落上限，不改变事实。

当前回复器是**确定性模板**，不是已接入大模型的自动写信产品。输出 `sent=false`、`requires_review=true`；页面仅记录 approve、minor/major edit、reject、escalate。编辑文本留作 `human_authored_unverified`，不能直接再次批准；系统无邮件发送端点。真实部署需要身份登录、权限校验、文档授权、持续评估和客户审核流程。
