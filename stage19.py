#!/usr/bin/env python3
"""Stage 19 live paid Discovery execution workbench."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fde_platform.discoveryexecution import (
    DiscoveryExecutionError,
    analyze_rehearsal,
    load_json,
    prepare_external_pack,
    preflight_external_execution,
    write_outputs,
)

STAGE = ROOT / "stages/19-live-discovery-execution"
DATA = STAGE / "data"
REHEARSAL = DATA / "synthetic-execution.json"
BASELINE = DATA / "regression-baseline.json"
EXTERNAL_TEMPLATE = STAGE / "templates/external-discovery-execution.example.json"


def check_baseline(report: dict) -> bool:
    expected = load_json(BASELINE)
    for key, value in expected.items():
        if report.get(key) != value:
            raise DiscoveryExecutionError(
                f"Stage 19 回归失败：{key} 期望 {value!r}，实际 {report.get(key)!r}")
    return True


def run_demo(output: Path, *, check=False, record_path=REHEARSAL):
    record = load_json(record_path)
    report = analyze_rehearsal(record)
    write_outputs(output, report, record)
    if check:
        check_baseline(report)
    print(f"Stage 19：{report['status']}；现场活动 {report['session_count']}；"
          f"交付物 {report['ready_deliverable_count']}/6；真实客户活动 0。")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 19 付费 Discovery 现场执行")
    parser.add_argument("command", choices=("demo", "prepare", "preflight"))
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/stage-19")
    parser.add_argument("--record", type=Path, default=REHEARSAL)
    parser.add_argument("--manifest", type=Path, help="仓库外真实 Discovery 执行清单")
    parser.add_argument("--check-baseline", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "demo":
            run_demo(args.output, check=args.check_baseline, record_path=args.record)
        elif args.command == "prepare":
            prepare_external_pack(args.output, load_json(EXTERNAL_TEMPLATE))
            print(f"Stage 19 外部执行资料包已生成：{args.output.resolve()}")
        else:
            if not args.manifest:
                raise DiscoveryExecutionError("preflight 必须提供 --manifest")
            report = preflight_external_execution(args.manifest, ROOT)
            write_outputs(args.output, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (DiscoveryExecutionError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"检查失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
