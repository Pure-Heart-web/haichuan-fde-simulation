# 海川工业泵 · FDE 交付学习案例

这是一个可复现的模拟客户项目。目前完成 **Stage 1–3 的业务与数据设计资料，以及 Stage 4 的可运行 Sprint 1 教学切片**。后续阶段按新需求继续扩展。

企业、联系人、邮件、型号、订单和指标均为教学虚构。样本中的数值用于练习分析，不是客户真实业务事实，也不是工业泵选型依据。

## 10 分钟运行

需要 Python 3.10 或更新版本，无第三方依赖、API Key 或网络要求。在本文件所在目录打开终端：

```bash
python3 stage_pipeline.py all
python3 -m unittest discover -s tests -v
```

`all` 依次运行四个阶段：Stage 1 生成六项 Discovery 交付物，Stage 2/3 生成资料与数据审计报告，Stage 4 将 20 封合成邮件导入审核队列并运行 100 条合成评估。结果分别保存在 `outputs/stage-01/` 至 `outputs/stage-04/`。Stage 4 的已有人工审核不会因重复运行而覆盖；动态报告会更新。

分析自己的演练记录：

```bash
python3 run.py analyze --input stages/01-discovery/data/simulation.json --output outputs/my-session
```

Stage 1 输入规范见 [数据说明](stages/01-discovery/data/README.md)。`run.py` 的退出码 `0` 表示检查通过或报告成功生成；`2` 表示数据无效；`3` 表示报告已生成但 Stage 1 退出条件尚未齐全。`stage_pipeline.py` 的 `0` 表示教学流程与回归检查已完成；Stage 4 会如实报告未达门槛字段。设计审计通过不表示已达到产品发布门槛。

Stage 1–3 资料可用任意 Markdown 阅读器浏览；Stage 4 的人工复核需启动本地页面。需要修改行为时，从 [Stage 1 命令入口](run.py)和 [Stage 4 命令入口](stage4.py)阅读；这套工具没有调用外部大模型，生成结果可以直接追溯到本地输入。

## 建议阅读和练习顺序

1. [学习路线与阶段边界](docs/learning-roadmap.md)：理解每阶段要作出的决策。
2. [Opportunity Brief](stages/01-discovery/guides/opportunity-brief.md)：带着假设进入会议。
3. [Discovery 执行计划](stages/01-discovery/guides/discovery-plan.md)：安排访谈、观察和取样。
4. [演练手册](stages/01-discovery/guides/workshop.md)：个人练习或团队分角色练习。
5. [记录模板](stages/01-discovery/templates/discovery-notebook.md)：先自行记录，再看参考答案。
6. [模拟会议与观察记录](stages/01-discovery/data/session-notes.md)：核对证据。
7. [参考交付物](stages/01-discovery/deliverables/README.md)：对照自己完成的六项产物。
8. [复现与验收](docs/reproduction.md)：修改样本，观察指标和退出条件如何变化。
9. [Stage 2 入口](stages/02-discovery/README.md)：对 Inquiry #017 做会议观察、问题建模和范围候选。
10. [Stage 3 入口](stages/03-data-boundary/README.md)：审查合成资料、权威来源、数据契约和评估设计。
11. [Stage 2–3 复现与反事实练习](docs/stage2-stage3-reproduction.md)：修改数据副本，验证审计为何失败。
12. [Stage 4 入口](stages/04-build-sprint-1/README.md)：运行邮件抽取、人工审核页面、反馈和 100 条合成集评估。

[模拟场景流程图](stages/01-discovery/guides/observed-workflow.md) 展示正常路径、专家升级和客户澄清回路。

## 文件夹地图

```text
docs/                         学习路线、指标口径、复现说明
stages/01-discovery/
  source/                     原始需求文档（原样保留）
  guides/                     项目简报、会议计划、角色卡及演练流程
  templates/                  空白记录与交付物模板
  data/                       合成询盘、知识材料、会议证据及输入规范
  deliverables/               程序生成的参考答案
stages/02-discovery/           Discovery 实战、问题/流程/决策交付物
stages/03-data-boundary/       合成资料包、治理记录、AI 边界与交接
stages/04-build-sprint-1/      Sprint 计划、合成评估集、失败复盘和交接
src/fde_discovery/            校验、指标计算、报告与阶段检查代码
src/fde_stage3/               Stage 2/3 资料审计代码
src/fde_platform/             Sprint 1 抽取、审核与评估代码
scripts/                      合成资料与评估集重建脚本
tests/                        指标计算、无效输入与阶段边界测试
run.py                        命令行入口
stage_pipeline.py             四阶段离线检查入口
stage4.py                     Sprint 1 demo / eval / review / process 命令入口
outputs/                      本地演练结果（不纳入版本管理）
```

四个阶段的“交付”是可追溯的问题定义、治理决定与一条可运行的抽取和审核切片。Stage 4 当前使用离线正则基线，合成样本总体字段准确率 96.7%，但流量和温度均为 90%，未达到每字段至少 95% 的设计门槛。没有真实模型、客户销售现场测试或实际 Pilot 成效。
