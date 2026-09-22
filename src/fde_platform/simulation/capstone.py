"""Evidence-based scoring for the Stage 16 team delivery capstone."""
from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path


class SimulationError(ValueError):
    """A simulation pack or submission is inconsistent."""


def load_json(path: Path | str) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SimulationError(f"无法读取模拟资料：{exc}") from exc
    if not isinstance(value, dict):
        raise SimulationError("模拟资料必须是 JSON object")
    return value


def _index(rows: list[dict], key: str, where: str) -> dict:
    result = {}
    for row in rows:
        value = row.get(key)
        if not value:
            raise SimulationError(f"{where} 缺少 {key}")
        if value in result:
            raise SimulationError(f"{where} {key} 重复：{value}")
        result[value] = row
    return result


def validate_scenario(scenario: dict) -> dict:
    if scenario.get("mode") != "synthetic_team_delivery_simulation":
        raise SimulationError("仓库场景只能使用 synthetic_team_delivery_simulation")
    rounds = _index(scenario.get("rounds", []), "round_id", "round")
    roles = _index(scenario.get("delivery_roles", []), "role_id", "role")
    artifacts = _index(scenario.get("required_artifacts", []), "artifact_id", "artifact")
    criteria = _index(scenario.get("scoring_criteria", []), "criterion_id", "criterion")
    controls = _index(scenario.get("critical_controls", []), "control_id", "control")
    if sum(row.get("max_points", 0) for row in criteria.values()) != 100:
        raise SimulationError("评分项满分合计必须为 100")
    for item in artifacts.values():
        if item.get("round_id") not in rounds or item.get("owner_role") not in roles:
            raise SimulationError(f"artifact {item['artifact_id']} 的 round/owner 无效")
    for item in criteria.values():
        if item.get("dimension") not in scenario.get("score_dimensions", {}):
            raise SimulationError(f"criterion {item['criterion_id']} 的 dimension 无效")
    return {"rounds": rounds, "roles": roles, "artifacts": artifacts,
            "criteria": criteria, "controls": controls}


def validate_submission(scenario: dict, submission: dict) -> dict:
    indexes = validate_scenario(scenario)
    if submission.get("mode") != "synthetic_team_submission":
        raise SimulationError("提交必须标记为 synthetic_team_submission")
    members = _index(submission.get("members", []), "member_id", "member")
    assigned_roles = defaultdict(list)
    for member in members.values():
        for role in member.get("roles", []):
            if role not in indexes["roles"]:
                raise SimulationError(f"成员 {member['member_id']} 使用未知角色 {role}")
            assigned_roles[role].append(member["member_id"])
    missing_roles = sorted(set(indexes["roles"]) - set(assigned_roles))
    if missing_roles:
        raise SimulationError("未分配交付角色：" + ", ".join(missing_roles))

    artifacts = _index(submission.get("artifacts", []), "artifact_id", "submission artifact")
    missing_artifacts = sorted(set(indexes["artifacts"]) - set(artifacts))
    if missing_artifacts:
        raise SimulationError("缺少交付物：" + ", ".join(missing_artifacts))
    for artifact_id, artifact in artifacts.items():
        if artifact_id not in indexes["artifacts"]:
            raise SimulationError(f"提交含未知交付物 {artifact_id}")
        owner = artifact.get("owner")
        reviewers = artifact.get("reviewers", [])
        if (owner not in members or not artifact.get("evidence_ref") or
                artifact.get("status") not in {"accepted", "conditional", "rejected"}):
            raise SimulationError(f"交付物 {artifact_id} 的 owner、evidence_ref 或 status 无效")
        if not reviewers or owner in reviewers or any(x not in members for x in reviewers):
            raise SimulationError(f"交付物 {artifact_id} 必须由另一成员审阅")
        expected_role = indexes["artifacts"][artifact_id]["owner_role"]
        if expected_role not in members[owner].get("roles", []):
            raise SimulationError(f"交付物 {artifact_id} Owner 未承担 {expected_role}")

    decisions = _index(submission.get("decisions", []), "decision_id", "decision")
    for decision in decisions.values():
        required = ("owner", "trigger_id", "decision", "rationale", "evidence_refs",
                    "risk", "reversibility", "customer_impact")
        missing = [key for key in required if decision.get(key) in (None, "", [])]
        if missing or decision.get("owner") not in members:
            raise SimulationError(f"决策 {decision['decision_id']} 缺完整责任证据")

    control_results = _index(submission.get("control_results", []), "control_id", "control result")
    if set(control_results) != set(indexes["controls"]):
        raise SimulationError("必须逐项提交所有 critical control 结果")
    for control in control_results.values():
        if control.get("status") not in {"passed", "failed"}:
            raise SimulationError(f"control {control['control_id']} 状态无效")
        if (control.get("owner") not in members or control.get("reviewer") not in members or
                control.get("owner") == control.get("reviewer") or not control.get("evidence_ref")):
            raise SimulationError(f"control {control['control_id']} 缺职责分离或证据")

    assessments = _index(submission.get("assessments", []), "criterion_id", "assessment")
    if set(assessments) != set(indexes["criteria"]):
        raise SimulationError("评分必须覆盖全部 criterion")
    evidence_refs = {row["evidence_ref"] for row in artifacts.values()}
    evidence_refs.update(row["evidence_ref"] for row in control_results.values())
    evidence_refs.update(ref for row in decisions.values() for ref in row["evidence_refs"])
    for criterion_id, assessment in assessments.items():
        criterion = indexes["criteria"][criterion_id]
        points = assessment.get("awarded_points")
        if not isinstance(points, int) or not 0 <= points <= criterion["max_points"]:
            raise SimulationError(f"criterion {criterion_id} 分数越界")
        if not assessment.get("assessor") or not assessment.get("rationale"):
            raise SimulationError(f"criterion {criterion_id} 缺 assessor/rationale")
        if not assessment.get("evidence_refs") or any(
                ref not in evidence_refs for ref in assessment["evidence_refs"]):
            raise SimulationError(f"criterion {criterion_id} 引用了不存在的证据")

    contributions = submission.get("individual_contributions", [])
    for row in contributions:
        if row.get("member_id") not in members or row.get("type") not in {
                "owned_artifact", "decision", "peer_review", "operational_action",
                "customer_explanation", "retrospective"} or not row.get("evidence_ref"):
            raise SimulationError("个人贡献记录无效")
        if row["evidence_ref"] not in evidence_refs:
            raise SimulationError(f"个人贡献引用不存在：{row['evidence_ref']}")
    return {**indexes, "members": members, "submission_artifacts": artifacts,
            "decisions": decisions, "control_results": control_results,
            "assessments": assessments, "contributions": contributions,
            "evidence_refs": evidence_refs}


def score_submission(scenario: dict, submission: dict) -> dict:
    data = validate_submission(scenario, submission)
    dimension_scores = {name: {"earned": 0, "max": maximum}
                        for name, maximum in scenario["score_dimensions"].items()}
    for criterion_id, assessment in data["assessments"].items():
        dimension = data["criteria"][criterion_id]["dimension"]
        dimension_scores[dimension]["earned"] += assessment["awarded_points"]
    raw_score = sum(row["earned"] for row in dimension_scores.values())
    failed_controls = [control_id for control_id, row in data["control_results"].items()
                       if row["status"] == "failed"]
    final_score = min(raw_score, 59) if failed_controls else raw_score

    contribution_types = defaultdict(set)
    contribution_count = defaultdict(int)
    for row in data["contributions"]:
        contribution_types[row["member_id"]].add(row["type"])
        contribution_count[row["member_id"]] += 1
    owned = defaultdict(int)
    accepted_owned = defaultdict(int)
    reviewed = defaultdict(int)
    for row in data["submission_artifacts"].values():
        owned[row["owner"]] += 1
        if row.get("status") == "accepted":
            accepted_owned[row["owner"]] += 1
        for reviewer in row["reviewers"]:
            reviewed[reviewer] += 1
    decisions = defaultdict(int)
    for row in data["decisions"].values():
        decisions[row["owner"]] += 1

    individual = {}
    for member_id, member in data["members"].items():
        rubric = member.get("technical_accountability", {})
        rubric_keys = ("judgment", "evidence", "operations", "communication", "learning")
        if set(rubric) != set(rubric_keys) or any(
                not isinstance(rubric[key], int) or not 0 <= rubric[key] <= 4
                for key in rubric_keys):
            raise SimulationError(f"成员 {member_id} technical_accountability 必须有五项 0-4 评分")
        assessors = member.get("accountability_assessors", [])
        accountability_evidence = member.get("accountability_evidence_refs", [])
        if (len(set(assessors)) < 2 or member_id in assessors or
                not accountability_evidence or any(
                    ref not in data["evidence_refs"] for ref in accountability_evidence)):
            raise SimulationError(f"成员 {member_id} 需要两名非本人评委和有效责任证据")
        accountability_score = sum(rubric.values()) * 5
        required_types = {"owned_artifact", "decision", "peer_review",
                          "operational_action", "customer_explanation", "retrospective"}
        missing_types = sorted(required_types - contribution_types[member_id])
        role_coverage = bool(accepted_owned[member_id] and reviewed[member_id] and
                             decisions[member_id])
        critical_owned_failure = any(row["status"] == "failed" and row["owner"] == member_id
                                     for row in data["control_results"].values())
        ready = (accountability_score >= 80 and not missing_types and role_coverage and
                 not critical_owned_failure and not failed_controls and final_score >= 80)
        individual[member_id] = {
            "display_name": member.get("display_name", member_id),
            "roles": member["roles"], "accountability_score": accountability_score,
            "owned_artifact_count": owned[member_id], "peer_review_count": reviewed[member_id],
            "decision_count": decisions[member_id], "contribution_count": contribution_count[member_id],
            "missing_contribution_types": missing_types,
            "critical_control_failure_owned": critical_owned_failure,
            "readiness": "TECHNICALLY_RESPONSIBLE" if ready else "SUPERVISED_PRACTICE_REQUIRED",
        }
    responsible_count = sum(row["readiness"] == "TECHNICALLY_RESPONSIBLE"
                            for row in individual.values())
    if failed_controls:
        status = "TEAM_NOT_READY_CRITICAL_CONTROL_FAILURE"
    elif final_score >= 85 and responsible_count == len(individual):
        status = "TEAM_READY_FOR_SUPERVISED_COMMERCIAL_DELIVERY"
    elif final_score >= 75:
        status = "TEAM_ITERATE_BEFORE_CUSTOMER_DELIVERY"
    else:
        status = "TEAM_FOUNDATION_GAPS"
    return {
        "status": status, "mode": submission["mode"], "team_id": submission.get("team_id"),
        "raw_score": raw_score, "final_score": final_score,
        "dimension_scores": dimension_scores, "failed_critical_controls": failed_controls,
        "member_count": len(individual), "technically_responsible_count": responsible_count,
        "individual_readiness": individual,
        "real_customer_data_used": False, "external_customer_actions": 0,
        "boundary": "模拟通过只允许进入受监督的商业交付练习，不代表可独立签约或操作真实客户生产系统",
    }


def render_score(report: dict) -> str:
    dims = "\n".join(f"| {name} | {row['earned']} | {row['max']} |"
                     for name, row in report["dimension_scores"].items())
    people = "\n".join(
        f"| {row['display_name']} | {', '.join(row['roles'])} | {row['accountability_score']} | "
        f"{row['owned_artifact_count']} | {row['peer_review_count']} | {row['decision_count']} | {row['readiness']} |"
        for row in report["individual_readiness"].values())
    return f"""# Stage 16 团队交付模拟评分

状态：`{report['status']}`；团队分数：**{report['final_score']}/100**；技术负责就绪：{report['technically_responsible_count']}/{report['member_count']}。

> 本结果来自合成团队提交。通过表示可以进入受监督的客户交付练习，不表示具备签约权限，也不授权访问真实客户生产系统。

## 团队维度

| 维度 | 得分 | 满分 |
|---|---:|---:|
{dims}

关键控制失败：{', '.join(report['failed_critical_controls']) or '无'}。

## 个人技术责任证据

| 成员 | 角色 | 责任评分 | Own | Review | Decision | 结论 |
|---|---|---:|---:|---:|---:|---|
{people}

个人结论同时要求：责任评分不低于 80；拥有交付物、跨成员审阅和决策；覆盖运行操作、客户解释与复盘；团队无关键控制失败。团队高分不能替代个人证据。
"""


def write_score(report: dict, output: Path | str) -> None:
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "team-score.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "team-score.md").write_text(render_score(report), encoding="utf-8")


def prepare_simulation(stage_root: Path, output: Path) -> dict:
    output = Path(output)
    participant = output / "participant-pack"
    facilitator = output / "facilitator-pack"
    participant.mkdir(parents=True, exist_ok=True)
    facilitator.mkdir(parents=True, exist_ok=True)
    for relative in ("README.md", "case/public-brief.md", "data/team-submission.blank.json",
                     "guides/technical-accountability-standard.md",
                     "templates/team-working-agreement.md", "templates/evidence-log.md",
                     "templates/decision-record.md", "templates/individual-learning-journal.md",
                     "templates/submission-guide.md"):
        source = stage_root / relative
        target = participant / source.name
        shutil.copyfile(source, target)
    for source in sorted((stage_root / "roles").glob("*.md")):
        shutil.copyfile(source, participant / f"role-{source.name}")
    for relative in ("facilitator/facilitator-guide.md", "facilitator/customer-panel.md",
                     "data/injects.json", "data/reference-submission.json"):
        source = stage_root / relative
        target = facilitator / source.name
        shutil.copyfile(source, target)
    manifest = {"status": "TEAM_SIMULATION_PACK_READY", "mode": "synthetic_only",
                "participant_files": sorted(p.name for p in participant.iterdir()),
                "facilitator_files": sorted(p.name for p in facilitator.iterdir()),
                "real_customer_data": False, "external_actions": 0}
    (output / "pack-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest
