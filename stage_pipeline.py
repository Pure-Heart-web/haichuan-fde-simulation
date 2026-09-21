#!/usr/bin/env python3
"""Run the staged, offline training checks without treating design as deployment."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from fde_discovery.core import DataError, load, gate
from fde_discovery.report import render
from fde_stage3.audit import AuditError, report_stage2, report_stage3, save_report


def main():
    parser = argparse.ArgumentParser(description='海川 FDE 阶段演练与审计')
    parser.add_argument('stage', choices=['stage1', 'stage2', 'stage3', 'stage4', 'stage5', 'stage6', 'stage7', 'stage8', 'stage9', 'stage10', 'stage11', 'stage12', 'stage13', 'all'])
    parser.add_argument('--output-root', type=Path, default=ROOT / 'outputs')
    parser.add_argument('--stage3-data', type=Path, help='另一个 Stage 3 数据目录，用于审计修改后的副本')
    args = parser.parse_args()
    try:
        if args.stage in ('stage1', 'all'):
            path = ROOT / 'stages/01-discovery/data/simulation.json'
            result = render(load(path), path, args.output_root / 'stage-01')
            print(f'Stage 1: {result["status"]}')
            if not result['complete']:
                return 3
        if args.stage in ('stage2', 'all'):
            result = save_report(args.output_root / 'stage-02', 'Stage 2 模拟资料检查', report_stage2(ROOT))
            print(f'Stage 2: {result["status"]}')
        if args.stage in ('stage3', 'all'):
            result = save_report(args.output_root / 'stage-03', 'Stage 3 合成数据与边界审计', report_stage3(ROOT, args.stage3_data))
            print(f'Stage 3: {result["status"]}')
        if args.stage in ('stage4', 'all'):
            from stage4 import run_demo
            code = run_demo((args.output_root / 'stage-04').resolve())
            if code:
                return code
        if args.stage in ('stage5', 'all'):
            from stage5 import run_demo
            code = run_demo((args.output_root / 'stage-05').resolve())
            if code:
                return code
        if args.stage in ('stage6', 'all'):
            from stage6 import run_demo
            code = run_demo((args.output_root / 'stage-06').resolve())
            if code:
                return code
        if args.stage in ('stage7', 'all'):
            from stage7 import run_demo, check_baseline
            output = (args.output_root / 'stage-07').resolve()
            code = run_demo(output)
            if code:
                return code
            code = check_baseline(output)
            if code:
                return code
        if args.stage in ('stage8', 'all'):
            from stage8 import run_demo, check_baseline
            output = (args.output_root / 'stage-08').resolve()
            code = run_demo(output)
            if code:
                return code
            code = check_baseline(output)
            if code:
                return code
            from stage8_vertical import run_demo as run_vertical, check_baseline as check_vertical
            vertical_output = (args.output_root / 'stage-08-vertical').resolve()
            code = run_vertical(vertical_output)
            if code:
                return code
            code = check_vertical(vertical_output)
            if code:
                return code
        if args.stage in ('stage9', 'all'):
            from stage9 import run_demo, check_baseline
            result = run_demo((args.output_root / 'stage-09').resolve())
            check_baseline(result)
        if args.stage in ('stage10', 'all'):
            from stage10 import run_demo
            run_demo((args.output_root / 'stage-10').resolve(), check_baseline=True)
        if args.stage in ('stage11', 'all'):
            from stage11 import run_demo
            run_demo((args.output_root / 'stage-11').resolve(), check_baseline=True)
        if args.stage in ('stage12', 'all'):
            from stage12 import run_demo
            run_demo((args.output_root / 'stage-12').resolve(), check_baseline=True)
        if args.stage in ('stage13', 'all'):
            from stage13 import run_demo
            run_demo((args.output_root / 'stage-13').resolve(), check_baseline=True)
        return 0
    except (AuditError, DataError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f'检查失败：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
