#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《大六壬断案》段级作者拆分与 anchor_id 回填（Task 3b）。

段边界规则：
  - `爱函按：` 或 `爱函按:`（前置为行首、文首、或 `。`）→ 起一新段，作者=阿甲
  - `缘生谛：` 或 `缘生谛:`（同上）→ 起一新段，作者=林景行
  - 其他 → 默认主段，作者=邵彦和
  - 段的结束 = 下一段的起始 or 文末

Frontmatter 侧改动（不改正文）：
  - 顶层 `anchor_id: 邵彦和-<slugify(卷篇)>-001`（若缺）
  - 顶层 `作者: 邵彦和`（若缺）
  - `含内嵌注家: [...]`（若段数 > 1，写除邵彦和外的作者花名列表）
  - `段索引:` YAML list，每段一 dict：`{anchor_id, 作者, start, end}`
  - 幂等：已有 `anchor_id` 非空则 skip

CLI:
  python3 tools/split_duanan_by_author.py [--vault 六壬vault] [--apply] [--sample GLOB]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

# 允许 tool 目录内互相 import
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from generate_anchor_ids import (  # noqa: E402
    slugify,
    compute_anchor_id,
    book_to_penname,
)

# ---------- 段边界正则 ----------
# 前导必须是行首、文首、或 `。`（含全角）；`爱函按` / `缘生谛` 后跟半/全角冒号。
# 使用捕获组：group(1) 标签，group(2) 冒号（不消费前导）。
_MARKER_RE = re.compile(r"(?:(?<=\n)|(?<=。)|(?<=\A))(爱函按|缘生谛)([：:])")

_AUTHOR_OF = {
    "爱函按": "阿甲",
    "缘生谛": "林景行",
}

# ---------- Segment ----------
@dataclass
class Segment:
    author: str
    start_line: int
    end_line: int
    first_line: str
    text: str

    def to_dict(self, anchor_id: str) -> dict:
        return {
            "anchor_id": anchor_id,
            "作者": self.author,
            "start": self.start_line,
            "end": self.end_line,
        }


def _line_index_of(body: str, pos: int) -> int:
    """返回 body[pos] 所在的 0-based line index。"""
    return body.count("\n", 0, pos)


def detect_segments(body: str) -> list[Segment]:
    """按段边界规则拆分 body，返回 Segment 列表。至少 1 段。

    第一段（若正文以标记开头则跳过）为 `邵彦和`。
    """
    if not body:
        return [Segment("邵彦和", 0, 0, "", "")]

    matches = list(_MARKER_RE.finditer(body))

    # 段起始点：(pos, author)。默认从 0 起的邵彦和段（除非 body 就以 marker 开头）。
    starts: list[tuple[int, str]] = []
    if not matches or matches[0].start(1) > 0:
        starts.append((0, "邵彦和"))
    for m in matches:
        starts.append((m.start(1), _AUTHOR_OF[m.group(1)]))

    segs: list[Segment] = []
    total_lines = body.count("\n")
    for i, (pos, author) in enumerate(starts):
        end_pos = starts[i + 1][0] if i + 1 < len(starts) else len(body)
        seg_text = body[pos:end_pos]
        start_line = _line_index_of(body, pos)
        # end_line: last non-empty line index of this segment
        end_line_pos = max(pos, end_pos - 1)
        end_line = _line_index_of(body, end_line_pos)
        first_line = seg_text.splitlines()[0] if seg_text.strip() else ""
        segs.append(Segment(
            author=author,
            start_line=start_line,
            end_line=end_line,
            first_line=first_line,
            text=seg_text,
        ))
    return segs


# ---------- body 提取 ----------
def extract_body(raw: str) -> str:
    """从整篇 md 中提取正文（frontmatter/H1/blockquote 全剥掉）。"""
    # 剥 frontmatter
    if raw.startswith("---"):
        lines = raw.split("\n")
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                lines = lines[i + 1:]
                break
        after_fm = "\n".join(lines)
    else:
        after_fm = raw

    lines = after_fm.split("\n")
    idx = 0
    n = len(lines)
    # 吃掉开头空行
    while idx < n and lines[idx].strip() == "":
        idx += 1
    # 吃掉 H1
    if idx < n and lines[idx].lstrip().startswith("#"):
        idx += 1
    while idx < n and lines[idx].strip() == "":
        idx += 1
    # 吃掉 blockquote 块（连续的 `>` 起始行）
    while idx < n and lines[idx].lstrip().startswith(">"):
        idx += 1
    while idx < n and lines[idx].strip() == "":
        idx += 1
    return "\n".join(lines[idx:])


# ---------- Frontmatter patch（文本级，不重排） ----------
def _split_frontmatter(raw: str) -> tuple[list[str] | None, str]:
    """返回 (fm_lines, after)；fm_lines 不含首尾 `---`，after 是 `---` 关闭行及以后。"""
    if not raw.startswith("---"):
        return None, raw
    lines = raw.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i:])
    return None, raw


def _has_field(fm_lines: list[str], field: str) -> tuple[bool, str | None]:
    pat = re.compile(rf"^{re.escape(field)}\s*:\s*(.*)$")
    for ln in fm_lines:
        if not ln or ln.startswith(" ") or ln.startswith("\t"):
            continue
        m = pat.match(ln)
        if m:
            val = m.group(1).strip()
            if val in ("", "null", "~"):
                return True, None
            return True, val
    return False, None


def _yaml_dump_inline_list(lst: list[str]) -> str:
    # `含内嵌注家: [阿甲, 林景行]` — 中文花名不需要引号
    if not lst:
        return "[]"
    return "[" + ", ".join(lst) + "]"


def _dump_segment_index_block(entries: list[dict]) -> list[str]:
    """把段索引写成多行 block 风格 YAML；返回按行插入的字符串列表。

    输出形式：
      段索引:
        - anchor_id: 邵彦和-...
          作者: 邵彦和
          start: 0
          end: 4
    """
    out = ["段索引:"]
    for e in entries:
        out.append(f"  - anchor_id: {e['anchor_id']}")
        out.append(f"    作者: {e['作者']}")
        out.append(f"    start: {e['start']}")
        out.append(f"    end: {e['end']}")
    return out


# ---------- Backfill ----------
@dataclass
class BackfillResult:
    path: str
    changed: bool
    reason: str
    main_anchor_id: str = ""
    segments: list[dict] = field(default_factory=list)
    inline_notators: list[str] = field(default_factory=list)


def backfill(path: Path, dry_run: bool = True) -> BackfillResult:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    fm_lines, after_fm = _split_frontmatter(raw)
    if fm_lines is None:
        return BackfillResult(str(path), False, "缺 frontmatter")

    try:
        data = yaml.safe_load("\n".join(fm_lines)) or {}
    except yaml.YAMLError as e:
        return BackfillResult(str(path), False, f"YAML 解析失败: {e}")

    if not isinstance(data, dict):
        return BackfillResult(str(path), False, "frontmatter 非 mapping")

    # 幂等：已有 anchor_id 非空则 skip
    has_anchor, anchor_val = _has_field(fm_lines, "anchor_id")
    has_author, author_val = _has_field(fm_lines, "作者")
    if (has_anchor and anchor_val) or (has_author and author_val):
        return BackfillResult(
            str(path), False,
            f"已有 anchor_id={anchor_val!r} 作者={author_val!r},跳过",
            main_anchor_id=anchor_val or "",
        )

    book_val = data.get("书")
    if not isinstance(book_val, str) or not book_val.strip():
        return BackfillResult(str(path), False, "缺 书 字段")

    chapter = data.get("卷篇") or path.stem
    if not isinstance(chapter, str) or not chapter.strip():
        return BackfillResult(str(path), False, "缺 卷篇 字段")

    # 提取正文并切段
    body = extract_body(raw)
    segs = detect_segments(body)

    # 为每段计算 anchor_id：同 md 内每作者独立从 001 递增
    per_author_counter: Counter = Counter()
    seg_dicts: list[dict] = []
    for s in segs:
        per_author_counter[s.author] += 1
        aid = compute_anchor_id(s.author, chapter, per_author_counter[s.author])
        seg_dicts.append(s.to_dict(aid))

    main_seg = seg_dicts[0] if seg_dicts and seg_dicts[0]["作者"] == "邵彦和" else None
    if main_seg is None:
        # 罕见情形：body 以 marker 开头。仍用邵彦和主段占位。
        main_anchor = compute_anchor_id("邵彦和", chapter, 1)
    else:
        main_anchor = main_seg["anchor_id"]

    # 含内嵌注家：出现过的、除邵彦和外的作者
    notator_seen: list[str] = []
    for s in segs:
        if s.author != "邵彦和" and s.author not in notator_seen:
            notator_seen.append(s.author)

    # ---- 写 frontmatter ----
    new_lines = list(fm_lines)
    # anchor_id
    if not (has_anchor and anchor_val):
        new_lines = _upsert_field_line(new_lines, "anchor_id", main_anchor)
    # 作者
    if not (has_author and author_val):
        new_lines = _upsert_field_line(new_lines, "作者", "邵彦和")

    # 含内嵌注家（可选；仅在 >1 段时写）
    if len(segs) > 1 and notator_seen:
        has_notator, _ = _has_field(new_lines, "含内嵌注家")
        if not has_notator:
            new_lines.append(f"含内嵌注家: {_yaml_dump_inline_list(notator_seen)}")

    # 段索引（新写；不追加到既有段索引）
    has_seg_idx, _ = _has_field(new_lines, "段索引")
    if not has_seg_idx:
        new_lines.extend(_dump_segment_index_block(seg_dicts))

    result = BackfillResult(
        path=str(path),
        changed=True,
        reason="apply" if not dry_run else "would-set",
        main_anchor_id=main_anchor,
        segments=seg_dicts,
        inline_notators=notator_seen,
    )

    if not dry_run:
        new_raw = "---\n" + "\n".join(new_lines) + "\n" + after_fm
        if raw.endswith("\n") and not new_raw.endswith("\n"):
            new_raw += "\n"
        path.write_text(new_raw, encoding="utf-8")

    return result


def _upsert_field_line(fm_lines: list[str], field: str, value: str) -> list[str]:
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


# ---------- CLI ----------
def _iter_targets(vault: Path, sample_glob: str | None) -> Iterable[Path]:
    root = vault / "10-底本" / "唐宋层" / "六壬断案"
    if not root.is_dir():
        return
    for md in sorted(root.glob("*.md")):
        if md.name.startswith("00-") or md.name.startswith("_"):
            continue
        if sample_glob:
            import fnmatch
            if not fnmatch.fnmatch(md.name, sample_glob):
                continue
        yield md


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="《大六壬断案》段级作者拆分与 anchor_id 回填")
    ap.add_argument("--vault", default="六壬vault", help="vault 根")
    ap.add_argument("--apply", action="store_true", help="真正写入；否则 dry-run")
    ap.add_argument("--sample", default=None, help="glob 过滤 md 文件名")
    args = ap.parse_args(argv)

    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"找不到 vault: {vault}", file=sys.stderr)
        return 2

    dry_run = not args.apply
    tallied = Counter()
    total_segs = Counter()
    inline_notator_files: list[tuple[str, list[str]]] = []
    changed_paths: list[BackfillResult] = []
    skipped_with_anchor: list[str] = []

    for md in _iter_targets(vault, args.sample):
        try:
            r = backfill(md, dry_run=dry_run)
        except Exception as e:  # pragma: no cover
            print(f"[ERROR] {md}: {e}", file=sys.stderr)
            tallied["error"] += 1
            continue
        tallied[r.reason] += 1
        if r.changed:
            changed_paths.append(r)
            for s in r.segments:
                total_segs[s["作者"]] += 1
            if r.inline_notators:
                inline_notator_files.append((r.path, r.inline_notators))
        elif "已有 anchor_id" in r.reason:
            skipped_with_anchor.append(r.path)

    # sample 详情
    if args.sample:
        for r in changed_paths:
            print(f"\n>>> {r.path}")
            print(f"  main_anchor_id = {r.main_anchor_id}")
            print(f"  含内嵌注家 = {r.inline_notators}")
            print(f"  段数 = {len(r.segments)}")
            for s in r.segments:
                first = s.get("first_line", "")
                print(
                    f"    - [{s['作者']}] {s['anchor_id']}  "
                    f"lines {s['start']}..{s['end']}"
                )

    # 汇总
    print("\n=== 段数分布（按作者） ===")
    for author in ("邵彦和", "阿甲", "林景行"):
        print(f"  {author}: {total_segs.get(author, 0)}")
    print(f"  合计: {sum(total_segs.values())}")

    print("\n=== 文件级统计 ===")
    print(f"  changed: {tallied.get('would-set', 0) + tallied.get('apply', 0)}")
    print(f"  跳过（已有 anchor_id）: {len(skipped_with_anchor)}")
    print(f"  错误 / 其他: {tallied.get('error', 0)}")

    print(f"\n  含内嵌注家（非邵彦和）文件: {len(inline_notator_files)}")
    dist = Counter()
    for _p, notators in inline_notator_files:
        key = "+".join(sorted(notators))
        dist[key] += 1
    for k, v in sorted(dist.items()):
        print(f"    {k}: {v}")

    print(f"\ndry_run={dry_run}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
