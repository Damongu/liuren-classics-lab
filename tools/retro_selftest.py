#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复盘引擎自测 —— 用构造数据直接打规则函数，不碰 vault，不产生副作用。

为什么要有这个：
    retro.py 的价值全在「阈值是死的、命中是确定的」。如果规则本身会漏判或误判，
    整套自我迭代就退化回「靠 agent 自觉」。所以每条规则都必须有
    「刚好不触发 / 刚好触发」两个用例把边界钉住。

用法：
    python3 tools/retro_selftest.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import retro  # noqa: E402
import tutor  # noqa: E402

TODAY = date.today()
FAILS = []


def d(n):
    return (TODAY - timedelta(days=n)).isoformat()


def sig(signals=(), sessions=()):
    return dict(signals=[dict(ts=f"{x.get('date', d(0))} 10:00",
                              date=x.get("date", d(0)),
                              session=x.get("session", "S1"),
                              type=x["type"], topic=x.get("topic", ""),
                              note=x.get("note", "n"),
                              resolved=x.get("resolved", False),
                              resolution="") for x in signals],
                sessions=list(sessions))


def st(levels=None, wrong=(), sessions=()):
    return dict(levels=levels or {}, wrong=list(wrong), sessions=list(sessions),
                wrong_archive=[], weak_groups={})


def lv1(topics):
    return {"1": dict(hist=[], passed=False, teachback=False,
                      mixed=dict(hist=[]), topics=topics)}


def check(name, got, want):
    if got == want:
        print(f"  ✅ {name}")
    else:
        print(f"  ❌ {name}：期望 {want}，实得 {got}")
        FAILS.append(name)


def hit(fn, s, g):
    return len(fn(s, g))


# ------------------------------------------------------------------ R1
def t_r1():
    ses = [dict(date=d(2), level=2, right=5, n=12),
           dict(date=d(1), level=2, right=6, n=12)]
    check("R1 连续两轮未达标 → 命中", hit(retro.rule_R1, st(sessions=ses), sig()), 1)
    ses2 = [dict(date=d(2), level=2, right=5, n=12),
            dict(date=d(1), level=2, right=12, n=12)]
    check("R1 末轮达标 → 不命中", hit(retro.rule_R1, st(sessions=ses2), sig()), 0)
    ses3 = [dict(date=d(1), level=2, right=5, n=12)]
    check("R1 只有一轮 → 不命中", hit(retro.rule_R1, st(sessions=ses3), sig()), 0)


# ------------------------------------------------------------------ R2
def t_r2():
    def w(i, reasons):
        return dict(key=f"k{i}", spec=["遁干", "x"], level=1, q=f"题{i}",
                    ans="甲", given="乙", first=d(1), streak=0, due=d(0),
                    reasons=reasons)
    two = [w(i, ["步骤遗漏"]) for i in range(2)]
    three = [w(i, ["步骤遗漏"]) for i in range(3)]
    base = [w(i, ["教学前基线", "步骤遗漏"]) for i in range(5)]
    check("R2 同因 2 条 → 不命中", hit(retro.rule_R2, st(wrong=two), sig()), 0)
    check("R2 同因 3 条 → 命中", hit(retro.rule_R2, st(wrong=three), sig()), 1)
    check("R2 教学前基线不计入", hit(retro.rule_R2, st(wrong=base), sig()), 0)


# ------------------------------------------------------------------ R3
def t_r3():
    ready = dict(hist=[1] * 12, teachback=False, passed=False)
    topics = {"寄宫": ready}
    fresh = st(levels=lv1(topics), sessions=[dict(date=d(0), level=1, right=12, n=12)])
    check("R3 当天刚练完未验收 → 不命中", hit(retro.rule_R3, fresh, sig()), 0)
    old = st(levels=lv1(topics), sessions=[dict(date=d(5), level=1, right=12, n=12)])
    check("R3 挂 5 天未验收 → 命中", hit(retro.rule_R3, old, sig()), 1)
    blocked = sig([dict(type="前置缺失", topic="寄宫")])
    check("R3 有前置缺失信号即命中", hit(retro.rule_R3, fresh, blocked), 1)
    done = st(levels=lv1({"寄宫": dict(hist=[1] * 12, teachback=True, passed=True)}),
              sessions=[dict(date=d(9), level=1, right=12, n=12)])
    check("R3 复述已过 → 不命中", hit(retro.rule_R3, done, sig()), 0)


# ------------------------------------------------------------------ R4
def t_r4():
    two = sig([dict(type="卡顿", session="S1"), dict(type="前置缺失", session="S1")])
    three = sig([dict(type="卡顿", session="S1")] * 2
                + [dict(type="前置缺失", session="S1")])
    split = sig([dict(type="卡顿", session="S1")] * 2
                + [dict(type="卡顿", session="S2")])
    solved = sig([dict(type="卡顿", session="S1", resolved=True)] * 3)
    check("R4 单节 2 条 → 不命中", hit(retro.rule_R4, st(), two), 0)
    check("R4 单节 3 条 → 命中", hit(retro.rule_R4, st(), three), 1)
    check("R4 跨会话不累加", hit(retro.rule_R4, st(), split), 0)
    check("R4 已处理信号不计入", hit(retro.rule_R4, st(), solved), 0)


# ------------------------------------------------------------------ R5
def t_r5():
    reask = sig([dict(type="重复追问", topic="天地盘")] * 3)
    reask2 = sig([dict(type="重复追问", topic="天地盘")] * 2)
    fig = sig([dict(type="图缺失", topic="三传")] * 2)
    notopic = sig([dict(type="重复追问", topic="")] * 5)
    check("R5 同概念追问 3 次 → 命中", hit(retro.rule_R5, st(), reask), 1)
    check("R5 追问 2 次 → 不命中", hit(retro.rule_R5, st(), reask2), 0)
    check("R5 图缺失 2 次 → 命中", hit(retro.rule_R5, st(), fig), 1)
    check("R5 未标概念不聚类", hit(retro.rule_R5, st(), notopic), 0)


# ------------------------------------------------------------------ R6
def t_r6():
    one = sig([dict(type="纠错", note="讲错了")])
    solved = sig([dict(type="纠错", note="讲错了", resolved=True)])
    check("R6 一条纠错就必须成稿", hit(retro.rule_R6, st(), one), 1)
    check("R6 已处理不再成稿", hit(retro.rule_R6, st(), solved), 0)


# ------------------------------------------------------------------ R7
def t_r7():
    def w(due):
        return dict(key="k", spec=["遁干", "x"], level=1, q="题", ans="甲",
                    given="乙", first=d(9), streak=0, due=due, reasons=["步骤遗漏"])
    check("R7 今天到期 → 不命中", hit(retro.rule_R7, st(wrong=[w(d(0))]), sig()), 0)
    check("R7 逾期 2 天 → 不命中（阈值为「超过」）",
          hit(retro.rule_R7, st(wrong=[w(d(2))]), sig()), 0)
    check("R7 逾期 5 天 → 命中", hit(retro.rule_R7, st(wrong=[w(d(5))]), sig()), 1)


# ------------------------------------------------------------------ R9/R10/R11
def t_r9():
    got = retro.rule_R9(st(), sig())
    src = (ROOT / "tools" / "tutor.py").read_text("utf-8")
    import re
    m = re.search(r'"--n".{0,80}?default=(\d+)', src, re.S)
    want = 0 if (m and int(m.group(1)) == tutor.PASS_WINDOW) else 1
    check("R9 与 tutor.py 实际配置一致", len(got), want)


def t_r10():
    ok = sig(sessions=[dict(id="S1", start=f"{d(0)} 09:00", end=f"{d(0)} 10:30",
                            minutes=90, topic="")])
    bad = sig(sessions=[dict(id="S1", start=f"{d(0)} 09:00", end=f"{d(0)} 12:00",
                             minutes=180, topic="")])
    check("R10 90 分钟 → 不命中", hit(retro.rule_R10, st(), ok), 0)
    check("R10 180 分钟 → 命中", hit(retro.rule_R10, st(), bad), 1)


def t_r11():
    passed = lv1({"遁干": dict(hist=[1] * 12, teachback=True, passed=True)})
    w = dict(key="k", spec=["遁干", "x"], level=1, q="题", ans="甲", given="乙",
             first=d(1), streak=0, due=d(0), reasons=["步骤遗漏"])
    base = dict(w, reasons=["教学前基线", "步骤遗漏"])
    check("R11 复述已过又错 → 命中",
          hit(retro.rule_R11, st(levels=passed, wrong=[w]), sig()), 1)
    check("R11 教学前基线题不算",
          hit(retro.rule_R11, st(levels=passed, wrong=[base]), sig()), 0)


# ------------------------------------------------------------------ R12–R14 导读
class _FakeGuide:
    """替身导读模块：只提供 R13／R14 需要的两个接口，避免自测读写真实 vault。"""

    LIMITS = {"A": 5, "B": 10, "C": 15}

    def __init__(self, cards=None):
        self._cards = cards or {}

    def grade_limit(self, g):
        return self.LIMITS.get(g, 10), 0

    def load_state(self):
        return dict(cards=self._cards)


def _with_guide(receipts, cards=None):
    """把 retro._guide_receipts 换成构造数据，返回恢复函数。"""
    orig = retro._guide_receipts
    fake = _FakeGuide(cards)
    retro._guide_receipts = lambda: (list(receipts), fake)
    return orig


def _restore_guide(orig):
    retro._guide_receipts = orig


def rcpt(entry, grade, result, minutes, day=0):
    return dict(entry=f"10-底本/六壬大全/01-第一册 起例/{entry}", grade=grade,
                result=result, minutes=minutes, at=f"{d(day)} 10:00")


def t_r12():
    orig = _with_guide([], {"x": dict(name="涉害法", grade="A")})
    try:
        one = sig([dict(type="导读不足", topic="涉害法")])
        two = sig([dict(type="导读不足", topic="涉害法"),
                   dict(type="导读不足", topic="涉害法")])
        split = sig([dict(type="导读不足", topic="涉害法", session="S1"),
                     dict(type="导读不足", topic="元首课", session="S2")])
        done = sig([dict(type="导读不足", topic="涉害法", resolved=True),
                    dict(type="导读不足", topic="涉害法", resolved=True)])
        check("R12 单节 1 次导读不足 → 不命中", hit(retro.rule_R12, st(), one), 0)
        check("R12 单节 2 次导读不足 → 命中", hit(retro.rule_R12, st(), two), 1)
        check("R12 分散在两节各 1 次 → 不命中", hit(retro.rule_R12, st(), split), 0)
        check("R12 已处理信号不计入", hit(retro.rule_R12, st(), done), 0)
        check("R12 卡顿不误判为导读不足",
              hit(retro.rule_R12, st(), sig([dict(type="卡顿"), dict(type="卡顿")])), 0)
    finally:
        _restore_guide(orig)


def t_r13():
    cases = [
        ("R13 连续两节 fail → 命中",
         [rcpt("005-涉害法", "A", "fail", 6, 2), rcpt("002-十干寄宫", "A", "fail", 7, 1)], 1),
        ("R13 末节 pass → 不命中",
         [rcpt("005-涉害法", "A", "fail", 6, 2), rcpt("002-十干寄宫", "A", "pass", 4, 1)], 0),
        ("R13 只有一节 fail → 不命中", [rcpt("005-涉害法", "A", "fail", 6, 1)], 0),
        ("R13 无回执 → 不命中", [], 0),
    ]
    for name, rs, want in cases:
        orig = _with_guide(rs)
        try:
            check(name, hit(retro.rule_R13, st(), sig()), want)
        finally:
            _restore_guide(orig)


def t_r14():
    over = [rcpt("a", "A", "pass", 9, 3), rcpt("b", "A", "pass", 8, 2),
            rcpt("c", "A", "pass", 7, 1)]                       # A 档上限 5，连超 3 节
    two = over[1:]                                              # 只连超 2 节
    mixed = [rcpt("a", "A", "pass", 9, 3), rcpt("b", "A", "pass", 4, 2),
             rcpt("c", "A", "pass", 8, 1)]                      # 中间一节没超
    other = [rcpt("a", "B", "pass", 9, 3), rcpt("b", "B", "pass", 8, 2),
             rcpt("c", "B", "pass", 9, 1)]                      # B 档上限 10，都没超
    nomin = [dict(rcpt("a", "A", "pass", 9, 3), minutes=None),
             rcpt("b", "A", "pass", 8, 2), rcpt("c", "A", "pass", 7, 1)]
    for name, rs, want in (
            ("R14 A 档连超 3 节 → 命中", over, 1),
            ("R14 只连超 2 节 → 不命中", two, 0),
            ("R14 中间一节未超 → 不命中", mixed, 0),
            ("R14 B 档均未超上限 → 不命中", other, 0),
            ("R14 缺用时的回执不计入，剩 2 节 → 不命中", nomin, 0)):
        orig = _with_guide(rs)
        try:
            check(name, hit(retro.rule_R14, st(), sig()), want)
        finally:
            _restore_guide(orig)


# ------------------------------------------------------------------ 红线与去重
def t_redline():
    fake = dict(rule="X", key="X|1", title="建议降低证据等级要求以加快进度",
                evidence=[], suggestion="放宽证据分级", benefit="", risk="",
                rollback="")
    check("红线：触碰证据分级的提案被拦掉", retro._hits_redline(fake), True)
    ok = dict(fake, title="建议拆节", suggestion="插入前置节")
    check("红线：普通教学提案不被拦", retro._hits_redline(ok), False)


def t_dedup():
    d0 = dict(proposals=[], last_brief=None, last_close=None)
    found = [dict(rule="R4", key="R4|S1", title="t", evidence=["e"],
                  suggestion="s", benefit="b", risk="r", rollback="k")]
    first = retro.draft(d0, found)
    second = retro.draft(d0, found)
    check("去重：同一 key 只起草一次", (len(first), len(second)), (1, 0))
    check("去重：提案状态为草案·待确认", d0["proposals"][0]["status"], "草案·待确认")
    retro.decide(d0, first[0]["id"], "已否决", "不需要")
    third = retro.draft(d0, found)
    check("去重：已否决后不再重复提出", len(third), 0)


def main():
    print("\n复盘引擎自测")
    print("─" * 62)
    for fn in (t_r1, t_r2, t_r3, t_r4, t_r5, t_r6, t_r7,
               t_r9, t_r10, t_r11, t_r12, t_r13, t_r14,
               t_redline, t_dedup):
        fn()
    print("─" * 62)
    if FAILS:
        print(f"❌ {len(FAILS)} 项失败：{'、'.join(FAILS)}\n")
        return 1
    print("✅ 全部通过\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
