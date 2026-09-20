# Stage 4 · Build Sprint 1

这是一条可运行的**教学切片**：`.eml` / 纯文本 → WorkItem → 原始字段抽取 → 单位规范化 → 校验 → InquiryRecord → 本地人工复核 → 不可覆盖的反馈事件 → 100 条合成样本离线评估。原始要求保留在 [Stage 4 文档](source/original-stage-04.md)。

当前抽取器是可替换的离线 `regex-baseline-v1`，不调用 LLM 或外部 API。它用来验证契约、异常路径和评估循环；版本化 [抽取提示词](../../src/fde_platform/domains/foreign_trade/prompts/inquiry_extraction_v1.md)为后续模型接入提供约束。20 条 Stage 3 邮件进入人工审核队列，另用 100 条新合成案例计算基线。两批都是模拟数据，不代表实际 Pilot 准确率。

## 直接体验

在项目根目录运行：

```bash
python3 stage4.py demo
python3 stage4.py review
```

打开终端显示的 `http://127.0.0.1:8765/`，选择一封邮件，可查看原文和字段，执行“批准原结果 / 保存更正 / 拒绝”。更正会在 `outputs/stage-04/review.sqlite3` 中新增审核事件，保留原抽取记录。按 `Ctrl+C` 停止本地服务。页面只监听本机，不含多用户身份认证，不能部署为客户生产页面。

只跑评估与回归检查：

```bash
python3 stage4.py eval --check-baseline
python3 -m unittest discover -s tests -v
```

处理单条邮件或文本：

```bash
python3 stage4.py process --eml stages/03-data-boundary/data/bundle/inquiries/inquiry_001.eml --source-id my-case
python3 stage4.py process --text 'Need 2 pumps. Flow 85 m3/h, head 38m, 380V/60Hz.' --source-id manual-001
```

`demo` 对同一 WorkItem 去重，重复运行不会覆盖既有人工审核。生成文件在 `outputs/stage-04/`：`review.sqlite3`、`telemetry.jsonl`、`eval-report.json/md`、`sprint-status.json/md`。`outputs/` 被 Git 忽略，避免把本地审核数据误提交。重建评估集请运行 `python3 scripts/build_stage4_eval.py`；它会覆盖合成标签文件，修改时先复制。

## 浏览资料

- [Sprint 计划、Issues 与验收标准](guides/sprint-plan.md)
- [设计审查与模块边界](guides/architecture-review.md)
- [评估方法与回归检查](guides/eval-method.md)
- [失败案例复盘与本次实测](deliverables/01-failure-review.md)
- [Sprint Review 和退出条件](deliverables/02-sprint-review.md)
- [Stage 5 交接](deliverables/03-stage-5-handoff.md)
- [ADR-005：事实、推断和默认值分离](../../docs/adr/ADR-005-no-silent-defaults.md)

## 当前结果的边界

本次 100 条合成集总体字段微平均为 96.7%，但流量、温度各为 90%，因此**每个关键字段至少 95% 的离线假设门槛未满足**。真实 100 条客户风格询盘、销售现场复核、模型成本和延迟都尚未采集；`sprint-status` 会保留此缺口。没有产品推荐、RAG、客户历史、报价、自动回复或自动发送。
