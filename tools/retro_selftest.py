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
    """R9 要同时认「写死数字」和「引用 PASS_WINDOW」两种默认值写法。

    P-007 实施后 `--n` 的默认值改成了符号 `PASS_WINDOW`。如果规则只会解析数字，
    它从此永远不命中——等于把这条配置守卫悄悄拆掉了。所以这里用替身源码把两种
    写法都过一遍，不去动真实的 tutor.py。
    """
    check("R9 现网配置（默认题量 = 达标窗口）→ 不命中",
          len(retro.rule_R9(st(), sig())), 0)

    W = tutor.PASS_WINDOW
    cases = (
        ("R9 默认写死 10、窗口 12 → 命中", "default=10", 1),
        (f"R9 默认写死 {W}（与窗口相同）→ 不命中", f"default={W}", 0),
        ("R9 默认引用 PASS_WINDOW → 不命中", "default=PASS_WINDOW", 0),
        ("R9 默认引用取不到值的符号 → 不猜，不命中", "default=SOME_UNKNOWN", 0),
    )
    orig = retro.Path.read_text
    for name, frag, want in cases:
        fake = f'    ap.add_argument("--n", type=int, {frag}, help="x")\n'
        retro.Path.read_text = (
            lambda self, *a, _f=fake, **k:
            _f if self.name == "tutor.py" else orig(self, *a, **k))
        try:
            check(name, len(retro.rule_R9(st(), sig())), want)
        finally:
            retro.Path.read_text = orig


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
               t_r9, t_r10, t_r11, t_redline, t_dedup):
        fn()
    print("─" * 62)
    if FAILS:
        print(f"❌ {len(FAILS)} 项失败：{'、'.join(FAILS)}\n")
        return 1
    print("✅ 全部通过\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
