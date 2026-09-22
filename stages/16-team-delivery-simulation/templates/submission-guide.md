# 团队提交 JSON 填写说明

复制 `team-submission.blank.json`，不要编辑场景或参考基线。所有 Evidence ID 先登记到 Evidence Log。

成员：

```json
{"member_id":"M01","display_name":"成员名","roles":["engagement_lead"],
 "technical_accountability":{"judgment":0,"evidence":0,"operations":0,"communication":0,"learning":0},
 "accountability_assessors":["facilitator-a","facilitator-b"],
 "accountability_evidence_refs":["EV-A01","EV-C07"]}
```

交付物：

```json
{"artifact_id":"A01","owner":"M01","reviewers":["M02"],
 "status":"accepted","evidence_ref":"EV-A01"}
```

决定必须包含 `decision_id`、`owner`、`trigger_id`、`decision`、`rationale`、`evidence_refs`、`risk`、`reversibility`、`customer_impact`。Control 逐项填写 `control_id/status/owner/reviewer/evidence_ref`。评分逐项填写 `criterion_id/awarded_points/assessor/rationale/evidence_refs`。

每位成员在 `individual_contributions` 各引用一次六种证据：`owned_artifact`、`decision`、`peer_review`、`operational_action`、`customer_explanation`、`retrospective`。同一证据可以支持多个真实相关的能力，但不能为了凑数重复引用无关内容。

评委先独立评分再合并。成员不得担任自己的责任量表评委；至少两位评委署名。个人技术责任评分是评委基于证据的结论，不是自评。
