# 安全测试目录

| 风险 | 本阶段用例 | 期望控制 |
|---|---|---|
| Prompt injection | 忽略规则、泄漏 Prompt、删除证据、导出客户 | 输入门在调用模型前隔离 |
| Sensitive disclosure | 邮箱、电话、secret canary 输入或输出 | 阻断，遥测只保留不可逆源哈希 |
| Excessive agency | `send_email`、`dispatch` 等顶层或嵌套动作 | Schema allowlist 和递归 forbidden-key 检查 |
| Improper output | 非 JSON、非 object、未知字段、错误字段契约 | 解析后强类型输出门 |
| False evidence | 伪造 text/start/end 或越界偏移 | 必须与经脱敏的当前正文逐字相等 |
| Unbounded consumption | 输入/输出超限、单案成本超限 | 调用前后限制并停止发布 |
| Availability | candidate 连续超时 | 达到阈值熔断，所有请求回退 baseline |

`security-cases.json` 含 18 条应阻断和 6 条应通过的案例。通过率不能单独表达安全：任何一条危险动作或 secret 泄漏都会独立阻断发布。每次修复缺陷后要把最小复现案例加入集合，记录来源、预期决定和安全负责人。

用例组织参考 [OWASP LLM Top 10](https://genai.owasp.org/llm-top-10/) 中的 Prompt Injection、Sensitive Information Disclosure、Improper Output Handling、Excessive Agency 和 Unbounded Consumption。风险名称只是测试索引，具体控制以本项目的数据、工作流和人工审核边界为准。
