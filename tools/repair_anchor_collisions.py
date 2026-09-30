"""Disambiguate existing duplicate file anchors without changing source bodies."""
from collections import defaultdict
import json
from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parent.parent


def repair(vault: Path) -> list[dict]:
    groups = defaultdict(list)
    for path in sorted((vault / '10-底本').rglob('*.md')):
        if path.name.startswith(('00-', '_')):
            continue
        raw = path.read_text(encoding='utf-8')
        if not raw.startswith('---\n'):
            continue
        front = raw.split('---', 2)[1]
        fm = yaml.safe_load(front) or {}
        if fm.get('anchor_id'):
            groups[fm['anchor_id']].append((path, raw, fm))
    changes = []
    for old, group in groups.items():
        if len(group) < 2:
            continue
        for number, (path, raw, fm) in enumerate(group, 1):
            # Keep every conflicting file unique; never silently select one old meaning.
            prefix, rest = old.split('-', 1)
            marker = re.sub(r'[^\w\u3400-\u9fff]+', '', str(fm.get('册', '')))
            marker = marker or f'同名{number:02d}'
            new = f'{prefix}-{marker}-{rest}'
            if new in groups:
                raise ValueError(f'迁移目标已存在：{new}')
            parts = raw.split('---', 2)
            front = re.sub(r'^anchor_id:.*$', f'anchor_id: {new}\n原anchor_id: {old}', parts[1], count=1, flags=re.M)
            path.write_text('---' + front + '---' + parts[2], encoding='utf-8')
            changes.append({'path': str(path.relative_to(vault)), 'old': old, 'new': new})
    if changes:
        report = ROOT / 'docs/anchor-collision-migration.json'
        report.write_text(json.dumps(changes, ensure_ascii=False, indent=2), encoding='utf-8')
    return changes


if __name__ == '__main__':
    changes = repair(ROOT / '六壬vault')
    print(json.dumps(changes, ensure_ascii=False, indent=2))
