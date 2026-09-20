# Sprint 1 计划与 Issue Breakdown

目标：10 个工作日内验证邮件转 InquiryRecord 的可靠性，并建立可重复的 Regression Eval。任务按稳定输入/输出契约拆分，团队角色只是模拟分工；进度以本仓库实际代码和测试为准。

| 日程 | Issue / Owner | 输入 → 输出 | 验收条件 | 本次状态 |
|---|---|---|---|---|
| D1 | A1 Domain Schema / Lead+A | 字段定义 → InquiryRecord | 类型、单位、空值语义、序列化与测试 | 已实现，字段语义仍需真实销售/陈工回读 |
| D1–2 | B1 Ingestion / C | `.eml`、text、HTML → WorkItem | 正文和附件元数据分离；无正文报错 | 已实现；附件内容不解析 |
| D2–4 | C1 Generic Extraction / A | WorkItem+Provider → ExtractionResult | JSON 解析、一次重试、失败可审、trace/prompt/model 记录 | 已实现；当前 Provider 为离线正则基线 |
| D3–4 | D1 Normalization / C | 原始值+单位 → canonical | m³/h、CMH、L/min、°F 转换测试 | 已实现常见单位 |
| D4–5 | E1 Validation / Lead+A | 原始字段 → 可信/警告/失败 | 负值拦截、证据原文定位、异常频率警告 | 已实现；业务阈值待 Owner 核准 |
| D5–8 | F1 Review UI / B | 邮件+字段 → 审核事件 | 原文、修改、批准、拒绝；不覆盖原结果 | 已实现本地单用户版 |
| D6–9 | G1 Feedback/Eval / Lead+A | 人工更正、Golden → 报告 | 字段级分母、失败分类、回归 CI | 已实现合成数据版 |
| D9–10 | H1 Review / 全员 | 报告与演示 → 下一步决定 | 报告实际失败、限制和 Stage 5 前置条件 | 已写复盘；真实销售测试待做 |

每个 Issue 的 Definition of Done：契约文档可追溯、正常和失败路径有测试、评估影响说明、无隐性默认、人工审核路径明确。提示词或提取器改动需要更新回归报告；数据契约改动需要讨论标签迁移。

**Sprint 范围控制。** 附件仅检测与排队；产品搜索、规则/推荐、RAG、报价和发信在此切片均无实现。若实际询盘主要靠附件提供参数，必须将附件覆盖列为下一 Sprint 的独立决策，而不能将缺失误归为“模型差”。
