# Sprint 3 教学审查与 Stage 7 交接

已完成 CustomerEntity、精确优先身份解析、ContextProvider、最近相关已完成订单、字段来源标签、知识元数据治理和检索、KnowledgeEvidence、Claim Policy、内容计划、租户风格、回复草稿、弃答、知识缺口反馈、三层合成评估、本地审核页面和显式编排。运行 `python3 stage_pipeline.py all` 与测试可复现。

尚未拥有真实客户身份授权、有效保修/认证源、生产订单 API、人工销售审核数据或邮件发送审批。Stage 3 的缺口仍然成立；Stage 6 新资料仅是教学模拟批准。`real_data_release_gate=NOT_EVALUATED`、`sent_messages=0`。当前高分只证明给定合成样本下规则运行一致，不表示实际 Pilot 的客户解析、知识正确率或业务收益。

Stage 7 前应由客户确认身份主数据 owner、订单“最近相关已完成”的业务定义、文档生效与撤销流程、销售/工程师角色权限、审核责任与回滚，以及可观测性、延迟/成本和事故响应。先进行 shadow mode 与人工比较，再考虑真实邮箱接入和发送动作。
