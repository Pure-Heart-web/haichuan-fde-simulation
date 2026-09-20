# 启航合成 Shadow 故障复盘

`python3 stage8.py incident` 在同一条 `QH-001`、同一套抽取/知识/资产数据上比较两次**离线排序**：旧逻辑虽然读到 `WO-QH-110`，但未把“昨日报养、装配确认待完成”传入决策，Top-1 是 `inspect_intake_condition`；售后 Domain 修正后 Top-1 是 `review_maintenance_work_order`。没有客户看见旧建议，也没有真实 Shadow 部署或维修事故。

| 排查层 | 证据 | 结论 |
|---|---|---|
| Extraction | QH-75、序列号、E37、5/8 bar、异响和最近保养被抽取 | 不是本次主因 |
| Context | 资产档案找到 `WO-QH-110`，日期早于请求且在七日内 | 数据可用，但旧决策没用它 |
| Knowledge/Rule | 现行 E37、保养和安全片段可取；异响触发高风险审核 | 安全阻断仍生效 |
| Diagnosis ranking | `use_context=False` 的进气条件先于维修工单；`True` 则相反 | 根因在售后 Domain 排序输入 |
| Human / external | 两个版本都仍需工程师审核，不输出自动维修步骤 | 没有对外传播 |

修复放在 `domains/after_sales/diagnosis.py`，增加回归样本并保持 Trace 的资产来源、规则/知识版本和候选顺序；暂**不**把“context-aware decision input”抽成 Core。海川的“same as previous order”显示类似模式，但二者历史语义与冲突规则不同，需要第三次独立验证才可能稳定抽象。真实事故还需影响面、已对外内容、止损时间、负责人、客户通知和签核记录。

第二个 UX 风险是照搬销售页面：售后工程师需要设备、维修史、风险与内部检查选项。Stage 8 新页面只复用任务/反馈机制，展示层单独开发；它不是生产前端或权限系统。
