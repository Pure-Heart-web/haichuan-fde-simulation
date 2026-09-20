# Shared Core / Domain Pack / Tenant Config 的实际边界

第二客户检验的是**语义稳定性**。原有 `WorkItem` 和 `core.extraction.extract` 不含泵字段，启航以 `source_type=ticket/call_transcript`、`domain=after_sales` 和 `ServiceCase` 类型化校验直接复用；`ServiceRegexProvider` 仅是本地可重复基线，不是 LLM 性能。新增 `EntityRef + ContextRequest + ContextRecord` 契约，使海川历史订单和启航资产维修可表达为同一“引用实体、请求相关上下文”的模式；两边实际查询仍各归 Domain。旧 `previous_order` 仍保留给 Stage 6/7，用适配与渐进迁移避免一次性重写。

| 能力 | 共享层 | 仍属于 Domain/Tenant 的部分 | 当前证据 |
|---|---|---|---|
| Ingestion / Extraction | WorkItem、JSON 解析/重试、版本与来源 | 邮件/工单 Adapter、Inquiry/ServiceCase 类型和验证 | 两条流程均能运行；只测合成样本 |
| Context | EntityRef/Request/Record 接口 | 客户已完成订单 vs 设备维修历史、选取规则 | 启航资产 Adapter 跑通；海川旧接口待迁移 |
| Knowledge | 租户作用域 → 有效期/状态/角色过滤 → 证据 | 手册集合、意图、适用机型、审批 | 启航与海川测试文档互不可见 |
| Rules | 条件/动作有限 DSL 执行和白名单 | 泵兼容规则 vs 售后安全规则；阈值属租户 | 售后规则能阻断，原泵引擎暂不迁移 |
| Recommendation | options/actions/warnings/evidence/risk/review 契约 | 产品排序 vs 故障诊断排序 | 海川显式适配，启航上下文排序；没有通用排序器 |
| Review / Feedback | 任务契约、负责人/角色、追加事件与 Trace 关联 | 销售页面 vs 售后设备页面、审批政策 | 两种 UI 分开；Stage 7 旧队列待迁移 |
| Eval / Trace | 输入版本、案例级结果、回归状态 | 字段、Top-1、风险和业务指标 | Stage 1–8 流水线与独立租户评估 |

不要把所有 Schema 退化成 `dict[str, Any]`：核心运行时可以接通用 JSON，但进入售后决策前必须过 `ServiceCase` 校验；海川继续有自己的 InquiryRecord。`core/platform/runtime.py` 不认识 E37、CP90 或维修角色，售后排序的 `recent_maintenance` 只在 `after_sales/diagnosis.py` 生效。第三个假想招聘 Domain 也许能复用工作项、上下文引用、规则与审核，但不因此开发通用低代码/BPM 平台。

## 配置、规则、代码与模型

| 变化 | 放置位置 | 例子 |
|---|---|---|
| 稳定有限且业务可理解 | Tenant Config | 租户 ID、审阅人、功能开关、资料映射 |
| 可解释的条件约束 | Domain/Tenant Rule Set | E37 + 异响 + 高温 → 工程师及安全阻断 |
| 数据访问、算法与执行结构 | Code | 先租户过滤、资产上下文和售后排序 |
| 不确定语言理解/生成 | Model Adapter（当前未接） | 真实转写与自然语言摘要，仍需评估 |

`tenant-config.json` 只提供少量固定参数；没有把整条售后业务流程塞进配置。`core/platform/tenant_store.py` 是本地 SQLite **作用域演示**，不提供生产登录、加密或 RLS；[隔离与发布门手册](tenancy-eval-release.md)列出升级路径。
