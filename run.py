#!/usr/bin/env python3
"""Run the local, offline FDE discovery exercise."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from fde_discovery.core import DataError, load
from fde_discovery.report import render


def main():
    parser = argparse.ArgumentParser(description='海川 FDE Stage 1 模拟 Discovery 工具')
    parser.add_argument('command', choices=['validate', 'demo', 'analyze'])
    parser.add_argument('--input', type=Path, default=ROOT / 'stages/01-discovery/data/simulation.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'outputs/stage-01')
    args = parser.parse_args()
    try:
        data = load(args.input)
        if args.command == 'validate':
            print(f'输入校验通过：{len(data["observations"])} 条观察，{len({i["role"] for i in data["interviews"]})} 个访谈角色；模式 {data["mode"]}')
            return 0
        if args.command == 'demo' and data['mode'] != 'simulation':
            raise DataError('demo 仅接受 simulation 数据；真实输入请使用 analyze')
        result = render(data, args.input, args.output)
        print(f'已生成：{args.output.resolve() / "README.md"}\n退出状态：{result["status"]}')
        return 0 if result['complete'] else 3
    except (DataError, OSError) as exc:
        print(f'错误：{exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
