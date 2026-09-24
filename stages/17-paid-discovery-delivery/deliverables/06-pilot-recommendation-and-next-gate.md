# Discovery Deliverable 06：Pilot 建议与下一 Gate

## 建议

`ITERATE / PREPARE AUTHORIZED SHADOW`。技术与流程演练支持继续准备，但真实 Shadow 不得开始，直到八项外部依赖全部关闭。

Pilot 候选范围：3 名销售、1 名工程师、英文离心泵询盘、4 周前测与 4 周 Shadow、只读邮箱和 CRM 查询、全部输出仅内部审核。具体用户、案例上限、日期、目标、费用和验收人由真实客户签署。

## Stop 条件

跨租户访问、直接标识符泄漏、未经批准的客户动作、虚假证据、高风险案例绕过人工、撤权后仍可访问、无法回滚到批准版本、未按时通知严重事故。Stop 后只有指定 Sponsor/Security/Delivery/Stop Owner 按恢复证据批准才能继续。

## 下一 Gate 外部证据

具名 Design Partner 与 Pilot SOW；真实数据和外置数据面授权；PostgreSQL 运行证据；企业 OIDC；Connector Sandbox；OTLP 后端；客户 UAT；值班和事故演练。任何教学 JSON 中的 `false` 不能由交付团队自行改成 `true`。
