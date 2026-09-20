# Source of Truth & Conflict Register

## 按业务域指定来源

| 域 | 来源 | 状态 | 使用边界 |
|---|---|---|---|
| 技术参数 | SRC-TECH | 模拟场景内已由陈工确认 | 只覆盖表内字段，不能推出最终适用性 |
| 销售描述 | SRC-MASTER | 暂定 | 技术字段不得覆盖 SRC-TECH |
| 客户历史 | SRC-ORD | 暂定 | 身份归并需销售运营确认 |
| 标准价格 | SRC-QUOTE | V1 范围外 | 时效和权限待核 |
| 特价 | SRC-DISC | 仅经理审批 | 不进入模型上下文 |
| 保修/认证 | 未提供 | 缺失 | 不生成确定性承诺 |

机器可读注册表：[source-of-truth.json](../data/source-of-truth.json)。优先级是**按字段与用途**定义的，不能说“最新 Excel 对所有问题都可信”。

## 冲突 D-001

CP90 在 SRC-TECH 中为 Flow 80–100、Head 35–42、Material SS316；在 SRC-MASTER 中为 Flow 75–95、Head 32–40、Material SS304。模拟会议里陈工确认技术参数以 `Pump_Selection_NEW` 为准，故 D-001 对这些字段标为 `resolved_for_technical_fields`。仍缺性能曲线、介质确认和真实版本批准日期，**不能将 CP90 判定为 Inquiry #017 的最终选型**。见 [conflicts.json](../data/conflicts.json)。

新的冲突流程：记录实体/字段/两份来源/版本/Owner → 将受影响字段隔离 → 等 Owner 批准及生效日期 → 更新注册表和评估样本 → 留审计痕迹。仅凭 `NEW`、`Final_v2` 等文件名不得自动决定权威。
