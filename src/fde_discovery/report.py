"""Render reviewable Markdown deliverables from structured discovery inputs."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from .core import STEPS, gate, metrics


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', '<br>')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(map(cell, headers)) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows]) + '\n'


def fmt(value):
    return '未知 / 无样本' if value is None else f'{value:.2f}'


def render(data, input_path, output_dir):
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    result, decision = metrics(data), gate(data)
    now = datetime.now(timezone.utc).isoformat(timespec='seconds')
    mode_note = ('**全部为模拟数据，仅用于教学；不代表真实客户发现或开发授权。**'
                 if data['mode'] == 'simulation' else
                 '**来源由录入者声明为真实；工具未验证真实性，仍需负责人回读与审批。**')
    prefix = f'{mode_note}\n\n数据集：`{data["dataset_id"]}` · 生成时间：{now}\n\n'
    prefix += '计算指标按输入重算；问题定义、决策表及确认意见来自人工录入，修改样本后须重新回读。证据位置见 [证据索引](evidence-index.md)。\n\n'
    files = {}
    a = data['assessment']
    files['01-problem-brief.md'] = '# Problem Brief V1\n\n' + prefix + a['problem'] + '\n\n## 待验证假设\n\n' + a['hypothesis'] + '\n\n## 证据分类\n\n' + table(['类别', '记录', '证据'], [(e['type'], e['text'], ', '.join(e['source_ids']) or '尚无') for e in a['evidence']]) + '\n## Non-goals\n\n' + '\n'.join('- ' + x for x in a['non_goals']) + '\n\n当前决定：按退出条件报告决定继续 Discovery 或进入下一阶段范围讨论；尚未批准正式开发。\n'
    files['02-as-is-workflow.md'] = '# As-Is Workflow\n\n' + prefix + table(['步骤', '角色', '实际行为与分支', '证据'], [(s['step'], s['owner'], s['detail'], s['source_id']) for s in a['workflow']]) + '\n以上为人工记录的实际流程，顺序可因案例反复；样本不足时需补充回放。首次实质回复可能是澄清，不等于已报价或已解决。\n'
    files['03-decision-map.md'] = '# Decision Map\n\n' + prefix + table(['决策', '输入', '依据', 'Owner', '缺失/冲突动作', '辅助与人工边界', '证据'], [(d['name'], d['inputs'], d['basis'], d['owner'], d['fallback'], d['boundary'], d['source_id']) for d in data['decisions']])
    files['04-data-inventory.md'] = '# Data / Knowledge Inventory V0\n\n' + prefix + table(['资料', '种类', 'Owner', '版本', '质量限制', '访问', '证据'], [(i['name'], i['kind'], i['owner'], i['version'], i['quality'], i['access'], i['source_id']) for i in data['inventory']]) + '\n尚无已确认的生产 API、权限、目录版本治理或数据完整性结论。下一步见 Open Questions。\n'
    metric_rows = []
    for key, label in [('sales_active_minutes', '销售主动处理'), ('simple_active_minutes', '简单询盘主动处理'), ('complex_active_minutes', '复杂询盘主动处理'), ('first_reply_minutes', '首次实质回复自然耗时')]:
        s = result[key]
        metric_rows.append([label, s['n'], fmt(s['total']), fmt(s['mean']), fmt(s['median']), fmt(s['p90'])])
    baseline = '# Baseline Metrics\n\n' + prefix + table(['指标（分钟）', 'n', '合计', '均值', '中位数', 'P90'], metric_rows)
    ratio = '未知' if result['escalation_ratio'] is None else f'{result["escalation_ratio"]:.1%}'
    baseline += f'\n技术升级：{result["escalated_count"]}/{result["sample_count"]}（{ratio}）。工程师样本总投入：{fmt(result["engineer_total_minutes"])} 分钟。\n\n'
    baseline += '## 复杂样本各步骤\n\n' + table(['步骤', '平均主动分钟'], [(STEPS[k], fmt(v)) for k, v in sorted(result['complex_step_mean_minutes'].items(), key=lambda kv: -(kv[1] or 0))])
    baseline += '\n## 逐案例追溯\n\n' + table(['案例', '类型', '主动分钟', '工程师分钟', '升级原因', '证据'], [(o['id'], o['complexity'], fmt(sum(o['steps'].values())), fmt(o['engineer_minutes']), o['escalation_reason'] or '无', o['source_id']) for o in data['observations']])
    baseline += '\n口径：销售六步主动时间相加，排除等待；首次回复按自然时间差；工程师可能与销售并行，不能直接加成端到端时长；P90 使用线性插值。输入为定向观察样本。每日有效询盘量、工程师每日咨询次数及 ROI 未知，不用样本数除以天数代替。样本比例不代表总体。\n'
    files['05-baseline-metrics.md'] = baseline
    files['06-open-questions.md'] = '# Open Questions\n\n' + prefix + table(['问题', '影响', '验证方法', 'Owner', '到期', '状态'], [(q['question'], q['impact'], q['method'], q['owner'], q['due'], '待验证') for q in data['questions']])
    gate_note = {'SIMULATION_READY': '模拟条件齐全，可进入 Stage 2 教学演练；真实客户条件尚未验证。', 'REAL_REVIEW_REQUIRED': '结构性条件齐全，交负责人复核证据和决定是否进入 Stage 2；不自动批准开发。', 'NEEDS_MORE_DISCOVERY': '条件尚不齐全，继续 Discovery 并补充下表缺口。'}[decision['status']]
    files['exit-review.md'] = '# Stage 1 退出条件\n\n' + prefix + f'状态：`{decision["status"]}`\n\n{gate_note}\n\n' + table(['条件', '结果', '证据', '确认备注'], [(r['criterion'], '满足' if r['passed'] else '缺口', ', '.join(r['evidence']), r.get('note', '结构性覆盖检查')) for r in decision['checks']]) + '\n人工签阅（练习时填写）：FDE ____；流程 Owner ____；知识 Owner ____；买单者 ____；日期 ____。程序只检查结构、引用和覆盖，不判断证据真实性或业务结论正确性。\n'
    source_rows = []
    for s in data['sources']:
        path = (Path(input_path).resolve().parent / s['path']).resolve()
        relative = quote(os.path.relpath(path, output), safe='/')
        source_rows.append([s['id'], s['title'], s['origin'], f'[原始材料]({relative})（按证据 ID 定位）'])
    files['evidence-index.md'] = '# 证据索引\n\n' + prefix.replace('证据位置见 [证据索引](evidence-index.md)。', '') + table(['ID', '内容', '来源类型', '位置'], source_rows)
    files['README.md'] = '# Stage 1 交付物索引\n\n' + prefix + '\n'.join(f'- [{name}]({name})' for name in files) + f'\n\n退出状态：`{decision["status"]}`。{gate_note}\n\n[机器可读指标与检查](metrics.json)。\n'
    files['metrics.json'] = json.dumps({'dataset_id': data['dataset_id'], 'mode': data['mode'], 'generated_at': now, 'metrics': result, 'gate': decision}, ensure_ascii=False, indent=2) + '\n'
    # Prepare all contents before replacing files; a validation failure never writes reports.
    for name, content in files.items():
        temp = output / ('.' + name + '.tmp')
        temp.write_text(content, encoding='utf-8')
        temp.replace(output / name)
    return decision
