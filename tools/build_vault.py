#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
唐宋层一键构建器
================

把 sources/ 下七部书的原始文件，一次性变成 Obsidian vault 里可互校的条目。

    python3 tools/build_vault.py              # 全量构建
    python3 tools/build_vault.py --dry-run    # 只报告不写
    python3 tools/build_vault.py --book 太白阴经   # 只构建一部
    python3 tools/build_vault.py --force      # 覆盖已存在条目（会丢批注）

为什么不用通用导入器
--------------------
七部书七种形态：Word97 二进制、docx、带页眉的 PDF 文本层、无标点白文 txt、
带校记的整理稿。通用切条器只能保证「不报错」，保证不了「切在篇界上」。
所以每部书一个 handler，各自认自己的卷篇标记。

繁简处理的两个坑（已修）
------------------------
opencc t2s 会把 `乾天門` 转成 `干天门`、`徵明` 转成 `征明`。
前者毁掉四维（乾天门／坤人门／巽地户／艮鬼路），后者毁掉月将异名。
本脚本对 `乾` `徵` 做占位符保护，其余照常转换。
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources"
VAULT = ROOT / "六壬vault"
TANGSONG = VAULT / "10-底本" / "唐宋层"

# ---------------------------------------------------------------- 繁简转换

_PROTECT = {"乾": "\ue001", "徵": "\ue002"}

try:
    import opencc

    _CC = opencc.OpenCC("t2s")
except Exception:
    _CC = None


def t2s(text: str) -> str:
    """繁转简，保护术语用字。没装 opencc 时原样返回。"""
    if _CC is None:
        return text
    for ch, ph in _PROTECT.items():
        text = text.replace(ch, ph)
    text = _CC.convert(text)
    for ch, ph in _PROTECT.items():
        text = text.replace(ph, ch)
    return text


CONV_NOTE = (
    "已转（opencc t2s，保护 乾/徵）" if _CC else "未转（未装 opencc）"
)

# ---------------------------------------------------------------- 通用工具


def clean(lines):
    """去掉页眉页脚、页码、纯符号行，压掉连续空行"""
    out, blank = [], False
    drop = re.compile(
        r"^[·・]?[\d０-９一二三四五六七八九十]+[·・]?$"  # 页码
        r"|^[—\-–—_=＝\s]{3,}$"  # 分隔线
        r"|^\s*$"
    )
    for ln in lines:
        s = ln.strip().replace("\u3000", " ").strip()
        if not s or drop.match(s):
            if not blank and out:
                out.append("")
                blank = True
            continue
        out.append(s)
        blank = False
    while out and out[-1] == "":
        out.pop()
    return out


def pdftext(path: Path) -> list:
    r = subprocess.run(
        ["pdftotext", "-enc", "UTF-8", str(path), "-"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(f"pdftotext 失败：{path.name}\n{r.stderr[:300]}")
    return r.stdout.split("\n")


def strip_running(lines, *marks):
    """删除反复出现的书名页眉"""
    return [l for l in lines if l.strip() not in marks]


MIN_CHARS = 15  # 短于此字数的条目视为切条残渣（卷首空壳、标题回声），丢弃


def pack(entries, book):
    """(标题, [正文行][, 附加frontmatter]) → (标题, 正文, 附加)；丢掉切条残渣"""
    out, dropped = [], []
    for item in entries:
        title, body = item[0], item[1]
        extra = item[2] if len(item) > 2 else {}
        text = "\n\n".join(
            p for p in ("\n".join(body)).split("\n\n") if p.strip()
        ).strip()
        title = t2s(title.strip())
        if len(text) < MIN_CHARS:
            if text:
                dropped.append((title, len(text)))
            continue
        out.append((title, t2s(text), extra))
    if dropped:
        d = "、".join(f"{t}({n}字)" for t, n in dropped[:4])
        more = f" 等 {len(dropped)} 条" if len(dropped) > 4 else ""
        print(f"      ⚠️ {book}：丢弃切条残渣 {d}{more}")
    return out


# ---------------------------------------------------------------- 各书 handler


def h_taibai(path: Path):
    """太白阴经：只取卷十「玄女式」及其下诸法（卷一—卷九为兵书正文，不入库）"""
    lines = strip_running(pdftext(path), "神机制敌太白阴经")
    # 定位正文卷十（目录里也有「卷十」，取最后一个）
    idx = [i for i, l in enumerate(lines) if l.strip() == "卷十"]
    start = idx[-1]
    # 六壬部分止于「△察情胜败篇」
    end = next(
        (i for i in range(start, len(lines)) if lines[i].strip() == "△察情胜败篇"),
        len(lines),
    )
    seg = clean(lines[start:end])

    entries, title, body = [], "卷十 杂式（玄女式前）", []
    for s in seg:
        if s.startswith("△"):
            if body:
                entries.append((title, body))
            title, body = s.lstrip("△").strip(), []
        else:
            body.append(s)
    if body:
        entries.append((title, body))
    return pack(entries, "太白阴经"), "卷十"


def h_zhanshi(path: Path):
    """占事略决：按「第N章」切，共 36 章"""
    lines = strip_running(pdftext(path), "占事略決", "占事略决")
    # 跳过目录：正文第一个「第1章」之后
    body_start = 0
    for i, l in enumerate(lines):
        if re.match(r"^第\s*1\s*章$", l.strip()):
            body_start = i
            break
    seg = clean(lines[body_start:])

    entries, title, body = [], None, []
    i = 0
    while i < len(seg):
        s = seg[i]
        m = re.match(r"^第\s*(\d+)\s*章$", s)
        if m:
            if title:
                entries.append((title, body))
            # 章名在下一个非空行（clean 后空行仍以 "" 保留，须跳过）
            j = i + 1
            while j < len(seg) and not seg[j].strip():
                j += 1
            name = seg[j].strip() if j < len(seg) else ""
            title = f"第{m.group(1)}章 {name}".strip()
            body = []
            i = j + 1
            continue
        body.append(s)
        i += 1
    if title:
        entries.append((title, body))
    return pack(entries, "占事略决"), "一卷"


def h_shendingjing(path: Path):
    """景祐六壬神定经：docx，按「釋X第N」切，保留〔影印頁 N〕定位"""
    import docx

    d = docx.Document(str(path))
    ps = [p.text.strip() for p in d.paragraphs if p.text.strip()]

    juan = "上卷"
    entries, title, body = [], "底本说明", []
    pian = re.compile(r"^釋.{1,8}第[一二三四五六七八九十百]+$")
    for p in ps:
        if p in ("上卷", "下卷"):
            juan = p
            continue
        if p == "目錄" or p.startswith("打开 Word"):
            continue
        if pian.match(p):
            if body:
                entries.append((title, body))
            title, body = f"{juan} {p}", []
        else:
            body.append(p)
    if body:
        entries.append((title, body))
    return pack(entries, "景祐六壬神定经"), "二卷本（明钞残帙）"


# 后集卷十六—二十＝司天少监杨维德等奉敕编纂的「占候诀五卷」。
# 六壬只占卷二十前半，但整组占候同出一手、共用一套术数名目，
# 故全部入库，靠「部 / 与六壬关系」分层，避免旁证被当成六壬硬证。
WJ_JUAN = ["后集卷十六", "后集卷十七", "后集卷十八",
           "后集卷十九上", "后集卷十九下", "后集卷二十"]

# (卷, 篇名关键字) → (部, 与六壬关系)；篇名留空表示该卷缺省
WJ_ROLE = [
    ("后集卷二十", "遁甲", "遁甲", "同源三式·共用神名"),
    ("后集卷二十", "", "六壬", "本体规则"),
    ("后集卷十九", "", "太乙", "同源三式·穷举立成表"),
    ("后集卷十八", "太乙", "太乙", "同源三式"),
    ("后集卷十八", "", "占候", "兵占背景"),
    ("后集卷十七", "风角", "风角", "术语共享·德刑杀墓纳音"),
    ("后集卷十七", "日辰占", "占候", "术语共享·干支分野"),
    ("后集卷十七", "二十八宿", "占候", "配套表·用禽法"),
    ("后集卷十七", "", "占候", "兵占背景"),
    ("后集卷十六", "", "占候", "编纂背景·同编者杨维德"),
]


def wj_role(juan: str, title: str):
    for j, kw, bu, rel in WJ_ROLE:
        if juan.startswith(j) and (not kw or kw in title):
            return bu, rel
    return "占候", "兵占背景"


def _wj_split_juan(lines):
    """按「后集卷X」标题切出卷块，返回 [(卷名, [行])]

    卷名在全书目录里也各出现一次，必须先跳到「第二編　後集」正文分界，
    否则「後集卷二十」会撞上目录里的那一条，把整个前集吞进卷块。
    """
    JUAN = ("後集卷十六", "後集卷十七", "後集卷十八",
            "後集卷十九上", "後集卷十九下", "後集卷二十")
    head = [i for i, l in enumerate(lines) if l.strip().endswith("後集")
            and l.strip().startswith("第二編")]
    body = head[-1] if head else 0
    marks = [(i, t2s(l.strip())) for i, l in enumerate(lines)
             if i > body and l.strip() in JUAN]
    out = []
    for k, (i, name) in enumerate(marks):
        j = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
        out.append((name, lines[i:j]))
    return out


def _wj_sections(block):
    """
    卷块 → (篇名, [(节名, [正文行])])。白文无标点，靠原始缩进分层：
      · 不缩进＝标题候选，缩进＝正文
      · 卷首「占候N」之后常有一段目录，目录首名再次出现即正文开始
      · 目录名被排进正文行里的（如「…必有覆軍死將二十八宿次舍【…」）就地拆出
      · 「甲為齊／乙為東夷／…」这类连排短行不是标题，是正文
    """
    IND = lambda raw: raw.startswith("\u3000") or raw.startswith("  ")
    junk = lambda s: not s or set(s) <= set("—-–_= ")

    pian, body_start = None, 0
    for i, l in enumerate(block):
        if re.fullmatch(r"占候[一二三四五]", l.strip()):
            pian, body_start = t2s(l.strip()), i + 1
            break

    # ---- 目录：卷首连续不缩进行，遇缩进行或首名重复即止
    run = []
    for i in range(body_start, len(block)):
        raw, s = block[i], block[i].strip()
        if junk(s):
            continue
        if IND(raw):
            break
        if run and s == run[0]:
            body_start = i
            break
        run.append(s)
    names = set(run)

    # ---- 展平为 (是否正文, 文本)，顺手把混排进正文的目录名拆出来
    seg, seen = [], set()
    for raw in block[body_start:]:
        s = raw.strip()
        if junk(s):
            continue
        split = False
        while True:
            def runon(n):
                if n in seen or n not in s or s.startswith(n):
                    return False
                j = s.index(n) + len(n)
                return j >= len(s) or s[j] == "【"

            hit = min((n for n in names if runon(n)),
                      key=s.index, default=None)
            if not hit:
                break
            head, s = s.split(hit, 1)
            if head.strip():
                seg.append((True, head.strip()))
            seg.append((False, hit))
            seen.add(hit)
            split = True
        if s.strip():
            is_body = IND(raw) or split
            seg.append((is_body, s.strip()))
            if not is_body:
                seen.add(s.strip())

    # ---- 判标题：命中目录名，或前后都是正文的孤立不缩进行
    out, title, body = [], "总说", []
    for k, (is_body, s) in enumerate(seg):
        if is_body:
            body.append(s)
            continue
        prev_b = seg[k - 1][0] if k else True
        next_b = seg[k + 1][0] if k + 1 < len(seg) else True
        if s in names or (prev_b and next_b):
            if body:
                out.append((title, body))
            title, body = s, []
        else:
            body.append(s)
    if body:
        out.append((title, body))
    return pian, out


def h_wujing(path: Path):
    """武经总要：入后集卷十六—二十「占候一至五」全部（六壬＋遁甲＋太乙＋风角＋占候）"""
    lines = open(path, encoding="utf-8-sig").read().replace("\r", "").split("\n")
    entries = []
    for juan, block in _wj_split_juan(lines):
        pian, secs = _wj_sections(block)
        # 卷二十「六壬」「遁甲」两段连排，遁甲标题之后各节都归遁甲
        dunjia = False
        for name, body in secs:
            if t2s(name) == "遁甲":
                dunjia = True
            bu, rel = wj_role(juan, "遁甲" if dunjia else t2s(name))
            title = f"{juan} {pian} {name}" if pian else f"{juan} {name}"
            entries.append((title, body, {"部": bu, "与六壬关系": rel}))
    return pack(entries, "武经总要"), "后集卷十六—二十「占候一至五」"


def h_xinjing(path: Path):
    """大六壬心镜：卷／门／篇三级；不缩进行为标题，缩进行为正文"""
    raw = open(path, encoding="utf-8-sig").read().split("\n")
    # 正文自第二个「大六壬心镜卷一」起（第一个在目录）
    marks = [
        i for i, l in enumerate(raw) if l.strip() == "大六壬心镜卷一"
    ]
    body_start = marks[-1] if len(marks) > 1 else 0
    # 目录块：从「目录」行到第一个「大六壬心镜卷一」之后的目录末尾。
    # 目录里同样列着「前序一/二/三」，不剔掉会和正文序跋重条。
    toc_start = next(
        (i for i, l in enumerate(raw) if l.strip() == "目录"), None
    )
    toc_end = marks[0] if marks else 0
    # 目录结束于正文首个序跋标题之前；取「前序一」的最后一次出现
    pre1 = [i for i, l in enumerate(raw) if l.strip() == "前序一"]
    if toc_start is not None and len(pre1) > 1:
        toc_end = pre1[-1]
    front = raw[toc_end:body_start] if toc_start is not None else raw[:body_start]
    seg = raw[body_start:]

    entries = []

    # --- 序跋
    fr, title, body = [], None, []
    for l in front:
        s = l.strip().replace("\u3000", " ").strip()
        if not s or set(s) <= set("—-–_= "):
            continue
        if s in ("前序一", "前序二", "前序三", "大六壬心镜序"):
            if title:
                fr.append((title, body))
            title, body = s, []
        elif title:
            body.append(s)
    if title:
        fr.append((title, body))
    entries += [(f"序跋 {t}", b) for t, b in fr]

    # --- 正文
    juan, men = "卷一", None
    title, body = None, []
    for l in seg:
        s = l.strip().replace("\u3000", " ").strip()
        if not s or set(s) <= set("—-—_ "):
            continue
        indented = l.startswith("\u3000") or l.startswith("  ")
        if not indented:
            m = re.match(r"^大六壬心镜(卷[一二三四五六七八九十]+)$", s)
            if m:
                if title:
                    entries.append((f"{juan} {men or ''} {title}".strip(), body))
                    title, body = None, []
                juan, men = m.group(1), None
                continue
            if s.endswith("门"):
                if title:
                    entries.append((f"{juan} {men or ''} {title}".strip(), body))
                    title, body = None, []
                men = s
                continue
            # 篇名
            if title:
                entries.append((f"{juan} {men or ''} {title}".strip(), body))
            title, body = s, []
        else:
            if title is None:  # 门下无篇名的散段
                title = men or juan
            body.append(s)
    if title:
        entries.append((f"{juan} {men or ''} {title}".strip(), body))

    return pack(entries, "六壬心镜"), "八卷本·清程氏手录"


CASE_RE = re.compile(r"^(\d{2,3})\.(.+)$")


def h_duanan(path: Path):
    """大六壬断案：442 则占例，按「NN.案名」切；顺带抽课例元数据"""
    lines = strip_running(pdftext(path), "大六壬断案")
    # 目次占前 280 行左右，正文自「序」起
    start = next(
        (i for i, l in enumerate(lines) if l.strip() == "序" and i > 100), 0
    )
    seg = clean(lines[start:])

    entries, title, body = [], "序与弁言", []
    chapter = None
    for s in seg:
        mc = re.match(r"^第([一二三四五六七八九十]+)章\s*(.+)$", s)
        if mc and "..." not in s:
            chapter = f"第{mc.group(1)}章 {mc.group(2)}"
            continue
        mk = CASE_RE.match(s)
        if mk and "..." not in s:
            if body:
                entries.append((title, body))
            num, name = mk.group(1), mk.group(2).strip()
            title = f"{num} {name}" + (f"（{chapter}）" if chapter else "")
            body = []
            continue
        body.append(s)
    if body:
        entries.append((title, body))
    return pack(entries, "六壬断案"), "缘生谛校注本"


def h_rengui(path: Path):
    """壬归：Word97，按「卷之N」与篇名切；先剥掉 Word 域代码"""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from doc_extract import extract

    text = extract(str(path))
    lines = []
    for l in text.split("\n"):
        s = l.strip()
        # 目录里的 TOC / HYPERLINK / PAGEREF 域代码
        if re.search(r"HYPERLINK|PAGEREF|^TOC |_Toc\d+", s):
            continue
        lines.append(s)
    seg = clean(lines)

    juan = None
    entries, title, body = [], "卷首", []
    pian = re.compile(r"^.{2,14}第[一二三四五六七八九十]+$")
    for s in seg:
        mj = re.match(r"^(卷之[一二三四五六七八九十]+)\s*(.*)$", s)
        if mj:
            if body:
                entries.append((title, body))
            juan = mj.group(1) + (f" {mj.group(2)}" if mj.group(2) else "")
            title, body = juan, []
            continue
        if pian.match(s) and len(s) <= 16:
            if body:
                entries.append((title, body))
            title, body = f"{juan} {s}" if juan else s, []
            continue
        body.append(s)
    if body:
        entries.append((title, body))
    return pack(entries, "壬归"), "七卷本"


# ---------------------------------------------------------------- 书目登记

BOOKS = {
    "太白阴经": dict(
        file="神机制敌太白阴经.pdf",
        handler=h_taibai,
        dating="唐·约759（乾元二年进献）",
        evidence="一手·基准层",
        reason="★★★",
        risk="无",
        note="全书十卷为兵书，仅卷十「玄女式」入库；余卷原文见 sources/。",
    ),
    "占事略决": dict(
        file="占事略決_中文正文_精校排版.pdf",
        handler=h_zhanshi,
        dating="十世纪末（约921–1005）",
        evidence="一手·基准层",
        reason="★★★",
        risk="无",
        note="域外传本，未参与明清改写。第2章「课用九法」为九宗门最早完整快照。",
    ),
    "景祐六壬神定经": dict(
        file="景祐六壬神定經_繁體整理稿.docx",
        handler=h_shendingjing,
        dating="北宋·1034（仁宗景祐间敕撰）",
        evidence="一手·基准层",
        reason="★★",
        risk="无",
        note="唯一官修六壬专书。今存二卷本为明钞残帙，第二十五篇缺。",
    ),
    "武经总要": dict(
        file="武經總要_四十卷_繁體易讀版.txt",
        handler=h_wujing,
        dating="北宋·1044（仁宗朝敕撰）",
        evidence="一手·基准层",
        reason="★★",
        risk="无",
        note=(
            "整组入后集卷十六—二十「占候一至五」＝司天少监杨维德等奉敕编的占候诀五卷。"
            "六壬只在卷二十前半（14 条＝硬证），其余按「部／与六壬关系」降级为"
            "遁甲・太乙・风角・占候旁证。白文无标点，靠缩进切条。"
            "已知录文错序：卷十七「五星」正文错排在「日辰占」条内，标题另在其后。"
        ),
    ),
    "六壬心镜": dict(
        file="大六壬心镜_完整整理文字版.txt",
        handler=h_xinjing,
        dating="唐（原书）；今本为清嘉庆辑校",
        evidence="二手·须句级过滤",
        reason="★★",
        risk="高（已见据《大全》《神枢经》补改）",
        note="含郑天民校记、程伟堂按、郇应清注三层今注，须逐条过滤后方可作证。",
    ),
    "六壬断案": dict(
        file="大六壬断案（缘生谛校注版）.pdf",
        handler=h_duanan,
        dating="记录层：南宋建炎间；文字层：清嘉庆辑校",
        evidence="二手·第二层",
        reason="★★",
        risk="低",
        note="442 则实占记录，每则带日干支／月将／时辰与盘，可作排盘器回归语料。",
    ),
    "壬归": dict(
        file="宋-壬归-打印整理版.doc",
        handler=h_rengui,
        dating="题宋郭子晟，无宋元著录，实际待考",
        evidence="参照·存疑待考",
        reason="★★★",
        risk="未查",
        note="不作断代证据。卷一「提纲例约」作结构性提问器使用。",
    ),
}

# ---------------------------------------------------------------- 写入 vault

FM_ORDER = [
    "类型",
    "书",
    "版本",
    "卷篇",
    "部",
    "与六壬关系",
    "断代",
    "证据等级",
    "理据价值",
    "抄大全风险",
    "繁简",
    "待核",
    "源文件",
]


def safe_name(s: str) -> str:
    """Obsidian 文件名安全化：去掉 / \\ : * ? " < > | # ^ [ ]"""
    s = re.sub(r'[/\\:*?"<>|#^\[\]]', "·", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return s[:110]


def write_entry(book_dir: Path, book: str, meta: dict, version: str,
                title: str, text: str, src_file: str, force: bool,
                extra: dict | None = None) -> str:
    stem = safe_name(f"{book}-{title}")
    p = book_dir / f"{stem}.md"
    if p.exists() and not force:
        return "skip"

    fm = {
        "类型": "底本条目",
        "书": book,
        "版本": version,
        "卷篇": title,
        "断代": meta["dating"],
        "证据等级": meta["evidence"],
        "理据价值": meta["reason"],
        "抄大全风险": meta["risk"],
        "繁简": CONV_NOTE,
        "待核": "true",
        "源文件": src_file,
    }
    fm.update(extra or {})
    head = ["---"]
    head += [f"{k}: {fm[k]}" for k in FM_ORDER if k in fm]
    tags = ["底本", "唐宋层", book]
    if fm.get("部") and fm["部"] != book:
        tags.append(f"{book}/{fm['部']}")
    head += [f"tags: [{', '.join(tags)}]", "---", ""]
    head += [f"# {book} {title}", ""]
    head += ["> ⚠️ 机器切分的录文，**未核原刻**。引用具体字句前须回原书影。", ""]
    p.write_text("\n".join(head) + text + "\n", encoding="utf-8")
    return "write"


def write_index(book_dir: Path, book: str, rows: list, version: str, meta: dict):
    lines = [
        "---",
        "tags: [索引/书目录]",
        f"书: {book}",
        "---",
        "",
        f"# {book} · 条目目录",
        "",
        f"- 版本：{version}",
        f"- 断代：{meta['dating']}",
        f"- 证据等级：{meta['evidence']}",
        f"- 条目：{len(rows)} 条，正文合计 {sum(r[1] for r in rows)} 字",
        "",
        f"> {meta['note']}",
        "",
    ]
    for title, n in rows:
        lines.append(f"- [[{safe_name(book + '-' + title)}]]（{n} 字）")
    (book_dir / f"00-{book}目录.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def write_report(book_dir: Path, book: str, rows: list, src_file: str,
                 skipped: int, version: str):
    total = sum(r[1] for r in rows)
    avg = total // max(1, len(rows))
    lines = [
        "---",
        "tags: [索引/导入报告]",
        f"书: {book}",
        "---",
        "",
        f"# 导入报告 · {book}",
        "",
        f"- 源文件：`{src_file}`",
        f"- 版本：{version}",
        f"- 条目 {len(rows)} 条（跳过 {skipped}），正文合计 {total} 字，平均 {avg} 字",
        f"- 繁简：{CONV_NOTE}",
        "",
        "## 条目字数",
        "",
        "字数明显偏离均值的条目优先回原书核对——抓取漏页通常就长这样。",
        "",
        "| 卷篇 | 字数 | 偏离均值 |",
        "| :--- | ---: | ---: |",
    ]
    for title, n in rows:
        d = n - avg
        mark = f"{d:+d}"
        if avg and abs(d) > avg * 1.5:
            mark = f"**{d:+d}** ⚠️"
        lines.append(f"| [[{safe_name(book + '-' + title)}]] | {n} | {mark} |")
    (book_dir / "_导入报告.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def update_bookcard(book_dir: Path, book: str, n: int):
    """把书卡的「导入状态」从「待导入」改成已导入 + 条目数"""
    for p in book_dir.glob("00-书卡-*.md"):
        txt = p.read_text(encoding="utf-8")
        new = re.sub(
            r"^导入状态:.*$",
            f"导入状态: 已导入（{n} 条）",
            txt,
            count=1,
            flags=re.M,
        )
        if new != txt:
            p.write_text(new, encoding="utf-8")
        return


# ---------------------------------------------------------------- 断案课例元数据

HEADER_RE = re.compile(
    r"([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])年"
    r".{0,12}?"
    r"([甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥])日"
    r"([子丑寅卯辰巳午未申酉戌亥])将"
    r"([子丑寅卯辰巳午未申酉戌亥])时"
)
GREG_RE = re.compile(r"占于\s*(\d{3,4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def harvest_cases(entries):
    """从断案条目里抽出可机器校验的课例元数据"""
    out = []
    for title, text, _extra in entries:
        m = HEADER_RE.search(text)
        if not m:
            continue
        g = GREG_RE.search(text)
        out.append(
            {
                "案": title,
                "年干支": m.group(1),
                "日干支": m.group(2),
                "月将": m.group(3),
                "占时": m.group(4),
                "公历": (
                    f"{int(g.group(1)):04d}-{int(g.group(2)):02d}-{int(g.group(3)):02d}"
                    if g
                    else None
                ),
            }
        )
    return out


# ---------------------------------------------------------------- 主流程


def build_one(name: str, dry: bool, force: bool):
    meta = BOOKS[name]
    src = SRC / meta["file"]
    if not src.exists():
        print(f"✗ {name}：源文件缺失 sources/{meta['file']}")
        return None

    try:
        entries, version = meta["handler"](src)
    except Exception as e:
        print(f"✗ {name}：抽取失败 —— {type(e).__name__}: {e}")
        return None

    if not entries:
        print(f"✗ {name}：切出 0 条，检查 handler 的卷篇标记")
        return None

    rows = [(t, len(x)) for t, x, _e in entries]
    total = sum(r[1] for r in rows)
    print(f"✓ {name}：{len(entries)} 条，{total} 字，版本「{version}」")
    for t, n in rows[:4]:
        print(f"      · {t}  ({n} 字)")
    if len(rows) > 4:
        print(f"      … 其余 {len(rows) - 4} 条")

    if dry:
        return dict(book=name, n=len(entries), chars=total)

    book_dir = TANGSONG / name
    book_dir.mkdir(parents=True, exist_ok=True)

    written = skipped = 0
    for title, text, extra in entries:
        r = write_entry(
            book_dir, name, meta, version, title, text, meta["file"], force,
            extra=extra,
        )
        written += r == "write"
        skipped += r == "skip"

    write_index(book_dir, name, rows, version, meta)
    write_report(book_dir, name, rows, meta["file"], skipped, version)
    update_bookcard(book_dir, name, len(entries))

    if name == "六壬断案":
        cases = harvest_cases(entries)
        (ROOT / "liuren-paipan" / "tests" / "duanan_cases.json").write_text(
            json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"      → 抽出可机器校验课例 {len(cases)} 则 "
              f"（liuren-paipan/tests/duanan_cases.json）")

    if skipped:
        print(f"      （跳过已存在 {skipped} 条，加 --force 可覆盖）")

    return dict(book=name, n=len(entries), chars=total)


def main():
    ap = argparse.ArgumentParser(description="唐宋层一键构建器")
    ap.add_argument("--book", help="只构建指定书目")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="覆盖已存在条目")
    ap.add_argument("--skip-pollution", action="store_true")
    args = ap.parse_args()

    if not SRC.is_dir():
        sys.exit(f"找不到 sources/ 目录：{SRC}")
    if not TANGSONG.is_dir():
        sys.exit(f"找不到 vault 唐宋层目录：{TANGSONG}")

    if _CC is None:
        print("⚠️  未装 opencc，繁体书目将保持原字形（跨书搜索会漏）")
        print("    修复：pip install opencc-python-reimplemented\n")

    names = [args.book] if args.book else list(BOOKS)
    for n in names:
        if n not in BOOKS:
            sys.exit(f"未登记的书目「{n}」。已登记：{'、'.join(BOOKS)}")

    print("=" * 60)
    stats = [s for n in names if (s := build_one(n, args.dry_run, args.force))]
    print("=" * 60)

    if args.dry_run:
        print("（--dry-run 未写入任何文件）")
        return

    print(f"共 {len(stats)} 部书，"
          f"{sum(s['n'] for s in stats)} 条，"
          f"{sum(s['chars'] for s in stats)} 字")

    if not args.skip_pollution:
        print("\n--- 清校污染标记 ---")
        subprocess.run(
            [sys.executable, str(ROOT / "tools" / "mark_pollution.py"),
             "--all", "--vault", str(VAULT)],
            cwd=str(ROOT),
        )


if __name__ == "__main__":
    main()
