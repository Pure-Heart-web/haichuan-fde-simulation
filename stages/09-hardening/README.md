# Stage 9：交付强化与真实系统边界演练

这一阶段围绕已完成的 `QH-001` / `P7-003` 纵向案例补齐**可验证的合成控制**。它不能替代客户授权、真实工程安全签核、企业身份提供方、独立人工标注或正式 Pilot。运行结果始终停在本机 `pending_send` 待发送区；不发邮件、不派工、不发布资料。

## 一键复现

在仓库根目录运行 Python 3.10+：

```bash
python3 stage9.py demo --check-baseline
python3 -m unittest discover -s tests -v
```

查看 `outputs/stage-09/hardening-report.md`、`hardening-report.json`，以及 `mock-services.sqlite3`、`platform.sqlite3`。期望：Stage 4 合成字段门槛已满足；10 条挑战案例中保留 3 处前线/工程师分歧；启航和海川两条原案例闭环，更正转写 `QH-001-R2` 保持待审；模拟邮箱一次超时后重试；2 条人工确认草稿都为 `pending_send`，实际发送为 0；Stage 7 的 12 条 Trace 和 1 条审核事件迁入海川租户的只读归档。重复运行不增加审核或发送记录。

Stage 4 修复是规则覆盖范围的改善：识别英文全写的流量和温度单位，在原 100 条**合成**集上流量、温度从 90% 升至 100%，整体从 96.7% 升至 98.9%。这不是新样本上的泛化证明。独立挑战集主要测试安全路由，而不是抽取准确率；两项指标应分开读。

## 自己走一遍有身份的审核

用一个新目录运行 `python3 stage9.py prepare --output outputs/my-stage9`。它只把两条初始输入推进审核队列，不替你做决定。本地演练身份的随机密码保存在 `outputs/my-stage9/identity/training-credentials.json`（文件权限 0600，目录已被 Git 忽略）；这只是本机模拟 IdP，不是企业 SSO。分别运行：

```bash
python3 stage9.py login --actor engineer-chen --output outputs/my-stage9
python3 stage9.py login --actor anna --output outputs/my-stage9
python3 stage9.py queue --token-file outputs/my-stage9/identity/engineer-chen.token --output outputs/my-stage9
```

`login` 会在终端安全提示输入相应密码，并写出 15 分钟有效的签名令牌。审核、结案与待发送区动作都从令牌读取租户和角色；不能靠命令参数自称其他人。先做启航：

```bash
python3 stage9.py review --case QH-001 --edited-action '先核对 WO-QH-110，工程师现场复核' --reason '昨日保养改变排查顺序' --token-file outputs/my-stage9/identity/engineer-chen.token --output outputs/my-stage9
python3 stage9.py close --case QH-001 --outcome-id SIM-CMMS-QH-001-CLOSE --token-file outputs/my-stage9/identity/engineer-chen.token --output outputs/my-stage9
python3 stage9.py confirm --case QH-001 --content '已收到故障信息，工程师将按工单现场复核；此处不提供远程维修步骤。' --token-file outputs/my-stage9/identity/engineer-chen.token --output outputs/my-stage9
```

海川原邮件**没有本次温度、电源等完整工况**。在模拟 CRM 记录确认之前，`confirm --content '建议 CP90'` 会拒绝。先用销售身份修改内部建议，再记录含具体工况的独立合成 CRM 来源；曲线通过后才允许把“暂定候选”放进待发送区：

```bash
python3 stage9.py review --case P7-003 --edited-action '先核实本次工况，再保留暂定候选' --reason '旧订单不能补全新需求' --token-file outputs/my-stage9/identity/anna.token --output outputs/my-stage9
python3 stage9.py close --case P7-003 --outcome-id SIM-CRM-P7-003-CONFIRM --token-file outputs/my-stage9/identity/anna.token --output outputs/my-stage9
python3 stage9.py confirm --case P7-003 --content 'CP90 仅为暂定候选，须再由人工确认。' --token-file outputs/my-stage9/identity/anna.token --output outputs/my-stage9
```

输入来源在模拟邮箱中按 `event_id` 和租户内 `source_id` 去重；改变旧来源内容会拒绝，版本更新需要显式引用上一来源 ID。一次 `SIM-MAIL-P7-003` 超时会进入可重试状态，延迟后恢复；到上限会成为死信。CMMS 的 `WO-QH-110` 和 CRM 的 `S6-ORD-002` 由模拟服务查询并留下查询日志，建议必须携带相应证据 ID。`QH-001-R2` 作为新版本重新审核，旧审核不会自动继承。

## 资料、标注和产品/安全发布门

`data/challenge-cases.json` 与 `data/dual-role-labels.json` 分开存放。静态标签是**合成角色扮演**，包含每位标注人的路线、理由和裁决；故意保留 3 处意见分歧。若团队成员想自己盲标，可用 `stage9.py login` 获取客服 `zhou`、工程师 `engineer-chen`、裁决人 `safety-owner-wu`（海川对应 `anna`、`mike`、`product-owner-li`）的令牌，依次执行：

```bash
python3 stage9.py label --case QH-TRANS-01 --route request_clarification --reason '需要回听录音' --token-file outputs/my-stage9/identity/zhou.token --output outputs/my-stage9
python3 stage9.py label --case QH-TRANS-01 --route abstain_and_escalate --reason '序列号不可信' --token-file outputs/my-stage9/identity/engineer-chen.token --output outputs/my-stage9
python3 stage9.py adjudicate --case QH-TRANS-01 --route abstain_and_escalate --reason '先冻结资产推断' --token-file outputs/my-stage9/identity/safety-owner-wu.token --output outputs/my-stage9
```

每位初标人看不到对方尚未裁决的标签；裁决必须等待两份记录，并保留理由。`labels-report` 按令牌租户过滤，`annotations.sqlite3` 保留原始分歧，不覆盖。直接读本机 SQLite 仍可绕过应用层权限，因此真实环境须再做磁盘访问控制、加密与审计。

`data/performance-curves.json` 是**虚构的 CP90 性能曲线**，只在声明的介质、温度、电源、流量区间和生效期内做线性插值，且只给“供人工复核”的结论；未知工况弃答、超出曲线升级。`data/service-rule-release.json` 记录模拟安全负责人及内容哈希，规则内容一变就拒绝加载。`95°C` 仍只是教学阈值，不能用于真实维修判断。真实发布需要厂家曲线、适用条件、工程审核、安全负责人签名和版本回退。

## 模型适配与独立评估

Stage 4 的 `Provider.complete` 契约仍是主入口。Stage 9 额外提供**可选本机 HTTP JSON 适配器**，仅接受显式 `127.0.0.1`/`localhost` 端点，禁止重定向与发送/派工动作字段。可先启动完全离线的规则替身服务：

```bash
python3 scripts/mock_model_service.py --port 8810
```

在另一终端运行：

```bash
python3 stage9.py model-eval --endpoint http://127.0.0.1:8810/extract --output outputs/my-stage9
```

`model-comparison.json` 并排记录字段正确率、证据覆盖、解析失败、P95、本机模拟费用，以及提示注入/敏感信息探针。上述服务**不是 LLM**，只验证接口与评估链；真正模型必须自行部署为同一 JSON 协议，并在授权数据、独立标签、费用账单和安全评审后才有可解释的对比。探针依据 [OWASP 2025 LLM Top 10](https://genai.owasp.org/llm-top-10/) 中的提示注入、敏感信息披露与过度代理风险选取，不是完整的安全认证。

## 迁移、运营与决策

`stage9.py migrate` 会生成独立的 Stage 7 旧队列副本，随后把 Trace、任务和审核事件复制到海川租户作用域，作为**只读归档**。用海川审计员令牌执行 `export-legacy --token-file ...`，启航令牌请求海川租户会被拒绝。旧页面尚未切换到新身份层；真实迁移仍需停写窗口、校验总数、双读、回退和权限评审。

`data/operations-plan.json` 冻结采用、人工修改、错误、专家负担、依赖故障、成本的口径和 Stop 条件。报告记录模拟超时恢复、待发送数、签核角色和回退动作。它会把当前决策保持在 `ITERATE_IN_SIMULATION`；缺少真实用户、独立标注、真实安全签核、企业身份与成本时，不允许把 Stage 7 的合成采用率写成 `EXPAND` 依据。这与 [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/) 的持续治理、测量和管理思路相符，但这里仅是教学映射。

`ITERATE_IN_SIMULATION` 初始只是待签核建议。模拟 Pilot、Safety、Platform 三位负责人需分别登录并对同一报告证据版本执行以下命令；本演练只允许 `STOP` 或 `ITERATE`，不接受 `EXPAND`：

```bash
python3 stage9.py ops-signoff --decision ITERATE --reason '继续合成迭代，真实门未通过' --token-file outputs/my-stage9/identity/pilot-owner-linda.token --output outputs/my-stage9
python3 stage9.py ops-signoff --decision ITERATE --reason '继续合成迭代，真实门未通过' --token-file outputs/my-stage9/identity/ops-safety-wu.token --output outputs/my-stage9
python3 stage9.py ops-signoff --decision ITERATE --reason '继续合成迭代，真实门未通过' --token-file outputs/my-stage9/identity/platform-owner-li.token --output outputs/my-stage9
python3 stage9.py ops-status --token-file outputs/my-stage9/identity/platform-owner-li.token --output outputs/my-stage9
```

签核绑定报告的案例、控制、服务状态和运营指标摘要；这些证据变化后，旧签核自动显示为过期，必须重新审阅。三人的决定不一致时保持待签核。运行 `stage9.py report` 会把当前有效签核同步进报告。这里的签核人仍是虚构身份，不能替代真实业务负责人批准。
