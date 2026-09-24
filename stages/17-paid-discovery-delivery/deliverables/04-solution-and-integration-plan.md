# Discovery Deliverable 04：Pilot 方案与集成计划

## 单一工作流

只读邮箱/事件源 → 入库前过滤 → 租户作用域 Inbox → 抽取与需求缺口 → 产品/知识证据 → 暂定建议 → 销售/工程师审核 → 待发送区 → 人工确认结果。Shadow 不写客户系统、不自动发送、不形成约束性报价。

## 环境和控制

- PostgreSQL Runtime Role 与强制 RLS，连接池使用事务内租户上下文；
- Authorization Code + PKCE 的企业 OIDC，MFA、组映射、撤权和轮换；
- OAuth 最小只读 Scope，分页、游标、Webhook、重复、乱序、更新、删除、429 和 Drift；
- OTLP Collector 执行属性允许列表、租户哈希、重试、批处理和保留；
- Model Gateway 绑定模型、Prompt、规则、知识、评估集、Commit 和镜像摘要；
- Kill Switch、Dead Letter、备份恢复、模型/规则/迁移回退和授权撤回演练。

## 实施顺序

Contract/Data/Security Gate → Sandbox 身份和 Connector → PostgreSQL/OTLP → 数据映射和回归 → UAT → 三班次演练 → 有限用户 Shadow。任何一步失败保持待审核或 Stop，不以静态配置替代运行证据。
