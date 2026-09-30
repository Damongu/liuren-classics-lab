"""Generate a source-bound seven-part guide for an actual v3 source anchor."""
from __future__ import annotations
import argparse
from datetime import datetime
import json
from pathlib import Path
import re

from guide import grade_of
from vault_sources import VAULT, get_source


def net_chars(raw: str) -> int:
    raw = re.sub(r'<!--.*?-->', '', raw, flags=re.S)
    raw = re.sub(r'^#{1,6} .*$', '', raw, flags=re.M)
    raw = re.sub(r'^>.*$', '', raw, flags=re.M)
    raw = re.sub(r'<[^>]+>', '', raw)
    return len(re.sub(r'\s', '', raw))


def check_guide(raw: str, item: dict) -> list[str]:
    errors = []
    if f'源hash: {item["note_sha256"]}' not in raw:
        errors.append('原文变化，导读已过期')
    if 'TODO(agent)' in raw:
        errors.append('导读待填写，不可开讲')
    for n in range(1, 8):
        if not re.search(rf'^## {n} ', raw, re.M):
            errors.append(f'缺第{n}件导读')
    grade, _, limit = grade_of(net_chars(item['text']))
    body = raw.split('---', 2)[-1] if raw.startswith('---') else raw
    if net_chars(body) > limit:
        errors.append(f'{grade}档导读超过{limit}字预算，须拆节')
    if grade == 'C' and not re.search(r'^\|.*\|', body, re.M):
        errors.append('C档须有精读/略读/回收分区表')
    return errors


def render(anchor: str) -> str:
    item = get_source(anchor)
    count = net_chars(item['text'])
    grade, minutes, words = grade_of(count)
    return '\n'.join([
        '---', '类型: 导读卡', f'原文锚点: {anchor}', f'源hash: {item["note_sha256"]}',
        f'导读档: {grade}', 'tags: [导读, v3]', '---', '', f'# 导读 {anchor}', '',
        '## 1 坐标', f'来源：`{item["path"]}`；层次：{item["layer"]}。', '',
        '## 2 文本体检', f'{count} 字，{grade} 档。{item["evidence"]}；未核原刻。',
        '经文、释文、眉批、校记与课盘不可混作同一作者或年代。', '',
        '## 3 切块与读法', 'TODO(agent)：列出本节精读块、略读块与跳过内容的回收时点；C档必须写分区表。', '',
        '## 4 生词护栏', 'TODO(agent)：只列本节必须解释的词，未学用途不提前考核。', '',
        '## 5 待答问题', 'TODO(agent)：写能检验本节理解的开放问题，不附答案。', '',
        '## 6 冲突预警', '待核原刻；有补校或未署来源括注时，移交复盘官确认文献层次。', '',
        '## 7 阅读预算', f'导读不超过{minutes}分钟／{words}字；超预算拆教学单元，不压缩取证。', '',
        '## 回执', '本节解决什么问题？先精读哪块？回执是软门槛，不能冒充正式复述验收。', '',
    ])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--anchor', required=True)
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--receipt', choices=('pass', 'fail'))
    ap.add_argument('--minutes', type=int, default=0)
    args = ap.parse_args(argv)
    if args.minutes < 0:
        ap.error('阅读耗时不能为负数')
    item = get_source(args.anchor)
    folder = VAULT / '15-导读/v3'
    path = folder / (args.anchor + '-导读.md')
    if args.receipt:
        if not path.exists():
            ap.error('未完成导读不能记录回执')
        problems = check_guide(path.read_text(encoding='utf-8'), item)
        if problems:
            ap.error('；'.join(problems))
        state_path = VAULT / '60-掌握度/_guide_v3_receipts.json'
        data = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else []
        grade, limit, _ = grade_of(net_chars(item['text']))
        data.append({'anchor': args.anchor, 'grade': grade, 'result': args.receipt,
                     'minutes': args.minutes, 'limit': limit, 'at': datetime.now().isoformat(timespec='seconds')})
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        print('已记录导读回执；收尾 --curriculum v3 检查 R12–R14')
        return 0
    if args.check:
        if not path.exists():
            print('导读卡缺失');return 1
        raw = path.read_text(encoding='utf-8')
        problems = check_guide(raw, item)
        if problems:
            print('；'.join(problems));return 1
        print('导读可用');return 0
    folder.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(render(args.anchor), encoding='utf-8')
    print(path)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
