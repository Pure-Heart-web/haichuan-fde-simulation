# 从教学分支转换为真实付费 Discovery

不要编辑教学 JSON 把 `simulated` 改成 `real`。为每个客户创建 Git 外 Deal Room 和客户数据面，只在代码仓库保留不含敏感信息的 Schema、适配器、测试和摘要。

## 必须替换

- 真实合同主体、Deal/Contract/PO ID、有效期和授权签字人；
- 具名 Sponsor、Process/Data/Security/Procurement/Acceptance/Stop Owner；
- 客户批准的范围、Non-goals、日期、交付物和接受标准；
- 实际费用、税、付款条件、成本预算和 Change Rate；
- 客户系统中的数据授权、安全评审、身份和 Connector 证据；
- 真实观察记录、基线和客户意见；
- 客户自己的 Acceptance、发票和付款系统状态。

## 可以复用

合同到验收的状态机、内容摘要绑定、依赖和变更结构、交付物目录、指标口径模板、开票释放清单、Stage 1–16 的代码/测试/Runbook，以及真实数据不进 Git 的边界。

## 真实证据引用

仓库只保存 `evidence_id`、类型、Owner、日期、状态、外部系统引用和必要的不可逆摘要。不要保存合同原文、客户名单、邮件原文、凭据、个人信息或可还原的业务数据。访问和保留按客户协议执行。

真实 Paid Discovery Complete 需要客户授权验收人签署交付物，且合同/财务系统确认对应里程碑。技术团队不能在代码中自行生成这些事实。
