# 输入数据规范

`simulation.json` 是 UTF-8 JSON；`session-notes.md` 是可阅读的原始模拟材料。没有任何真实客户资料。不要将文件中的 scenario Fact 写作真实客户事实。

| 字段 | 内容 |
|---|---|
| schema_version | 当前为 1 |
| dataset_id / mode | 唯一数据集标签；mode 为 simulation 或 real |
| sources | 证据 ID、标题、相对于输入文件的本地文件路径、origin（simulation / real）；路径中的文件必须存在 |
| interviews | role（buyer / sales / engineer）、source_id |
| observations | 案例 ID、complexity（simple / complex）、source_id、带时区的 received_at / first_reply_at、六步 steps、escalated、escalation_reason、engineer_minutes |
| inventory | 资料名称、source_id、owner、version、quality、access、kind（inquiries / product / history 等） |
| assessment | problem、hypothesis、non_goals、evidence 分类台账和 workflow 实际步骤 |
| decisions | 决策、输入、依据、Owner、异常路径、人工边界和来源 |
| questions | 待验证问题、Owner、due、method、impact |
| checks | bottleneck / escalation / error_cost 三项人工研判，包含 confirmed、note、source_ids |

六步必须完整：requirements、lookup、selection、history、quote、draft。未发生的步骤填已观察的 0；漏记不能填 0。分钟数必须是有限非负数；升级必须给出原因；无升级不允许有工程师投入。销售主动时间不能超过收件到首次回复的自然时长。初版数据不支持多次升级咨询事件和工程师独立计时区间，因此不计算全天咨询次数。

`checks` 是人工回读的记录，不能因为程序能算指标就自动填 true。确认项必须引用存在的证据。退出条件检查会结合三类访谈、至少 3 次观察、资料种类和 Non-goals。真实模式要求所有来源均声明 real，但这只是结构检查，不证明真实性。

所有报告共用证据索引，可通过相对链接打开原始材料；具体内容由证据编号定位。移动输入文件时同步修改 `sources[].path`，例如从 `outputs/practice.json` 指回原始资料可写 `../stages/01-discovery/data/session-notes.md`。
