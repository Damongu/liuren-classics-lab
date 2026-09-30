#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
禄命辅助 stub 增补工具（Task 5）。

在 `六壬vault/90-禄命辅助/<slugify(概念名)>.md` 生成 stub 文件。
frontmatter 与四段模板与 8 张 seed 完全同构。

CLI：
  python3 tools/add_lulu_stub.py <概念名> [--别名 A,B] [--tags a,b] [--vault 六壬vault]

策略：
  - 若目标文件已存在：拒绝并 exit code 非零；不覆盖
  - 文件名：`slugify(概念名).md`（空白折叠为 `-`）
  - frontmatter 里 `概念名` 保留原始名（带空格），仅文件名 slugified
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable

# ---- 模板 ----
# 四段占位，每段 `<!-- TODO(D-N): ... -->` 说明子项目 D 会填内容
BODY_TEMPLATE = """## 一、界说

<!-- TODO(D-1): 该概念在禄命法与六壬中的一致含义（一句话） -->

## 二、在断辞中的用法

<!-- TODO(D-2): 举 1–2 个宋本断辞用例，标 anchor_id -->

## 三、宋本硬证

<!-- TODO(D-3): 列 2 处宋本原文出处 -->

## 四、易混淆点

<!-- TODO(D-4): 与他书或近义概念的区别 -->
"""


# ---- slugify ----
# 与 generate_anchor_ids.slugify 保持同构，但独立实现以避免跨模块耦合
_WHITESPACE = re.compile(r"[\s　]+")
_DASH_RUN = re.compile(r"-{2,}")


def slugify_concept(text: str) -> str:
    """将概念名归一化为可作文件名的字符串。

    空白（含全角空格）折叠为单个 `-`；首尾 `-` 去除。汉字保留。
    """
    if not isinstance(text, str):
        return ""
    s = text.strip()
    s = _WHITESPACE.sub("-", s)
    s = _DASH_RUN.sub("-", s).strip("-")
    return s


# ---- frontmatter 生成 ----
def _fmt_yaml_list(items: Iterable[str]) -> str:
    """以 flow 风格输出列表：[a, b, c]。空列表输出 []。"""
    xs = list(items)
    if not xs:
        return "[]"
    return "[" + ", ".join(xs) + "]"


def stub_content(
    concept_name: str,
    aliases: list[str] | None = None,
    extra_tags: list[str] | None = None,
) -> str:
    """生成一张 stub 的完整 md 文本（frontmatter + 四段模板 body）。"""
    tags = ["禄命辅助", "stub"]
    if extra_tags:
        for t in extra_tags:
            t = t.strip()
            if t and t not in tags:
                tags.append(t)

    lines = ["---"]
    lines.append(f"概念名: {concept_name}")
    if aliases:
        cleaned = [a.strip() for a in aliases if a.strip()]
        lines.append(f"别名: {_fmt_yaml_list(cleaned)}")
    lines.append("所属层: 禄命辅助")
    lines.append("状态: stub")
    lines.append("宋本硬证: []")
    lines.append(f"tags: {_fmt_yaml_list(tags)}")
    lines.append("---")
    lines.append("")  # 空行分隔 frontmatter 与正文
    fm = "\n".join(lines) + "\n"
    return fm + BODY_TEMPLATE


# ---- 主 API ----
DEFAULT_VAULT = Path("六壬vault")
LULU_SUBDIR = "90-禄命辅助"


def create_stub(
    concept_name: str,
    vault_root: Path | str = DEFAULT_VAULT,
    aliases: list[str] | None = None,
    extra_tags: list[str] | None = None,
) -> Path:
    """在 `<vault_root>/90-禄命辅助/<slugify(concept_name)>.md` 生成 stub。

    - 若文件已存在，抛 FileExistsError（不覆盖）。
    - 返回新建文件的 Path。
    """
    vault_root = Path(vault_root)
    d = vault_root / LULU_SUBDIR
    if not d.is_dir():
        raise FileNotFoundError(f"目标目录不存在：{d}")

    slug = slugify_concept(concept_name)
    if not slug:
        raise ValueError(f"概念名 slugify 后为空：{concept_name!r}")

    path = d / f"{slug}.md"
    if path.exists():
        raise FileExistsError(f"文件已存在，不覆盖：{path}")

    path.write_text(stub_content(concept_name, aliases, extra_tags),
                    encoding="utf-8")
    return path


# ---- CLI ----
def _split_csv(s: str | None) -> list[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="禄命辅助 stub 增补工具",
    )
    ap.add_argument("concept", help="概念名（如 `天医` 或 `天医 星`）")
    ap.add_argument("--别名", dest="aliases", default="",
                    help="别名，逗号分隔（如 `A,B`）")
    ap.add_argument("--tags", dest="tags", default="",
                    help="额外 tags，逗号分隔（默认已含 `禄命辅助,stub`）")
    ap.add_argument("--vault", default=str(DEFAULT_VAULT),
                    help="vault 根目录（默认 六壬vault）")
    args = ap.parse_args(argv)

    try:
        path = create_stub(
            args.concept,
            vault_root=args.vault,
            aliases=_split_csv(args.aliases),
            extra_tags=_split_csv(args.tags),
        )
    except FileExistsError as e:
        print(f"[add_lulu_stub] 拒绝：{e}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as e:
        print(f"[add_lulu_stub] 错误：{e}", file=sys.stderr)
        return 2

    print(f"[add_lulu_stub] 已生成：{path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
