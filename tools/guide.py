#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导读卡生成器 —— 把「读《六壬大全》当前条目」从一句口头义务变成有结构的一步。

为什么需要它（见 00-索引/导读流程-方案.md，提案 P-008）：
    原流程第 2 步只写了「先读原文、注文和课图，再解释概念」，没有任何可检查动作。
    于是每节读多少、先读哪块、跳过什么，全靠临场决定 —— 节与节不一致，也无法复盘。
    真正被漏掉的是四拍第一拍装不下的那部分：原文定位、文本身份（原刻／今注／今人补入）、
    切块读法、与上一节的推进关系、跳过说明。

    导读七件套里，第 2、4、6、7 件全部可由本程序从 frontmatter、正文结构、路线图和
    训练状态算出来；只有第 3 件（切块与读法）与第 5 件（待答问题）需要 agent 判断。
    程序负责硬结构，agent 负责判断 —— 与 signal_log.py / retro.py 同一分工。

用法：
    python3 tools/guide.py --entry 涉害法                 # 生成／刷新导读卡骨架
    python3 tools/guide.py --entry 涉害法 --check         # 只看状态，不写盘
    python3 tools/guide.py --entry 涉害法 --receipt pass --minutes 6
    python3 tools/guide.py --list                         # 已有导读卡一览
    python3 tools/guide.py --list --stale                 # 只列过期（底本比导读卡新）
    python3 tools/guide.py --index                        # 刷新 00-索引/导读进度.md
    python3 tools/guide.py --grades                       # 列档位与上限

边界：
    本程序**不写导读内容**，只生成骨架与可计算的五件。第 3、5 件留 `TODO(agent)` 占位，
    由 agent 在课堂上填。骨架不得冒充导读；`--check` 会把仍有占位的卡报为「未完成」。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

VAULT = ROOT / "六壬vault"
BOOK_DIR = VAULT / "10-底本" / "六壬大全"
TANGSONG_DIR = VAULT / "10-底本" / "唐宋层"
GUIDE_DIR = VAULT / "15-导读"
STATE = VAULT / "60-掌握度" / "_guide_state.json"
INDEX_MD = VAULT / "00-索引" / "导读进度.md"
ROADMAP = VAULT / "00-索引" / "阅读路线图.md"

TODO = "TODO(agent)"

# 档位按正文净字数判定，不按类型 —— 实测 257 条：毕法有 14 条不足 200 字，
# 课体有 67 条落在 B 档，按类型判档会给短条目派长导读。
GRADES = (
    ("A", 0, 199, 5, 400),
    ("B", 200, 3000, 10, 700),
    ("C", 3001, 10 ** 9, 15, 1000),
)


def grade_of(chars: int):
    """返回 (档, 分钟上限, 字数上限)。"""
    for g, lo, hi, mins, words in GRADES:
        if lo <= chars <= hi:
            return g, mins, words
    return "C", 15, 1000


def grade_limit(g: str):
    for name, _lo, _hi, mins, words in GRADES:
        if name == g:
            return mins, words
    return 15, 1000


# 逐条匹配不到零基础课序时的阶段兜底（与 阅读路线图 的阶段章节一致）
STAGE_COURSE = {
    "0": "查阅类（不通读，遇到再查）",
    "1": "第 1A–4 课（寄宫、旬空、旬遁、天地盘、四课、贼克比用）",
    "2": "第 6 课（十二天将与贵人）",
    "3": "第 4–5 课（三传主干与九宗门其余规则）",
    "4": "第 8 课（课体期）",
    "5": "第 8 课（赋文期）",
    "6": "第 8 课（毕法期）",
    "7": "第 8 课（专题与考据）",
}

# 前置概念 → 训练关卡，用于判断该前置是否已通关
PRE_TO_LEVEL = {
    "寄宫": 1, "旬空": 1, "旬遁": 1, "遁干": 1,
    "式盘最小模型": 0,
    "天地盘": 2, "月将加时": 2,
    "四课": 3,
    "九宗门": 4, "课体": 4,
    "三传": 5, "三传主干": 5,
    "十二天将": 6, "天将": 6, "贵人": 6,
    "涉害": 7,
    "月将与地方时": 9, "真实时空": 9,
}


# ------------------------------------------------------------------ 底本解析

def split_fm(raw: str):
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end < 0:
        return {}, raw
    fm = {}
    for ln in raw[3:end].splitlines():
        m = re.match(r"^([^\s:#][^:]*):\s*(.*)$", ln)
        if m:
            fm[m.group(1).strip()] = m.group(2).strip()
    return fm, raw[end + 4:]


def net_body(body: str):
    """原刻正文净文本：剔除盘与今注剥离区。"""
    if "## 原刻正文" in body:
        body = body.split("## 原刻正文", 1)[1]
    for cut in ("## 盘", "## 今注剥离区"):
        body = body.split(cut)[0]
    return body


def parse_entry(path: Path):
    raw = path.read_text("utf-8")
    fm, body = split_fm(raw)
    core = net_body(body)
    return dict(
        path=path,
        rel=path.relative_to(VAULT).as_posix()[:-3],
        name=path.stem,
        fm=fm,
        chars=len(re.sub(r"\s", "", core)),
        lines=[ln.strip() for ln in core.splitlines() if ln.strip()],
        has_pan="## 盘" in raw,
        has_jinzhu="## 今注剥离区" in raw,
        mtime=datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
    )


def resolve_entry(q: str):
    """支持「005-涉害法」「涉害法」「01-第一册 起例/005-涉害法」等写法。"""
    q = q.strip().replace(".md", "")
    cands = sorted(BOOK_DIR.rglob("*.md"))
    exact = [p for p in cands if p.stem == q or p.relative_to(BOOK_DIR).as_posix()[:-3] == q]
    if exact:
        return exact[0]
    part = [p for p in cands if q in p.stem]
    if len(part) == 1:
        return part[0]
    if not part:
        raise SystemExit(f"找不到底本条目：{q}\n（在 {BOOK_DIR.relative_to(ROOT)} 下按文件名匹配）")
    raise SystemExit("匹配到多条，请写得更具体：\n  "
                     + "\n  ".join(p.relative_to(BOOK_DIR).as_posix() for p in part[:10]))


# ------------------------------------------------------------------ 五件可计算内容

def roadmap_rows():
    """解析 阅读路线图 的「零基础执行序」表：[(课序, 内容纯文本)]。"""
    if not ROADMAP.exists():
        return []
    rows = []
    for ln in ROADMAP.read_text("utf-8").splitlines():
        m = re.match(r"^\|\s*([0-9][0-9A-C]*)\s*\|\s*(.+?)\s*\|", ln)
        if not m:
            continue
        txt = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", m.group(2))
        txt = re.sub(r"\[\[([^\]]*)\]\]", r"\1", txt).strip()
        rows.append((m.group(1), txt))
    return rows


def course_position(e):
    """本条在零基础课序里的位置，以及上一课是什么。"""
    rows = roadmap_rows()
    key = (e["fm"].get("节") or e["fm"].get("篇") or e["name"]).strip()
    core = re.sub(r"^\d+-", "", key)
    core = re.sub(r"[法课卦]$", "", core) or key
    idx = None
    for i, (_no, txt) in enumerate(rows):
        if key and (key in txt or txt in key):
            idx = i
            break
        if len(core) >= 2 and core in txt:
            idx = i
            break
    if idx is None:
        # 逐条匹配不到时按阶段兜底：路线图的阶段章节与零基础课序是同一套依赖关系
        stage = str(e["fm"].get("阶段", "?")).strip()
        span = STAGE_COURSE.get(stage)
        if span:
            return (f"按阶段 {stage} 归入{span}（该条未单列于零基础课序表）",
                    f"程序无法定位（该条未单列于课序表）→ 由 agent 在导读里点明："
                    f"本阶段紧接的上一节内容是什么")
        return f"未列入零基础课序（frontmatter 阶段 {stage}）", "——"
    cur = f"第 {rows[idx][0]} 课「{rows[idx][1]}」"
    prev = f"第 {rows[idx - 1][0]} 课「{rows[idx - 1][1]}」" if idx else "无（本条即第一课）"
    return cur, prev


def reflow(lines):
    """把被原刻行宽切断的句子接回去。

    底本按原刻换行，一句话常被拆在两行（「…必顺其正，无」／「乱动反常之理。」）。
    规则：上一行没有以句末标点收尾，就把本行接上去；但「第六册」「【元首课】」这类
    短且不带标点的标题行单独成行，不参与拼接。
    """
    def is_title(s):
        return len(s) <= 12 and not re.search(r"[。；，！？、]", s)

    out = []
    for ln in lines:
        if is_title(ln) or not out or is_title(out[-1]) \
                or re.search(r"[。；！？」』）]$", out[-1]):
            out.append(ln)
        else:
            out[-1] += ln
    return out


def split_blocks(lines, grade="B"):
    """切块候选。程序只给候选，性质与取舍由 agent 判断。

    粒度随档位变：
    - A 档（口诀、短名目）：连逗号一起断，一句口诀切成上下半句，便于逐条对规则。
    - B / C 档（散文、课体、赋文）：先把原刻断行接回成完整句，再按句末标点断，
      并把不足 8 字的碎片并回上一句，免得残句独占一行把导读表撑成噪音。
    """
    seps = r"[。；，！？]" if grade == "A" else r"[。；！？]"
    keep = 10 if grade == "A" else 14
    if grade != "A":
        lines = reflow(lines)
    out = []
    for ln in lines:
        if len(ln) <= keep:
            out.append(ln)
            continue
        parts = [p.strip() for p in re.split(rf"(?<={seps})", ln) if p.strip()]
        if len(parts) <= 1:
            out.append(ln)
            continue
        if grade == "A":
            out += parts
            continue
        # 只在同一原文行内合并碎片，不跨行，免得把标题和正文粘成一块
        merged = []
        for p in parts:
            if merged and len(p) < 8 and len(merged[-1]) < 60:
                merged[-1] += p
            else:
                merged.append(p)
        out += merged
    return out


def preteach_terms(e):
    """生词护栏：把本条前置分成「已通关」「未通关」「程序无记录」三类。"""
    raw = e["fm"].get("前置", "")
    terms = [t.strip() for t in raw.strip("[]").split(",") if t.strip()]
    if not terms:
        return [], [], []
    done, todo, unknown = [], [], []
    try:
        import tutor
        ts = tutor.load_state()
        l1 = tutor.lv_state(ts, 1)
        for t in terms:
            lid = None
            for kw, i in PRE_TO_LEVEL.items():
                if kw in t or t in kw:
                    lid = i
                    break
            if lid == 1:
                hit = [k for k in tutor.LEVEL1_TOPICS if k in t or t in k]
                if hit:
                    (done if tutor.topic_passed(l1, hit[0]) else todo).append(t)
                else:
                    unknown.append(t)
            elif lid:
                s = tutor.lv_state(ts, lid)
                (done if tutor.final_passed(s, lid) else todo).append(t)
            else:
                unknown.append(t)
    except Exception:                                            # noqa: BLE001
        unknown = list(terms)
    return todo, done, unknown


_FM_CACHE = None


def all_entries():
    """全部底本条目的轻量索引（六壬大全 + 唐宋层），用于查同名规则。"""
    global _FM_CACHE
    if _FM_CACHE is not None:
        return _FM_CACHE
    out = []
    for root in (BOOK_DIR, TANGSONG_DIR):
        if not root.is_dir():
            continue
        for p in root.rglob("*.md"):
            if p.name.startswith("_"):
                continue
            fm, _ = split_fm(p.read_text("utf-8"))
            out.append(dict(name=p.stem, book=fm.get("书", root.name),
                            ce=fm.get("册", ""), jie=fm.get("节", ""),
                            page=fm.get("页", ""), type=fm.get("类型", ""),
                            pollute=fm.get("污染", ""), rel=p.relative_to(VAULT).as_posix()[:-3]))
    _FM_CACHE = out
    return out


def conflict_hints(e, limit=6):
    """同名规则在别处的出现位置 —— 只给线索，定性交 agent。"""
    key = (e["fm"].get("节") or e["name"]).strip()
    core = re.sub(r"^\d+-", "", key)
    core = re.sub(r"[法课卦]$", "", core)
    if len(core) < 2:
        return []
    hits = []
    for x in all_entries():
        if x["name"] == e["name"]:
            continue
        hay = f"{x['name']}{x['jie']}"
        if core in hay:
            tag = "《" + (x["book"] or "?") + "》"
            extra = f"｜{x['ce']}" if x["ce"] else ""
            page = f"｜p{x['page']}" if x["page"] else ""
            warn = "　⚠标记污染" if str(x["pollute"]).lower() == "true" else ""
            hits.append(f"{tag}{extra} {x['name']}{page}｜{x['type']}{warn}")
    return sorted(hits)[:limit]


# ------------------------------------------------------------------ 状态

def load_state():
    d = json.loads(STATE.read_text("utf-8")) if STATE.exists() else {}
    d.setdefault("cards", {})
    return d


def save_state(d):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")


def card_path(e):
    rel = e["path"].relative_to(BOOK_DIR).as_posix()[:-3]
    return GUIDE_DIR / (rel + "-导读.md")


def receipts_all(d):
    out = []
    for entry, c in d["cards"].items():
        for r in c.get("receipts", []):
            out.append(dict(r, entry=entry, grade=c.get("grade", "?")))
    return sorted(out, key=lambda x: x.get("at", ""))


# ------------------------------------------------------------------ 生成

def render(e):
    g, mins, words = grade_of(e["chars"])
    cur, prev = course_position(e)
    todo_terms, done_terms, unknown_terms = preteach_terms(e)
    hints = conflict_hints(e)
    blocks = split_blocks(e["lines"], g)
    fm = e["fm"]
    body_kind = []
    body_kind.append("有今注剥离区（备查，不作证据）" if e["has_jinzhu"] else "无今注剥离区")
    body_kind.append(f"有盘 {fm.get('盘数', '?')} 幅（原样未解析）" if e["has_pan"] else "无盘")
    if "今人补入" in fm.get("类型", ""):
        body_kind.append("**今人补入，不作答案**")

    L = [
        "---",
        "类型: 导读卡",
        f"底本: {e['rel']}",
        f"节: {fm.get('节') or fm.get('篇') or e['name']}",
        f"档: {g}",
        f"净字数: {e['chars']}",
        f"版本: {fm.get('版本', '')}",
        f"生成: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"底本更新: {e['mtime']}",
        "回执: 未验",
        "tags: [导读, 导读/档" + g + "]",
        "---",
        "",
        f"# 导读｜{e['name']}",
        "",
        f"> 由 `tools/guide.py` 生成骨架；第 3、5 件由 agent 在课堂填写。",
        f"> 导读只做定位、切分和读法交代，**不讲原理、不给结论**——原理归第一拍「解释」。",
        "",
        f"底本：[[{e['rel']}|{e['name']}]]",
        "",
        "## 1 坐标",
        "",
        f"- 位置：{fm.get('册', '?')}｜{fm.get('篇', '?')}｜{fm.get('节') or '—'}"
        f"　原书页 {fm.get('页', '?')}　类型 {fm.get('类型', '?')}",
        f"- 阶段：{fm.get('阶段', '?')} {fm.get('阶段名', '')}",
        f"- 零基础课序：{cur}",
        f"- 上一课：{prev}",
        f"- 本条接的接口：{TODO} 一句话说明它接在上一课的哪个产出上，不展开原理。",
        "",
        "## 2 文本体检",
        "",
        f"- 正文净字数 {e['chars']}，判为 **{g} 档**（导读上限 {mins} 分钟 / {words} 字）。",
        f"- 文本身份：{'；'.join(body_kind)}。",
        f"- 正文行数：{len(e['lines'])} 行。",
        f"- 字词风险：{TODO} 列异体字、疑难字、易误读为形容词的术语；无则写「无」。",
        "",
        "## 3 切块与读法",
        "",
        f"{TODO}　把正文切块，逐块标性质（规则／例外／修辞凑韵／断语／象辞／课例），",
        "并标明本节精读、略读、暂时跳过；跳过必须写原因与回收时点。",
        "",
        "| 块 | 原文 | 性质 | 本节 |",
        "| :---: | :--- | :--- | :--- |",
    ]
    cap = 12 if g == "A" else 16
    for i, ln in enumerate(blocks[:cap], 1):
        show = ln if len(ln) <= 28 else ln[:27] + "…"
        L.append(f"| {i} | {show.replace('|', '｜')} | {TODO} | {TODO} |")
    if len(blocks) > cap:
        tip = "请按段合并成分区表，先给分区，再挑本节要精读的分区" if g == "C" \
            else "请合并同类块，只保留本节真正要处理的块"
        L.append(f"| … | （其余 {len(blocks) - cap} 块未列，{g} 档{tip}） | | |")

    L += [
        "",
        "## 4 生词护栏",
        "",
    ]
    if todo_terms:
        L.append("本条前置中**尚未通关**的概念，本节只当名词记住，不展开：")
        L += [f"- {t}" for t in todo_terms]
    if unknown_terms:
        L.append("程序无训练记录、需 agent 当场确认是否已教过：")
        L += [f"- {t}" for t in unknown_terms]
    if done_terms:
        L.append("已通关前置（可正常使用，不必再当生词）：" + "、".join(done_terms) + "。")
    if not (todo_terms or unknown_terms or done_terms):
        L.append("- 本条未标注前置，无需护栏。")

    L += [
        "",
        "## 5 待答问题",
        "",
        f"{TODO}　写 2–3 个读完应能回答的问题，**只摆问题不给答案**。",
        "",
        "1. ",
        "2. ",
        "3. ",
        "",
        "## 6 冲突预警",
        "",
    ]
    if hints:
        L.append("同名／同题材条目（本节只挂号，佐证留到第二拍）：")
        L += [f"- {h}" for h in hints]
    else:
        L.append("- 全库未见同名条目，暂无冲突线索。")

    L += [
        "",
        "## 7 阅读预算",
        "",
        f"- 导读 ≤ {mins} 分钟 / {words} 字；超出即视为讲课，回执带 `--minutes` 时"
        "程序会自动打 `导读超时`。",
        f"- 原文精读预计 {max(3, min(20, e['chars'] // 60 + 3))} 分钟。",
        "",
        "## 回执",
        "",
        "导读讲完、进四拍之前问两句（答案都在上面，属复述型）：",
        "",
        "1. 这一条要解决什么问题？",
        "2. 本节先读哪块、先不读哪块？",
        "",
        "软门槛：答不出**不阻断本节**，只补做第 1 件坐标与第 3 件切块，随后照常进四拍。",
        "两种结果都要落一条回执，`fail` 与超时都由程序自动打点，不必手写 signal_log：",
        "",
        "```bash",
        f"python3 tools/guide.py --entry {e['name']} --receipt pass --minutes N",
        f"python3 tools/guide.py --entry {e['name']} --receipt fail --minutes N",
        "```",
        "",
        "## 关联",
        "",
        "- [[导读流程-方案]]",
        "- [[教学流程复盘]]",
        "- [[阅读路线图]]",
        "",
    ]
    return "\n".join(L), g, mins


def cmd_entry(args):
    e = parse_entry(resolve_entry(args.entry))
    cp = card_path(e)
    text, g, mins = render(e)
    d = load_state()
    rec = d["cards"].get(e["rel"], {})

    if args.check:
        print(f"\n条目：{e['name']}　净字数 {e['chars']}　档 {g}（≤{mins} 分钟）")
        if not cp.exists():
            print(f"导读卡：缺失 → python3 tools/guide.py --entry {e['name']}")
            return 1
        old = cp.read_text("utf-8")
        n_todo = old.count(TODO)
        stale = rec.get("source_mtime") and rec["source_mtime"] < e["mtime"]
        print(f"导读卡：{cp.relative_to(VAULT)}")
        print(f"　未填占位 {n_todo} 处" + ("（未完成）" if n_todo else "（已完成）"))
        print("　状态：" + ("⚠️ 过期，底本已更新，建议重生成" if stale else "与底本同步"))
        print(f"　回执：{rec.get('receipts', [])[-1]['result'] if rec.get('receipts') else '未验'}\n")
        return 0

    if cp.exists() and not args.force:
        print(f"导读卡已存在：{cp.relative_to(VAULT)}")
        print("　如需按最新底本重生成骨架（会覆盖已填内容）请加 --force；"
              "只想看状态请加 --check。")
        return 1

    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(text, "utf-8")
    d["cards"][e["rel"]] = dict(
        entry=e["rel"], name=e["name"], card=cp.relative_to(VAULT).as_posix(),
        grade=g, chars=e["chars"],
        generated=datetime.now().strftime("%Y-%m-%d %H:%M"),
        source_mtime=e["mtime"], receipts=rec.get("receipts", []))
    save_state(d)
    write_index(d)
    print(f"\n已生成导读卡：{cp.relative_to(VAULT)}")
    print(f"　档 {g}｜净字数 {e['chars']}｜导读上限 {mins} 分钟")
    print(f"　待 agent 填：第 3 件切块与读法、第 5 件待答问题（共 {text.count(TODO)} 处占位）")
    print("　填完再讲；骨架本身不是导读。\n")
    return 0


def log_signal(kind, topic, note):
    """把导读侧的摩擦直接写进 signal_log，免得靠 agent 自觉补打点。"""
    try:
        import signal_log as sl
    except Exception as ex:                                   # pragma: no cover
        print(f"（打点失败，需手动 signal_log add --type {kind}：{ex}）")
        return
    d = sl.load()
    d["signals"].append(dict(
        ts=datetime.now().strftime("%Y-%m-%d %H:%M"),
        date=datetime.now().strftime("%Y-%m-%d"),
        session=sl.sid_of(d), type=kind, topic=topic, note=note,
        resolved=False, resolution="", src="guide.py"))
    sl.save(d)
    print(f"→ 已自动打点 [{kind}] {topic}｜{note}")


def cmd_receipt(args):
    e = parse_entry(resolve_entry(args.entry))
    d = load_state()
    c = d["cards"].get(e["rel"])
    if not c:
        print("这一条还没有导读卡，先生成：python3 tools/guide.py --entry " + e["name"])
        return 2
    c.setdefault("receipts", []).append(dict(
        at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        result=args.receipt, minutes=args.minutes))
    save_state(d)
    cp = VAULT / c["card"]
    if cp.exists():
        cp.write_text(re.sub(r"^回执: .*$", f"回执: {args.receipt}",
                             cp.read_text("utf-8"), count=1, flags=re.M), "utf-8")
    write_index(d)
    g = c.get("grade", "B")
    mins, _w = grade_limit(g)
    print(f"{e['name']} 回执：{args.receipt}"
          + (f"　用时 {args.minutes} 分钟（{g} 档上限 {mins}）"
             if args.minutes else ""))
    if args.receipt == "fail":
        log_signal("导读不足", e["name"],
                   f"{g} 档回执未通过（第 1／3 件需补做）")
        print("→ 软门槛：只补第 1 件坐标与第 3 件切块，不阻断本节，继续四拍。")
    if args.minutes and args.minutes > mins:
        log_signal("导读超时", e["name"],
                   f"{g} 档导读用时 {args.minutes} 分钟，超上限 {mins}")
        print("→ 收尾 retro.py --close 会检查是否连续超时（R14）。")
    return 0


def cmd_list(args):
    d = load_state()
    rows = []
    for rel, c in sorted(d["cards"].items()):
        p = BOOK_DIR.parent.parent / (rel + ".md")
        src = VAULT / (rel + ".md")
        mt = (datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
              if src.exists() else "?")
        stale = c.get("source_mtime", "") < mt
        cp = VAULT / c["card"]
        n_todo = cp.read_text("utf-8").count(TODO) if cp.exists() else -1
        if args.stale and not stale:
            continue
        rows.append((c["name"], c.get("grade", "?"), c.get("chars", 0),
                     n_todo, "过期" if stale else "同步",
                     (c.get("receipts") or [{}])[-1].get("result", "未验")))
    print(f"\n导读卡{'（仅过期）' if args.stale else ''}　{len(rows)} 张")
    print("─" * 74)
    print(f"  {'条目':<14}{'档':<4}{'净字':>6}　{'占位':>4}　{'底本':<6}{'回执'}")
    for n, g, ch, td, st, rc in rows:
        print(f"  {n:<14}{g:<4}{ch:>6}　{(td if td >= 0 else '缺卡'):>4}　{st:<6}{rc}")
    if not rows:
        print("  （无）")
    print("─" * 74 + "\n")
    return 0


def write_index(d=None):
    d = d or load_state()
    total = len(list(BOOK_DIR.rglob("*.md"))) if BOOK_DIR.is_dir() else 0
    lines = [
        "---", "类型: 索引", "tags: [索引/导读]", "---", "",
        "# 导读进度", "",
        "> 由 `tools/guide.py` 自动维护，**不要手改**。",
        f"> 最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M')}", "",
        f"《六壬大全》主线共 {total} 条；导读卡按节生成，不批量预生成"
        "（理由见 [[导读流程-方案]] 第九·五节）。", "",
        f"已有导读卡 **{len(d['cards'])}** 张。", "",
        "| 条目 | 档 | 净字数 | 未填占位 | 底本同步 | 回执 | 生成 |",
        "| :--- | :---: | ---: | ---: | :--- | :--- | :--- |",
    ]
    for rel, c in sorted(d["cards"].items()):
        src = VAULT / (rel + ".md")
        mt = (datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
              if src.exists() else "?")
        stale = c.get("source_mtime", "") < mt
        cp = VAULT / c["card"]
        n_todo = cp.read_text("utf-8").count(TODO) if cp.exists() else "缺卡"
        rc = (c.get("receipts") or [{}])[-1].get("result", "未验")
        card_link = c["card"][:-3] if c["card"].endswith(".md") else c["card"]
        lines.append(f"| [[{card_link}\\|{c['name']}]] | {c.get('grade', '?')} | "
                     f"{c.get('chars', 0)} | {n_todo} | "
                     f"{'⚠️过期' if stale else '同步'} | {rc} | {c.get('generated', '')} |")
    if not d["cards"]:
        lines.append("| — | — | — | — | — | — | — |")
    lines += ["", "## 说明", "",
              "- **未填占位**：卡里剩余 `TODO(agent)` 数量；不为 0 说明第 3、5 件尚未填，"
              "骨架不能当导读用。",
              "- **底本同步**：底本条目比导读卡新时标过期，需 `--entry X --force` 重生成。",
              "- **回执**：`pass` / `fail` / `未验`；连续两节 `fail` 会由 "
              "`retro.py` 起草拆节提案。", "",
              "## 关联", "", "- [[导读流程-方案]]", "- [[教学流程复盘]]",
              "- [[阅读路线图]]", "- [[掌握度看板]]", ""]
    INDEX_MD.parent.mkdir(parents=True, exist_ok=True)
    INDEX_MD.write_text("\n".join(lines), "utf-8")
    return INDEX_MD


def cmd_grades(args):
    print("\n导读档位（按正文净字数判定，不按类型）")
    print("─" * 62)
    for g, lo, hi, mins, words in GRADES:
        rng = f"{lo}–{hi} 字" if hi < 10 ** 9 else f"> {lo - 1} 字"
        print(f"  {g} 档　{rng:<14} 导读 ≤ {mins} 分钟 / {words} 字"
              + ("　且必须给分区表" if g == "C" else ""))
    print("─" * 62)
    print("  七件套：1 坐标　2 文本体检　3 切块与读法　4 生词护栏"
          "　5 待答问题　6 冲突预警　7 阅读预算")
    print("  全档七件必给；A 档可把第 2、4、6、7 件压缩成一行。\n")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="导读卡生成器（只出骨架，不写导读内容）")
    ap.add_argument("--entry", help="底本条目，如 涉害法 / 005-涉害法")
    ap.add_argument("--check", action="store_true", help="只看状态，不写盘")
    ap.add_argument("--force", action="store_true", help="覆盖已存在的导读卡")
    ap.add_argument("--receipt", choices=("pass", "fail"), help="记录回执结果")
    ap.add_argument("--minutes", type=int, default=0, help="本次导读实际用时")
    ap.add_argument("--list", action="store_true", help="列已有导读卡")
    ap.add_argument("--stale", action="store_true", help="配合 --list：只列过期")
    ap.add_argument("--index", action="store_true", help="刷新导读进度索引")
    ap.add_argument("--grades", action="store_true", help="列档位与上限")
    args = ap.parse_args(argv)

    if args.grades:
        return cmd_grades(args)
    if args.index:
        p = write_index()
        print(f"已刷新 {p.relative_to(VAULT)}")
        return 0
    if args.list:
        return cmd_list(args)
    if args.receipt:
        if not args.entry:
            print("--receipt 需要同时给 --entry")
            return 2
        return cmd_receipt(args)
    if args.entry:
        return cmd_entry(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
