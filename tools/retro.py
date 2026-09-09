#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""教学复盘引擎 —— 把「每轮结束做一次审计」从文字义务变成一条必须敲的命令。

背景（为什么必须是程序，不能只写在 AGENTS.md 里）：
    AGENTS.md 早就写了「每轮结束主动做流程一致性审计」，但它一直没真正发生。
    原因有三个，都是结构性的，不是态度问题：
      1. 七项检查里有一半依赖 agent 对刚发生的对话的主观回忆，
         而会话一关，这段记忆就没了 —— 只有用户还记得，所以只能由用户来指出。
      2. 「结束回复前请自查」是纯文字义务，没有工具锚点。
         项目里真正被稳定执行的动作（排盘、出题、判分）都有一条必须敲的命令。
      3. 触发条件没有数字。「错题是否被少数原因重复堆积」——多少条算堆积？
         没写死，就永远可以判定「暂无异常」。

    本工具把这三点补上：阈值写死在 RULES 里，证据来自 _tutor_state.json 与
    signal_log.py 的打点，输出是**已成稿的待确认提案**，agent 只需念给用户听。

用法：
    python3 tools/retro.py --brief          # 【开场必跑】今天学什么、到期复现、待确认提案
    python3 tools/retro.py --close          # 【收尾必跑】跑全部规则，起草提案并写盘
    python3 tools/retro.py --check          # 只跑规则看结果，不写盘（dry-run）
    python3 tools/retro.py --proposals      # 列全部提案及状态
    python3 tools/retro.py --approve P-007 --note "同意，本周实施"
    python3 tools/retro.py --reject  P-007 --note "不需要，先跑满三轮再看"
    python3 tools/retro.py --defer   P-007 --note "等天地盘学完再议"
    python3 tools/retro.py --implemented P-007 --note "已落地：新增第0课"

权限边界（红线，见 AGENTS.md 第 2.8 节）：
    本工具**只会起草提案，永远不会自动改教学流程**。
    它也不会生成任何触碰以下内容的提案：证据分级、污染判定、四拍顺序、
    排盘器算法、「宋据优先」的立场。这五项不接受以「学得更快」为理由的优化。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import tutor  # noqa: E402  复用同一套常量与判定，避免配置漂移
from signal_log import load as load_signals  # noqa: E402

VAULT = ROOT / "六壬vault"
RETRO_JSON = VAULT / "60-掌握度" / "_retro_state.json"
RETRO_MD = VAULT / "00-索引" / "教学流程复盘.md"
CHANGE_MD = VAULT / "60-掌握度" / "教学策略变更记录.md"
MARK_B, MARK_E = "<!-- retro:begin -->", "<!-- retro:end -->"
PROPOSAL_HEAD = "## 待审批建议"

OPEN_STATES = ("草案·待确认", "已批准（待实施）", "暂缓")
TODAY = date.today()

# 阈值集中在这里。改阈值本身属于流程变更，须先经用户批准。
TH = dict(
    fail_rounds=2,        # R1 同一关连续未达标轮数
    same_reason=3,        # R2 同一错误原因的活跃错题条数
    teachback_lag=3,      # R3 程序达标但复述未验收的天数
    stuck_per_session=3,  # R4 单节「卡顿／前置缺失」条数
    reask_per_topic=3,    # R5 同一概念「重复追问」条数
    figure_per_topic=2,   # R5b 同一概念「图缺失」条数
    overdue_days=2,       # R7 复现逾期天数
    stale_days=7,         # R8 提案挂着未决的天数
    session_minutes=110,  # R10 单节时长上限
    guide_gap_per_session=2,   # R12 单节「导读不足」条数
    receipt_fail_streak=2,     # R13 连续回执未通过节数
    guide_over_streak=3,       # R14 同档导读连续超时节数
)

# 红线关键词：命中即不允许生成提案（防止「教学优化」侵蚀考据标准）
REDLINE = ("证据等级", "证据分级", "污染", "四拍", "宋据", "排盘器算法", "判分算法")


# ------------------------------------------------------------------ 状态

def load_retro():
    d = json.loads(RETRO_JSON.read_text("utf-8")) if RETRO_JSON.exists() else {}
    d.setdefault("proposals", [])
    d.setdefault("last_brief", None)
    d.setdefault("last_close", None)
    return d


def save_retro(d):
    RETRO_JSON.parent.mkdir(parents=True, exist_ok=True)
    RETRO_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")


def next_pid(d):
    """提案编号接着 教学流程复盘.md 里手写的 P-006 往后排，不重号。"""
    used = [0]
    if RETRO_MD.exists():
        used += [int(m) for m in re.findall(r"P-(\d{3})", RETRO_MD.read_text("utf-8"))]
    used += [int(p["id"].split("-")[1]) for p in d["proposals"]]
    return f"P-{max(used) + 1:03d}"


def days_since(s):
    try:
        return (TODAY - datetime.strptime(s[:10], "%Y-%m-%d").date()).days
    except (ValueError, TypeError):
        return 0


# ------------------------------------------------------------------ 规则

def _fresh_signals(sig):
    return [x for x in sig["signals"] if not x.get("resolved")]


def rule_R1(ts, sig):
    """同一关连续多轮未达标 → 教学粒度过大，应拆节而不是加题。"""
    out = []
    by_level = {}
    for s in ts.get("sessions", []):
        by_level.setdefault(s["level"], []).append(s)
    for lid, rows in by_level.items():
        tail = rows[-TH["fail_rounds"]:]
        if len(tail) < TH["fail_rounds"]:
            continue
        if all(r["n"] and r["right"] / r["n"] < tutor.PASS_RATE for r in tail):
            name = tutor.LV.get(lid, {}).get("name", f"关{lid}")
            out.append(dict(
                rule="R1", key=f"R1|{lid}",
                title=f"关卡{lid}「{name}」连续 {len(tail)} 轮未达标，建议拆节",
                evidence=[f"最近 {len(tail)} 轮成绩：" + "、".join(
                    f"{r['right']}/{r['n']}" for r in tail),
                    f"达标线为 {tutor.PASS_CORRECT}/{tutor.PASS_WINDOW}，均未触及。"],
                suggestion=f"把关卡{lid}按依赖关系拆成两节，先单独训练前半段，"
                           f"通过后再合并；不靠加题量硬冲达标线。",
                benefit="把「反复刷题」换成「补前置」，避免用正确率掩盖概念断点。",
                risk="拆节会增加节数，短期进度看起来变慢。",
                rollback=f"保留关卡{lid}原有成绩与判分逻辑，拆节只加练习入口；"
                         f"效果不好即恢复整关训练。"))
    return out


def rule_R2(ts, sig):
    """同一错误原因堆积 → 应按原因做变式，不再逐题堆队列。"""
    cnt = {}
    for w in ts.get("wrong", []):
        reasons = w.get("reasons", ["待归因"])
        # 教学前基线题已由 P-003 单独处理，不再计入「原因堆积」
        if "教学前基线" in reasons:
            continue
        for r in reasons:
            cnt.setdefault(r, []).append(w)
    out = []
    for reason, items in cnt.items():
        if len(items) >= TH["same_reason"]:
            out.append(dict(
                rule="R2", key=f"R2|{reason}",
                title=f"活跃错题中「{reason}」已积 {len(items)} 条，建议转按原因训练",
                evidence=[f"同一原因错题 {len(items)} 条：" + "；".join(
                    w["q"][:24] for w in items[:4])],
                suggestion=f"用 `tools/tutor.py --weak {reason}` 做 3–5 道变式，"
                           f"连续答对两道后停止即时加题；原题仍按 1/3/7/21 天复现。",
                benefit="队列不再被同类错题淹没，训练对准错误原因而非题目数量。",
                risk="变式题若与原题过近，可能只是换皮重做。",
                rollback="变式不计入正式专项成绩，停用后仍可回到逐题复现。"))
    return out


def rule_R3(ts, sig):
    """程序达标但白话复述长期未验收 → 程序题没覆盖理解。"""
    out = []
    l1 = tutor.lv_state(ts, 1)
    for topic in tutor.LEVEL1_TOPICS:
        s = tutor.topic_state(l1, topic)
        if tutor.score_ready(s) and not s.get("teachback"):
            block = [x for x in _fresh_signals(sig)
                     if x.get("topic") == topic and x["type"] in ("前置缺失", "卡顿")]
            # 没有 ready_at 字段可用，退而以「关卡 1 最后一次练习距今多久」作代理：
            # 刚练完当场没验收不算异常，挂了几天还没验收才算。
            last = max((r["date"] for r in ts.get("sessions", []) if r["level"] == 1),
                       default="")
            lag = days_since(last) if last else 0
            if block or lag >= TH["teachback_lag"]:
                out.append(dict(
                    rule="R3", key=f"R3|{topic}",
                    title=f"「{topic}」程序已达标但白话复述未通过，建议补前置后再验收",
                    evidence=[f"程序成绩 {sum(s['hist'][-tutor.PASS_WINDOW:])}/"
                              f"{tutor.PASS_WINDOW}，已达标；`teachback` 仍为未通过。"]
                             + [f"信号 #{x['type']}：{x['note']}" for x in block[:3]],
                    suggestion=f"先补齐「{topic}」被追问到的前置概念，再重做复述验收；"
                               f"不重复刷 {tutor.PASS_WINDOW} 题专项。",
                    benefit="把「会算」和「讲得清」分开处理，正确率不再冒充理解。",
                    risk="补前置会引入新节，可能提前接触后续术语。",
                    rollback="前置节严格限定范围；无效则退回原验收流程，成绩不动。"))
    return out


def rule_R4(ts, sig):
    """单节卡顿过多 → 本节前置依赖缺失。"""
    out = []
    per = {}
    for x in _fresh_signals(sig):
        if x["type"] in ("卡顿", "前置缺失"):
            per.setdefault(x.get("session", "?"), []).append(x)
    for sid, items in per.items():
        if len(items) >= TH["stuck_per_session"]:
            topics = sorted({x["topic"] for x in items if x["topic"]})
            out.append(dict(
                rule="R4", key=f"R4|{sid}",
                title=f"会话 {sid} 出现 {len(items)} 次卡顿／前置缺失，建议插入前置节",
                evidence=[f"涉及概念：{'、'.join(topics) or '未标注'}"]
                         + [f"{x['ts']} [{x['type']}] {x['note']}" for x in items[:4]],
                suggestion="在本节之前插入一节只讲依赖关系的短节，"
                           "把本节反复被追问的对象先建立起来，再回到原内容。",
                benefit="减少「靠追问倒序补术语」，教学与验收回到同一粒度。",
                risk="前置节讲太多会变成脱离《六壬大全》另起课程。",
                rollback="前置节限定为一张图加数句定义；无效则取消，恢复原顺序。"))
    return out


def rule_R5(ts, sig):
    """同一概念被反复追问／多次要图 → 该概念需要图或最小模型。"""
    out = []
    reask, figure = {}, {}
    for x in _fresh_signals(sig):
        if not x.get("topic"):
            continue
        if x["type"] == "重复追问":
            reask.setdefault(x["topic"], []).append(x)
        if x["type"] == "图缺失":
            figure.setdefault(x["topic"], []).append(x)
    for topic, items in reask.items():
        if len(items) >= TH["reask_per_topic"]:
            out.append(dict(
                rule="R5", key=f"R5|reask|{topic}",
                title=f"「{topic}」被重复追问 {len(items)} 次，建议改讲法",
                evidence=[f"{x['ts']} {x['note']}" for x in items[:4]],
                suggestion=f"改用「先给可操作步骤 + 一个排盘器实例」的顺序讲「{topic}」，"
                           f"必要时补空间关系图；不再用同一套说法重复解释。",
                benefit="把重复解释的成本一次性转成一张图或一个实例。",
                risk="配图可能被误当作原书证据。",
                rollback="重绘图统一标注「重绘示意，不作证据」；无效则回退为纯表格。"))
    for topic, items in figure.items():
        if len(items) >= TH["figure_per_topic"]:
            out.append(dict(
                rule="R5", key=f"R5|figure|{topic}",
                title=f"「{topic}」出现 {len(items)} 次纯文字讲不清，建议固定配图",
                evidence=[f"{x['ts']} {x['note']}" for x in items[:4]],
                suggestion=f"为「{topic}」在概念卡里固定一张图（优先原书影像并标页码）。",
                benefit="空间／流程关系用图一次说清，不靠反复描述。",
                risk="图多了会变装饰。",
                rollback="只保留一张；无效即删除，回到表格。"))
    return out


def rule_R6(ts, sig):
    """用户亲自指出的问题 —— 必须当轮成稿，不允许无声吞掉。"""
    items = [x for x in _fresh_signals(sig) if x["type"] == "纠错"]
    if not items:
        return []
    return [dict(
        rule="R6", key=f"R6|{x['ts']}",
        title=f"用户指出的问题需成稿：{(x['note'] or '未记录现象')[:36]}",
        evidence=[f"{x['ts']}｜概念 {x['topic'] or '未标注'}｜{x['note']}"],
        suggestion="把该问题转成具体的流程或讲法修改；若判断不需改流程，"
                   "也必须写明理由后请用户否决，不得直接静默处理。",
        benefit="用户指出的问题一律留痕成案，不再只停在对话里。",
        risk="可能把一次性笔误升级成流程改动。",
        rollback="用户否决即标「已否决」，保留记录避免重复提出。") for x in items]


def rule_R7(ts, sig):
    """错题复现逾期 → 节奏问题。"""
    limit = (TODAY - timedelta(days=TH["overdue_days"])).isoformat()
    late = [w for w in ts.get("wrong", []) if w.get("due", "9999") < limit]
    if not late:
        return []
    return [dict(
        rule="R7", key=f"R7|{late[0]['due']}",
        title=f"{len(late)} 条错题复现已逾期超过 {TH['overdue_days']} 天，建议调节奏",
        evidence=[f"最早到期 {min(w['due'] for w in late)}，今天 {TODAY.isoformat()}。"]
                 + [f"关{w['level']}｜{w['q'][:28]}（到期 {w['due']}）" for w in late[:4]],
        suggestion="下一节开场先跑 `tools/tutor.py --review` 清逾期原题，"
                   "再讲新内容；若长期清不完，把 1/3/7/21 改为更宽的节奏并记录。",
        benefit="间隔重复只有按期做才成立，逾期越久越接近重新学。",
        risk="先清旧题会推迟新进度。",
        rollback="节奏参数保留原值；调整无效即恢复 1/3/7/21。")]


def rule_R9(ts, sig):
    """配置一致性：默认题量必须与统计窗口对齐（P-002 当年就是这里出问题）。

    P-007 实施后 `--n` 的默认值写成了符号 `PASS_WINDOW`，两者从此不可能失配；
    但规则不能因此形同虚设——若以后有人改回写死的数字，这里照样要抓出来。
    """
    src = (ROOT / "tools" / "tutor.py").read_text("utf-8")
    m = re.search(r'"--n".{0,120}?default=(\w+)', src, re.S)
    if not m:
        return []
    raw = m.group(1)
    if not raw.isdigit():
        # 默认值写成符号：能取到值就按值比，取不到就不猜（宁可漏报也不误报）
        val = getattr(tutor, raw.split(".")[-1], None)
        if not isinstance(val, int) or val == tutor.PASS_WINDOW:
            return []
        default_n = val
    else:
        default_n = int(raw)
    if default_n == tutor.PASS_WINDOW:
        return []
    return [dict(
        rule="R9", key=f"R9|{default_n}|{tutor.PASS_WINDOW}",
        title=f"配置冲突：默认题量 {default_n} 与统计窗口 {tutor.PASS_WINDOW} 不一致",
        evidence=[f"`tutor.py --n` 默认 {default_n} 题；"
                  f"达标判定读最近 {tutor.PASS_WINDOW} 题、要求 "
                  f"{tutor.PASS_CORRECT} 题正确。",
                  "按默认题量跑一轮，天然不足以触发达标判定。"],
        suggestion=f"把默认题量改为 {tutor.PASS_WINDOW}，或把达标窗口改为 {default_n}，"
                   f"两者取一，不要并存。",
        benefit="一轮结束点与达标判定对齐，成绩可解释。",
        risk="改窗口会影响历史成绩的可比性。",
        rollback="旧 hist 数据不动，只改判定参数；无效即改回。")]


def rule_R10(ts, sig):
    """单节过长 → 轮次拆分。"""
    long = [s for s in sig.get("sessions", [])
            if (s.get("minutes") or 0) > TH["session_minutes"]]
    if not long:
        return []
    s = long[-1]
    return [dict(
        rule="R10", key=f"R10|{s['id']}",
        title=f"会话 {s['id']} 长 {s['minutes']} 分钟，超出单节 60–90 分钟约定",
        evidence=[f"{s['start']} → {s.get('end')}，共 {s['minutes']} 分钟；"
                  f"约定单节 60–90 分钟。"],
        suggestion="把「解释＋佐证」与「练习＋复述验收」拆成两节，中间留一次间隔。",
        benefit="避免末段疲劳时做复述验收，验收结论更可信。",
        risk="拆节后上下文需要重新交代。",
        rollback="开场 `retro.py --brief` 已能恢复上下文；无效即恢复整节。")]


def rule_R11(ts, sig):
    """复述已通过却又在复现中错 → 验收标准可能过松。"""
    out = []
    l1 = tutor.lv_state(ts, 1)
    for topic in tutor.LEVEL1_TOPICS:
        s = tutor.topic_state(l1, topic)
        if not s.get("teachback"):
            continue
        bad = [w for w in ts.get("wrong", [])
               if w["spec"][0] == topic and "教学前基线" not in w.get("reasons", [])
               and days_since(w.get("first", "")) <= 30]
        if bad:
            out.append(dict(
                rule="R11", key=f"R11|{topic}",
                title=f"「{topic}」复述已通过，却新增 {len(bad)} 条错题，建议复查验收标准",
                evidence=[f"关{w['level']}｜{w['q'][:30]}（{w.get('first')}）" for w in bad[:3]],
                suggestion="撤销该概念复述通过状态，回到错点四拍，再重做一次白话复述；"
                           "并在验收清单里补上这次漏掉的检查点。",
                benefit="复述验收不再只是「讲得顺」，而必须覆盖实际易错点。",
                risk="频繁撤销会让通过标准显得反复。",
                rollback="保留原通过记录与撤销理由，可追溯恢复。"))
    return out


def _guide_receipts():
    """按时间排序的导读回执，附档位；导读模块不可用时返回空。"""
    try:
        import guide
        return guide.receipts_all(guide.load_state()), guide
    except Exception:                                          # pragma: no cover
        return [], None


def rule_R12(ts, sig):
    """单节多次「导读不足」→ 该档导读模板不够用，要改模板而不是多讲一遍。

    病因和 R4／R5 不同：R4／R5 是讲解阶段的依赖与讲法问题，这里坏在导读本身的
    定位、切分、文本身份交代，所以单独开药方。
    """
    out = []
    per = {}
    for x in _fresh_signals(sig):
        if x["type"] == "导读不足":
            per.setdefault(x.get("session", "?"), []).append(x)
    _r, gmod = _guide_receipts()
    cards = {}
    if gmod:
        cards = {c.get("name", ""): c.get("grade", "?")
                 for c in gmod.load_state()["cards"].values()}
    for sid, items in per.items():
        if len(items) < TH["guide_gap_per_session"]:
            continue
        topics = sorted({x["topic"] for x in items if x["topic"]})
        grades = sorted({cards.get(t, "?") for t in topics}) or ["?"]
        out.append(dict(
            rule="R12", key=f"R12|{sid}",
            title=f"会话 {sid} 出现 {len(items)} 次导读不足，建议修订 "
                  f"{'／'.join(grades)} 档导读模板",
            evidence=[f"涉及条目：{'、'.join(topics) or '未标注'}"]
                     + [f"{x['ts']} {x['note']}" for x in items[:4]],
            suggestion="改 `tools/guide.py` 里该档模板的措辞与件序：把本节答不出的那一件"
                       "（多为第 1 件坐标或第 3 件切块）提到最前，并在模板里写死它必须"
                       "回答的问题；不要靠临场多讲一遍补救。",
            benefit="同一档次的后续条目一次性受益，导读缺口不再逐节复发。",
            risk="模板越改越长，可能把导读挤成第二次讲解。",
            rollback="模板改动只加不超过两行；无效即回滚到上一版模板文本。"))
    return out


def rule_R13(ts, sig):
    """连续两节回执未通过 → 节的粒度或档位判错，应降档或拆节。"""
    rs, gmod = _guide_receipts()
    if len(rs) < TH["receipt_fail_streak"]:
        return []
    tail = rs[-TH["receipt_fail_streak"]:]
    if any(r.get("result") != "fail" for r in tail):
        return []
    names = "、".join(dict.fromkeys(r["entry"].split("/")[-1] for r in tail))
    return [dict(
        rule="R13", key="R13|" + tail[-1].get("at", ""),
        title=f"连续 {len(tail)} 节导读回执未通过（{names}），建议降档或拆节",
        evidence=[f"{r.get('at')}｜{r['entry'].split('/')[-1]}｜{r.get('grade')} 档｜"
                  f"用时 {r.get('minutes') or '未记'} 分钟" for r in tail],
        suggestion="把这两条按「一节只处理一组规则」重新拆节，或把档位下调一级"
                   "（净字数临界时按低档处理），拆完再各自重生成导读卡。",
        benefit="回执问题的根源多是节太大，拆节比反复加导读更省时间。",
        risk="拆节会让总节数变多，进度看起来变慢。",
        rollback="拆节只在这两条上试行；无效即按原节合回，导读卡 --force 重生成。")]


def rule_R14(ts, sig):
    """某档导读连续超时 → 该档预算或件数不合实际。"""
    rs, gmod = _guide_receipts()
    if not gmod:
        return []
    per = {}
    for r in rs:
        if not r.get("minutes"):
            continue
        g = r.get("grade", "?")
        lim = gmod.grade_limit(g)[0] if g in ("A", "B", "C") else 10 ** 9
        per.setdefault(g, []).append((r, r["minutes"] > lim, lim))
    out = []
    need = TH["guide_over_streak"]
    for g, items in per.items():
        tail = items[-need:]
        if len(tail) < need or not all(flag for _r, flag, _l in tail):
            continue
        lim = tail[-1][2]
        out.append(dict(
            rule="R14", key=f"R14|{g}|{tail[-1][0].get('at', '')}",
            title=f"{g} 档导读连续 {need} 节超时（上限 {lim} 分钟），建议压件数或调预算",
            evidence=[f"{r.get('at')}｜{r['entry'].split('/')[-1]}｜"
                      f"用时 {r['minutes']} 分钟 > 上限 {l}" for r, _f, l in tail],
            suggestion=f"二选一：① 把 {g} 档的第 2、6、7 件压成一行（只留净字数、"
                       f"一条冲突线索、时间上限）；② 把 {g} 档上限上调到实际中位用时并"
                       f"同步改 `GRADES`。选定后写进方案，不要两头都放宽。",
            benefit="导读时间回到可预期区间，不再侵占四拍的时间。",
            risk="压件数可能漏掉冲突预警；放宽上限会让整节变长。",
            rollback="两项改动都只动一处参数或一档模板，无效即改回原值。"))
    return out


RULES = (rule_R1, rule_R2, rule_R3, rule_R4, rule_R5,
         rule_R6, rule_R7, rule_R9, rule_R10, rule_R11,
         rule_R12, rule_R13, rule_R14)


def run_rules(ts, sig):
    found = []
    for fn in RULES:
        try:
            found += fn(ts, sig) or []
        except Exception as e:                                  # noqa: BLE001
            found.append(dict(rule="ERR", key=f"ERR|{fn.__name__}",
                              title=f"规则 {fn.__name__} 执行失败：{e}",
                              evidence=[repr(e)], suggestion="修规则本身。",
                              benefit="—", risk="—", rollback="—"))
    return [f for f in found if not _hits_redline(f)]


def _hits_redline(f):
    text = f["title"] + f["suggestion"]
    return any(k in text for k in REDLINE)


# ------------------------------------------------------------------ 提案

def draft(d, found):
    """把命中规则写成待确认提案；已提过（含已否决）的不重复起草。"""
    seen = {p.get("key") for p in d["proposals"]}
    new = []
    for f in found:
        if f["key"] in seen:
            continue
        pid = next_pid(d)
        p = dict(id=pid, key=f["key"], rule=f["rule"], title=f["title"],
                 status="草案·待确认", created=TODAY.isoformat(),
                 evidence=f["evidence"], suggestion=f["suggestion"],
                 benefit=f["benefit"], risk=f["risk"], rollback=f["rollback"],
                 decided=None, decided_at=None, note="")
        d["proposals"].append(p)
        seen.add(f["key"])
        new.append(p)
    return new


def decide(d, pid, status, note):
    for p in d["proposals"]:
        if p["id"] == pid:
            p["status"] = status
            p["decided"] = status
            p["decided_at"] = TODAY.isoformat()
            p["note"] = note or ""
            return p
    return None


def open_proposals(d):
    return [p for p in d["proposals"] if p["status"] in OPEN_STATES]


def stale_proposals(d):
    return [p for p in open_proposals(d)
            if days_since(p["created"]) >= TH["stale_days"]]


# ------------------------------------------------------------------ 回写

def write_retro_md(d):
    """把机器起草的提案写进 教学流程复盘.md 的机器区，手写 P-001~P-006 不动。"""
    if not RETRO_MD.exists():
        return
    lines = [MARK_B, "",
             "### 机器起草区（`tools/retro.py` 自动维护，不要手改）", "",
             f"最后复盘：{datetime.now():%Y-%m-%d %H:%M}　"
             f"待确认 {sum(1 for p in d['proposals'] if p['status'] == '草案·待确认')} 条", ""]
    if not d["proposals"]:
        lines += ["暂无机器起草的提案。", ""]
    for p in d["proposals"]:
        lines += [f"#### {p['id']}｜{p['title']}", "",
                  f"- **状态**：{p['status']}"
                  + (f"（{p['decided_at']}）" if p.get("decided_at") else ""),
                  f"- **触发规则**：{p['rule']}　**起草日期**：{p['created']}",
                  "- **现状证据**："]
        lines += [f"  - {e}" for e in p["evidence"]]
        lines += [f"- **修改建议**：{p['suggestion']}",
                  f"- **预期收益**：{p['benefit']}",
                  f"- **潜在风险**：{p['risk']}",
                  f"- **回退办法**：{p['rollback']}"]
        if p.get("note"):
            lines.append(f"- **用户意见**：{p['note']}")
        lines.append("")
    lines += [MARK_E, ""]
    block = "\n".join(lines)

    old = RETRO_MD.read_text("utf-8")
    if MARK_B in old and MARK_E in old:
        pre, rest = old.split(MARK_B, 1)
        new = pre + block + rest.split(MARK_E, 1)[1].lstrip("\n")
    elif PROPOSAL_HEAD in old:
        pre, rest = old.split(PROPOSAL_HEAD, 1)
        new = pre + PROPOSAL_HEAD + "\n\n" + block + rest.lstrip("\n")
    else:
        new = old.rstrip() + "\n\n" + PROPOSAL_HEAD + "\n\n" + block
    RETRO_MD.write_text(new, "utf-8")


def write_change_md(d):
    lines = ["---", "类型: 变更记录", "tags: [掌握度/流程, 流程/变更]", "---", "",
             "# 教学策略变更记录", "",
             "> 由 `tools/retro.py` 维护。**任何教学方式的改变都必须先在这里留痕**，",
             "> 否则无法回答「为什么现在这么教」。提案原文见 [[教学流程复盘]]。",
             f"> 最后更新：{datetime.now():%Y-%m-%d %H:%M}", "",
             "## 已决提案", "",
             "| 提案 | 标题 | 规则 | 起草 | 结论 | 决定日 | 用户意见 |",
             "| :--- | :--- | :---: | :---: | :--- | :---: | :--- |"]
    decided = [p for p in d["proposals"] if p.get("decided")]
    for p in decided:
        lines.append(f"| {p['id']} | {p['title']} | {p['rule']} | {p['created']} | "
                     f"{p['status']} | {p['decided_at']} | {p.get('note') or '—'} |")
    if not decided:
        lines.append("| — | 暂无已决提案 | — | — | — | — | — |")
    lines += ["", "## 待确认", "",
              "| 提案 | 标题 | 起草 | 已挂(天) |", "| :--- | :--- | :---: | ---: |"]
    op = open_proposals(d)
    for p in op:
        lines.append(f"| {p['id']} | {p['title']} | {p['created']} | "
                     f"{days_since(p['created'])} |")
    if not op:
        lines.append("| — | 暂无待确认提案 | — | — |")
    lines += ["", "## 不可协商红线", "",
              "以下内容不接受以「学得更快、体验更好」为理由的优化提案，",
              "`retro.py` 也不会生成触碰它们的提案：", "",
              "1. 证据分级与污染判定规则；",
              "2. 解释 → 佐证 → 理解 → 质疑 的四拍顺序；",
              "3. 排盘器算法与程序判分口径；",
              "4. 「宋据优先、无宋据就写无宋据」的立场；",
              "5. 流程变更必须先经用户批准这条元规则本身。", "",
              "## 关联", "", "- [[教学流程复盘]]", "- [[教学互动日志]]",
              "- [[学习画像]]", ""]
    CHANGE_MD.parent.mkdir(parents=True, exist_ok=True)
    CHANGE_MD.write_text("\n".join(lines), "utf-8")


# ------------------------------------------------------------------ 输出

def show_brief(ts, sig, d):
    print("\n" + "═" * 70)
    print(f"  开场简报　{TODAY.isoformat()}")
    print("═" * 70)

    lid = tutor.pick_level(ts)
    print(f"\n▸ 建议内容：关卡 {lid}「{tutor.LV[lid]['name']}」")
    l1 = tutor.lv_state(ts, 1)
    if lid == 1:
        for t in tutor.LEVEL1_TOPICS:
            s = tutor.topic_state(l1, t)
            n = len(s["hist"])
            mark = "✅通过" if tutor.topic_passed(l1, t) else (
                "🗣待复述" if tutor.score_ready(s) else "🔸在练" if n else "⬜未开")
            print(f"    · {t}：{n} 题　{mark}")

    due = tutor.due_items(ts)
    limit = (TODAY - timedelta(days=TH["overdue_days"])).isoformat()
    late = [w for w in ts.get("wrong", []) if w.get("due", "9999") < limit]
    print(f"\n▸ 到期复现：{len(due)} 条"
          + (f"（其中逾期 {len(late)} 条）" if late else ""))
    for w in due[:5]:
        print(f"    · 关{w['level']}｜{w['q'][:40]}（到期 {w['due']}）")

    fresh = _fresh_signals(sig)
    print(f"\n▸ 上轮遗留信号：{len(fresh)} 条未处理")
    stat = {}
    for x in fresh:
        stat[x["type"]] = stat.get(x["type"], 0) + 1
    for k, v in stat.items():
        print(f"    · {k} × {v}")

    op = open_proposals(d)
    print(f"\n▸ 未结清提案：{len(op)} 条")
    for p in op:
        age = days_since(p["created"])
        flag = "  ⚠挂太久" if age >= TH["stale_days"] else ""
        print(f"    · {p['id']}［{p['status']}］{p['title']}"
              f"（{age} 天前起草）{flag}")
    if not op:
        print("    （无）")

    print("\n▸ 本节要记得：")
    print("    · 摩擦当场打点：python3 tools/signal_log.py add --type 卡顿 "
          "--topic X --note \"...\"")
    print("    · 收尾必跑：python3 tools/retro.py --close")
    print("═" * 70 + "\n")


def show_close(found, new, d, dry=False):
    print("\n" + "═" * 70)
    print(f"  收尾复盘{'（dry-run，未写盘）' if dry else ''}　{TODAY.isoformat()}")
    print("═" * 70)
    print(f"\n▸ 规则检查：{len(RULES)} 条规则，命中 {len(found)} 项")
    if not found:
        print("    · 全部通过，无需打扰用户。")
    for f in found:
        print(f"    · [{f['rule']}] {f['title']}")

    if dry:
        print("\n▸ dry-run 不起草提案；实际起草请跑 --close。")
    else:
        print(f"\n▸ 新起草提案：{len(new)} 条")
    for p in new:
        print(f"\n  ── {p['id']}｜{p['title']}")
        for e in p["evidence"][:3]:
            print(f"     证据：{e}")
        print(f"     建议：{p['suggestion']}")
        print(f"     收益：{p['benefit']}")
        print(f"     风险：{p['risk']}")
        print(f"     回退：{p['rollback']}")
    dup = 0 if dry else len(found) - len(new)
    if dup > 0:
        print(f"\n    （另有 {dup} 项已提过，不重复起草）")

    if new:
        print("\n▸ agent 必须做的事：把上面每条提案在对话里向用户讲清"
              "「证据／建议／收益／风险／回退」，然后等用户表态：")
        for p in new:
            print(f"    同意：python3 tools/retro.py --approve {p['id']} --note \"...\"")
            print(f"    否决：python3 tools/retro.py --reject  {p['id']} --note \"...\"")
        print("    用户没明确表态前，不得按提案修改任何教学流程。")
    print("═" * 70 + "\n")


def show_proposals(d):
    print("\n提案总表")
    print("─" * 74)
    for p in d["proposals"]:
        print(f"  {p['id']}  [{p['rule']:<3}] {p['status']:<12} "
              f"{p['created']}  {p['title']}")
    if not d["proposals"]:
        print("  （机器起草区为空；手写提案见 教学流程复盘.md）")
    print("─" * 74)
    print(f"  待确认 {sum(1 for p in d['proposals'] if p['status'] == '草案·待确认')}"
          f"　挂超 {TH['stale_days']} 天 {len(stale_proposals(d))}\n")


# ------------------------------------------------------------------ 入口

def main(argv=None):
    ap = argparse.ArgumentParser(description="教学复盘引擎（只起草，不自动改流程）")
    ap.add_argument("--brief", action="store_true", help="开场简报")
    ap.add_argument("--close", action="store_true", help="收尾复盘并起草提案")
    ap.add_argument("--check", action="store_true", help="只跑规则，不写盘")
    ap.add_argument("--proposals", action="store_true", help="列提案")
    ap.add_argument("--approve", metavar="PID")
    ap.add_argument("--reject", metavar="PID")
    ap.add_argument("--defer", metavar="PID")
    ap.add_argument("--implemented", metavar="PID")
    ap.add_argument("--note", default="")
    ap.add_argument("--rules", action="store_true", help="列规则与阈值")
    args = ap.parse_args(argv)

    ts = tutor.load_state()
    sig = load_signals()
    d = load_retro()

    if args.rules:
        print("\n复盘规则与阈值（改阈值属流程变更，须先经用户批准）")
        print("─" * 74)
        for fn in RULES:
            doc = (fn.__doc__ or "").strip().splitlines()[0]
            print(f"  {fn.__name__[5:]:<4} {doc}")
        print("─" * 74)
        for k, v in TH.items():
            print(f"  {k:<18} = {v}")
        print()
        return 0

    for pid, status in ((args.approve, "已批准（待实施）"),
                        (args.reject, "已否决"),
                        (args.defer, "暂缓"),
                        (args.implemented, "已批准、已实施")):
        if pid:
            p = decide(d, pid, status, args.note)
            if not p:
                print(f"找不到提案 {pid}（机器起草区）。手写 P-001~P-006 请直接改 md。")
                return 2
            save_retro(d)
            write_retro_md(d)
            write_change_md(d)
            print(f"{pid} → {status}　{args.note or ''}")
            print("已写入 教学流程复盘.md 与 教学策略变更记录.md")
            return 0

    if args.proposals:
        show_proposals(d)
        return 0

    if args.brief:
        show_brief(ts, sig, d)
        d["last_brief"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_retro(d)
        return 0

    if args.check or args.close:
        found = run_rules(ts, sig)
        if args.check:
            show_close(found, [], d, dry=True)
            return 0
        new = draft(d, found)
        d["last_close"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        save_retro(d)
        write_retro_md(d)
        write_change_md(d)
        show_close(found, new, d)
        return 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
