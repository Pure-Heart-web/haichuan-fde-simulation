# Stage 15：Commercial Delivery Room

本阶段把已经完成的技术案例转换成一套可演练的商务交付资料。目标不是“做一份销售 PPT”，而是让销售、FDE、客户 Sponsor、采购、数据、安全和验收人围绕同一份交易档案工作，并防止把演示、意向或技术通过误写成合同、授权或收入。

所有公司、人员、价格、日期和签核均为**教学虚构**。模板不是法律、税务或会计意见；用于真实客户前，应由本公司法务、财务、安全和授权签字人审阅。

## 一次完整演练

```bash
python3 stage15.py demo --check-baseline --output outputs/my-commercial-room
```

生成：

- `commercial-readiness.md/json`：当前商务 Gate、缺口和下一动作；
- `invoice-plan.csv`：按阶段拆分的开票触发点，UTF-8 BOM 可直接用表格工具打开；
- `evidence-register.csv`：每份证据的状态、Owner 和所服务的 Gate。

校验修改后的交易档案：

```bash
cp stages/15-commercial-delivery/data/haichuan-deal-record.json outputs/my-deal.json
python3 stage15.py validate --deal-file outputs/my-deal.json
python3 stage15.py report --deal-file outputs/my-deal.json --output outputs/my-deal-room
```

校验器会阻止这些常见误报：未批准前置 Gate 却批准后续 Gate、用 draft 证据签核、Shadow 缺数据/安全/SOW/UAT/事故计划、付款比例不等于 100%、把合成指标写成客户基线、把意向金额写成已签金额。

## 商务资料地图

| 时点 | 首要资料 | 作出的决定 |
|---|---|---|
| 首次接触前后 | [机会资格与 Discovery 访谈](templates/opportunity-qualification.md) | 是否值得投入售前；谁有问题、预算和决定权 |
| 方案形成 | [付费 Discovery 方案/SOW](templates/discovery-proposal-sow.md) | 先购买什么结果；验收什么；何时停止 |
| 推进签约 | [Mutual Action Plan](templates/mutual-action-plan.md) | 双方人员、日期、依赖和采购路径 |
| 采购/法务/安全 | [合同与尽调清单](templates/contract-security-checklist.md) | 哪些条款、数据和安全问题必须在开工前关闭 |
| 试点报价 | [Pilot SOW](templates/pilot-sow.md) + [商务报价单](templates/commercial-order-form.md) | 固定范围、价格、付款、客户依赖和变更机制 |
| Shadow 运行 | [成功计分卡](templates/pilot-success-scorecard.md) | 用冻结分母判断 Stop / Iterate / Expand |
| 变化发生 | [Change Request](templates/change-request.md) | 是否改变价格、排期、风险或验收基线 |
| 阶段结束 | [验收证书](templates/acceptance-certificate.md) | 接受、附条件接受或拒绝，并触发相应付款 |
| 生产与移交 | [上线和移交清单](templates/go-live-handover.md) | 谁批准上线、谁接手运行、哪些访问需撤销 |
| 续约/扩容 | [QBR 与扩容提案](templates/qbr-expansion.md) | 价值是否可复现；下一范围是否另行购买 |

另见 [商务推进 Playbook](guides/commercial-playbook.md)、[客户邮件模板](templates/customer-email-pack.md) 和两个已填写的海川示例：[机会记录](examples/haichuan-opportunity-note.md)、[Discovery 方案](examples/haichuan-discovery-proposal.md)。

## 当前案例的真实结论

海川示例只通过 Gate A“机会资格”，下一步是签署付费 Discovery。四阶段总潜在金额 CNY 1,480,000 是教学报价结构，当前已签约金额为 0。Stage 14 的技术预检不能代替采购订单、真实数据授权、客户安全批准或客户验收，因此 Shadow 和生产 Gate 均保持阻断。

启航 `QH-001` 可在 Discovery 中作为第二 Domain 的复用证据，但不能据此声称已有第二个付费客户。若把本资料用于启航，应复制交易档案并独立设置 Sponsor、范围、指标、授权、价格和签核，不能复用海川的商务批准。

## 推荐角色演练

五人分别扮演客户 Sponsor、客户采购/安全、Account Executive、FDE Lead、Delivery/CS Owner。先只给前三人机会记录，要求他们完成 Discovery SOW 和 MAP；再由采购/安全提出条款和数据问题；最后由 FDE 使用验证器检查是否有人越过 Gate。演练结束要能回答：谁付钱、买什么结果、由谁接受、证据在哪里、未达标如何停止、范围变化怎样计价。
