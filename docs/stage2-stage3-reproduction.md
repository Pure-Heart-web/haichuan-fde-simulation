# Stage 2–3 复现与反事实练习

从项目根目录运行：

```bash
python3 stage_pipeline.py all
python3 -m unittest discover -s tests -v
```

预期输出依次为 `SIMULATION_READY`、`STAGE2_READY_FOR_DATA_DISCOVERY`、`DESIGN_READY_FOR_REVIEW`。打开 `outputs/stage-02/audit-report.md`、`outputs/stage-03/audit-report.md`，以及各阶段 `deliverables/README.md`。这三个状态仅用于模拟练习，不是客户签约、开发批准或 Release Gate 达标。

## Stage 2：证据纪律练习

先只读 #017 原始叙事，在空白模板中分别列出观察、主张、假设和未知。对照参考交付物，特别检查：15/30 分钟是否被误写为计时结果；“每天几十次”是否被当基线；“损失几万”是否被当财务事实；CP90 是否被当最终合格型号。用一页纸说明下一轮如何获得可推翻这些判断的数据。

## Stage 3：数据审计练习

`scripts/build_stage3_fixture.py` 可从源码重建**合成**资料包，会覆盖 `stages/03-data-boundary/data/` 中生成的 JSON 和邮件；请只在准备恢复演练数据时使用。做反事实练习应复制整个 `stages/03-data-boundary/data/` 到 `outputs/practice-stage3/`，编辑副本并运行：

```bash
python3 stage_pipeline.py stage3 --stage3-data outputs/practice-stage3 --output-root outputs/practice-result
```

| 修改副本 | 预期 |
|---|---|
| 将 `SRC-DISC.model_context` 改成 `approved_extract_only` | 审计失败，特价禁止入模型上下文 |
| 把 E-001 的回复路径指向 reply_002 | 审计失败，邮件配对错误 |
| 给 E-001 填 `preferred_candidate=CP90` | 审计失败，未批准的最终型号 |
| 把 `identity.entities[0].autolink_allowed` 改为 true | 审计失败，暂定身份不得自动关联 |
| 从 D-001 的 `fields` 删除 `material` | 审计失败，冲突台账未覆盖实际差异 |

失败命令返回退出码 2；报告目录可能仍存上次的成功报告，复核时以本次终端输出及报告的生成时间为准。检查程序只检验练习资料的结构、引用和明确边界，不证明真实来源权威或规则工程正确。
