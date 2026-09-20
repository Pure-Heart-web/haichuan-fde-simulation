# Stage 6：Customer Context、Enterprise Knowledge、Evidence 与 Reply Draft

本阶段用离线、无第三方依赖的教学切片走通：文本询盘 → Stage 4 抽取 → 客户身份 → 最近相关已完成订单 → Stage 5 暂定推荐 → 有版本知识检索 → Claim Policy → 内容计划 → 英文回复草稿 → 人工审核与知识缺口反馈。**不发送邮件，不修改 CRM，不输出价格或最终型号承诺。**

Stage 3 当时把客户历史标为身份待确认，把保修和认证政策标为缺失。本阶段新增的客户、订单、保修和 CE 文件全是**独立虚构的 Stage 6 教学来源**，只在模拟环境内启用，不能倒推为 Stage 3 已批准资料或真实客户政策。

## 运行与浏览

在仓库根目录使用 Python 3.10+：

```bash
python3 stage6.py demo
python3 stage6.py draft --case S6-001
python3 stage6.py eval
python3 stage6.py review
python3 -m unittest discover -s tests -v
```

`review` 在 `http://127.0.0.1:8767/` 打开本地页面。`outputs/stage-06/drafts/` 有逐案完整 JSON，`outputs/stage-06/stage6-eval.md` 是指标报告，SQLite 队列保存未覆盖的原草稿、追加式审核事件和知识缺口反馈。重复 `demo` 不覆盖既有审核。`draft --input your-case.json` 可读取单条 JSON：至少包含 `id`、`sender`、`text`，可选 `company_name`、`region`、`subject`、`as_of`。单条命令只打印结果，不写队列。

建议依次看：

| 案例 | 要观察的边界 |
|---|---|
| `S6-001` | 明确说“same as previous order”后才恢复 CP90 历史；保修 12 个月与 CE 均有来源，电气参数仍要确认 |
| `S6-002` | 本次 400V/60Hz 与历史 380V/50Hz 冲突；本次明确值优先，历史值仅作对照 |
| `S6-003` | “ABC Marine” 别名对应两家客户；不能打开任何一家的订单历史，不能批准草稿 |
| `S6-005` | ATEX 只有 draft 文件；检索弃答，产生知识缺口，人工答案仍需治理 |
| `S6-006` | 典型交期 4–6 周附“待生产确认”；没有价格或具体交货承诺 |
| `S6-008` | 户外安装技术说明触发工程师审核 |

先填写 [练习记录模板](templates/review-notebook.md)，再读[来源与流程手册](guides/workflow-and-governance.md)、[评估口径](guides/evaluation.md)、[ADR-006–010](deliverables/adr-006-010.md)、[失败复盘](deliverables/failure-review.md)和[Sprint 3 交接](deliverables/sprint-review.md)。[原始 Stage 6 文档](source/original-stage-06.md)完整保留供对照。

## 代码入口

| 位置 | 内容 |
|---|---|
| `core/context/` + `domains/foreign_trade/context/` | CustomerEntity、身份解析、ContextProvider、最近已完成订单 |
| `core/knowledge/retrieval.py` | 文档治理校验、元数据先过滤、关键词检索、KnowledgeEvidence |
| `core/policy/claims.py` | Claim 白名单、证据和审批引用验证 |
| `core/generation/draft.py` | 内容计划与风格实现分层；当前为确定性模板基线，不调用 LLM |
| `domains/foreign_trade/reply/` | 显式编排、合成评估、草稿审核与知识缺口存储 |
| `apps/draft_review_web.py` | 仅绑定本机的审核页面 |

当前仿真案例的高指标不能当作 Pilot 结果。它们证明数据契约和保护边界在有限样例中可复现；真实来源授权、身份校验、知识签核、销售接受率及生产安全措施都还没有完成。
