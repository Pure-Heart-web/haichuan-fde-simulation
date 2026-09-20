# 复现与验收

1. 运行 `python3 run.py validate`，应显示 6 条观察、3 个访谈角色和输入校验通过。
2. 运行 `python3 run.py demo`，打开 `outputs/stage-01/README.md` 和六项交付物。
3. 核对 `05-baseline-metrics.md`：销售主动处理总计 202 分钟、均值 33.67 分钟；复杂样本均值 51 分钟，简单样本均值 16.33 分钟；升级 3/6；工程师总投入 56 分钟。
4. 核对复杂样本：产品选型平均 15 分钟、需求整理 12.33 分钟，报价 3.33 分钟。这支持进一步验证知识和需求整理瓶颈，但不能证明系统价值或全年节省。
5. 查看退出条件：应为 `SIMULATION_READY`。这只是练习场景已满足模拟证据要求。
6. 执行 `python3 -m unittest discover -s tests -v`，验证计算、证据检查和真实/模拟边界。

## 反事实练习

复制 `simulation.json` 到 `outputs/practice.json`，将副本中所有 `sources[].path` 改为 `../stages/01-discovery/data/session-notes.md`（来源路径相对于输入文件），再修改练习字段并运行：

```bash
python3 run.py analyze --input outputs/practice.json --output outputs/practice-report
```

| 修改 | 预期结果 |
|---|---|
| 删除工程师访谈记录 | 报告仍生成，角色条件失败，退出码 3 |
| 将 `checks.error_cost.confirmed` 改为 false | 错误成本条件失败，不可进入下一阶段演练 |
| 将某观察的 `source_id` 改为不存在的 ID | 数据无效，退出码 2，不生成新报告 |
| 将回复时间改为收件之前 | 数据无效，退出码 2 |
| 删除一个观察步骤 | 数据无效，不能用 0 悄悄替代缺失记录 |
| 仅把 `mode` 改成 real | 由于证据仍为 simulation，拒绝作为真实项目输入 |

如果运行失败，以终端的退出码和错误为准；目标文件夹可能保留上次成功生成的报告，不代表本轮成功。比较报告页头的数据集 ID 与生成时间。

## 接入新的演练数据

先写原始记录和证据编号，再改 JSON；不要为了通过检查补造证据。观察数不足或缺访谈等属于 Discovery 未完成，允许生成缺口报告。负数、时间错序、悬空引用、步骤漏记属于数据质量错误，先修复再分析。

真实项目需改用真实且授权的脱敏资料，逐项审阅 `assessment`、`decisions`、`questions` 和 `checks` 中人工填写的内容。工具仅检查结构与引用，不会验证证据是否真实、推断是否正确。`REAL_REVIEW_REQUIRED` 只表示可供负责人审阅，不是开工批准。
