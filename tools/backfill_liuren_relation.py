#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
`与六壬关系` 批量回填（Task 4，甲方案 - 开放集）。

- 消费：`六壬vault/10-底本/**/*.md` 的 frontmatter
- 派生 penname：读 `作者` 字段（优先），否则回落到 `书` 字段经
  `generate_anchor_ids.book_to_penname` 映射
- 派生 chapter：`卷篇 / 节 / 篇 / 册` 优先，文件名 stem 兜底
- 查 `liuren_relation_rules.default_relation(penname, chapter)`
- **幂等**：只在 `与六壬关系` 缺字段或值为空时写入；已存在任何非空值都跳过
- **文本级 patch**：不重排字段、不改 tags flow 风格；缺字段追加到 fm 尾部，
  空值就地替换字段行

CLI:
  python3 tools/backfill_liuren_relation.py --selftest
  python3 tools/backfill_liuren_relation.py [--vault 六壬vault]           # dry-run
  python3 tools/backfill_liuren_relation.py --vault 六壬vault --apply     # 写入
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

# 复用 Task 3a 的花名映射（书 → penname）与 slug/文本工具
sys.path.insert(0, str(Path(__file__).resolve().parent))
from generate_anchor_ids import (  # noqa: E402
    _BOOK_TO_PENNAME,
    _chapter_of,
    _has_field,
    _insert_field,
    _replace_field_line,
    _split_frontmatter,
    book_to_penname as _book_to_penname_upstream,
)
from liuren_relation_rules import RULES, default_relation  # noqa: E402


# ---------- alias：书 → 花名（补充 book_to_penname 未覆盖的书名） ----------
# 由于 3a 已列全常见书魂，此处保留一个空 alias hook，未来遇到新书可直接扩展；
# 3b 拆出的 阿甲 / 林景行 是 `作者` 字段的值，本工具不通过书名派生。
_BOOK_ALIAS: dict[str, str] = {
    # e.g. "神机制敌太白阴经": "太白"
    # 目前 3a 的 _BOOK_TO_PENNAME 已含 3 种太白别名与 2 种中黄经别名，无需再补
}


def book_to_penname(book: str) -> str:
    """把 `书` 字段值映射到花名；未知书抛 KeyError。"""
    if not isinstance(book, str):
        raise KeyError(f"book 必须是 str，实为 {type(book).__name__}: {book!r}")
    key = book.strip()
    if key in _BOOK_TO_PENNAME:
        return _BOOK_TO_PENNAME[key]
    if key in _BOOK_ALIAS:
        return _BOOK_ALIAS[key]
    raise KeyError(f"未知书名：{book!r}（未在 _BOOK_TO_PENNAME/_BOOK_ALIAS 登记）")


# ---------- 单文件 backfill ----------
@dataclass
class RelResult:
    changed: bool
    before: str | None
    after: str | None
    reason: str
    path: str
    penname: str = ""
    chapter: str = ""


def _penname_from_data(data: dict, path: Path) -> str:
    """优先 `作者` 字段（Task 3a/3b 已写入的花名），否则用 `书` 派生。

    未知花名/书名 → KeyError（让流程停下、便于报告差异）。
    """
    author_val = data.get("作者")
    if isinstance(author_val, str) and author_val.strip():
        penname = author_val.strip()
        if penname not in RULES:
            raise KeyError(
                f"作者 花名 {penname!r} 未在 liuren_relation_rules.RULES 登记 "
                f"(path={path})"
            )
        return penname
    # 回落到 `书` 字段
    book_val = data.get("书")
    if not isinstance(book_val, str) or not book_val.strip():
        raise KeyError(f"frontmatter 缺 `书` 与 `作者`，无法派生 penname (path={path})")
    return book_to_penname(book_val)


def backfill_one(path: Path, dry_run: bool = True) -> RelResult:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    fm_lines, body, _ = _split_frontmatter(raw)
    if fm_lines is None:
        return RelResult(False, None, None, "缺 frontmatter", str(path))
    try:
        data = yaml.safe_load("\n".join(fm_lines)) or {}
    except yaml.YAMLError as e:
        return RelResult(False, None, None, f"YAML 解析失败: {e}", str(path))
    if not isinstance(data, dict):
        return RelResult(False, None, None, "frontmatter 顶层不是 mapping", str(path))

    # stub 跳过（v3 checker 已降级为 info）
    if isinstance(data.get("状态"), str) and data["状态"].strip() == "stub":
        return RelResult(False, None, None, "状态=stub，跳过", str(path))

    has_rel, rel_val = _has_field(fm_lines, "与六壬关系")

    # 甲方案：只在缺失时写入；已存在任何非空值都跳过（哪怕值不在 v3 枚举里）
    if has_rel and rel_val:
        return RelResult(
            False, rel_val, rel_val,
            f"已存在 与六壬关系={rel_val!r}，跳过",
            str(path),
        )

    # 派生 penname / chapter
    penname = _penname_from_data(data, path)
    chapter = _chapter_of(data, path)
    fallback = default_relation(penname, chapter)

    new_lines = list(fm_lines)
    if has_rel and not rel_val:
        # 空值就地替换
        new_lines = _replace_field_line(new_lines, "与六壬关系", fallback)
    else:
        new_lines = _insert_field(new_lines, "与六壬关系", fallback)

    if not dry_run:
        new_raw = "---\n" + "\n".join(new_lines) + "\n" + body
        if raw.endswith("\n") and not new_raw.endswith("\n"):
            new_raw += "\n"
        path.write_text(new_raw, encoding="utf-8")

    return RelResult(
        True, rel_val, fallback,
        "apply" if not dry_run else "would-set",
        str(path),
        penname=penname,
        chapter=chapter,
    )


# ---------- 目录扫描 ----------
_DEFAULT_ROOTS = ["10-底本/唐宋层", "10-底本/六壬大全"]


def _iter_targets(vault: Path) -> Iterable[Path]:
    for sub in _DEFAULT_ROOTS:
        root = vault / sub
        if not root.is_dir():
            continue
        for book_dir in sorted(root.iterdir()):
            if not book_dir.is_dir():
                continue
            for md in sorted(book_dir.rglob("*.md")):
                if md.name.startswith("00-") or md.name.startswith("_"):
                    continue
                yield md


# ---------- Selftest ----------
def _run_selftest() -> int:
    cases: list[tuple[str, str, str | type]] = [
        ("武经", "六壬占法", "主体"),
        ("武经", "遁甲", "遁甲"),
        ("武经", "未知篇", "占候旁证"),
        ("太白", "玄女式", "主体"),
        ("太白", "推五帝法", "占候旁证"),
        ("凝神子", "任何篇", "主体"),
        ("大全查手", "任何条", "字典"),
        ("未知作者", "任何篇", KeyError),
    ]
    passed = 0
    for penname, chapter, expected in cases:
        try:
            got = default_relation(penname, chapter)
            if isinstance(expected, type) and issubclass(expected, BaseException):
                print(f"FAIL: default_relation({penname!r}, {chapter!r}) = {got!r}, "
                      f"expected raise {expected.__name__}")
                continue
            if got == expected:
                print(f"OK  : default_relation({penname!r}, {chapter!r}) = {got!r}")
                passed += 1
            else:
                print(f"FAIL: default_relation({penname!r}, {chapter!r}) = {got!r}, "
                      f"expected {expected!r}")
        except Exception as e:
            if isinstance(expected, type) and isinstance(e, expected):
                print(f"OK  : default_relation({penname!r}, {chapter!r}) raised "
                      f"{type(e).__name__} as expected")
                passed += 1
            else:
                print(f"FAIL: default_relation({penname!r}, {chapter!r}) raised "
                      f"{type(e).__name__}: {e}; expected {expected!r}")
    total = len(cases)
    print(f"\nSelftest: {passed}/{total} OK")
    return 0 if passed == total else 1


# ---------- CLI ----------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="与六壬关系 批量回填（Task 4，甲方案）")
    ap.add_argument("--vault", default="六壬vault", help="vault 根（默认 六壬vault）")
    ap.add_argument("--apply", action="store_true", help="真正写入；否则 dry-run")
    ap.add_argument("--selftest", action="store_true", help="跑规则表 selftest 后退出")
    args = ap.parse_args(argv)

    if args.selftest:
        return _run_selftest()

    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"找不到 vault: {vault}", file=sys.stderr)
        return 2
    dry_run = not args.apply

    tallied = Counter()
    by_book: dict[str, Counter] = defaultdict(Counter)
    by_relation: Counter = Counter()
    changed: list[RelResult] = []
    errors: list[tuple[str, Exception]] = []

    for md in _iter_targets(vault):
        try:
            r = backfill_one(md, dry_run=dry_run)
        except Exception as e:
            errors.append((str(md), e))
            tallied["error"] += 1
            print(f"[ERROR] {md}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        book_dir = md.parent.name
        by_book[book_dir][r.reason] += 1
        tallied[r.reason] += 1
        if r.changed:
            changed.append(r)
            by_relation[r.after or ""] += 1

    # 打印 changed 明细（前若干条）
    for r in changed[:40]:
        print(f"[{r.reason}] {r.path}  →  与六壬关系={r.after!r} "
              f"(penname={r.penname!r}, chapter={r.chapter!r})")
    if len(changed) > 40:
        print(f"... 省略 {len(changed) - 40} 条 changed（共 {len(changed)}）")

    print("\n=== 按书统计 ===")
    for book, cnt in sorted(by_book.items()):
        parts = ", ".join(f"{k}={v}" for k, v in sorted(cnt.items()))
        print(f"{book}: {parts}")

    print("\n=== 按关系值统计 ===")
    for rel, n in sorted(by_relation.items(), key=lambda kv: -kv[1]):
        print(f"{rel}: {n}")

    total_changed = sum(v for k, v in tallied.items() if k in {"apply", "would-set"})
    total_skip = tallied.get("已存在 与六壬关系", 0)
    skip_all = sum(v for k, v in tallied.items() if k.startswith("已存在") or "跳过" in k)
    print(
        f"\n汇总：changed={total_changed}, skip={skip_all}, "
        f"errors={tallied.get('error', 0)}, dry_run={dry_run}"
    )

    if errors:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
