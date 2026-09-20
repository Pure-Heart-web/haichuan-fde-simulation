# Data Inventory V1 · 合成资料

完整逐项元数据见 [manifest.json](../data/manifest.json)。所有数据均为教学虚构，Excel 与 PDF 在本案例中使用 JSON 和 Markdown 摘录替身；没有真实附件或生产系统 API。

| 来源 ID | 数据类别 | 用途 | Owner | 当前质量与可信状态 |
|---|---|---|---|---|
| SRC-INQ / SRC-REP | Data | 20 对询盘及回复 | Sales | 合成且定向设计，无实际邮件附件 |
| SRC-TECH | Structured Data | 技术参数 | Technical | 模拟会议确认字段权威，缺曲线和实物规格 |
| SRC-MASTER | Structured Data | 销售描述 | Sales | CP90 技术字段与 SRC-TECH 冲突，不能用于技术决策 |
| SRC-CAT24 / SRC-CAT25 | Knowledge | 对外资料 | Marketing/Technical | 2024 归档，2025 可能落后于技术表 |
| SRC-ORD | Context | 10 个历史订单 | Sales Operations | ABC Marine 别名待身份核查 |
| SRC-FAQ | Knowledge | 常见问题 | Sales | 保修与认证权威文件未提供 |
| SRC-CHAT | Tacit Knowledge | 技术聊天线索 | Technical | 无版本和完整上下文，需提炼、验证 |
| SRC-QUOTE | Pricing Data | 标准价 | Sales | 时效待核，V1 范围外 |
| SRC-DISC | Sensitive Policy | 客户特价 | Management | 高敏感，仅经理审批流程可用 |

**覆盖边界。** 本演练包具备 20/20 邮件配对、10 个订单和 5 个特殊案例，但均是合成数据。原稿提出的销售培训 PPT、完整 PDF、实际曲线、批准保修政策、证书库和真实 IT 权限尚未提供。它们属于数据缺口，不能被清单的“文件数够了”掩盖。

**五类信息的使用。** 产品技术字段属于 Structured Data；历史订单属于 Context；FAQ/目录属于 Knowledge；经批准的条件约束属于 Rules；聊天和陈工经验属于 Tacit Knowledge。报价和特价单独管理敏感性，不混入一般知识库。
