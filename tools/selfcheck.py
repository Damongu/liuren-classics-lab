#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自检：确认 vault 完整、可用、没有断链。

用途：
  1. 解压后跑一次，确认包没坏。
  2. 每次 build_vault.py 之后跑一次，确认构建结果正常。
  3. 手工编辑 vault 之后跑一次，确认没写坏双链。

用法：
  python3 tools/selfcheck.py
  python3 tools/selfcheck.py --vault 六壬vault
  python3 tools/selfcheck.py --quiet      # 只输出结论

退出码：0 全通过；1 有错误；2 只有警告。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from collections import defaultdict
from pathlib import Path

# 期望的目录骨架
EXPECTED_DIRS = [
    "00-索引",
    "10-底本",
    "15-导读",
    "20-概念卡",
    "30-课例",
    "40-考据卡",
    "50-校读笔记",
    "60-掌握度",
    "70-待查",
    "90-禄命对照",
    "99-今注剥离",
]

# 期望的八部书及其最少条数（低于此数说明构建不完整）
EXPECTED_BOOKS = {
    "太白阴经": 15,
    "占事略决": 30,
    "景祐六壬神定经": 35,
    "武经总要": 10,
    "六壬心镜": 180,
    "六壬断案": 200,
    "壬归": 35,
    "卜筮书残卷": 2,
}

# 必须存在的关键文件
KEY_FILES = [
    "50-校读笔记/对校矩阵-五个判别点.md",
    "50-校读笔记/互校污染规则-方法卡.md",
    "70-待查/待查清单.md",
    "00-索引/佐证层书目分级.md",
    "00-索引/证据面板.md",
    "00-索引/唐宋层导入指南.md",
    "00-索引/导读流程-方案.md",
]

WIKILINK = re.compile(r"\[\[([^\]|#\\]+)(?:\\?[|#][^\]]*)?\]\]")
# 注：表格内的双链要写 [[目标\|显示]]，转义竖线也算分隔符，故 \\ 一并终止捕获


class Report:
    def __init__(self, quiet=False):
        self.errors: list[str] = []
        self.warns: list[str] = []
        self.oks: list[str] = []
        self.quiet = quiet

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warns.append(msg)

    def ok(self, msg):
        self.oks.append(msg)
        if not self.quiet:
            print(f"  ✅ {msg}")


def split_fm(raw: str):
    if not raw.startswith("---"):
        return None, raw
    lines = raw.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1 :])
    return None, raw


def check_skeleton(vault: Path, r: Report):
    if not r.quiet:
        print("\n[1/8] 目录骨架")
    missing = [d for d in EXPECTED_DIRS if not (vault / d).is_dir()]
    if missing:
        r.err(f"缺目录：{'、'.join(missing)}")
    else:
        r.ok(f"{len(EXPECTED_DIRS)} 个顶层目录齐全")


def check_key_files(vault: Path, r: Report):
    if not r.quiet:
        print("\n[2/8] 关键文件")
    missing = [f for f in KEY_FILES if not (vault / f).is_file()]
    if missing:
        r.err(f"缺关键文件：{'、'.join(missing)}")
    else:
        r.ok(f"{len(KEY_FILES)} 个关键文件齐全")


def check_books(vault: Path, r: Report):
    if not r.quiet:
        print("\n[3/8] 八部唐宋层书")
    root = vault / "10-底本" / "唐宋层"
    if not root.is_dir():
        r.err("找不到 10-底本/唐宋层，底本未导入")
        return {}

    counts = {}
    for book, minimum in EXPECTED_BOOKS.items():
        d = root / book
        if not d.is_dir():
            r.err(f"《{book}》目录不存在")
            counts[book] = 0
            continue
        entries = [
            p
            for p in d.glob("*.md")
            if not p.name.startswith("00-") and not p.name.startswith("_")
        ]
        n = len(entries)
        counts[book] = n
        if n < minimum:
            r.err(f"《{book}》只有 {n} 条，少于预期 {minimum} 条，构建可能未完成")
        else:
            r.ok(f"《{book}》{n} 条")

        if not (d / f"00-{book}目录.md").is_file():
            r.warn(f"《{book}》缺目录文件 00-{book}目录.md")
        if not (d / f"00-书卡-{book}.md").is_file():
            r.warn(f"《{book}》缺书卡")
    return counts


def check_frontmatter(vault: Path, r: Report):
    if not r.quiet:
        print("\n[4/8] 底本条目 frontmatter")
    root = vault / "10-底本" / "唐宋层"
    if not root.is_dir():
        return
    bad_fm, no_book, total = [], [], 0
    for p in root.rglob("*.md"):
        if p.name.startswith("00-") or p.name.startswith("_"):
            continue
        total += 1
        raw = p.read_text(encoding="utf-8")
        fm, _ = split_fm(raw)
        if fm is None:
            bad_fm.append(p.name)
            continue
        if not any(ln.startswith("书:") for ln in fm):
            no_book.append(p.name)
    if bad_fm:
        r.err(f"{len(bad_fm)} 条缺 frontmatter，例：{bad_fm[0]}")
    if no_book:
        r.err(f"{len(no_book)} 条 frontmatter 缺「书」字段，例：{no_book[0]}")
    if not bad_fm and not no_book:
        r.ok(f"{total} 条底本条目 frontmatter 均合规")


def check_pollution(vault: Path, r: Report):
    if not r.quiet:
        print("\n[5/8] 污染标记")
    root = vault / "10-底本" / "唐宋层"
    if not root.is_dir():
        return
    stats = defaultdict(lambda: {"污染": 0, "今注": 0, "总": 0})
    for p in root.rglob("*.md"):
        if p.name.startswith("00-") or p.name.startswith("_"):
            continue
        book = p.parent.name
        raw = p.read_text(encoding="utf-8")
        fm, _ = split_fm(raw)
        if fm is None:
            continue
        stats[book]["总"] += 1
        for ln in fm:
            if ln.startswith("污染:") and "true" in ln:
                stats[book]["污染"] += 1
            if ln.startswith("今注:") and "true" in ln:
                stats[book]["今注"] += 1

    tables = list(root.rglob("_污染位置表.md"))
    if not tables:
        r.warn("没有任何 _污染位置表.md，污染标记器可能没跑过："
               "python3 tools/mark_pollution.py --all")
    else:
        r.ok(f"{len(tables)} 部书已生成污染位置表")

    xj = stats.get("六壬心镜", {})
    if xj.get("总", 0) and xj.get("污染", 0) == 0:
        r.warn("《六壬心镜》0 条污染标记 —— 该书本应有清人校记，"
               "请确认 mark_pollution.py 跑过且规则未被改坏")
    elif xj.get("污染", 0):
        r.ok(f"《六壬心镜》{xj['污染']} 条字句被改、{xj['今注']} 条含今注（符合预期）")

    da = stats.get("六壬断案", {})
    if da.get("污染", 0) > 20:
        r.warn(f"《六壬断案》有 {da['污染']} 条被标为字句被改 —— 偏高。"
               "该书应以「今注」为主，请检查污染规则是否把校注误判为改字")

    for book in ("太白阴经", "占事略决", "景祐六壬神定经", "武经总要"):
        n = stats.get(book, {}).get("污染", 0)
        if n:
            r.warn(f"《{book}》有 {n} 条污染标记 —— 基准层硬本不应有清校污染，请人工复核")


def check_links(vault: Path, r: Report):
    if not r.quiet:
        print("\n[6/8] 双链完整性")
    # 收集所有 note 名（不含扩展名）
    names = set()
    for p in vault.rglob("*.md"):
        names.add(p.stem)

    broken = defaultdict(list)
    for p in vault.rglob("*.md"):
        raw = p.read_text(encoding="utf-8")
        for m in WIKILINK.finditer(raw):
            target = m.group(1).strip()
            # 允许写成 路径/名字 的形式，取最后一段
            leaf = target.split("/")[-1]
            if leaf not in names and target not in names:
                broken[leaf].append(p.stem)

    if broken:
        total = sum(len(v) for v in broken.values())
        r.warn(f"{len(broken)} 个断链目标（共 {total} 处引用）")
        if not r.quiet:
            for tgt, srcs in sorted(broken.items(), key=lambda x: -len(x[1]))[:10]:
                print(f"      · [[{tgt}]] ← {len(srcs)} 处，如 {srcs[0]}")
            if len(broken) > 10:
                print(f"      … 其余 {len(broken) - 10} 个")
    else:
        r.ok("无断链")


DV_KEYWORDS = {
    "TABLE", "LIST", "TASK", "CALENDAR", "WITHOUT", "ID", "FROM", "WHERE", "SORT",
    "GROUP", "BY", "FLATTEN", "LIMIT", "AS", "AND", "OR", "NOT", "ASC", "DESC",
    "NULL", "TRUE", "FALSE",
}
DV_FUNCS = {
    "date", "today", "now", "dur", "contains", "econtains", "icontains", "any", "all",
    "none", "reverse", "sort", "length", "sum", "min", "max", "round", "number",
    "string", "striptime", "choice", "default", "filter", "map", "link", "elink",
    "rows", "file", "meta", "dateformat", "durationformat", "regexmatch",
}
DV_IMPLICIT = {"file", "tags", "tag", "aliases", "rows"}
DV_BLOCK = re.compile(r"```dataview\s*\n(.*?)```", re.S)


def dv_field_refs(block: str):
    """抽出 dataview 查询里真正处于「字段位置」的标识符。

    要排除：字符串字面量、FROM 后的 tag/路径、as 后的显示别名、file.xxx、关键字与函数名。
    否则会把 #概念卡 这种 tag 名和 as 到期 这种别名误报成字段。
    """
    s = re.sub(r'"[^"]*"', ' "" ', block)
    s = re.sub(r"\bFROM\b.*?(?=\b(?:WHERE|SORT|GROUP|FLATTEN|LIMIT)\b|$)", " ", s,
               flags=re.S | re.I)
    s = re.sub(r"\b[Aa][Ss]\s+[A-Za-z_\u4e00-\u9fff][\w\u4e00-\u9fff]*", " ", s)
    s = re.sub(r"\bfile\.\w+", " ", s)
    s = re.sub(r"^\s*(?:TABLE|LIST|TASK|CALENDAR)(?:\s+WITHOUT\s+ID)?", " ", s, flags=re.I)
    out = []
    for tok in re.findall(r"[A-Za-z_\u4e00-\u9fff][A-Za-z0-9_\u4e00-\u9fff]*", s):
        if tok.upper() in DV_KEYWORDS or tok in DV_FUNCS or tok in DV_IMPLICIT:
            continue
        out.append(tok)
    return out


def check_dataview(vault: Path, r: Report):
    """Dataview 查询引用的字段必须真实存在于某条笔记的 frontmatter。

    字段名写错时 Dataview 不报错，只会渲染出一张空表 —— 属于静默失败，必须机器兜住。
    """
    if not r.quiet:
        print("\n[7/8] Dataview 字段一致性")
    present = set()
    for md in vault.rglob("*.md"):
        fm, _ = split_fm(md.read_text("utf-8"))
        if not fm:
            continue
        for line in fm:
            m = re.match(r"^([^\s:#][^:]*):", line)
            if m:
                present.add(m.group(1).strip())
    bad = {}
    nblk = 0
    for md in sorted(vault.rglob("*.md")):
        rel = md.relative_to(vault).as_posix()
        for blk in DV_BLOCK.findall(md.read_text("utf-8")):
            nblk += 1
            for f in dv_field_refs(blk):
                if f not in present:
                    bad.setdefault(f, set()).add(rel)
    if bad:
        for f, files in sorted(bad.items()):
            r.err(f"Dataview 字段 `{f}` 在任何笔记里都不存在（查询会永远为空）→ "
                  + ", ".join(sorted(files)))
    else:
        r.ok(f"{nblk} 个 dataview 查询引用的字段全部存在")


def check_guides(vault: Path, r: Report):
    """导读卡：底本在不在、占位填没填、有没有被底本改动甩过期。

    这三件都是静默失败：卡还在、能打开、看着像导读，但内容已经不对应当前底本，
    或者根本还是骨架。所以宁可多报警告，也不让骨架冒充导读。
    """
    if not r.quiet:
        print("\n[8/8] 导读卡")
    gdir = vault / "15-导读"
    state_p = vault / "60-掌握度" / "_guide_state.json"
    cards = sorted(p for p in gdir.rglob("*-导读.md")) if gdir.is_dir() else []
    if not cards:
        r.ok("尚无导读卡（按节生成，不批量预生成）")
        return
    state = {}
    if state_p.is_file():
        try:
            state = json.loads(state_p.read_text("utf-8")).get("cards", {})
        except json.JSONDecodeError:
            r.err("_guide_state.json 解析失败，导读进度已损坏 → 删掉后按节重生成")
    n_todo = n_stale = n_orphan = 0
    for cp in cards:
        raw = cp.read_text("utf-8")
        rel = cp.relative_to(vault).as_posix()
        m = re.search(r"^底本: (.+)$", raw, re.M)
        src = vault / ((m.group(1).strip() if m else "") + ".md")
        if not m or not src.is_file():
            n_orphan += 1
            r.err(f"导读卡找不到对应底本条目：{rel}")
            continue
        if raw.count("TODO(agent)"):
            n_todo += 1
            r.warn(f"导读卡仍是骨架，未填第 3／5 件：{rel}"
                   f"（{raw.count('TODO(agent)')} 处占位，骨架不能当导读用）")
        rec = state.get(m.group(1).strip(), {})
        mt = datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        if rec.get("source_mtime") and rec["source_mtime"] < mt:
            n_stale += 1
            r.warn(f"导读卡已过期，底本更新于 {mt}：{rel}"
                   f"　→ python3 tools/guide.py --entry {cp.stem[:-3]} --force")
    idx = vault / "00-索引" / "导读进度.md"
    if not idx.is_file():
        r.warn("缺 00-索引/导读进度.md → python3 tools/guide.py --index")
    elif state and len(state) != len(cards):
        r.warn(f"导读卡 {len(cards)} 张与进度记录 {len(state)} 条不一致 → "
               "python3 tools/guide.py --index")
    if not (n_todo or n_stale or n_orphan):
        r.ok(f"{len(cards)} 张导读卡：底本齐、占位已填、与底本同步")


def main():
    ap = argparse.ArgumentParser(description="六壬 vault 自检")
    ap.add_argument("--vault", default="六壬vault")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    vault = Path(args.vault)
    if not vault.is_dir():
        sys.exit(f"找不到 vault：{vault}（请在 六壬agent工作区/ 下运行）")

    r = Report(args.quiet)
    if not args.quiet:
        print(f"自检 vault：{vault.resolve()}")

    check_skeleton(vault, r)
    check_key_files(vault, r)
    counts = check_books(vault, r)
    check_frontmatter(vault, r)
    check_pollution(vault, r)
    check_links(vault, r)
    check_dataview(vault, r)
    check_guides(vault, r)

    # 汇总
    print("\n" + "=" * 56)
    if counts:
        total = sum(counts.values())
        print(f"底本条目合计：{total} 条")
    if r.errors:
        print(f"\n❌ 错误 {len(r.errors)} 项（vault 不完整，需重建）：")
        for e in r.errors:
            print(f"   · {e}")
    if r.warns:
        print(f"\n⚠️  警告 {len(r.warns)} 项（可用，但建议处理）：")
        for w in r.warns:
            print(f"   · {w}")
    if not r.errors and not r.warns:
        print("\n✅ 全部通过。vault 完整可用。")
    elif not r.errors:
        print("\n✅ 无错误。vault 可用。")

    if r.errors:
        print("\n重建：python3 tools/build_vault.py --force")
        sys.exit(1)
    sys.exit(2 if r.warns else 0)


if __name__ == "__main__":
    main()
