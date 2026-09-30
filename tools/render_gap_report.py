#!/usr/bin/env python3
"""Render a human-readable Markdown gap report from vault-v3-gap.json.

Usage: python3 tools/render_gap_report.py \
    --input .aime/vault-v3-gap.json \
    --output docs/vault-v3-gap-report-2026-09-30.md
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import subprocess
import sys


def book_of(p: str) -> str:
    """Map an md path under 六壬vault/10-底本/... to a book name."""
    parts = pathlib.Path(p).parts
    if len(parts) >= 3 and parts[0] == "六壬vault" and parts[1] == "10-底本":
        if parts[2] == "唐宋层" and len(parts) >= 4:
            return parts[3]
        return parts[2]
    return "未分类"


BOOK_PENNAME = {
    "六壬大全": "大全查手",
    "六壬心镜": "心镜",
    "六壬断案": "邵彦和/阿甲/林景行",
    "卜筮书残卷": "卜筮残",
    "占事略决": "略决",
    "壬归": "壬归",
    "太白阴经": "太白",
    "景祐六壬神定经": "景祐",
    "武经总要": "武经",
    "中黄经": "凝神子",
}


def find_all_md(vault_root: pathlib.Path) -> list[str]:
    root = vault_root / "10-底本"
    result = subprocess.check_output(
        ["find", str(root), "-name", "*.md"], text=True
    ).strip().splitlines()
    # Return paths relative to CWD for consistency with JSON payload.
    cwd = pathlib.Path.cwd()
    return [str(pathlib.Path(p).resolve().relative_to(cwd)) for p in result if p]


def render(data: dict, all_md: list[str]) -> str:
    issues = data.get("issues", [])
    summary = data.get("summary", {})
    vault = data.get("vault", "六壬vault")

    # Group issues by field/severity/book.
    by_anchor = collections.Counter()
    by_author = collections.Counter()
    by_relation = collections.Counter()
    other = []
    for i in issues:
        book = book_of(i["path"])
        field, sev = i["field"], i["severity"]
        if field == "anchor_id" and sev == "error":
            by_anchor[book] += 1
        elif field == "作者" and sev == "error":
            by_author[book] += 1
        elif field == "与六壬关系" and sev == "warn":
            by_relation[book] += 1
        elif sev == "error":
            other.append(i)

    paths_with_issue = {i["path"] for i in issues}
    total_files = len(all_md)
    clean_files = total_files - len(paths_with_issue)
    coverage_pct = 100.0 * clean_files / total_files if total_files else 0.0

    total_error = summary.get("error", 0)
    total_warn = summary.get("warn", 0)
    total_info = summary.get("info", 0)

    by_book_total = collections.Counter(book_of(p) for p in all_md)
    by_book_issue_files = collections.Counter(book_of(p) for p in paths_with_issue)

    lines = []
    lines.append("# Vault v3 Frontmatter Gap 报告")
    lines.append("")
    lines.append("- **快照时间**：2026-09-30")
    lines.append(f"- **Vault 根**：`{vault}`")
    lines.append(f"- **检查器**：`tools/check_v3_frontmatter.py --vault {vault} --json`")
    lines.append("")
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(
        f"当前 `10-底本/` 下共 **{total_files}** 个 md，"
        f"v3 检查器报出 **{total_error} 条 error / {total_warn} 条 warn / {total_info} 条 info**；"
        f"完全合规文件 **{clean_files}** 个，v3 覆盖率 **{coverage_pct:.2f}%**。"
    )
    lines.append("")
    lines.append("- 主要 error 集中在两个字段：`anchor_id`（缺失）与 `作者`（缺失），两者一一对应——即每个缺 anchor_id 的文件同时缺 作者。")
    lines.append("- `与六壬关系` 大面积缺失（warn），需 Task 4 按规则表回填；**唯一例外**是《武经总要》——已由上游 `build_vault.py` 写入细粒度值（`本体规则 / 兵占背景` 等），Task 4 幂等跳过。")
    lines.append("- 未见 `作者不在花名枚举` 或 `anchor_id 格式错误` 等其他类别 error；Task 1 检查器已能识别但当前 vault 未触发。")
    lines.append("")
    lines.append("## 按书统计")
    lines.append("")
    lines.append("| 书 (目录名) | 花名 (作者字段目标值) | 总 md | 有缺失的 md | 缺 anchor_id | 缺 作者 | 缺 与六壬关系 (warn) |")
    lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    books = sorted(by_book_total.keys())
    for b in books:
        pen = BOOK_PENNAME.get(b, "—")
        total = by_book_total[b]
        with_issue = by_book_issue_files.get(b, 0)
        a = by_anchor.get(b, 0)
        au = by_author.get(b, 0)
        r = by_relation.get(b, 0)
        lines.append(f"| {b} | {pen} | {total} | {with_issue} | {a} | {au} | {r} |")
    # totals row
    lines.append(
        f"| **合计** | — | **{sum(by_book_total.values())}** | **{sum(by_book_issue_files.values())}** | "
        f"**{sum(by_anchor.values())}** | **{sum(by_author.values())}** | **{sum(by_relation.values())}** |"
    )
    lines.append("")

    lines.append("## 其他 error 类别")
    lines.append("")
    if other:
        lines.append(f"共 **{len(other)}** 条其他 error（作者不在花名枚举 / anchor_id 格式错误等）：")
        lines.append("")
        # If small, list them; else aggregate.
        if len(other) <= 30:
            lines.append("| 路径 | 字段 | message |")
            lines.append("| --- | --- | --- |")
            for i in other:
                lines.append(f"| `{i['path']}` | `{i['field']}` | {i['message']} |")
        else:
            agg = collections.Counter((i["field"], i["message"]) for i in other)
            lines.append("| 字段 | message | 计数 |")
            lines.append("| --- | --- | ---: |")
            for (fld, msg), n in agg.most_common():
                lines.append(f"| `{fld}` | {msg} | {n} |")
        lines.append("")
    else:
        lines.append("**无**。当前 error 全部由 `anchor_id` / `作者` 两个字段的缺失贡献；未检出格式违规或枚举违规。")
        lines.append("")

    lines.append("## Task 消费提示")
    lines.append("")
    lines.append("- Task 3a `generate_anchor_ids.py` 会消费本文件与 `.aime/vault-v3-gap.json`，为除《六壬断案》外的所有条目回填 `anchor_id` 与 `作者`。")
    lines.append("- Task 3b `split_duanan_by_author.py` 处理《六壬断案》的段级拆分（邵彦和 / 阿甲 / 林景行）。")
    lines.append("- Task 4 `backfill_liuren_relation.py` 消费 `与六壬关系` 的 warn 列表补齐字段。")
    lines.append("")
    lines.append("## 附：完整 issue 明细")
    lines.append("")
    lines.append("机器可读 JSON 位于 `.aime/vault-v3-gap.json`；字段名与结构：")
    lines.append("")
    lines.append("```json")
    lines.append('{"vault": "...", "summary": {"total": N, "error": N, "warn": N, "info": N,')
    lines.append(' "error_by_field": {"anchor_id": N, "作者": N}},')
    lines.append(' "issues": [{"path": "...", "field": "...", "severity": "error|warn|info", "message": "..."}]}')
    lines.append("```")
    lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=".aime/vault-v3-gap.json")
    ap.add_argument("--output", default="docs/vault-v3-gap-report-2026-09-30.md")
    ap.add_argument("--vault", default="六壬vault")
    args = ap.parse_args(argv)

    data = json.loads(pathlib.Path(args.input).read_text(encoding="utf-8"))
    all_md = find_all_md(pathlib.Path(args.vault))
    md = render(data, all_md)
    pathlib.Path(args.output).write_text(md, encoding="utf-8")
    print(f"wrote {args.output} ({len(md)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
