#!/usr/bin/env python3
"""Stage 17 paid Discovery delivery, acceptance and invoice-readiness rehearsal."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fde_platform.deliverycontrol import (DeliveryControlError, analyze_delivery,
                                          load_json, write_outputs)

STAGE = ROOT / "stages/17-paid-discovery-delivery"
DATA = STAGE / "data"
CONTRACT = DATA / "synthetic-contract.json"
ACCEPTANCE = DATA / "synthetic-acceptance.json"
DEPENDENCIES = DATA / "dependency-register.json"
CHANGES = DATA / "change-requests.json"
BASELINE = DATA / "regression-baseline.json"


def check_baseline(report):
    expected = load_json(BASELINE)
    for key, value in expected.items():
        if report.get(key) != value:
            raise DeliveryControlError(
                f"Stage 17 回归失败：{key} 期望 {value!r}，实际 {report.get(key)!r}")
    return True


def run_demo(output: Path, *, check=False, contract_path=CONTRACT,
             acceptance_path=ACCEPTANCE):
    contract = load_json(contract_path)
    acceptance = load_json(acceptance_path)
    report = analyze_delivery(STAGE, contract, acceptance,
                              load_json(DEPENDENCIES), load_json(CHANGES))
    write_outputs(output, report, contract)
    if check:
        check_baseline(report)
    print(f"Stage 17：{report['status']}；合成验收 {report['accepted_deliverable_count']}/"
          f"{report['deliverable_count']}；模拟可开票 CNY {report['simulated_invoice_eligible_cny']}；"
          "实际回款 0；Shadow 未授权。")
    return report


def main():
    parser = argparse.ArgumentParser(description="Stage 17 付费 Discovery 交付与验收")
    parser.add_argument("command", choices=("demo", "validate"))
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/stage-17")
    parser.add_argument("--contract", type=Path, default=CONTRACT)
    parser.add_argument("--acceptance", type=Path, default=ACCEPTANCE)
    parser.add_argument("--check-baseline", action="store_true")
    args = parser.parse_args()
    try:
        report = run_demo(args.output, check=args.check_baseline,
                          contract_path=args.contract, acceptance_path=args.acceptance)
        if args.command == "validate":
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (DeliveryControlError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"检查失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
