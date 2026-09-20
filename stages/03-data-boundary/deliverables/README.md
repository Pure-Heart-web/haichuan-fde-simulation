# Stage 3 交付物索引

| 文件 | 用途 |
|---|---|
| [01 Data Inventory V1](01-data-inventory.md) | 来源、质量与类别 |
| [02 Source of Truth & Conflict Register](02-source-of-truth.md) | 字段级权威、冲突与剩余风险 |
| [03 Identity & Tacit Knowledge](03-identity-and-rules.md) | 客户身份与规则候选治理 |
| [04 Security Classification](04-security.md) | 数据敏感级别与模型上下文约束 |
| [05 AI Boundary Matrix](05-ai-boundary.md) | 每个任务的主要机制、复核与失败动作 |
| [06 Architecture V0](06-architecture.md) | 数据流和可控交接点 |
| [07 Core Data Contracts](07-data-contracts.md) | 对象字段和不变量 |
| [08 Golden Dataset V0](08-golden-dataset.md) | 20 个合成样本标签与评估设计 |
| [09 Release Gate V0](09-release-gate.md) | 假设门槛和退出检查 |
| [10 Stage 4 Handoff](10-stage-4-handoff.md) | 第一开发切片与团队分工 |

机器可读来源：[`manifest.json`](../data/manifest.json)、[`source-of-truth.json`](../data/source-of-truth.json)、[`conflicts.json`](../data/conflicts.json)、[`identity.json`](../data/identity.json)、[`rules.json`](../data/rules.json)、[`golden.json`](../data/golden.json)。运行 `python3 stage_pipeline.py stage3` 会核对数量、引用和隔离边界，并写出动态审计报告。静态文档是供人讨论的设计版本，机器检查不证明业务内容已由真实客户批准。
