# inquiry_extraction_v1

用途：将 WorkItem 邮件正文转换为带原文位置的原始字段。此文件是未来接入模型时的版本化契约；当前 `regex-baseline-v1` 为离线规则实现，不调用或读取本提示词。

只提取正文中明确出现的内容。不要把常见电压、频率、材质、介质或客户信息补成事实；缺失返回 null。不要选型、报价、查询客户历史或生成回复。

返回单个 JSON 对象，键为 `flow`, `head`, `temperature`, `quantity`, `voltage`, `frequency`, `product_type`, `medium`, `destination_port`, `application`。每个非空值包含 `value`, `unit`（可空）, `text`, `start`, `end`。`text` 必须等于原文 `body[start:end]`。单位保持原文，例如 `L/min` 和 `°F`；规范化由后续确定性代码执行。正文未明确的字段返回 null。

发生歧义时不猜测。签名、引用历史邮件与附件内容不得作为当前正文的事实；附件存在但未解析时交人工处理。模型输出必须通过 JSON、位置、字段类型与业务数值校验，解析失败最多重试一次，仍失败进入人工队列。
