# 工业设备 · FDE 交付学习案例

这是一个可复现的模拟客户项目。目前完成 **Stage 1–7 的海川工业泵发现、构建和试点运营演练，Stage 8 的启航设备售后与双客户产品化，Stage 9 的交付强化，Stage 10 的客户接入与受控 Shadow Pilot，Stage 11 的生产形态 Delivery Room，Stage 12 的模型评估、安全、Canary 与回滚，Stage 13 的设计合作客户现场准备与统一工作台，Stage 14 的集成实验室与授权 Shadow 预检，Stage 15 的商务交付 Gate，以及 Stage 16 的团队商业交付毕业模拟与个人技术责任评估**。后续阶段按新需求继续扩展。

企业、联系人、邮件、设备、型号、订单和指标均为教学虚构。样本中的数值用于练习分析，不是客户真实业务事实，也不是泵选型或设备维修依据。

## 10 分钟运行

需要 Python 3.10 或更新版本，无第三方依赖、API Key 或网络要求。在本文件所在目录打开终端：

```bash
python3 stage_pipeline.py all --output-root outputs/my-stage-1-16-run
python3 -m unittest discover -s tests -v
```

`--output-root` 建议每次使用新目录；历史审核记录与当前代码版本不同时，流水线会按设计拒绝覆盖。

`all` 依次运行十六个阶段：Stage 1–3 生成 Discovery 与数据审计，Stage 4–6 运行抽取、产品匹配与证据化草稿的合成评估，Stage 7 重放试点事件，Stage 8 执行双租户与纵向案例，Stage 9–14 检查交付强化、客户接入、运行、模型、现场与集成控制，Stage 15 校验商务交易档案与 A–F Gate，Stage 16 评分团队和个人技术责任证据。结果保存在 `outputs/stage-01/` 至 `outputs/stage-16/`，另有 `outputs/stage-08-vertical/`。

分析自己的演练记录：

```bash
python3 run.py analyze --input stages/01-discovery/data/simulation.json --output outputs/my-session
```

Stage 1 输入规范见 [数据说明](stages/01-discovery/data/README.md)。`run.py` 的退出码 `0` 表示检查通过或报告成功生成；`2` 表示数据无效；`3` 表示报告已生成但 Stage 1 退出条件尚未齐全。`stage_pipeline.py` 的 `0` 表示教学流程与回归检查已完成；Stage 4 会如实报告未达门槛字段。设计审计通过不表示已达到产品发布门槛。

Stage 1–3 资料可用任意 Markdown 阅读器浏览；后续阶段提供本地页面、命令行或 HTTP 控制台。代码入口依次为 [Stage 1](run.py)、[Stage 4](stage4.py)、[Stage 5](stage5.py)、[Stage 6](stage6.py)、[Stage 7](stage7.py)、[Stage 8](stage8.py)、[双案例纵向演练](stage8_vertical.py)、[交付强化](stage9.py)、[客户接入](stage10.py)、[Delivery Room](stage11.py)、[模型安全 Canary](stage12.py)、[现场试点准备](stage13.py)、[集成实验室](stage14.py)、[商务交付室](stage15.py) 和[团队毕业模拟](stage16.py)；默认不调用外部大模型，生成结果可以追溯到本地输入。

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
13. [Stage 5 入口](stages/05-product-recommendation/README.md)：运行产品目录清洗、搜索、规则、排序、专家升级、审核与匹配评估。
14. [Stage 6 入口](stages/06-context-knowledge-reply/README.md)：运行客户身份/订单上下文、有版本知识检索、Claim Policy、回复草稿与审核反馈。
15. [Stage 7 入口](stages/07-pilot-operations/README.md)：演练受控试点、分角色审核、全链路追踪、分群采用率、数据发布门和故障降级。
16. [Stage 8 入口](stages/08-productization/README.md)：模拟第二客户售后 Discovery，运行双租户、领域安全规则、上下文排序和产品化 Review。
17. [双 Domain 纵向交付手册](stages/08-productization/vertical/README.md)：自己扮演工程师与销售，完成模拟接入、审核修改和结果记录。
18. [Stage 9 交付强化手册](stages/09-hardening/README.md)：复现双角色标注、模拟外部服务、发布门、身份校验、迁移和运营决策。
19. [Stage 10 客户接入与 Shadow Pilot](stages/10-customer-onboarding/README.md)：验证授权清单、脱敏、幂等更新、角色审核、保留期和真实切换门。
20. [Stage 11 Production-like Delivery Room](stages/11-delivery-room/README.md)：运行持久化队列、Worker、双人发布、Mock HTTP、Trace、值班和事故复盘。
21. [Stage 12 Model Evaluation, Safety & Canary](stages/12-model-safety-canary/README.md)：运行模型注册、离线对比、攻防集、确定性 Canary、熔断和职责分离回滚。
22. [Stage 13 Design Partner Pilot Readiness](stages/13-pilot-readiness/README.md)：演练外置授权包、训练 OIDC、PostgreSQL RLS 契约、统一工作台、班次交接、SLO 与紧急回退。
23. [Stage 14 Integration Lab](stages/14-integration-shadow/README.md)：用真实运行状态阻断和恢复 Gate，演练只读 Connector、OIDC 轮换、遥测脱敏、证据包和真实 Shadow 预检。
24. [Stage 15 Commercial Delivery Room](stages/15-commercial-delivery/README.md)：演练机会资格、付费 Discovery、MAP、尽调、Pilot SOW、报价、验收、移交和续约，并用机器 Gate 防止商务状态夸大。
25. [Stage 16 团队真实商业交付模拟](stages/16-team-delivery-simulation/README.md)：6 人角色分工完成六轮交付与十二个事件注入，用团队和个人证据评价是否能在监督下承担客户技术责任。

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
stages/05-product-recommendation/ 产品目录、规则、24 条合成匹配集、评估和交接
stages/06-context-knowledge-reply/ 客户与订单样本、知识文档、评估、ADR 和演练手册
stages/07-pilot-operations/ 合成试点事件、操作手册、事故复盘、ADR 和决策记录
stages/08-productization/  启航合成资料、双客户抽象边界、故障复盘与产品化决策
  vertical/                  QH-001 / P7-003 模拟外部输入、审核和结果资料
stages/09-hardening/         挑战集、双角色标注、曲线/安全签核、运营口径及演练手册
stages/10-customer-onboarding/ 合成设计合作客户包、真实切换手册、检查表及评审记录
stages/11-delivery-room/      生产形态运行时、36 案例、API、Runbook、UAT 与交付治理
stages/12-model-safety-canary/ 模型注册、100 案例对比、攻防集、Canary、熔断与回滚
stages/13-pilot-readiness/     授权包、OIDC/RLS 契约、人工工作台、班次、SLO 与 UAT
stages/14-integration-shadow/   跨层 Gate、只读 Connector、OIDC/OTLP Lab、Shadow 证据与外部预检
stages/15-commercial-delivery/  资格、提案、MAP、合同尽调、报价、验收、移交与续约资料
stages/16-team-delivery-simulation/ 团队角色、客户剧本、事件注入、评分与个人培养资料
src/fde_discovery/            校验、指标计算、报告与阶段检查代码
src/fde_stage3/               Stage 2/3 资料审计代码
src/fde_platform/             Sprint 1–3 抽取、推荐、知识、草稿、审核与评估代码
scripts/                      合成资料与评估集重建脚本
tests/                        指标计算、无效输入与阶段边界测试
run.py                        命令行入口
stage_pipeline.py             十三阶段离线检查入口
stage4.py                     Sprint 1 demo / eval / review / process 命令入口
stage5.py                     Sprint 2 demo / eval / recommend / from-stage4 / review 入口
stage6.py                     Sprint 3 demo / eval / draft / review 入口
stage7.py                     Pilot demo / dashboard / trace / incident / review / eval 入口
stage8.py                     双租户 demo / eval / trace / incident / review 入口
stage8_vertical.py            双 Domain prepare / review / close / report / demo 入口
stage9.py                     交付强化 demo / prepare / login / label / review / eval 入口
stage10.py                    客户包校验 / prepare / login / queue / review / purge / readiness 入口
stage11.py                    Delivery Room demo / worker / review / approve / dispatch / trace / API 入口
stage11_mock_server.py        本机 OAuth 与 Mock 客户端点
stage12.py                    模型注册 / 评估 / 安全 / Canary / 熔断 / 回滚入口
stage13.py                    现场准备 / 身份 / 班次 / SLO / 工作台入口
stage14.py                    集成实验室 / 事故 Gate / 证据包 / Shadow 预检入口
stage15.py                    商务交易档案 / 付款计划 / A–F Gate 校验入口
stage16.py                    团队模拟包生成 / 交付评分 / 个人技术责任评估入口
outputs/                      本地演练结果（不纳入版本管理）
```

十六个阶段的“交付”是可追溯的问题定义、治理决定与可运行的抽取、推荐、审核、运营、产品化、客户接入、生产形态、模型发布、现场班次、集成实验室、商务 Gate 和团队责任演练。Stage 14 依然使用本地集成 Lab；Stage 15–16 的交易、客户事件、金额、人员、评分和签核均为教学虚构。它们不能替代生产数据面、企业 SSO、授权客户现场测试、实际 Pilot 成效、有效合同或真实项目负责人对成员的长期观察。
