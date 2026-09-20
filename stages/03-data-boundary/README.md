# Stage 3 · 数据发现、知识治理与 AI 边界

原始材料：[Stage 3 文档](source/original-stage-03.md)。本阶段提供可浏览的**合成资料包**及治理与评估设计。示例数据仅用来训练证据治理和边界设计；型号/材料规则不得用于真实选型。

## 运行

从项目根目录：

```bash
python3 stage_pipeline.py stage2
python3 stage_pipeline.py stage3
python3 stage_pipeline.py all
python3 -m unittest discover -s tests -v
```

`stage3` 检查 20 对询盘与回复、10 个订单、5 个特殊案例的链接与数据结构，输出数据质量报告及设计阶段退出检查到 `outputs/stage-03/`。`all` 顺序运行 Stage 1–3。退出状态 `DESIGN_READY_FOR_REVIEW` 表示演练材料满足设计审查的结构条件；不代表通过 Release Gate、获得真实客户批准或可立即上线。

## 学习顺序

1. [数据审查演练](guides/data-review-workshop.md) 与 [合成数据说明](data/README.md)。
2. 浏览 `data/bundle/`：原始 `.eml`、产品表的 JSON 教学替身、订单、FAQ 与技术聊天摘录。
3. 用 [空白治理工作本](templates/governance-workbook.md) 独立标注，再对照 [交付物索引](deliverables/README.md)。
4. 运行检查，打开 `outputs/stage-03/audit-report.md`，修复故意引入的路径或引用错误。
5. 阅读 [Stage 4 交接](deliverables/10-stage-4-handoff.md)，明确哪些只属于未来开发。

原稿示例 E-001 使用 P90，而 Stage 2 为 CP90；且介质未明确，无法确认任何最终型号。本项目统一把它记为“待验证候选 CP90”，评估标签只要求提出澄清、标记风险和保留人工复核，不把 CP90 写成最终正确选型。
