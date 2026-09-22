#!/usr/bin/env python3
"""Stage 15 commercial delivery-room rehearsal."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fde_platform.commercial import DealValidationError, analyze_deal, load_deal, write_outputs

DATA = ROOT / "stages/15-commercial-delivery/data"
DEFAULT_DEAL = DATA / "haichuan-deal-record.json"
BASELINE = DATA / "regression-baseline.json"


def check_baseline(report: dict) -> bool:
    expected = json.loads(BASELINE.read_text(encoding="utf-8"))
    for key, value in expected.items():
        if report.get(key) != value:
            raise DealValidationError(
                f"Stage 15 回归失败：{key} 期望 {value!r}，实际 {report.get(key)!r}")
    return True


def run_demo(output: Path, *, deal_file: Path = DEFAULT_DEAL,
             check: bool = False) -> dict:
    deal = load_deal(deal_file)
    report = write_outputs(deal, output)
    if check:
        check_baseline(report)
    print(f"Stage 15：{report['status']}；下一 Gate {report['next_gate']}；"
          f"已签约 CNY {report['booked_value_cny']}；真实收入声明 false。")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 15 商务交付资料与 Gate 演练")
    parser.add_argument("command", choices=("demo", "validate", "report"))
    parser.add_argument("--deal-file", type=Path, default=DEFAULT_DEAL)
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/stage-15")
    parser.add_argument("--check-baseline", action="store_true")
    args = parser.parse_args()
    try:
        deal = load_deal(args.deal_file)
        if args.command == "validate":
            report = analyze_deal(deal)
            if args.check_baseline:
                check_baseline(report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            run_demo(args.output, deal_file=args.deal_file,
                     check=args.check_baseline)
        return 0
    except (DealValidationError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"检查失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
