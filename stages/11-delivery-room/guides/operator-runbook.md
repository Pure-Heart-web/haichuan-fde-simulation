# Delivery Room 运行与值班手册

## 每班开始

1. 检查 `/health`、Inbox/Outbox Dead Letter、待审核积压和最长等待。
2. 检查 Connector 凭据有效期、客户 Schema 版本和知识/规则版本。
3. 确认当班销售、工程师、Release Manager 与事故负责人。
4. 核对 Stop 开关和回退路径可用。

## Worker Dead Letter

先停止对应来源的继续回填，保留事件 ID、来源版本和错误类别。判断是临时依赖故障、数据错误还是 Schema 漂移。临时故障恢复后重放；Schema 漂移需更新映射、用隔离样本回归并由数据 Owner 批准。不得直接改数据库状态跳过验证。

## Outbox Dead Letter

确认消息已有审核人与不同 Release Manager，检查 Mock/客户端点状态和 Idempotency-Key。未知投递结果时先查询目标系统，避免盲目重发。恢复后使用同一 Key 重放。真实项目需由业务 Owner 决定是否改走原人工渠道。

## 安全或越权

发现跨租户、敏感信息或未批准投递时立即关闭 Connector 与 Dispatcher，保存只含引用的审计记录，通知安全和数据 Owner，评估影响范围并启动删除/通知流程。未经事故负责人批准不恢复。

## 每班结束

记录新增、更新、重复、Retry、Dead Letter、积压、人工修改、专家分钟、Mock/真实投递和事故。合成演练中的脚本动作必须标为 roleplay，不能计入真实采用或客户收益。
