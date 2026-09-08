#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清校污染标记器
==============

扫描 vault 中唐宋层底本条目，命中「校记语」的条目在 frontmatter 打上：

    污染: true
    污染类型: 据大全回改 / 今改今补 / 疑脱疑衍 / 据他本改

为什么需要这一步
----------------
《六壬心镜》今本是清程树勋手录、程伟堂校的辑校本，卷八已见
「今伟堂据《大全》及程鹏南本改正」。凡校记明示据《大全》改的字句，
拿去校《六壬大全》得到的「一致」是**同源**，不是**同真**——
构成循环污染，不能作为独立证据。

用法
----
    # 先探，不写文件
    python3 tools/mark_pollution.py --book 六壬心镜 --dry-run

    # 正式标记
    python3 tools/mark_pollution.py --book 六壬心镜

    # 扫所有唐宋层
    python3 tools/mark_pollution.py --all

    # 清除标记重来
    python3 tools/mark_pollution.py --book 六壬心镜 --clear
"""

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 校记语规则
#
# 两个正交的标记，别混：
#
#   污染: true —— 字句被后人**改动**过。不能作为《六壬大全》的独立证据。
#   今注: true —— 混入了后人**注释**，原文字句未必被改。引用时须剥离注文。
#
# 「伟堂据《大全》补」是前者；「伟堂按：……」是后者。
# 早先版本把两者合并，导致《断案》里几十条纯注释被误判成污染。

POLLUTION_RULES = [
    (
        "据大全回改",
        [
            r"[据據依]《?大全》?",
            r"六壬大全[^。；]{0,8}(改|補|补|正|校)",
        ],
    ),
    (
        "据他本改",
        [
            # 「伟堂据程鹏南本补入」「据入式并程鹏南本恭校」
            r"[据據][^，。；]{0,14}本[^，。；]{0,8}(改|正|補|补|校|入)",
            r"[据據]《[^》]{1,12}》[^，。；]{0,8}(改|正|補|补|校|入)",
            r"(伟堂|偉堂|树勋|樹勳|樹勋|郑天民|鄭天民)[^，。；]{0,6}[据據]",
            r"通神集[^。；]{0,8}(補|补|入|出|集)",
        ],
    ),
    (
        "今改今补",
        [
            r"今[据據][^，。；]{0,12}[正校改補补]",
            r"今改",
            r"今補",
            r"今补",
            r"今[正校]之",
            r"今删",
            r"今刪",
            r"今仍之",
            r"恭校",
        ],
    ),
    (
        "疑脱疑衍",
        [
            r"疑脱",
            r"疑脫",
            r"疑衍",
            r"疑误",
            r"疑誤",
            r"疑是",
            r"原本脱",
            r"原本脫",
            r"多脱误",
            r"多脫誤",
            r"原缺",
            r"原闕",
            r"字脱",
            r"字脫",
            r"衍文",
            r"脱文",
            r"脫文",
            r"未敢[删刪]",
        ],
    ),
]

# 后人注释混入（不改字，但引用时须剥离）
ANNOTATION_PATS = [
    r"郑按",
    r"鄭按",
    r"伟堂按",
    r"偉堂按",
    r"爱函按",
    r"愛函按",
    r"缘生谛",
    r"緣生諦",
    r"郇注",
    r"郇应清",
    r"郇應清",
    r"愚按",
    r"◎",
]

COMPILED = [
    (name, [re.compile(p) for p in pats]) for name, pats in POLLUTION_RULES
]
ANNO = [re.compile(p) for p in ANNOTATION_PATS]


def _frags(text: str, pats, cap=3):
    hits = []
    for p in pats:
        for m in p.finditer(text):
            s = max(0, m.start() - 12)
            e = min(len(text), m.end() + 12)
            hits.append(text[s:e].replace("\n", " ").strip())
            if len(hits) >= cap:
                return hits
    return hits


def detect(text: str):
    """返回 (污染类型, 命中证据列表)；没命中返回 (None, [])"""
    for name, pats in COMPILED:
        hits = _frags(text, pats)
        if hits:
            return name, hits
    return None, []


def detect_annotation(text: str):
    """返回后人注释的命中片段列表；没命中返回 []"""
    return _frags(text, ANNO, cap=2)


# ---------------------------------------------------------------- frontmatter
def split_fm(raw: str):
    """拆成 (frontmatter行列表, 正文)。没有 fm 则返回 (None, raw)"""
    if not raw.startswith("---"):
        return None, raw
    lines = raw.split("\n")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, raw
    return lines[1:end], "\n".join(lines[end + 1 :])


def rebuild(fm_lines, body: str) -> str:
    return "---\n" + "\n".join(fm_lines) + "\n---\n" + body


def set_field(fm_lines, key: str, value: str):
    """就地设置 frontmatter 字段；不存在则插到 tags 之前（或末尾）"""
    for i, ln in enumerate(fm_lines):
        if ln.startswith(key + ":"):
            fm_lines[i] = f"{key}: {value}"
            return
    idx = len(fm_lines)
    for i, ln in enumerate(fm_lines):
        if ln.startswith("tags:"):
            idx = i
            break
    fm_lines.insert(idx, f"{key}: {value}")


def del_field(fm_lines, key: str):
    return [ln for ln in fm_lines if not ln.startswith(key + ":")]


# ---------------------------------------------------------------- 主流程
def process_book(book_dir: Path, dry: bool, clear: bool):
    entries = sorted(
        p
        for p in book_dir.glob("*.md")
        if not p.name.startswith("00-") and not p.name.startswith("_")
    )
    if not entries:
        return None

    marked, annotated, cleaned, results = 0, 0, 0, []

    for p in entries:
        raw = p.read_text(encoding="utf-8")
        fm_lines, body = split_fm(raw)
        if fm_lines is None:
            continue

        if clear:
            new_fm = fm_lines
            for k in ("污染", "污染类型", "今注", "今注来源"):
                new_fm = del_field(new_fm, k)
            if len(new_fm) != len(fm_lines):
                cleaned += 1
                if not dry:
                    p.write_text(rebuild(new_fm, body), encoding="utf-8")
            continue

        kind, hits = detect(body)
        anno = detect_annotation(body)
        if not kind and not anno:
            continue

        if kind:
            marked += 1
        if anno:
            annotated += 1
        results.append((p.name, kind, hits, anno))

        if not dry:
            if kind:
                set_field(fm_lines, "污染", "true")
                set_field(fm_lines, "污染类型", kind)
            if anno:
                set_field(fm_lines, "今注", "true")
            p.write_text(rebuild(fm_lines, body), encoding="utf-8")

    return {
        "book": book_dir.name,
        "total": len(entries),
        "marked": marked,
        "annotated": annotated,
        "cleaned": cleaned,
        "results": results,
    }


def write_report(book_dir: Path, stat: dict):
    total = max(1, stat["total"])
    lines = [
        "---",
        "tags: [索引/污染位置表]",
        f"书: {stat['book']}",
        "---",
        "",
        f"# 污染位置表 · {stat['book']}",
        "",
        "> 机器扫描结果。两个标记是**正交**的，别混：",
        ">",
        "> - `污染: true` —— 字句被后人**改动**过。这类条目"
        "**不能作为《六壬大全》的独立证据**，因为它本身可能就是据《大全》改的。",
        "> - `今注: true` —— 只是混入了后人**注文**，原文字句未必被改。"
        "引用时剥离注文即可，证据力不打折。",
        ">",
        "> 判定规则见 `[[互校污染规则-方法卡]]`。",
        "",
        f"- 扫描条目：{stat['total']} 条",
        f"- 字句被改（污染）：**{stat['marked']} 条**"
        f"（{stat['marked'] * 100 // total}%）",
        f"- 混入今注：{stat['annotated']} 条"
        f"（{stat['annotated'] * 100 // total}%）",
        "",
    ]
    if stat["results"]:
        lines += [
            "| 条目 | 字句被改 | 今注 | 命中片段 |",
            "| :--- | :--- | :--- | :--- |",
        ]
        for name, kind, hits, anno in stat["results"]:
            stem = name[:-3]
            frag = " ／ ".join(h.replace("|", "／") for h in (hits or anno)[:2])
            lines.append(
                f"| [[{stem}]] | {kind or '—'} | {'✓' if anno else '—'} | {frag} |"
            )
    else:
        lines.append("**未命中任何校记语或今注。** 若该书本应有校记，检查录文是否已被删注。")

    lines += [
        "",
        "## 人工复核清单",
        "",
        "机器只认关键词，会有两类错：",
        "",
        "1. **漏报**：校记写在书末「校勘记」而非正文夹注里 → 手工翻一遍书末。",
        "2. **误报**：正文本身在讨论「脱」「衍」等术语 → 逐条确认后手工删掉 frontmatter 的 `污染` 行。",
        "",
        "复核完把本文件的 `状态` 改成 `已复核`。",
    ]
    (book_dir / "_污染位置表.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="清校污染标记器")
    ap.add_argument("--vault", default="六壬vault", help="vault 路径")
    ap.add_argument("--book", help="书名（唐宋层下的目录名）")
    ap.add_argument("--all", action="store_true", help="扫所有唐宋层书目")
    ap.add_argument("--dry-run", action="store_true", help="只报告不写入")
    ap.add_argument("--clear", action="store_true", help="清除已有污染标记")
    args = ap.parse_args()

    root = Path(args.vault) / "10-底本" / "唐宋层"
    if not root.is_dir():
        sys.exit(f"找不到唐宋层目录：{root}（请在 六壬agent工作区/ 下运行）")

    if args.all:
        books = [d for d in sorted(root.iterdir()) if d.is_dir()]
    elif args.book:
        d = root / args.book
        if not d.is_dir():
            have = "、".join(x.name for x in sorted(root.iterdir()) if x.is_dir())
            sys.exit(f"找不到「{args.book}」。现有：{have}")
        books = [d]
    else:
        sys.exit("请指定 --book <书名> 或 --all")

    grand = 0
    for d in books:
        stat = process_book(d, args.dry_run, args.clear)
        if stat is None:
            print(f"— {d.name}：无条目（还没导入？）")
            continue

        if args.clear:
            print(f"— {d.name}：清除标记 {stat['cleaned']} 条")
            continue

        pct = stat["marked"] * 100 // max(1, stat["total"])
        flag = "⛔" if pct >= 30 else ("⚠️" if stat["marked"] else "✅")
        print(
            f"{flag} {d.name}：{stat['total']} 条 → "
            f"字句被改 {stat['marked']}（{pct}%）／今注 {stat['annotated']}"
        )
        改 = [r for r in stat["results"] if r[1]]
        for name, kind, hits, _ in 改[:8]:
            print(f"      · {name[:-3]}  [{kind}]  {hits[0][:40]}")
        if len(改) > 8:
            print(f"      … 其余 {len(改) - 8} 条见污染位置表")

        grand += stat["marked"]
        if not args.dry_run:
            write_report(d, stat)

    if args.dry_run:
        print("\n（--dry-run 未写入任何文件）")
    elif not args.clear:
        print(f"\n共标记 {grand} 条，各书目录下已生成 `_污染位置表.md`")
        print("下一步：人工复核漏报（校记常在书末「校勘记」，机器扫不到正文夹注之外的）")


if __name__ == "__main__":
    main()
