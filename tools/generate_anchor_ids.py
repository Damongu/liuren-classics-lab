#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用 anchor_id 生成器与批量回填（Task 3a，断案除外）。

- 计算 anchor_id：`<花名>-<slugify(卷篇)>-<段序 3 位>`
- 回填 frontmatter：同时补 `anchor_id` 与 `作者`（若缺）
- 幂等：已有 `anchor_id`（非空）时 skip，不覆盖既有 `作者`
- 文本级 patch，**不重排字段**、**不改 tags flow 风格**

CLI:
  python3 tools/generate_anchor_ids.py [--vault 六壬vault] [--apply]
  python3 tools/generate_anchor_ids.py --vault 六壬vault --skip-book 六壬断案
  python3 tools/generate_anchor_ids.py --vault 六壬vault --skip-book 六壬断案,六壬大全
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


# ---------- 花名映射 ----------
# 覆盖 Task 3a 说明中列出的所有书；`卜筮书` 是 `卜筮书残卷` 部分 md 中 `书:` 字段的实际值，
# 一并映射。`六壬断案` 花名默认为 `邵彦和`（主段），本工具通过 --skip-book 排除 3b。
_BOOK_TO_PENNAME: dict[str, str] = {
    "太白阴经": "太白",
    "神机制敌太白阴经": "太白",
    "神机制敌太白阴经（简称《太白阴经》，又名《太白阴符》）": "太白",
    "大六壬五变中黄经": "凝神子",
    "中黄经": "凝神子",
    "六壬心镜": "心镜",
    "景祐六壬神定经": "景祐",
    "武经总要": "武经",
    "壬归": "壬归",
    "占事略决": "略决",
    "卜筮书残卷": "卜筮残",
    "卜筮书": "卜筮残",
    "六壬大全": "大全查手",
    "六壬断案": "邵彦和",
}


def book_to_penname(book: str) -> str:
    """把 `书` 字段字符串映射到花名；未知书抛 KeyError。"""
    if not isinstance(book, str):
        raise KeyError(f"book 必须是 str，实为 {type(book).__name__}: {book!r}")
    key = book.strip()
    if key not in _BOOK_TO_PENNAME:
        raise KeyError(f"未知书名：{book!r}（尚未在花名映射表中登记）")
    return _BOOK_TO_PENNAME[key]


# ---------- slugify ----------
# 只允许 [汉字 / ASCII 字母数字 / 连字符]。空白（含全角空格）折叠为单个 `-`。
_ALLOWED = re.compile(r"[A-Za-z0-9一-鿿\-]")
_WHITESPACE = re.compile(r"[\s　]+")
_DASH_RUN = re.compile(r"-{2,}")


def slugify(text: str) -> str:
    """归一化 chapter 段：去首尾空白、内部空白→`-`、丢弃非汉字/字母数字/`-` 的字符、去重连字符。"""
    if not isinstance(text, str):
        return ""
    s = text.strip()
    s = _WHITESPACE.sub("-", s)
    # 过滤非允许字符（保留 `-`）
    s = "".join(ch if _ALLOWED.match(ch) else "-" for ch in s)
    s = _DASH_RUN.sub("-", s).strip("-")
    return s


# ---------- anchor_id ----------
def compute_anchor_id(penname: str, chapter: str, index: int) -> str:
    """纯函数：拼 anchor_id。"""
    return f"{penname}-{slugify(chapter)}-{int(index):03d}"


# ---------- Backfill 结构 ----------
@dataclass
class BackfillResult:
    changed: bool
    before: str | None       # 原 anchor_id（若已有）
    after: str               # 计算或既有 anchor_id
    author_before: str | None = None
    author_after: str | None = None
    reason: str = ""         # skip/apply 的说明
    path: str = ""


# ---------- Frontmatter 文本级 patch ----------
_FM_OPEN = "---"


def _split_frontmatter(raw: str) -> tuple[list[str] | None, str, str]:
    """返回 (fm_lines, body, newline_style)；若无 fm，fm_lines=None。

    fm_lines 不含首尾 `---`。body 包含关闭 `---` 之后的所有内容（含开头换行）。
    """
    if not raw.startswith("---"):
        return None, raw, "\n"
    lines = raw.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            fm_lines = lines[1:i]
            body = "\n".join(lines[i:])  # 保留关闭 --- 行及以后
            return fm_lines, body, "\n"
    return None, raw, "\n"


def _has_field(fm_lines: list[str], field: str) -> tuple[bool, str | None]:
    """检查 frontmatter 是否已有 `field:` 顶层键；返回 (present, value_str_or_None)。

    只匹配顶层（无前导空格）的 `field:` 行。value 若为空视为缺。
    """
    pat = re.compile(rf"^{re.escape(field)}\s*:\s*(.*)$")
    for ln in fm_lines:
        # 顶层字段：无缩进
        if not ln or ln.startswith(" ") or ln.startswith("\t"):
            continue
        m = pat.match(ln)
        if m:
            val = m.group(1).strip()
            if val == "" or val.lower() == "null" or val == "~":
                return True, None
            return True, val
    return False, None


def _get_field_from_yaml(fm_lines: list[str], field: str):
    try:
        data = yaml.safe_load("\n".join(fm_lines)) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data.get(field)


def _insert_field(fm_lines: list[str], field: str, value: str) -> list[str]:
    """在 fm_lines 末尾追加 `field: value` 行（不重排既有字段）。"""
    return fm_lines + [f"{field}: {value}"]


# ---------- Chapter 提取 ----------
def _chapter_of(data: dict, path: Path) -> str:
    """按优先级：`卷篇` → `节` → `篇` → `册` → 文件名 stem（去扩展名）。"""
    for k in ("卷篇", "节", "篇", "册"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return path.stem


# ---------- 单文件 backfill ----------
_BOOK_DIR_FROM_PATH = re.compile(r".*/10-底本/(?:唐宋层/)?(?P<book>[^/]+)/")


def _book_from_path(path: Path) -> str | None:
    m = _BOOK_DIR_FROM_PATH.match(str(path).replace("\\", "/"))
    return m.group("book") if m else None


def _sibling_index(path: Path, chapter: str, penname: str) -> int:
    """在同一"书目录"下，按文件名字典序里、同 (penname, chapter) 组内的位置（1 起）。

    对典型条目（每 chapter 单文件），返回 1。
    """
    book_dir = path.parent
    idx = 1
    for sibling in sorted(book_dir.glob("*.md")):
        if sibling.name.startswith("00-") or sibling.name.startswith("_"):
            continue
        if sibling == path:
            return idx
        try:
            raw = sibling.read_text(encoding="utf-8")
        except OSError:
            continue
        fm_lines, _body, _ = _split_frontmatter(raw)
        if fm_lines is None:
            continue
        try:
            data = yaml.safe_load("\n".join(fm_lines)) or {}
        except yaml.YAMLError:
            continue
        if not isinstance(data, dict):
            continue
        book = data.get("书")
        try:
            sib_penname = book_to_penname(book) if isinstance(book, str) else None
        except KeyError:
            sib_penname = None
        if sib_penname != penname:
            continue
        sib_chapter = _chapter_of(data, sibling)
        if slugify(sib_chapter) == slugify(chapter):
            idx += 1
    return idx


def backfill(path: Path, dry_run: bool = True) -> BackfillResult:
    """回填单个 md 的 anchor_id 与 作者（若缺）。幂等。"""
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    fm_lines, body, _ = _split_frontmatter(raw)

    if fm_lines is None:
        return BackfillResult(
            changed=False, before=None, after="",
            reason="缺 frontmatter，跳过", path=str(path),
        )

    try:
        data = yaml.safe_load("\n".join(fm_lines)) or {}
    except yaml.YAMLError as e:
        return BackfillResult(
            changed=False, before=None, after="",
            reason=f"YAML 解析失败: {e}", path=str(path),
        )
    if not isinstance(data, dict):
        return BackfillResult(
            changed=False, before=None, after="",
            reason="frontmatter 顶层不是 mapping，跳过", path=str(path),
        )

    # 骨架 stub 也跳过（v3 checker 已处理为 info）
    if isinstance(data.get("状态"), str) and data["状态"].strip() == "stub":
        return BackfillResult(
            changed=False, before=None, after="",
            reason="状态=stub，跳过", path=str(path),
        )

    # 判断 anchor_id
    has_anchor, anchor_val = _has_field(fm_lines, "anchor_id")
    has_author, author_val = _has_field(fm_lines, "作者")

    # 派生 penname
    book_val = data.get("书")
    if not isinstance(book_val, str) or not book_val.strip():
        return BackfillResult(
            changed=False, before=anchor_val, after=anchor_val or "",
            reason="frontmatter 缺 `书` 字段，跳过", path=str(path),
        )
    try:
        penname = book_to_penname(book_val)
    except KeyError as e:
        return BackfillResult(
            changed=False, before=anchor_val, after=anchor_val or "",
            reason=f"未知书名 {book_val!r}，跳过: {e}", path=str(path),
        )

    chapter = _chapter_of(data, path)
    if not chapter:
        return BackfillResult(
            changed=False, before=anchor_val, after=anchor_val or "",
            reason="无法推断卷篇/节，跳过", path=str(path),
        )

    changed = False
    new_lines = list(fm_lines)
    computed_anchor = anchor_val
    author_after = author_val

    # anchor_id：已有非空 → skip；缺 → 计算并插入
    if has_anchor and anchor_val:
        pass  # 保留
    else:
        idx = _sibling_index(path, chapter, penname)
        computed_anchor = compute_anchor_id(penname, chapter, idx)
        # 若已有空值字段，则替换该行；否则追加
        if has_anchor and not anchor_val:
            new_lines = _replace_field_line(new_lines, "anchor_id", computed_anchor)
        else:
            new_lines = _insert_field(new_lines, "anchor_id", computed_anchor)
        changed = True

    # 作者：只在缺时写
    if has_author and author_val:
        pass
    else:
        author_after = penname
        if has_author and not author_val:
            new_lines = _replace_field_line(new_lines, "作者", author_after)
        else:
            new_lines = _insert_field(new_lines, "作者", author_after)
        changed = True

    if changed and not dry_run:
        new_raw = "---\n" + "\n".join(new_lines) + "\n" + body
        # 保证与原文相同的末尾换行行为
        if raw.endswith("\n") and not new_raw.endswith("\n"):
            new_raw += "\n"
        path.write_text(new_raw, encoding="utf-8")

    return BackfillResult(
        changed=changed,
        before=anchor_val,
        after=computed_anchor or "",
        author_before=author_val,
        author_after=author_after,
        reason="apply" if (changed and not dry_run) else ("would-set" if changed else "skip"),
        path=str(path),
    )


def _replace_field_line(fm_lines: list[str], field: str, value: str) -> list[str]:
    pat = re.compile(rf"^{re.escape(field)}\s*:\s*(.*)$")
    out = []
    replaced = False
    for ln in fm_lines:
        if not replaced and (not ln.startswith(" ") and not ln.startswith("\t")):
            if pat.match(ln):
                out.append(f"{field}: {value}")
                replaced = True
                continue
        out.append(ln)
    if not replaced:
        out.append(f"{field}: {value}")
    return out


# ---------- 目录扫描 & CLI ----------
_DEFAULT_ROOTS = ["10-底本/唐宋层", "10-底本/六壬大全"]


def _iter_targets(vault: Path, skip_books: set[str]) -> Iterable[Path]:
    for sub in _DEFAULT_ROOTS:
        root = vault / sub
        if not root.is_dir():
            continue
        # 遍历一层子目录（书目录），再遍历 md
        for book_dir in sorted(root.iterdir()):
            if not book_dir.is_dir():
                continue
            if book_dir.name in skip_books:
                continue
            for md in sorted(book_dir.rglob("*.md")):
                if md.name.startswith("00-") or md.name.startswith("_"):
                    continue
                yield md


def _parse_skip(values: list[str] | None) -> set[str]:
    out: set[str] = set()
    for v in values or []:
        for part in v.split(","):
            part = part.strip()
            if part:
                out.add(part)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="通用 anchor_id 生成器与批量回填（断案除外）")
    ap.add_argument("--vault", default="六壬vault", help="vault 根（默认 六壬vault）")
    ap.add_argument("--apply", action="store_true", help="真正写入；否则 dry-run")
    ap.add_argument(
        "--skip-book",
        action="append",
        default=[],
        help="跳过书名（可多次或用逗号分隔）；例如 --skip-book 六壬断案",
    )
    args = ap.parse_args(argv)

    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"找不到 vault: {vault}", file=sys.stderr)
        return 2

    skip = _parse_skip(args.skip_book)
    dry_run = not args.apply

    tallied = Counter()
    by_book: dict[str, Counter] = defaultdict(Counter)
    changed_paths: list[BackfillResult] = []

    for md in _iter_targets(vault, skip):
        try:
            r = backfill(md, dry_run=dry_run)
        except Exception as e:  # pragma: no cover
            print(f"[ERROR] {md}: {e}", file=sys.stderr)
            tallied["error"] += 1
            continue
        book_dir = md.parent.name
        by_book[book_dir][r.reason] += 1
        tallied[r.reason] += 1
        if r.changed:
            changed_paths.append(r)

    # 打印明细（changed 部分）
    for r in changed_paths[:40]:
        print(f"[{r.reason}] {r.path}  →  anchor_id={r.after!r} 作者={r.author_after!r}")
    if len(changed_paths) > 40:
        print(f"... 省略 {len(changed_paths) - 40} 条 changed（共 {len(changed_paths)}）")

    print("\n=== 按书统计 ===")
    for book, cnt in sorted(by_book.items()):
        parts = ", ".join(f"{k}={v}" for k, v in sorted(cnt.items()))
        print(f"{book}: {parts}")

    total_changed = sum(v for k, v in tallied.items() if k in {"apply", "would-set"})
    print(
        f"\n汇总：changed={total_changed}, skip={tallied.get('skip', 0)}, "
        f"errors={tallied.get('error', 0)}, dry_run={dry_run}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
