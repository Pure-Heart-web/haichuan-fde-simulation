# Delivery Room UAT 检查表

- [ ] 新事件、完全重复、内容变化和连续更新符合来源契约
- [ ] 服务重启后 Inbox、审核和 Outbox 不丢失
- [ ] Worker 租约过期可以恢复，失败达到上限进入 Dead Letter
- [ ] 来源更新重新打开审核，旧未投递意图失效
- [ ] 错误角色、其他租户和过期身份全部拒绝并记录审计
- [ ] 提示注入、高风险和关键信息缺失按策略路由
- [ ] 审核人与 Release Manager 分离
- [ ] 未批准 Outbox 无法投递
- [ ] 重试使用相同 Idempotency-Key，不产生重复业务动作
- [ ] Trace 能重建来源、版本、系统结果、人工动作和投递结果
- [ ] 指标来自事件库；合成、Mock 和真实指标明确分开
- [ ] Stop、回退、恢复和复盘演练完成

UAT 结论：`REJECT / ITERATE / ACCEPT FOR CONTROLLED SHADOW`  
业务 Owner：`_____`　安全 Owner：`_____`　数据 Owner：`_____`　日期：`_____`
