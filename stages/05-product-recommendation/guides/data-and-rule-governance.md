# 产品数据与规则治理

## 来源优先级

Stage 3 `SRC-TECH` 的 `Pump_Selection_NEW.json` 决定 CP80、CP90、CP100 的流量、扬程和材质。Stage 5 的 `ST5-EXT` 只补充模拟温度、频率、标准配置，`ST5-SUPP` 只添加测试用 SKU。Stage 3 销售主表与技术表的 CP90 冲突继续保留在 Stage 3 审计里，绝不合并成一个“平均”值。`training_only` 转换为 `active_simulated` 仅表示在本地教学搜索中可用，不表示客户产品真实在售。

材质别名表有版本。`SS316`、`316SS`、`SUS316` 归一为 `SS316`；`CI`、`Cast Iron` 归一为 `CAST_IRON`。泛称 `Stainless Steel` 没有足够信息区分牌号，`CPX-UNK` 进入隔离列表，不能参与排序。范围错误、频率错误、未知状态和不支持的产品族同样隔离；重名 SKU 阻断加载。每个有效候选保留来源 ID/版本、扩展来源、材质映射版本、数值区间。

## Rule V1 的生命周期

规则文件是 `data/rule-registry.json`，限白名单字段、`equals/in/gte/lte/exists` 条件，以及 `exclude_candidate/add_warning/require_review/add_requirement` 动作。引擎不求值任意 Python 表达式。每条规则必须有 ID、版本、owner、来源和状态；只有 `active_in_simulation` 执行。生产生效还需要客户工程负责人验证、测试签核和新环境审批，本案例没有执行生产批准。

| 规则 | 当前状态 | 模拟证据与作用 |
|---|---|---|
| `PUMP_MATERIAL_001` | 教学环境启用 | Stage 3 `R-001`：海水排除铸铁候选 |
| `HIGH_TEMP_001` | 教学环境启用 | Stage 3 `R-002`：≥80°C 触发密封/材料工程师审核，即使没有候选 |
| `MEDIUM_UNKNOWN_001` | 教学环境启用 | Stage 2 观察：介质未知要补资料并升级 |
| `CURVE_EDGE_001` | **候选，不执行** | Stage 3 `R-003` 尚未验证性能曲线；不能据此做硬排除 |

排序权重放在 `tenants/haichuan/product-preferences.json`，与领域规则分开。0.45/0.45/0.10 和靠边阈值 0.20 都是模拟假设。修改权重必须重跑评估并检查误升级和人工接受；不应把它们包装为陈工确认的工程经验。价格、库存和历史转化都未接入。规则命中会附来源与版本，允许事后解释为什么排除或升级。

## 审核与回滚

推荐产物及原始 InquiryRecord 一次写入、不可覆盖；人工 approve、choose_another、escalate 只追加事件。工程师任务只允许 engineer 角色批准；未知介质不得批准。销售可以升级；页面不发客户邮件。若将来规则造成误排，先把其状态退回 candidate 并重跑已冻结的 Golden 数据，保留旧事件与版本供审计。
