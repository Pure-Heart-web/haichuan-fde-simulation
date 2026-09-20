# 第一轮 Failure Review · 实际合成数据结果

运行 `python3 stage4.py eval` 生成可复算的 [动态报告](../../../outputs/stage-04/eval-report.md)。本次离线正则基线在 100 条合成样本、900 个字段比较上的微平均准确率为 **96.7%**；非空字段 96.4%、空值字段 100%。流量与温度分别只有 **90%**，未达到当前“每字段 ≥95%”的练习门槛。解析失败率 0%，因为本次基线始终产生合法 JSON；这不代表外部模型解析可靠。

| 失败簇 | 当前证据 | 分类 | 下一步 |
|---|---|---|---|
| S4-031–035 | `cubic meters per hour`、`total dynamic head of ... metres` 未提取 | 自然语言表达覆盖 | 明确支持单位词形与前后置 Head，再补反例 |
| S4-036–040 | `degrees Celsius` 与 `machines` 未提取 | 单位/数量词形覆盖 | 规范化和抽取分别修正；防止误提签名数字 |
| S4-051–055 | `liters per minute`、`degrees Fahrenheit` 未提取 | 单位词形识别 | 扩展原始单位识别，保持换算在确定性层 |
| F-001（原稿教学对话） | `cooling water` 与 `water` 标签颗粒度争议 | Ontology / Schema | 采用 `medium_category` + `medium_description`，业务 Owner 复核 |
| F-003（原稿教学对话） | 介质只在附件中 | Attachment coverage | Sprint 1 标记 `attachment_processing_required`，后续单列附件解析任务 |

本项目的中英混合和 HTML 样本在当前合成集全对，原因是模板覆盖有限；不能推断真实邮件中这两类输入已解决。数据契约将 `medium_category` 与 `medium_description` 分开，展示层可组合“Cooling Water / Centrifugal Pump”，底层仍保持产品类型和应用分离。

**技术投资判断。** 30 个字段差异来自表达覆盖和单位词形，当前没有 LLM 模型能力对照数据，因此没有证据支持“换模型更好”。优先补输入标注、词形处理和审核样本，再决定是否接入或比较模型。
