要完成一个商业 FDE 项目交付，标准不能只是“代码上线、测试通过”，而应是：

> **客户批准的业务范围已经在目标环境运行，验收指标达到约定值，安全和运营责任完成移交，客户签署验收，支持与付款节点正式生效。**

当前案例已经足以支持售前演示、技术尽调和付费 Discovery，也可以进入设计合作客户的集成准备；还不能声称完成生产商业交付，因为真实环境、真实用户、真实集成和业务价值证据仍为 0。

## 建议把商业交付拆成三种完成状态

| 状态 | 完成含义 | 当前案例 |
|---|---|---|
| **Paid Discovery Complete** | 问题、范围、基线、数据、风险、方案和试点计划得到客户确认 | 基本具备模板和演练能力 |
| **Paid Shadow Pilot Complete** | 在客户授权环境处理真实数据，真实用户完成有限周期试用，但系统不自动对外执行 | 尚未完成 |
| **Production Delivery Complete** | 正式环境上线、真实集成运行、SLA/值班/安全/回退生效，并完成客户验收与移交 | 尚未完成 |

商业上最好分别签约、分别验收、分别收费，避免把 Discovery、Pilot 和生产上线塞进一个模糊的“AI 项目”。

# 一、必须和客户敲定的商业事项

## 1. 项目目标和范围

必须明确：

- 具体客户、部门、业务流程和区域
- 只做外贸询盘、售后工单，还是两者都做
- 输入渠道：邮箱、电话、CRM、CMMS、附件
- 系统输出：字段、候选、内部建议、回复草稿
- 哪些动作只建议、哪些允许人工批准后执行
- 明确不做什么
- 第一阶段用户数量、案例数量和起止日期
- 哪些变化属于缺陷，哪些属于 Change Request

交付物应形成客户签署的：

- Statement of Work
- Scope / Non-goals
- RACI
- Milestone 与付款节点
- Change Request 流程

## 2. 业务基线与价值指标

必须在上线前冻结基线，至少包括：

- 当前每类案例平均处理时间
- 工程师介入次数和分钟数
- 漏字段、返工和错误升级情况
- 当前积压与响应时间
- 人工处理成本
- 案例数量与复杂度分布

Pilot 验收不能只使用“准确率提高”，还要包含：

- Accept / Edit / Escalate / Abstain
- 人工修改幅度
- 每案节省时间
- 工程师负担变化
- 知识缺口
- 用户采用情况
- 每案模型与基础设施成本
- 事故数量和恢复时间

数值门槛应由客户和交付团队共同冻结，不能在 Pilot 结束后根据结果调整。

## 3. 验收定义

每个里程碑都要明确：

- 输入是什么
- 客户提供什么
- FDE 团队交付什么
- 用什么环境验证
- 谁负责测试
- 哪些指标必须达到
- 允许哪些已知限制
- 哪些缺陷会阻止验收
- 谁有签字权
- 超期未反馈如何处理

最终至少需要：

- 技术验收
- 业务 UAT
- 安全验收
- 运维验收
- 项目 Sponsor 验收

# 二、必须补齐的客户与法律边界

## 1. 数据处理约定

需要敲定：

- 数据的控制方和处理方
- 处理目的
- 授权数据源和字段
- 数据所在区域
- 数据保留期
- 删除、导出和授权撤销方式
- 是否允许数据进入模型服务
- 是否允许用于评估、微调或产品改进
- 日志和 Trace 可以保留哪些字段
- 供应商和子处理方名单
- 安全事故通知时限

真实数据必须使用 Git 外的客户数据面和 Secret Manager，不能通过修改示例 JSON 中的 `false` 来代替授权。

## 2. AI 责任边界

必须写入合同和产品界面：

- AI 输出是建议还是正式结论
- 哪些工况必须弃答
- 哪些工况必须工程师审核
- 谁对最终泵选型或维修决定负责
- 是否允许自动发送邮件
- 是否允许修改 CRM/CMMS
- 是否允许触发采购、报价或维修动作
- 错误建议如何上报、撤回和通知受影响人员

OWASP 将过多功能、权限和自主性视为 Excessive Agency 的主要风险，因此初始商业 Pilot 应保持只读、最小权限和人工确认。[OWASP Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)

## 3. 知识产权与成果归属

需要确定：

- 客户原始数据归属
- 客户标注和反馈归属
- 通用 Core 代码归属
- 客户专属 Adapter、规则和配置归属
- Prompt、评估集和模型配置归属
- 是否允许将脱敏经验用于其他客户
- 项目结束后代码、镜像和数据如何处置

# 三、生产技术需要达到的程度

## P0：正式数据面

必须完成：

- PostgreSQL Repository 替换 SQLite Runtime
- 独立 Runtime Role
- 所有租户表启用并强制 RLS
- 连接池复用不泄漏 Tenant Context
- 数据库迁移、回滚和兼容性验证
- 自动备份及恢复演练
- 加密、密钥轮换、保留期和删除
- 生产与测试环境隔离

PostgreSQL 表所有者和 `BYPASSRLS` 角色可能绕过 RLS，因此测试不能只覆盖普通查询，还要覆盖后台任务、导出、备份和管理脚本。[PostgreSQL RLS](https://www.postgresql.org/docs/17/ddl-rowsecurity.html)

## P0：企业身份

必须完成：

- 客户 OIDC Discovery
- Authorization Code + PKCE
- JWKS 公钥签名验证
- Issuer、Audience、Nonce、Expiry 检查
- MFA
- Group-to-role 映射
- 账户禁用和撤权
- Key Rotation
- 安全 Session Cookie
- CSRF、登出和会话超时
- Break-glass 账户与审计

OIDC 的 Discovery、`jwks_uri`、签名验证和 Key Rotation 应由真实客户身份租户验证。[OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html)

## P0：真实 Connector

至少完成一个真实邮箱和一个 CRM/CMMS Sandbox：

- OAuth 最小 Scope
- 分页和增量游标
- Webhook 验签
- 重复和乱序
- 更新、删除与撤回
- 附件和大小限制
- 429 与 Retry-After
- 超时和熔断
- Schema Drift
- 补数与对账
- 凭据撤销
- 客户 API 审计

Shadow 阶段仍应保持写入权限关闭。

## P0：可观测与运营

必须具备：

- OTLP Collector
- Trace、Metric、Log 关联
- 敏感字段允许列表
- 租户隔离
- 告警
- Dashboard
- Dead Letter 和积压告警
- 模型质量和成本告警
- 数据保留与删除
- 值班表
- 事故分级和响应时限

OpenTelemetry 建议通过 Collector 统一执行重试、批处理、加密和敏感数据过滤。[OpenTelemetry Collector](https://opentelemetry.io/docs/collector/)

## P0：恢复能力

必须实际演练：

- App 重启
- Worker 崩溃
- 数据库重启
- Connector 超时和限流
- 模型不可用
- 消息重复和乱序
- 数据版本回退
- 模型回退
- 数据库迁移回退
- 备份恢复
- Kill Switch
- 客户撤回授权

事故不能在“开始重试”时关闭，只能在业务状态恢复并完成验证后关闭。当前 Stage 14 已经实现了这一点。

# 四、AI 系统需要达到的程度

## 1. 独立评估集

需要由客户业务人员和工程师分别标注，保留：

- 原始判断
- 分歧
- 裁决
- 裁决人
- 理由
- 数据版本
- 标注时间

评估至少按以下切片报告：

- 正常案例
- 复杂案例
- 信息缺失
- 证据冲突
- 过期手册
- 高风险工况
- 转写错误
- 附件缺失
- 提示注入
- 跨租户请求
- 新客户或新产品分布

## 2. 模型与规则发布治理

每次发布应绑定：

- 模型 Provider 和版本
- Prompt 版本
- Rule Pack 版本
- Knowledge Snapshot
- 评估集版本
- 代码 Commit
- 镜像摘要
- 发布审批
- Canary 比例
- 回滚目标

## 3. 安全硬门

以下项目建议保持零容忍：

- 跨租户成功访问
- 未经批准的客户动作
- 泄漏直接标识符
- 引用不存在的证据
- 高风险案例绕过人工审核
- 被提示注入诱导执行工具
- 已撤权账户继续访问
- 无法恢复到已批准版本

NIST AI RMF 强调部署后的监测、人工覆盖、事故响应、恢复、停用和变更管理；商业验收应要求这些能力有真实运行证据。[NIST AI RMF Playbook](https://airc.nist.gov/docs/AI_RMF_Playbook.pdf)

# 五、运营和组织需要敲定

必须指定真实姓名或岗位：

- Customer Sponsor
- Customer Product Owner
- Customer Data Owner
- Customer Security Owner
- FDE Delivery Owner
- Technical Lead
- Model Owner
- Domain Expert
- Pilot Operator
- Release Manager
- Incident Commander
- Stop Owner
- On-call Primary / Secondary

还要明确：

- 工作时间和支持时间
- P0/P1/P2 定义
- 响应和恢复目标
- 升级联系人
- 客户沟通模板
- 周报和 Steering Meeting
- 事故复盘时限
- Stop/Iterate/Expand 签核人
- 项目结束后的支持团队

# 六、商业条款还需要补齐

建议明确：

- Discovery 费用
- Integration 费用
- Pilot 费用
- 正式上线费用
- 月度平台或支持费用
- 模型和云资源如何计费
- 超出案例量或 Token 预算如何处理
- 第三方费用由谁承担
- 付款里程碑
- 验收延迟的处理方式
- Change Request 费率
- SLA Credit
- 合同终止后的数据删除和系统下线

同时要做单位经济模型：

```text
单案收入或价值
- 模型成本
- 基础设施成本
- 人工审核成本
- 工程师支持成本
- 客户专属维护成本
= 单案贡献
```

如果每新增一个客户都需要修改 Core、重新做大量标注和长期驻场，项目可能可以交付，但还没有形成可扩展产品。

# 七、建议的商业验收 Gate

## Gate A：Discovery 签署

- SOW、范围、RACI、基线、数据源和验收指标签署
- 客户提供数据和人员承诺
- 商业报价与付款节点确认

## Gate B：Security & Integration Ready

- 数据协议和安全审查通过
- PostgreSQL、OIDC、Connector、OTLP 在客户测试环境通过
- UAT 和事故演练计划冻结

## Gate C：Authorized Shadow Start

- 有限用户、案例类型和期限冻结
- 所有输出仅内部可见
- 客户写入关闭
- Stop Owner 和值班生效

## Gate D：Paid Pilot Acceptance

- 达到预先冻结的质量、安全、采用、效率和成本门槛
- 无未解决 P0/P1 事故
- 客户签署 UAT 和 Pilot Acceptance
- 决定 Stop、Iterate 或 Production

## Gate E：Production Go-Live

- 正式身份、数据面、监控、备份、恢复和支持生效
- 生产变更和回滚演练通过
- 客户批准有限写入范围
- Go-live 签署

## Gate F：Final Handover

- 架构、代码、镜像、配置、Runbook、UAT 和培训完成
- 管理员和操作员培训完成
- 支持团队接管
- 已知问题与技术债被客户接受
- 最终验收签字
- 付款节点达成

# 当前最需要客户敲定的八件事

1. 首个真实设计合作客户是谁。
2. 唯一 Pilot Workflow 是什么。
3. 谁是 Sponsor、Data Owner、Security Owner 和 Stop Owner。
4. 哪些真实数据可以进入 Shadow。
5. 客户使用什么邮箱、CRM/CMMS、OIDC 和部署环境。
6. Pilot 的用户、案例数、期限和成功指标。
7. 是否只读，以及未来可能允许的第一个写入动作。
8. Discovery、Pilot、Production 各自如何收费和验收。

如果这八项还没有答案，继续增加更多模拟 Stage 的商业收益会快速下降。技术上最合适的下一步是完成 Stage 15 的真实生产栈演练；商业上最关键的下一步是找到一个具名 Design Partner，签署付费 Discovery 和有限 Shadow Pilot，而不是直接承诺生产上线。