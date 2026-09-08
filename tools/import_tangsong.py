#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
唐宋层文献导入器 —— 把本地抓取的书目文件夹转成 Obsidian vault 条目。

用法（在 六壬agent工作区/ 下执行）：

    # 先看一眼会发生什么，不写文件
    python3 tools/import_tangsong.py --src ~/六壬书/太白阴经 --book 太白阴经 --dry-run

    # 正式导入
    python3 tools/import_tangsong.py --src ~/六壬书/太白阴经 --book 太白阴经 \
        --evidence 一手 --dating "唐·约759" --version 十卷本

    # 大文件按标题切条（一个 txt 里塞了整本书时用）
    python3 tools/import_tangsong.py --src ~/六壬书/武經總要_全書抓取 --book 武经总要 \
        --split-headings --evidence 一手 --dating "北宋·仁宗朝"

设计取舍：
- 纯标准库，不装依赖也能跑。装了 opencc 会自动把繁体正文转简体（便于全文搜索与对校），
  没装则保留原文并在 frontmatter 标 `繁简: 未转`。
- 默认幂等：已存在的条目跳过，不覆盖你的批注。要重导用 --force。
- 每次导入都写 `_导入报告.md`，核对文件数与字数用它。
"""

import argparse
import html
import json
import os
import re
import sys
from pathlib import Path

TEXT_EXT = {".txt", ".md", ".markdown", ".html", ".htm", ".json", ".xml"}
# gb18030 几乎能"成功"解码任意字节，直接按顺序 try 会把 Big5 解成乱码。
# 所以：全部候选都解一遍，按中文可读性打分取最优。
ENCODINGS = ["utf-8-sig", "utf-8", "gb18030", "big5hkscs", "cp950", "latin-1"]
ILLEGAL = r'[\\/:*?"<>|\n\r\t]'

COMMON = set("的一是不了在人有我他这为之大来以个中上们到说国和地也子时道日月年"
             "卷第法課课占用神將将天干支上下四三二一子丑寅卯辰巳午未申酉戌亥"
             "壬六甲乙丙丁戊己庚辛癸吉凶陰陽阴阳者也而其以於于")


def score_cn(s: str) -> float:
    """中文可读性打分：常用字与汉字比例加分，私用区 / 生僻块 / 替换符减分。"""
    if not s:
        return -1e9
    sample = s[:4000]
    cjk = common = weird = 0
    for ch in sample:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF:
            cjk += 1
            if ch in COMMON:
                common += 1
        elif 0xE000 <= o <= 0xF8FF or 0x3400 <= o <= 0x4DBF or ch == "\ufffd":
            weird += 1
        elif o < 0x20 and ch not in "\n\r\t":
            weird += 1
    n = len(sample)
    return (cjk / n) * 1.0 + (common / n) * 4.0 - (weird / n) * 8.0


# ---------- 读取 ----------

def read_text(path: Path):
    raw = path.read_bytes()
    # UTF-8 能严格解出来就直接用，不必打分
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            pass
    best, best_enc, best_score = None, None, -1e9
    for enc in ENCODINGS:
        try:
            s = raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
        sc = score_cn(s)
        if sc > best_score:
            best, best_enc, best_score = s, enc, sc
    if best is None:
        return raw.decode("utf-8", errors="replace"), "utf-8(replace)"
    return best, best_enc


def strip_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|li|h[1-6]|tr)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def from_json(s: str) -> str:
    try:
        obj = json.loads(s)
    except Exception:
        return s
    buf = []

    def walk(o):
        if isinstance(o, str):
            buf.append(o)
        elif isinstance(o, dict):
            for k in ("title", "chapter", "name", "text", "content", "body"):
                if k in o:
                    walk(o[k])
            for k, v in o.items():
                if k not in ("title", "chapter", "name", "text", "content", "body"):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(obj)
    return "\n\n".join(x.strip() for x in buf if x and x.strip())


def load(path: Path):
    s, enc = read_text(path)
    ext = path.suffix.lower()
    if ext in (".html", ".htm", ".xml"):
        s = strip_html(s)
    elif ext == ".json":
        s = from_json(s)
    return s.strip(), enc

# ---------- 繁简 ----------

class Conv:
    def __init__(self, enable: bool):
        self.fn = None
        self.tag = "未转"
        if not enable:
            return
        try:
            from opencc import OpenCC  # type: ignore
            cc = OpenCC("t2s")
            self.fn = cc.convert
            self.tag = "已转简（opencc t2s）"
        except Exception:
            self.tag = "未转（未装 opencc）"

    def __call__(self, s: str) -> str:
        return self.fn(s) if self.fn else s

# ---------- 切条 ----------

HEAD_PATTERNS = [
    re.compile(r"^#{1,4}\s*(\S.*)$"),                                  # markdown 标题
    re.compile(r"^\s*(卷[一二三四五六七八九十百廿\d]+.*)$"),            # 卷一 / 卷十
    re.compile(r"^\s*(第[一二三四五六七八九十百廿\d]+[篇章卷法課课].*)$"),
    re.compile(r"^\s*([一二三四五六七八九十]{1,3}[、．.]\s*\S.*)$"),
]


def split_by_heading(text: str, min_chars: int = 120):
    lines = text.splitlines()
    chunks, title, buf = [], None, []

    def flush():
        body = "\n".join(buf).strip()
        if title is None and not body:
            return
        if body and len(body) < min_chars and chunks:
            chunks[-1][1] += "\n\n" + ((title + "\n") if title else "") + body
            return
        chunks.append([title, body])

    for ln in lines:
        hit = None
        for pat in HEAD_PATTERNS:
            m = pat.match(ln)
            if m and len(m.group(1).strip()) <= 40:
                hit = m.group(1).strip()
                break
        if hit:
            flush()
            title, buf = hit, []
        else:
            buf.append(ln)
    flush()
    return [(t, b) for t, b in chunks if b.strip()]

# ---------- 命名 ----------

def clean_name(s: str, limit: int = 60) -> str:
    s = re.sub(ILLEGAL, "_", s).strip().strip(".")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"^\d+[-_.]?\s*", "", s)  # 去掉抓取工具加的序号前缀
    return (s[:limit] or "未命名")


def unique(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suf, i = path.stem, path.suffix, 2
    while True:
        p = path.with_name(f"{stem}-{i}{suf}")
        if not p.exists():
            return p
        i += 1

# ---------- 写条目 ----------

FM = """---
类型: 底本条目
书: {book}
版本: {version}
卷篇: {juan}
断代: {dating}
证据等级: {evidence}
理据价值: {reason}
抄大全风险: {risk}
繁简: {conv}
待核: true
源文件: {src}
源编码: {enc}
tags: [底本, 唐宋层, {tag}]
---

"""


def write_entry(out_dir: Path, book: str, juan: str, body: str, meta: dict, force: bool):
    fname = clean_name(f"{book}-{juan}") + ".md"
    target = out_dir / fname
    if target.exists() and not force:
        return None, "skip"
    if target.exists() and force:
        target.unlink()
    fm = FM.format(book=book, version=meta["version"], juan=juan, dating=meta["dating"],
                   evidence=meta["evidence"], reason=meta["reason"], risk=meta["risk"],
                   conv=meta["conv"], src=meta["src"], enc=meta["enc"],
                   tag=re.sub(r"\s+", "", book))
    head = f"# {book} {juan}\n\n> ⚠️ 机器导入的录文，**未核原刻**。引用具体字句前须回原书影。\n\n"
    target.write_text(fm + head + body.strip() + "\n", encoding="utf-8")
    return target, "write"

# ---------- 主流程 ----------

def main():
    ap = argparse.ArgumentParser(description="唐宋层文献导入器")
    ap.add_argument("--src", required=True, help="本地书目文件夹")
    ap.add_argument("--book", required=True, help="书名（用于目录名与 frontmatter）")
    ap.add_argument("--vault", default="六壬vault", help="vault 路径")
    ap.add_argument("--version", default="待考", help="版本 / 传本，如 十卷本")
    ap.add_argument("--dating", default="待考", help="断代，如 唐·约759")
    ap.add_argument("--evidence", default="待判", help="一手 / 二手 / 参照 / 待考 / 不采信")
    ap.add_argument("--reason", default="待判", help="理据价值 ★ / ★★ / ★★★")
    ap.add_argument("--risk", default="未查", help="抄大全风险 无 / 低 / 高 / 未查")
    ap.add_argument("--split-headings", action="store_true", help="单文件按标题切条")
    ap.add_argument("--min-chars", type=int, default=120,
                    help="切条时，短于此字数的段落并入上一条（默认 120，设 0 则每个标题都独立成条）")
    ap.add_argument("--no-convert", action="store_true", help="不做繁→简转换")
    ap.add_argument("--force", action="store_true", help="覆盖已存在条目")
    ap.add_argument("--dry-run", action="store_true", help="只报告不写入")
    args = ap.parse_args()

    src = Path(os.path.expanduser(args.src))
    if not src.exists():
        sys.exit(f"✗ 源目录不存在：{src}")
    out_dir = Path(args.vault) / "10-底本" / "唐宋层" / clean_name(args.book, 40)
    conv = Conv(not args.no_convert)

    files = sorted(p for p in src.rglob("*") if p.is_file() and p.suffix.lower() in TEXT_EXT)
    if not files:
        sys.exit(f"✗ {src} 下没找到可读文本（支持 {sorted(TEXT_EXT)}）")

    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    rows, written, skipped, total_chars = [], 0, 0, 0
    for f in files:
        text, enc = load(f)
        if not text:
            rows.append((f.name, "-", 0, "空文件，跳过"))
            continue
        text = conv(text)
        pieces = (split_by_heading(text, args.min_chars) if args.split_headings
                  else [(None, text)])
        if not pieces:
            pieces = [(None, text)]
        for title, body in pieces:
            juan = clean_name(title or f.stem, 50)
            total_chars += len(body)
            meta = dict(version=args.version, dating=args.dating, evidence=args.evidence,
                        reason=args.reason, risk=args.risk, conv=conv.tag,
                        src=f"{f.relative_to(src)}", enc=enc)
            if args.dry_run:
                rows.append((f.name, juan, len(body), "将写入"))
                written += 1
                continue
            target, act = write_entry(out_dir, args.book, juan, body, meta, args.force)
            if act == "write":
                written += 1
                rows.append((f.name, juan, len(body), target.name))
            else:
                skipped += 1
                rows.append((f.name, juan, len(body), "已存在，跳过"))

    print(f"\n书：{args.book}   源：{src}")
    print(f"文件 {len(files)} 个 → 条目 {written} 条（跳过 {skipped}），正文 {total_chars:,} 字")
    print(f"繁简：{conv.tag}")
    print(f"输出：{out_dir}")

    if args.dry_run:
        for r in rows[:30]:
            print("   ", r)
        print("\n（--dry-run 未写入任何文件）")
        return

    # 书内目录页 + 导入报告
    entries = sorted(p.stem for p in out_dir.glob("*.md") if not p.name.startswith("00-"))
    toc = [f"---\ntags: [索引/唐宋层]\n---\n", f"# {args.book} · 条目目录\n",
           f"共 {len(entries)} 条。书卡见 `[[00-书卡-{args.book}]]`（若已建）。\n"]
    toc += [f"- [[{e}]]" for e in entries]
    (out_dir / f"00-{clean_name(args.book,30)}目录.md").write_text("\n".join(toc) + "\n", encoding="utf-8")

    rep = ["---\ntags: [索引/导入报告]\n---\n", f"# 导入报告 · {args.book}\n",
           f"- 源目录：`{src}`", f"- 文件 {len(files)} 个 → 条目 {written} 条（跳过 {skipped}）",
           f"- 正文合计 {total_chars:,} 字", f"- 繁简：{conv.tag}",
           f"- 切条方式：{'按标题切条' if args.split_headings else '一文件一条'}\n",
           "| 源文件 | 条目 | 字数 | 结果 |", "| :--- | :--- | ---: | :--- |"]
    rep += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    (out_dir / "_导入报告.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("已生成：条目目录、_导入报告.md")


if __name__ == "__main__":
    main()
