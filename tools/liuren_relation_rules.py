#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
`与六壬关系` fallback 规则表（Task 4，甲方案 - 开放集）。

只作为**缺字段时的 fallback**：Task 4 的 backfill 工具只在 frontmatter
缺 `与六壬关系` 或该字段为空时写入本表返回的值，不覆盖上游
`build_vault.py` 已写入的细粒度值（如 `本体规则 / 兵占背景 /
同源三式·共用神名` 等）。

结构：`RULES[book_penname][chapter_pattern] = relation`

- key1 = 花名（`太白 / 武经 / 心镜 / 凝神子 / 景祐 / 壬归 / 略决 /
  卜筮残 / 大全查手 / 邵彦和 / 阿甲 / 林景行`），与 v3 `作者` 字段花名一致
- key2 = chapter 子串匹配 pattern；`*` 为兜底
- value = 与六壬关系 值（v3 粗粒度：`主体 / 旁证 / 遁甲 / 太乙 /
  占候旁证 / N/A / 字典` 等）

`default_relation(penname, chapter)` 按具体 pattern 优先、`*` 兜底顺序返回。
未在 RULES 登记的 penname 抛 `KeyError`。
"""
from __future__ import annotations


RULES: dict[str, dict[str, str]] = {
    # 宋本主线六部：所有条目默认 主体
    "凝神子": {"*": "主体"},
    "心镜":   {"*": "主体"},
    "景祐":   {"*": "主体"},
    "壬归":   {"*": "主体"},

    # 断案三魂：全部 主体
    "邵彦和": {"*": "主体"},
    "阿甲":   {"*": "主体"},
    "林景行": {"*": "主体"},

    # 武经总要·后集卷二十「六壬占法」= 主体；其余卷十六~二十占候五卷按篇实际
    # （上游 build_vault.py 已给多数条目写了细粒度值，这里只 fallback 未写入的）
    "武经": {
        "六壬占法":  "主体",
        "六壬":      "主体",     # 卷二十「六壬」篇
        "占候·天文": "占候旁证",
        "占候·气候": "占候旁证",
        "遁甲":      "遁甲",
        "太乙":      "太乙",
        "*":         "占候旁证",
    },

    # 太白阴经
    "太白": {
        "玄女式":         "主体",
        "元女式":         "主体",   # 「卷十 元女式（录文待核）」的另一异写
        "推伏吟反吟法":   "主体",
        "推月将加时法":   "主体",
        "推月将法":       "主体",
        "推三十六禽法":   "占候旁证",
        "推五帝法":       "占候旁证",
        "*":              "占候旁证",
    },

    # 唐本佐证
    "略决":     {"*": "主体"},
    "卜筮残":   {"*": "主体"},

    # 大全 = 字典
    "大全查手": {"*": "字典"},
}


def default_relation(penname: str, chapter: str) -> str:
    """按 RULES 表返回 fallback 值。

    - penname 未登记 → KeyError
    - chapter 无具体 pattern 命中 → 返回 `*` 兜底
    - 具体 pattern 优先（按子串 `in chapter` 匹配）
    """
    if penname not in RULES:
        raise KeyError(f"未知花名：{penname!r}（尚未在 RULES 中登记）")
    entry = RULES[penname]
    chapter_str = chapter if isinstance(chapter, str) else ""
    # 具体 pattern 先匹配（排除 `*`）
    for pat, rel in entry.items():
        if pat == "*":
            continue
        if pat and pat in chapter_str:
            return rel
    # 兜底 `*`
    if "*" in entry:
        return entry["*"]
    raise KeyError(f"{penname!r} 下未设置 `*` 兜底且 chapter={chapter!r} 无命中")
