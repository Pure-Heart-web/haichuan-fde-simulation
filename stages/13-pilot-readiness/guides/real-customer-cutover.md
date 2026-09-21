# 真实客户外置包与切换门

Stage 13 不接收真实客户数据。进入 Authorized Shadow Pilot 时，客户包应由部署环境外置挂载，仓库只保留 Schema、脱敏测试和 Secret 引用。

## 外置包内容

- 双方批准的处理目的、数据来源、字段、用户、区域、保留期和撤销方式。
- 客户数据负责人、安全负责人、Pilot Owner、Stop Owner 和事故联系方式。
- Connector 应用身份、OAuth scope、回调地址、限流、补数和撤权步骤。
- 企业 OIDC issuer、audience、JWKS、group-to-role 映射、MFA 和账户撤销测试。
- 知识库所有者、版本、适用条件、发布和撤回策略。
- 生产数据面、备份、恢复、加密、密钥轮换、审计与删除证据。

## 不得进入 Git 的内容

- 原始邮件、电话转写、CRM/CMMS 导出、附件和知识库全文。
- 客户名称、联系人、邮箱、电话、订单号、设备序列号和未公开价格。
- OAuth client secret、数据库密码、OIDC 私钥、API key 和生产 token。

## 切换 Gate

1. 授权证据、外置包哈希和责任人均已核对。
2. PostgreSQL 迁移在隔离环境实际执行，包括跨租户读、写、检索、Trace 和导出测试。
3. 企业 OIDC/JWKS、MFA、角色映射和撤权在客户测试租户通过。
4. Connector 使用最小权限，已验证重复、断线、限流、Schema 漂移和补数。
5. OTLP 后端默认不采集 Prompt、正文、工具参数和模型输出，且完成权限与保留期检查。
6. 客户 UAT、值班、事故联络、Stop 和 rollback 演练通过。
7. 初始运行只允许 Shadow；任何客户侧写入或发送需另外的范围和审批。

OWASP 建议将授权放在下游系统执行，限制工具功能、权限和自主性，并对敏感动作保留人工确认。参考 [OWASP Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)。
