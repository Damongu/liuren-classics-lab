#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为历史 --card 落的 30-课例/*.md 补 v3 frontmatter 字段。

从每张卡自身 frontmatter 的 `课式/日干支/占时/月将` 计算 anchor_id，
在 frontmatter 顶部插入 `anchor_id`、`作者: 排盘守卫`、`与六壬关系: 主体`
（若缺）。仅追加行，不改动既有 frontmatter 的字段顺序与文本格式。

用法：
  python3 tools/backfill_paipan_card_v3.py --vault 六壬vault
  python3 tools/backfill_paipan_card_v3.py --vault 六壬vault --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


DEFAULTS = [
    ("anchor_id", None),        # 特殊：动态算
    ("作者", "排盘守卫"),
    ("与六壬关系", "主体"),
]


def split_fm(raw: str):
    if not raw.startswith("---"):
        return None, None, raw
    lines = raw.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], i, raw
    return None, None, raw


def make_anchor_id(fm: dict) -> str:
    return f"排盘守卫-{fm['课式']}{fm['日干支']}{fm['占时']}{fm['月将']}-001"


def backfill_file(path: Path, dry_run: bool = False) -> tuple[bool, str]:
    raw = path.read_text(encoding="utf-8")
    fm_lines, close_idx, _ = split_fm(raw)
    if fm_lines is None:
        return False, "无 frontmatter，跳过"

    fm_text = "\n".join(fm_lines)
    data = yaml.safe_load(fm_text) or {}
    if not isinstance(data, dict):
        return False, "frontmatter 非 mapping，跳过"

    prepend = []
    changed = []

    # anchor_id
    if not data.get("anchor_id"):
        needed = ["课式", "日干支", "占时", "月将"]
        if not all(k in data for k in needed):
            return False, f"缺 {needed} 无法计算 anchor_id"
        prepend.append(f"anchor_id: {make_anchor_id(data)}")
        changed.append("anchor_id")

    if not data.get("作者"):
        prepend.append("作者: 排盘守卫")
        changed.append("作者")

    if not data.get("与六壬关系"):
        prepend.append("与六壬关系: 主体")
        changed.append("与六壬关系")

    if not prepend:
        return False, "字段齐备，无需修改"

    lines = raw.split("\n")
    # lines[0] == '---'；把 prepend 插入其后、原 frontmatter 之前
    new_lines = [lines[0]] + prepend + lines[1:]
    new_raw = "\n".join(new_lines)

    if dry_run:
        return True, f"补 {changed}（dry-run）"
    path.write_text(new_raw, encoding="utf-8")
    return True, f"补 {changed} → anchor_id={prepend[0].split(': ',1)[1] if prepend[0].startswith('anchor_id') else '(已有)'}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default="六壬vault")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    d = Path(a.vault) / "30-课例"
    if not d.is_dir():
        print(f"找不到 {d}", file=sys.stderr)
        return 2

    changed = 0
    for p in sorted(d.rglob("*.md")):
        if p.name.startswith("_") or p.name.startswith("00-"):
            continue
        did, msg = backfill_file(p, dry_run=a.dry_run)
        print(f"[{'CHANGE' if did else '  skip'}] {p.name}  ·  {msg}")
        if did:
            changed += 1
    print(f"\n共处理 {changed} 张卡")
    return 0


if __name__ == "__main__":
    sys.exit(main())
