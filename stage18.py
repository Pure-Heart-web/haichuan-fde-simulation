#!/usr/bin/env python3
"""Stage 18 Design Partner acquisition and contracting workbench."""
import argparse
from datetime import date
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from fde_platform.partnercontracting import (
    ContractingError,
    analyze_candidate_pipeline,
    load_json,
    preflight_external_manifest,
    prepare_partner_pack,
    write_demo_outputs,
    write_preflight_outputs,
)

STAGE = ROOT / "stages/18-design-partner-contracting"
DATA = STAGE / "data"
PIPELINE = DATA / "candidate-pipeline.json"
BASELINE = DATA / "regression-baseline.json"
MANIFEST_TEMPLATE = STAGE / "templates/external-partner-manifest.example.json"


def check_baseline(report: dict) -> bool:
    expected = load_json(BASELINE)
    for key, value in expected.items():
        if report.get(key) != value:
            raise ContractingError(
                f"Stage 18 回归失败：{key} 期望 {value!r}，实际 {report.get(key)!r}")
    return True


def run_demo(output: Path, *, check=False, pipeline_path=PIPELINE):
    report = analyze_candidate_pipeline(load_json(pipeline_path))
    write_demo_outputs(output, report)
    if check:
        check_baseline(report)
    print(f"Stage 18：{report['status']}；合成候选 {report['candidate_count']}；"
          f"合格 {report['qualified_candidate_count']}；真实具名客户 0；真实合同 0。")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage 18 Design Partner 获取与签约预检")
    parser.add_argument("command", choices=("demo", "prepare", "preflight"))
    parser.add_argument("--output", type=Path, default=ROOT / "outputs/stage-18")
    parser.add_argument("--pipeline", type=Path, default=PIPELINE)
    parser.add_argument("--manifest", type=Path, help="仓库外的真实客户交易清单")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None)
    parser.add_argument("--check-baseline", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "demo":
            run_demo(args.output, check=args.check_baseline, pipeline_path=args.pipeline)
        elif args.command == "prepare":
            prepare_partner_pack(args.output, load_json(MANIFEST_TEMPLATE))
            print(f"Stage 18 外部交易资料包已生成：{args.output.resolve()}")
        else:
            if not args.manifest:
                raise ContractingError("preflight 必须提供 --manifest")
            report = preflight_external_manifest(args.manifest, ROOT, as_of=args.as_of)
            write_preflight_outputs(args.output, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (ContractingError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"检查失败：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
