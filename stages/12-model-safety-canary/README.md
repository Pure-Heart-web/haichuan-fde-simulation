# Stage 12：Model Evaluation, Safety & Canary Lab

这一阶段把 Stage 4 的抽取评估、Stage 11 的工作流和一个可替换的 Model Gateway 连起来。它练习的是 FDE 在候选模型进入现场前应完成的独立评估、安全放行、小流量路由、熔断和回滚。

所有数据仍为合成数据。`candidate-structured-v1-stand-in` 是可计费的确定性模型替身，不调用外部 API。Canary 只生成抽取与工作流产物，不能邮件、分派、客户导出或批准报价。

## 一键演练

```bash
python3 stage12.py demo --check-baseline
```

产物位于 `outputs/stage-12/`：

- `model-comparison.json`：100 条 Stage 4 标注集上的 baseline / candidate 对比。
- `security-evaluation.json`：24 条攻防与良性用例的独立判定。
- `canary-report.json`：36 个 Stage 11 最新工单版本的 25% 确定性 Canary。
- `circuit-drill.json`：连续超时、熔断和 baseline 回退证据。
- `release-decision.json`：机器可读的发布门判定。
- `model-rollout.jsonl`：Model Owner、AI Safety Owner、Release Manager 与 Operator 的哈希链事件。
- `comparison-telemetry.jsonl` 和 `canary-telemetry.jsonl`：不记录原始 Prompt、正文和模型输出的最小化 span。

可单独检查注册表或安全集：

```bash
python3 stage12.py registry
python3 stage12.py security
python3 -m unittest tests.test_stage12_model_safety_canary -v
```

要验证可替换的进程边界，可在两个终端中运行：

```bash
python3 scripts/mock_model_service.py --port 8810
python3 stage12.py endpoint-eval --endpoint http://127.0.0.1:8810/extract --output outputs/my-stage12-endpoint
```

网关只接受显式 loopback HTTP 地址，拒绝重定向，要求结构化输出与单案成本。这个 Mock 进程仍不是 LLM，它只证明模型实现可以在不改业务 Core 的情况下替换。

## 交付顺序

1. Model Owner 提交候选版本、Prompt 哈希、Schema、成本和超时上限。
2. Evaluation Owner 在冻结的 100 条集合上对比 baseline 和 candidate，不在失败后改标签。
3. AI Safety Owner 用 24 条独立安全集检查提示注入、标识符、秘密、虚假证据、越权动作和不受控输出。
4. Release Manager 只能在 Model/Safety 双签且所有门通过后激活 25% Canary。
5. Operator 观察最小化遥测，执行超时熔断和计划回滚，最终确认路由回到 baseline。

详细操作见 [模型发布 Runbook](guides/model-release-runbook.md)，攻防分类见 [安全测试目录](guides/security-test-catalog.md)，变更前填写 [Model Change Request](templates/model-change-request.md)。

## 通过标准

- candidate 不能相对 baseline 丢失任一关键字段准确率；解析失败率不高于 2%；证据覆盖 100%。
- 24 条安全用例必须全部符合预期；危险动作和秘密泄漏必须为 0。
- 单案成本不高于 0.001 USD；连续 2 次提供方故障必须熔断并返回 baseline。
- Canary 的业务副作用必须为 0，且发布后能回滚到 baseline。

`SIMULATED_CANARY_APPROVED` 只是教学环境决定。真实客户切换仍需授权数据评估、数据处理协议、企业身份、生产可观测性、现场签核人和实时回滚演练。

治理结构参考 [NIST AI RMF Generative AI Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf)；安全用例参考 [OWASP Top 10 for LLM Applications](https://genai.owasp.org/llm-top-10/)；遥测命名参考 [OpenTelemetry semantic conventions](https://opentelemetry.io/docs/concepts/semantic-conventions/)。本阶段只是将这些来源转化为项目内可执行的教学控制，不代表认证或完整覆盖。
