# Stage 5：产品搜索、规则、推荐与专家知识工程

本阶段把已结构化的询盘接入**仅支持标准离心泵**的离线教学切片：产品规范化 → 确定性硬筛 → 有版本规则 → 透明排序 → 暂定建议 → 人工审核。企业、产品和指标均为模拟；不提供最终选型、报价、库存判断或客户发送功能。

## 五分钟复现

在仓库根目录使用 Python 3.10+；不需依赖包、网络或 API Key：

```bash
python3 stage5.py demo
python3 stage5.py review
```

浏览器打开 `http://127.0.0.1:8766/`，选择 `MATCH-006` 查看海水询盘中 `CP85-CI` 被规则排除，尝试用 sales 角色批准会被拒绝；用 engineer 角色审核暂列首位或点击升级。`MATCH-012` 演示高温且没有合格产品时仍触发规则；`MATCH-001` 演示销售可审的清水单候选。页面仅绑定本机回环地址，审核事件追加保存到 `outputs/stage-05/recommendations.sqlite3`。再次 `demo` 不覆盖已有建议或审核事件。推荐即使获人工批准，仍是教学候选，不是报价或工程选型。

单条输入与 Stage 4 联动：

```bash
python3 stage5.py recommend --inquiry stages/05-product-recommendation/data/example-inquiry.json
python3 stage4.py demo
python3 stage4.py review
python3 stage5.py from-stage4
python3 stage5.py eval
python3 stage_pipeline.py all
python3 -m unittest discover -s tests -v
```

`from-stage4` 只导入 Stage 4 最后一次人工事件为 approve/edit 的记录；未审核或 reject 的记录跳过。Stage 4 的 `review` 在本机 `8765`，Stage 5 在 `8766`。`recommend` 输出只读 JSON，不写审核库；需要新的队列可用 `demo` 或 `from-stage4`。输出默认写入 `outputs/stage-05/`，可用 `--output` 指定其他目录。

## 阅读顺序与交付物

1. [Sprint 2 演练计划](guides/sprint-plan.md)：角色、练习步骤与验收证据。
2. [数据和规则治理](guides/data-and-rule-governance.md)：权威字段、隔离、规则生命周期。
3. [ADR：产品推荐与文档检索](deliverables/adr-product-search.md)：为什么先硬筛再排序。
4. [评估协议](guides/matching-eval.md)：标签、分母和实际合成结果。
5. [失败复盘与技术债](deliverables/failure-review-and-debt.md)：误升级、范围边缘与补数触发条件。
6. [Sprint 2 审查和交接](deliverables/sprint-review.md)：完成证据、未通过的真实数据门槛、下一阶段准备。
7. [原始 Stage 5 文档](source/original-stage-05.md)：保留原稿，供对照。

可先填写 [审核练习记录模板](templates/review-notebook.md) 再看报告。运行得到的 JSON/Markdown 报告在 `outputs/stage-05/`，不会提交到仓库；静态交付物记录设计判断与当前合成基线。

## 模块地图

| 模块 | 作用 |
|---|---|
| `products/catalog.py` | 读取 Stage 3 技术权威表，合并 Stage 5 明示扩展，隔离歧义数据 |
| `products/search.py` | 状态、产品族、流量、扬程、温度、频率硬筛 |
| `core/rules/engine.py` | 白名单 DSL；仅执行 `active_in_simulation` 规则 |
| `products/ranking.py` | 区间中心距离代理分数；无性能曲线 |
| `recommendation/service.py` | 排除、排序、升级、证据和暂定建议 |
| `recommendation/store.py` | 不可覆盖建议、追加式人工审核事件 |
| `apps/recommendation_web.py` | 本机审核页面，按角色限制批准 |
| `recommendation/eval.py` | 合成标签评估与逐案失败输出 |

Stage 3 的 `Pump_Selection_NEW.json` 是流量、扬程和材质的模拟权威来源。原始 Stage 5 文稿中的示例区间若与其冲突，以 Stage 3 已登记的来源决定为准。Stage 5 扩展只增加温度、频率和教学状态，不覆盖上述权威字段。没有性能曲线，`range_edge_proxy` 绝不能解释成实际最佳效率区间。
