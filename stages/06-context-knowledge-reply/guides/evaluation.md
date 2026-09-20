# Stage 6 评估协议与分母

冻结数据：12 条人工编写的身份/订单案例、50 条按意图和元数据变化构造的 FAQ 案例、10 条端到端草稿案例。全部是**教学合成**，其中 FAQ 问句大量使用同义改写，不能视为独立历史样本。代码不读取标签来生成答案；标签在 `context-eval.jsonl`、`knowledge-eval.jsonl`、`generation-eval-labels.jsonl`。

Context：Customer Resolution Accuracy 在 12 条中同时比较状态与 customer_id；Previous Order Resolution Accuracy 只在标有上一单 ID 的案例上计算；Wrong Customer Context Rate 统计给出错误订单的案例数 / 12。Knowledge：Correct Source@1 与 Recall@5 只在标有预期文档的案例上计算；Outdated Document Retrieval Rate 是非 active 文档召回数 / 所有召回文档数；Knowledge Gap Rate 是无结果案例数 / 50，**不是错误率**，Gap Detection Accuracy 才比较应弃答与实际弃答。Generation：Unsupported Claim Rate 是未通过 Claim Policy 的 Claim 数 / Claim 总数；Evidence Coverage 只在需要证据的 Claim 中计算；Fact Accuracy 检查独立标签指定的必须/禁止短语；Claim/Gap Match 比较类型与缺口；Human Acceptance/Edit 仅从审核事件计算，没有事件时是 N/A。

当前运行 `python3 stage6.py eval` 的合成基线：身份与上一单解析均 100%，错误客户上下文 0；50 条检索案例 Correct Source@1/Recall@5 均 100%，过期文档检索 0，Knowledge Gap Rate 44%（有意设置的 ATEX、SKU、地区或日期缺口）；10 条草稿共 40 个 Claim，政策违规 0、证据覆盖 100%。这些数字主要验证边界条件，不能外推到真实客户。没有实际销售审核时，接受率与编辑率为 N/A。原稿中的 98%、94%、1.8%、84% 等 Pilot 数字只是案例示例，仓库不报告为实测。

`python3 stage6.py eval --check-baseline` 对冻结样本执行合成回归检查，CI 也运行它。基线仅防止当前教学案例退化；不能替代真实 Pilot Release Gate。

真实 Pilot 前需取得授权的客户身份和订单快照、正式政策/证书及生效历史、盲标注的独立问答集；把企业、产品线、地区、时间分布纳入切分。实际销售的 Accept/Minor/Major/Reject、编辑原因和处理耗时应通过人工事件采集。只有这些来源、分母和审核口径固定后，才谈 Release Gate 或业务改善。
