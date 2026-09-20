# Sprint 1 Review 与退出条件

**目标。** 验证邮件或文本能否成为可追溯、可人工更正的 InquiryRecord。当前已经有本地端到端演示与 100 条合成集评估。Stage 3 的 20 封合成邮件进入本地 SQLite 审核队列；销售的真实现场测试尚未进行。

**已实现。** WorkItem、typed InquiryRecord、可替换 Provider 的通用抽取编排、原始单位规范化、字段证据校验、一次解析重试、失败审核路径、本地 Review UI、不可覆盖的 Feedback Event、Prompt/Provider 版本、JSONL telemetry、合成 Golden Dataset 和回归 CI。运行路径见 [Stage 4 入口](../README.md)。

**结果。** 本次正则基线的合成集总体字段准确率 96.7%，流量和温度均 90%，设计门槛未满足。现有代码不调用 LLM；源文档中的“96.8%、18% 人工修改、2.8 秒 P95、$0.018/封”是教学叙事示例，不能作为本仓库的实测值。没有真实人工修改率或审核时间数据。

| Stage 4 退出项 | 现状 |
|---|---|
| Sprint Goal、Repo 边界、WorkItem、InquiryRecord | 已有文件与运行测试 |
| Generic Extraction、Normalization、Validation | 已实现离线基线；模型 Provider 待后续接入 |
| Simple Human Review、Feedback Event | 本地页面与 SQLite 不可覆盖事件已实现；真实销售尚未试用 |
| Golden Dataset、Eval CI | 100 条合成集和回归基线已实现；真实样本待授权获取 |
| Prompt Versioning、Observability | 版本标识和本地 JSONL 追踪已实现；无模型请求日志 |
| Failure Review、ADR-005 | 已按实际失败与原稿危险默认值案例形成记录 |
| 真实 100 条与 Pilot Release Gate | **未完成**：未获得真实数据、真实模型和客户审核 |

**决定。** 可用于团队演练和下一轮设计审查；不能进入真实客户 Pilot。需先提高流量与温度字段表现，并获得真实脱敏样本、审核者与标签。之后评估是否加入模型 Provider、附件解析或 Stage 5 产品检索。未触碰产品推荐、RAG、历史订单、报价、自动回复或自动发送。
