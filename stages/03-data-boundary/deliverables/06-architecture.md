# Architecture V0 · 设计图

```mermaid
flowchart TD
    A[邮箱适配器] --> B[WorkItem]
    B --> C[结构化提取与 Schema 校验]
    C --> D[确定性单位标准化]
    D --> E[InquiryRecord]
    E --> F[客户身份/订单 Context Provider]
    E --> G[技术产品库硬过滤]
    E --> H[批准文档检索]
    F --> I[规则与冲突拦截]
    G --> I
    H --> I
    I --> J[候选、警告和证据]
    J --> K[ReviewTask: 销售/工程师]
    K --> L[人审后的回复草稿]
    L --> M[人工发送]
    N[高敏感特价/报价审批] -. V1 隔离 .- I
```

隔离点：原始聊天只进入规则候选队列；已批准技术字段和知识才能进入查询；客户身份歧义停止自动关联；冲突字段阻断候选确认；特价不进入生成上下文。推荐必须携带来源、版本和风险；审核结果回写评估与规则问题单，不自动修改权威来源。

模块边界供 Stage 4 设计审查参考：`ingestion`、`extraction`、`normalization`、`entities/context`、`products`、`rules`、`retrieval`、`recommendations`、`review`、`evals`。这是接口建议，不预设数据库或模型供应商。
