# 合成客户资料包

`bundle/` 是用于教学的压缩包替身，所有邮箱、公司、价格、型号和订单都虚构。只存储 UTF-8 文本，以便不用 Excel、PDF 或外部服务即可浏览、比较版本和运行审计：

| 原稿中的文件 | 本案例替身 | 限制 |
|---|---|---|
| 20 条 inquiry_*.eml + 20 条 reply_*.eml | `bundle/inquiries/`、`bundle/replies/` | 邮件为合成，回复由人审的场景文本；不包含真实附件 |
| 产品 Excel：Selection_NEW、Master_Final_v2 | `bundle/products/*.json` | 保留冲突字段与来源，不模拟 Excel 格式细节 |
| Catalog 2024/2025 PDF | `bundle/products/catalog_*.md` | 展示版本冲突摘录，不是可用于选型的产品目录 |
| 10 个成交订单 | `bundle/orders/orders.json` | 客户别名待核验，不含真实客户身份 |
| 5 个失败/特殊案例 | `bundle/special_cases.json` | 错误与补问场景，不等于真实事故 |
| FAQ、技术咨询记录 | `bundle/faq.md`、`bundle/tech_chat.txt` | 未批准的聊天不能当权威规则 |
| 标准价/客户特价 | `bundle/pricing/*.json` | 仅虚构占位；高敏感数据禁止进入模型上下文 |

`manifest.json` 逐项记录数据类别、Owner、敏感级别、文件与候选可信度。`golden.json` 保存 20 个询盘的设计标签，作为 Stage 4 评估集草稿。标签中的 `preferred_candidate` 为空：缺少批准的性能曲线和充分工况，不能把教学型号当真值。`source-of-truth.json`、`conflicts.json`、`identity.json`、`rules.json` 是治理决定及未决事项的机器可读版本。

数据规范：来源路径均相对于本目录；ID 全局唯一；Golden Case 的 inquiry/reply 路径必须存在且数字配对；订单至少 10 条；特殊案例至少 5 条；`candidate` 规则不能在运行时当成 `verified`；`Highly Sensitive` 来源必须禁止进入生成模型上下文。
