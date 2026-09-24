#!/usr/bin/env python3
"""Stage 22 Pilot acceptance and production decision workbench."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fde_platform.pilotacceptance import (
    PilotAcceptanceError, analyze_rehearsal, load_json, prepare_external_pack,
    preflight_external_decision, write_outputs,
)

STAGE = ROOT / "stages/22-pilot-acceptance-production-decision"
DATA = STAGE / "data"
REHEARSAL = DATA / "synthetic-pilot-acceptance.json"
BASELINE = DATA / "regression-baseline.json"
EXTERNAL_TEMPLATE = STAGE / "templates/external-pilot-acceptance.example.json"


def check_baseline(report: dict) -> bool:
    expected = load_json(BASELINE)
    for key, value in expected.items():
        if report.get(key) != value:
            raise PilotAcceptanceError(
                f"Stage 22 回归失败：{key} 期望 {value!r}，实际 {report.get(key)!r}")
    return True


def run_demo(output: Path, *, check=False, record_path=REHEARSAL):
    record = load_json(record_path)
    report = analyze_rehearsal(STAGE, record)
    write_outputs(output, report, record)
    if check:
        check_baseline(report)
    print(f"Stage 22：{report['status']}；验收 {report['accepted_criteria_count']}/6；"
          f"生产准备 {report['production_readiness_ready_count']}/10；"
          f"生产授权 {report['production_authorized']}。")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 22 Pilot 验收与生产决策")
    parser.add_argument("command", choices=("demo", "prepare", "preflight"))
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/stage-22")
    parser.add_argument("--record", type=Path, default=REHEARSAL)
    parser.add_argument("--manifest", type=Path, help="仓库外真实 Pilot 验收清单")
    parser.add_argument("--check-baseline", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "demo":
            run_demo(args.output, check=args.check_baseline, record_path=args.record)
        elif args.command == "prepare":
            prepare_external_pack(args.output, load_json(EXTERNAL_TEMPLATE))
            print(f"Stage 22 外部验收资料包已生成：{args.output.resolve()}")
        else:
            if not args.manifest:
                raise PilotAcceptanceError("preflight 必须提供 --manifest")
            report = preflight_external_decision(args.manifest, ROOT)
            write_outputs(args.output, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (PilotAcceptanceError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"检查失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
