# Stage 16：团队真实商业交付模拟

这是 Stage 1–15 的团队毕业项目。6 名成员从一个已资格但未签约的海川商机出发，完成付费 Discovery、数据与安全设计、构建和授权 Shadow、事故与范围变化、验收与移交建议。主持人按轮次释放信息，团队不能预先假设客户已经授权，也不能用技术测试替代合同、数据、安全或验收 Gate。

公司、人员、系统、合同、数据、金额、故障和签核全部为教学虚构。模拟通过只表示可以进入**受监督的商业交付实践**，不授予签约权，也不允许访问真实客户生产系统。

## 适用团队

- 标准：6 名参与者 + 2–4 名主持/客户评委，10 个半天或 2 个集中日；
- 4–5 人：允许一人兼任两个交付角色，但每个角色必须有明确 Accountable；
- 7–9 人：增加工程师、数据分析、PM/客户成功，仍保留 6 个 Accountable 角色；
- 个人自学：按顺序轮换 6 个角色，每轮写清自己当时掌握的信息，不看主持人包。

## 快速开始

主持人在仓库根目录执行：

```bash
python3 stage16.py prepare --output outputs/team-capstone
```

把 `outputs/team-capstone/participant-pack/` 发给参与者；只把 `facilitator-pack/` 给主持人与客户评委。参与者在独立分支或文件夹工作，使用真实 Git review 流程，并运行现有 Stage 1–15 工具形成证据。

参考答案演示与评分器自检：

```bash
python3 stage16.py demo --check-baseline --output outputs/stage-16
```

团队完成后，把空白 JSON 填成提交记录并评分：

```bash
python3 stage16.py score \
  --submission outputs/team-capstone/team-submission.json \
  --output outputs/team-capstone/final-score
```

## 角色分工

| 角色 | 对结果 Accountable | 不能转嫁的责任 |
|---|---|---|
| Engagement Lead | Buyer、价值、范围、MAP、SOW、Gate 与高管沟通 | 不承诺团队尚未评估的结果 |
| FDE Technical Lead | 端到端方案、取舍、复用边界和技术 Go/No-go | 能解释失败模式并在证据不足时停止 |
| AI Evaluation Lead | 数据集、模型/规则评估、攻防、证据和发布门 | 不用平均准确率掩盖危险失败 |
| Platform & Integration Lead | Connector、身份、租户、运行时、观测和恢复 | 对重复、更新、限流、死信和隔离负责 |
| Security & Data Lead | 授权、最小化、隐私、威胁、审计和安全 Gate | 真实数据进入系统前先验证权限和用途 |
| Workflow & Adoption Lead | 人工审核、容量、培训、采用、反馈、UAT 与移交 | 处理真实人员绕过和专家负担 |

详细角色卡在 [roles](roles/)；评价标准见 [技术负责人能力标准](guides/technical-accountability-standard.md)。每件必交产物只有一个 Owner，至少一名不同成员审阅。重要决定要留下触发、证据、风险、可逆性和客户影响。

## 两周学习节奏

| 日程 | Round | 客户互动 | 团队输出 | 学习重点 |
|---|---|---|---|---|
| Day 0 | R0 | 无 | 角色、工作协议、环境、分支、证据规则 | 建立责任和协作方式 |
| Day 1–2 | R1 | Sponsor/采购会议 | Problem Brief、Discovery 计划、As-Is、SOW/MAP | 先理解问题再承诺方案 |
| Day 3 | R2 | 数据/安全工作坊 | 授权、SoT、架构、评估计划、ADR | 在约束中设计可交付系统 |
| Day 4–6 | R3 | 用户评审/Shadow | 可运行纵向流程、Trace、评估、审核和采用方案 | 把代码放入人的工作流 |
| Day 7 | R4 | 事故桥/变更会 | Stop、沟通、恢复、复盘和 Change Request | 对故障与商业变化负责 |
| Day 8–9 | R5 | 验收/高管汇报 | Scorecard、建议、UAT、移交、30 天计划 | 用证据提出可执行结论 |
| Day 10 | 答辩 | 评委会 | 团队演示、个人答辩、学习计划 | 证明个人可以承担技术责任 |

压缩为两天时，每轮 60–120 分钟，仍不得删除事故轮、客户评审和个人答辩。

## 学习回路

每轮执行相同回路：收到有限事实 → 写假设/未知 → 指定 Owner → 建最小证据 → 同伴审阅 → 客户/主持人挑战 → 决定与 Gate → 复盘。禁止先看参考提交；参考提交仅供主持人在评分口径争议时使用。

个人每天更新 [学习日志](templates/individual-learning-journal.md)：自己做了什么决定、什么证据改变了判断、审阅发现了什么、如何向非技术客户解释、下次会怎样做。最后答辩随机抽取本人未负责的交付物，验证是否理解端到端系统。

## 团队必须使用的仓库路径

1. Stage 1–3：重新做问题、数据和边界，不直接复制参考结论；
2. Stage 8 `QH-001 / P7-003`：证明共享 Core 与 Domain 边界；
3. Stage 9–12：运行挑战集、身份、模型、安全、Canary 和回滚；
4. Stage 13–14：演练身份、RLS、Connector、事故 Gate 与证据包；
5. Stage 15：维护 SOW、MAP、Gate、付款、变更和验收；
6. Stage 16：把证据索引到团队提交并接受独立评分。

团队可修改代码，但必须用测试、Trace、ADR 和回退说明证明行为。高风险修复要先加失败用例，再修代码，再演示恢复。

## 通过标准

- 团队：至少 85/100、8 个关键控制全部通过、所有交付物有不同成员审阅；
- 个人：责任量表至少 80/100；至少 Own 一项交付物、Review 他人产物、主导一个决定；并分别留有运行操作、客户解释和复盘证据；
- 任一关键控制失败，团队分数上限为 59；团队高分不能替代个人证据；
- 输出 `TECHNICALLY_RESPONSIBLE` 表示可在监督下承担客户技术责任。连续两次不同场景通过、并由真实项目负责人观察，才适合讨论独立负责。

参考提交得分 93/100，6/6 成员达到模拟标准；它展示证据结构，不是唯一正确方案。

## 资料地图

- [参与者公开案例](case/public-brief.md)
- [主持人手册](facilitator/facilitator-guide.md)
- [客户评委剧本](facilitator/customer-panel.md)
- [事件注入](data/injects.json)
- [团队工作协议](templates/team-working-agreement.md)
- [证据台账](templates/evidence-log.md)
- [决策记录](templates/decision-record.md)
- [个人学习日志](templates/individual-learning-journal.md)
- [参考团队提交](data/reference-submission.json)

真实客户演练时只复用框架和代码，不复制本案例的公司名、人员、价格、基线、授权或签核。先创建独立租户、外置数据区和客户批准的证据包。
