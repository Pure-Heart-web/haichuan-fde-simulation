#!/usr/bin/env python3
"""Stage 20 customer acceptance and Pilot investment decision workbench."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fde_platform.acceptanceinvestment import (
    AcceptanceInvestmentError,
    analyze_rehearsal,
    load_json,
    prepare_external_pack,
    preflight_external_decision,
    write_outputs,
)

STAGE = ROOT / "stages/20-acceptance-investment"
DATA = STAGE / "data"
REHEARSAL = DATA / "synthetic-acceptance-investment.json"
BASELINE = DATA / "regression-baseline.json"
EXTERNAL_TEMPLATE = STAGE / "templates/external-acceptance-investment.example.json"


def check_baseline(report: dict) -> bool:
    expected = load_json(BASELINE)
    for key, value in expected.items():
        if report.get(key) != value:
            raise AcceptanceInvestmentError(
                f"Stage 20 回归失败：{key} 期望 {value!r}，实际 {report.get(key)!r}")
    return True


def run_demo(output: Path, *, check=False, record_path=REHEARSAL):
    record = load_json(record_path)
    report = analyze_rehearsal(STAGE, record)
    write_outputs(output, report, record)
    if check:
        check_baseline(report)
    print(f"Stage 20：{report['status']}；验收 {report['accepted_deliverable_count']}/6；"
          f"Steering {report['steering_decision']}；Pilot 授权 {report['pilot_authorized']}。")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 20 客户验收与 Pilot 投资门")
    parser.add_argument("command", choices=("demo", "prepare", "preflight"))
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/stage-20")
    parser.add_argument("--record", type=Path, default=REHEARSAL)
    parser.add_argument("--manifest", type=Path, help="仓库外真实客户验收和投资清单")
    parser.add_argument("--check-baseline", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "demo":
            run_demo(args.output, check=args.check_baseline, record_path=args.record)
        elif args.command == "prepare":
            prepare_external_pack(args.output, load_json(EXTERNAL_TEMPLATE))
            print(f"Stage 20 外部验收资料包已生成：{args.output.resolve()}")
        else:
            if not args.manifest:
                raise AcceptanceInvestmentError("preflight 必须提供 --manifest")
            report = preflight_external_decision(args.manifest, ROOT)
            write_outputs(args.output, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (AcceptanceInvestmentError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"检查失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
