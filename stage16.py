#!/usr/bin/env python3
"""Stage 16 team commercial-delivery capstone."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fde_platform.simulation import SimulationError, load_json, prepare_simulation, score_submission
from fde_platform.simulation.capstone import write_score

STAGE = ROOT / "stages/16-team-delivery-simulation"
SCENARIO = STAGE / "data/scenario.json"
REFERENCE = STAGE / "data/reference-submission.json"
BASELINE = STAGE / "data/regression-baseline.json"


def check_baseline(report):
    expected = load_json(BASELINE)
    for key, value in expected.items():
        if report.get(key) != value:
            raise SimulationError(
                f"Stage 16 回归失败：{key} 期望 {value!r}，实际 {report.get(key)!r}")
    return True


def run_demo(output: Path, *, check=False):
    output = Path(output)
    manifest = prepare_simulation(STAGE, output / "simulation-pack")
    report = score_submission(load_json(SCENARIO), load_json(REFERENCE))
    write_score(report, output)
    if check:
        check_baseline(report)
    print(f"Stage 16：{report['status']}；团队 {report['final_score']}/100；"
          f"技术负责就绪 {report['technically_responsible_count']}/{report['member_count']}；真实客户动作 0。")
    return report


def main():
    parser = argparse.ArgumentParser(description="Stage 16 团队真实商业交付模拟")
    parser.add_argument("command", choices=("prepare", "score", "demo"))
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/stage-16")
    parser.add_argument("--submission", type=Path, default=REFERENCE)
    parser.add_argument("--check-baseline", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare_simulation(STAGE, args.output)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "score":
            report = score_submission(load_json(SCENARIO), load_json(args.submission))
            write_score(report, args.output)
            if args.check_baseline:
                check_baseline(report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            run_demo(args.output, check=args.check_baseline)
        return 0
    except (SimulationError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"检查失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
