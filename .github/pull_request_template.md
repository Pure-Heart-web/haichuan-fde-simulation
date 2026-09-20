## Problem

这次变更解决哪个可观察的问题？附具体案例或失败分类。

## Scope 与边界

涉及哪些模块？哪些行为/接口被修改？Core 是否仍不依赖 foreign_trade？

## Input / Output

契约、字段语义、缺失值、单位和证据位置如何变化？

## Eval impact

附修改前后 `python3 stage4.py eval --check-baseline` 的结果；说明每字段和失败案例的变化。若变更标签，说明审核人与数据集版本。

## Risks and rollback

解析失败、默认值、人工审核、数据隔离有哪些风险？如何停用或回退？

## Validation

- [ ] 单元/集成测试通过
- [ ] 回归评估通过或解释明确差异
- [ ] 更新文档、Prompt/Model 版本及 ADR（如适用）
