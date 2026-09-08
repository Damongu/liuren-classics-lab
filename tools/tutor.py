#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六壬交互式教学器 —— 关卡制训练 + 确定性判分 + 掌握度回写。

设计要点：
  1. 出题与判分**完全不经过 LLM**。题目从 720 课穷举里采样，标准答案由排盘器给出，
     所以判分绝对准确；讲解用排盘器自带的 reason 推导链。
  2. 课体分布极不均匀（别责仅 9/720、昴星 16、八专 16），随机抽题几乎练不到。
     所以判定类关卡按课体**分层等概率**采样。
  3. 遇到底本自相矛盾处（如涉害比用格），答另一说判「半对」并把分歧摊开，
     而不是判错 —— 这是本项目的立场：分歧要看见，不要被抹平。

用法：
    python3 tools/tutor.py                # 按当前进度自动选关
    python3 tools/tutor.py --level 4      # 指定关卡
    python3 tools/tutor.py --n 20         # 本轮题量
    python3 tools/tutor.py --review       # 只做错题复现
    python3 tools/tutor.py --status        # 看进度，不答题
    python3 tools/tutor.py --list         # 列关卡
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "liuren-paipan"))

from liuren import Options, from_ganzhi, from_time                      # noqa: E402
from liuren.ganzhi import (GAN, JIGONG, ZHI, dungan, gz_name, kongwang,  # noqa: E402
                           shift)
from liuren.render import pad, render_kes, render_plate                   # noqa: E402
from liuren.search import enumerate720, filter_courses                   # noqa: E402

VAULT = ROOT / "六壬vault"
STATE = VAULT / "60-掌握度" / "_tutor_state.json"
RECORD = VAULT / "60-掌握度" / "训练记录.md"
WRONGQ = VAULT / "60-掌握度" / "错题队列.md"
MARK_B, MARK_E = "<!-- tutor:begin -->", "<!-- tutor:end -->"

INTERVALS = [1, 3, 7, 21]        # 间隔重复节奏（天）
PASS_WINDOW, PASS_RATE = 12, 0.85  # 通关：近 12 题正确率 ≥ 85%

_ALL = None


def all720():
    global _ALL
    if _ALL is None:
        _ALL = enumerate720()
    return _ALL


def by_keshi():
    d = {}
    for c in all720():
        d.setdefault(c.keshi, []).append(c)
    return d


# ---------------------------------------------------------------- 答案规整

_TRASH = str.maketrans("", "", " \t，,、。·．.→->|/｜;；:：'\"　")


def norm(s: str) -> str:
    return (s or "").strip().translate(_TRASH)


def ok(user: str, answers) -> bool:
    u = norm(user)
    return bool(u) and any(u == norm(a) for a in answers)


# ---------------------------------------------------------------- 题目采样

def rnd_case(rng, keshi=None):
    """随机取一课。keshi 指定时分层采样。返回 (day_gz, shi, jiang, plate)。"""
    if keshi:
        c = rng.choice(by_keshi()[keshi])
        gz, k = c.day_gz, c.k
    else:
        gz, k = gz_name(rng.randrange(60)), rng.randrange(12)
    shi = ZHI[rng.randrange(12)]
    jiang = shift(shi, k)
    return gz, shi, jiang, from_ganzhi(gz, shi, jiang)


def head(gz, shi, jiang, daynight=None):
    s = f"{gz}日　{shi}时　{jiang}将"
    return s + (f"　（{daynight}）" if daynight else "")


# ---------------------------------------------------------------- 各关出题

def g_jigong(rng):
    """L1 地基：寄宫 / 旬空 / 遁干。"""
    kind = rng.choice(["寄宫", "旬空", "遁干"])
    if kind == "寄宫":
        g = GAN[rng.randrange(10)]
        return dict(q=f"{g} 的寄宫在哪一宫？", ans=[JIGONG[g]],
                    src="第一册 002-十干寄宫", spec=("寄宫", g))
    gz = gz_name(rng.randrange(60))
    if kind == "旬空":
        a, b = kongwang(gz)
        return dict(q=f"{gz}日的旬空（空亡）是哪两支？", ans=[a + b, b + a],
                    src="第一册 起例·旬空", spec=("旬空", gz))
    z = ZHI[rng.randrange(12)]
    d = dungan(gz, z)
    return dict(q=f"{gz}日，{z} 上遁得何干？（本旬不含则答「无」）",
                ans=[d] if d else ["无", "None", "空"],
                src="第一册 起例·遁干", spec=("遁干", gz + z))


def g_ju(rng):
    """L2 起局与天盘。"""
    gz, shi, jiang, p = rnd_case(rng)
    if rng.random() < 0.5:
        return dict(q=f"{head(gz, shi, jiang)}\n问：这是第几局？（月将加占时，顺行位移）",
                    ans=[str(p.k)], plate=p, src="20-概念卡/天地盘",
                    spec=("局", gz, shi, jiang))
    z = ZHI[rng.randrange(12)]
    return dict(q=f"{head(gz, shi, jiang)}\n问：地盘 {z} 宫上的天盘支是什么？",
                ans=[p.tian[z]], plate=p, src="20-概念卡/天地盘",
                spec=("天盘", gz, shi, jiang, z))


def g_sike(rng):
    """L3 四课。"""
    gz, shi, jiang, p = rnd_case(rng)
    ups = "".join(k.up for k in p.kes)
    return dict(q=f"{head(gz, shi, jiang)}\n问：写出一至四课的上神（四个字，按课序）",
                ans=[ups], plate=p, src="20-概念卡/四课",
                spec=("四课", gz, shi, jiang))


def g_keshi(rng):
    """L4 九宗门判定 —— 按课体分层等概率。"""
    ks = rng.choice(sorted(by_keshi()))
    gz, shi, jiang, p = rnd_case(rng, keshi=ks)
    return dict(q=f"{head(gz, shi, jiang)}\n{render_kes(p)}\n"
                  f"问：此课当用九宗门哪一门起三传？",
                ans=[p.keshi, p.keshi + "课", p.keshi + "法"], plate=p,
                src="第一册 003~011 入手法诸诀｜第六册 课经一",
                spec=("课体", gz, shi, jiang))


def g_chuan(rng):
    """L5 三传。"""
    gz, shi, jiang, p = rnd_case(rng)
    d = dict(q=f"{head(gz, shi, jiang)}\n问：三传是什么？（三个字，初→中→末）",
             ans=["".join(p.chuan)], plate=p,
             src="20-概念卡/三传主干（贼克与比用）",
             spec=("三传", gz, shi, jiang))
    alt = _alt_chuan(p)
    if alt:
        d["alt"] = alt
    return d


def _alt_chuan(p):
    """底本分歧：另一说的初传若不同，登记为半对。"""
    out = {}
    for dv in p.divergences:
        other = dv.get("另一说")
        if other and other != p.chuan[0]:
            out[norm(other)] = dv
    return out


def g_jiang12(rng):
    """L6 十二天将与贵人。"""
    dn = rng.choice(["昼", "夜"])
    gz, shi, jiang, _ = rnd_case(rng)
    p = from_ganzhi(gz, shi, jiang, daynight=dn)
    if rng.random() < 0.5:
        return dict(q=f"{head(gz, shi, jiang, dn)}\n问：贵人落在哪个天盘支上？"
                      f"顺行还是逆行？（如「丑 顺」）",
                    ans=[p.guiren + p.guiren_dir, p.guiren + p.guiren_dir + "行"],
                    plate=p, src="20-概念卡/十二天将与昼夜贵人",
                    spec=("贵人", gz, shi, jiang, dn))
    z = rng.choice([k.up for k in p.kes] or ZHI)
    return dict(q=f"{head(gz, shi, jiang, dn)}\n问：天盘 {z} 上乘何将？",
                ans=[p.jiang12[z]], plate=p,
                src="20-概念卡/十二天将与昼夜贵人",
                spec=("乘将", gz, shi, jiang, dn, z))


def g_shehai(rng):
    """L7 涉害专项：格 + 初传。"""
    gz, shi, jiang, p = rnd_case(rng, keshi="涉害")
    d = dict(q=f"{head(gz, shi, jiang)}\n{render_kes(p)}\n"
               f"问：此涉害课属何格？初传取谁？（如「比用格 戌」）",
             ans=[p.keshi_sub + p.chuan[0]],
             plate=p, src="第一册 005-涉害法｜第六册 004-涉害课",
             spec=("涉害", gz, shi, jiang))
    alt = _shehai_alt(p)
    if alt:
        d["alt"] = alt
    return d


def _shehai_alt(p):
    """涉害题的另一说键：格与初传两项齐全，顺序不限。"""
    sub = norm(p.keshi_sub)
    return {k: v for a, v in _alt_chuan(p).items()
            for k in (a + sub, sub + a)}


def g_reverse(rng):
    """L8 逆向：给课体与三传，倒推日课。"""
    ks = rng.choice(["元首", "重审", "知一", "涉害", "遥克", "昴星",
                     "别责", "八专", "伏吟", "返吟"])
    c = rng.choice(by_keshi()[ks])
    hits = filter_courses(all720(), keshi=ks, chuan_has=None)
    same = [x for x in hits if x.chuan == c.chuan]
    ans = sorted({f"{x.day_gz}{x.k}" for x in same})
    return dict(q=f"课体：{ks}　三传：{'→'.join(c.chuan)}\n"
                  f"问：给出一个符合的「日干支+局数」（如「甲子3」）。"
                  f"全盘共 {len(same)} 个解。",
                ans=ans, plate=c.plate,
                src="排盘器 find 子命令｜第六册 课经一",
                spec=("逆向", ks, "".join(c.chuan)),
                note=f"全部解：{'、'.join(ans[:12])}"
                     + ("…" if len(ans) > 12 else ""))


def g_real(rng):
    """L9 真实时空：月将换将与昼夜。"""
    y = 2026
    m, d = rng.randrange(1, 13), rng.randrange(1, 29)
    hh = rng.randrange(0, 24)
    place = rng.choice(["成都", "北京", "乌鲁木齐", "上海", "拉萨", "哈尔滨"])
    clock = datetime(y, m, d, hh, rng.choice([5, 20, 40]))
    p = from_time(clock, place)
    note = (f"平太阳时：{p.place.name} 经度 {p.place.lon:.1f}°，"
            f"时差 {(p.place.lon - 120) * 4:+.1f} 分钟\n"
            f"换将：{p.jiang_source}\n昼夜：{p.daynight}（{p.daynight_why}）")
    if rng.random() < 0.5:
        return dict(q=f"{clock:%Y-%m-%d %H:%M}　{place}\n"
                      f"问：此刻用何月将？（按中气换将）",
                    ans=[p.jiang, p.jiang + "将"], plate=p, note=note,
                    src="20-概念卡/月将与地方时",
                    spec=("月将", clock.isoformat(), place))
    return dict(q=f"{clock:%Y-%m-%d %H:%M}　{place}\n"
                  f"问：按地方平太阳时，占时是哪个时辰？（答一个字）",
                ans=[p.shi, p.shi + "时"], plate=p, note=note,
                src="20-概念卡/月将与地方时",
                spec=("占时", clock.isoformat(), place))


LEVELS = [
    dict(id=1, name="地基·寄宫旬空遁干", stage=1, gen=g_jigong,
         card="20-概念卡/天地盘"),
    dict(id=2, name="起局·天地盘", stage=1, gen=g_ju,
         card="20-概念卡/天地盘"),
    dict(id=3, name="四课", stage=1, gen=g_sike,
         card="20-概念卡/四课"),
    dict(id=4, name="九宗门判定", stage=3, gen=g_keshi,
         card="50-校读笔记/对校矩阵-六个判别点"),
    dict(id=5, name="三传", stage=3, gen=g_chuan,
         card="20-概念卡/三传主干（贼克与比用）"),
    dict(id=6, name="十二天将与贵人", stage=2, gen=g_jiang12,
         card="20-概念卡/十二天将与昼夜贵人"),
    dict(id=7, name="涉害专项", stage=3, gen=g_shehai,
         card="40-考据卡"),
    dict(id=8, name="逆向倒推日课", stage=4, gen=g_reverse,
         card="00-索引/排盘器用法"),
    dict(id=9, name="真实时空·换将与平太阳时", stage=1, gen=g_real,
         card="20-概念卡/月将与地方时"),
]
LV = {l["id"]: l for l in LEVELS}


# ---------------------------------------------------------------- 错题重建

def replay(spec):
    """由题目规格反向重建原题 —— 间隔重复必须重问同一题，不是换新题。"""
    kind = spec[0]
    if kind == "寄宫":
        g = spec[1]
        return dict(q=f"{g} 的寄宫在哪一宫？", ans=[JIGONG[g]],
                    src="第一册 002-十干寄宫", spec=tuple(spec))
    if kind == "旬空":
        a, b = kongwang(spec[1])
        return dict(q=f"{spec[1]}日的旬空（空亡）是哪两支？", ans=[a + b, b + a],
                    src="第一册 起例·旬空", spec=tuple(spec))
    if kind == "遁干":
        gz, z = spec[1][:2], spec[1][2]
        d = dungan(gz, z)
        return dict(q=f"{gz}日，{z} 上遁得何干？（本旬不含则答「无」）",
                    ans=[d] if d else ["无", "None", "空"],
                    src="第一册 起例·遁干", spec=tuple(spec))
    if kind in ("局", "天盘", "四课", "课体", "三传", "涉害"):
        gz, shi, jiang = spec[1], spec[2], spec[3]
        p = from_ganzhi(gz, shi, jiang)
        base = dict(plate=p, spec=tuple(spec))
        if kind == "局":
            return base | dict(
                q=f"{head(gz, shi, jiang)}\n问：这是第几局？（月将加占时，顺行位移）",
                ans=[str(p.k)], src="20-概念卡/天地盘")
        if kind == "天盘":
            z = spec[4]
            return base | dict(
                q=f"{head(gz, shi, jiang)}\n问：地盘 {z} 宫上的天盘支是什么？",
                ans=[p.tian[z]], src="20-概念卡/天地盘")
        if kind == "四课":
            return base | dict(
                q=f"{head(gz, shi, jiang)}\n问：写出一至四课的上神（四个字，按课序）",
                ans=["".join(k.up for k in p.kes)], src="20-概念卡/四课")
        if kind == "课体":
            return base | dict(
                q=f"{head(gz, shi, jiang)}\n{render_kes(p)}\n"
                  f"问：此课当用九宗门哪一门起三传？",
                ans=[p.keshi, p.keshi + "课", p.keshi + "法"],
                src="第一册 003~011 入手法诸诀｜第六册 课经一")
        if kind == "三传":
            return base | dict(
                q=f"{head(gz, shi, jiang)}\n问：三传是什么？（三个字，初→中→末）",
                ans=["".join(p.chuan)], alt=_alt_chuan(p),
                src="20-概念卡/三传主干（贼克与比用）")
        return base | dict(
            q=f"{head(gz, shi, jiang)}\n{render_kes(p)}\n"
              f"问：此涉害课属何格？初传取谁？（如「比用格 戌」）",
            ans=[p.keshi_sub + p.chuan[0]], alt=_shehai_alt(p),
            src="第一册 005-涉害法｜第六册 004-涉害课")
    if kind in ("贵人", "乘将"):
        gz, shi, jiang, dn = spec[1], spec[2], spec[3], spec[4]
        p = from_ganzhi(gz, shi, jiang, daynight=dn)
        if kind == "贵人":
            return dict(q=f"{head(gz, shi, jiang, dn)}\n问：贵人落在哪个天盘支上？"
                          f"顺行还是逆行？（如「丑 顺」）",
                        ans=[p.guiren + p.guiren_dir,
                             p.guiren + p.guiren_dir + "行"],
                        plate=p, src="20-概念卡/十二天将与昼夜贵人",
                        spec=tuple(spec))
        z = spec[5]
        return dict(q=f"{head(gz, shi, jiang, dn)}\n问：天盘 {z} 上乘何将？",
                    ans=[p.jiang12[z]], plate=p,
                    src="20-概念卡/十二天将与昼夜贵人", spec=tuple(spec))
    if kind == "逆向":
        ks, chuan = spec[1], tuple(spec[2])
        same = [x for x in all720() if x.keshi == ks and x.chuan == chuan]
        ans = sorted({f"{x.day_gz}{x.k}" for x in same})
        return dict(q=f"课体：{ks}　三传：{'→'.join(chuan)}\n"
                      f"问：给出一个符合的「日干支+局数」（如「甲子3」）。"
                      f"全盘共 {len(same)} 个解。",
                    ans=ans, plate=same[0].plate if same else None,
                    src="排盘器 find 子命令｜第六册 课经一", spec=tuple(spec),
                    note=f"全部解：{'、'.join(ans[:12])}"
                         + ("…" if len(ans) > 12 else ""))
    if kind in ("月将", "占时"):
        clock, place = datetime.fromisoformat(spec[1]), spec[2]
        p = from_time(clock, place)
        note = (f"平太阳时：{p.place.name} 经度 {p.place.lon:.1f}°，"
                f"时差 {(p.place.lon - 120) * 4:+.1f} 分钟\n"
                f"换将：{p.jiang_source}\n昼夜：{p.daynight}（{p.daynight_why}）")
        if kind == "月将":
            return dict(q=f"{clock:%Y-%m-%d %H:%M}　{place}\n"
                          f"问：此刻用何月将？（按中气换将）",
                        ans=[p.jiang, p.jiang + "将"], plate=p, note=note,
                        src="20-概念卡/月将与地方时", spec=tuple(spec))
        return dict(q=f"{clock:%Y-%m-%d %H:%M}　{place}\n"
                      f"问：按地方平太阳时，占时是哪个时辰？（答一个字）",
                    ans=[p.shi, p.shi + "时"], plate=p, note=note,
                    src="20-概念卡/月将与地方时", spec=tuple(spec))
    raise ValueError(f"未知题型：{kind}")


# ---------------------------------------------------------------- 状态

def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text("utf-8"))
        except Exception:
            pass
    return {"levels": {}, "wrong": [], "sessions": []}


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), "utf-8")


def lv_state(st, lid):
    return st["levels"].setdefault(str(lid), {"hist": [], "passed": False})


def rate(hist, n=PASS_WINDOW):
    w = hist[-n:]
    return (sum(w) / len(w)) if w else 0.0


def pick_level(st):
    for l in LEVELS:
        s = lv_state(st, l["id"])
        if not (len(s["hist"]) >= PASS_WINDOW and rate(s["hist"]) >= PASS_RATE):
            return l["id"]
    return LEVELS[-1]["id"]


# ---------------------------------------------------------------- 讲解

def explain(item, p):
    out = []
    if p is not None:
        if item["spec"][0] not in ("寄宫", "旬空", "遁干"):
            out.append(render_plate(p))
            out.append(render_kes(p))
            out.append(f"三传：{'→'.join(p.chuan)}　课体：{p.keshi}·{p.keshi_sub}")
        if p.reason:
            out.append("推导：" + "；".join(p.reason))
        for dv in p.divergences:
            out.append(f"⚠ 分歧「{dv['规则']}」本盘取 {dv['本盘取']}，"
                       f"另一说取 {dv['另一说']}\n   依据：{dv['依据']}\n"
                       f"   另说：{dv['另说依据']}")
    if item.get("note"):
        out.append(item["note"])
    out.append(f"出处：{item['src']}")
    return "\n".join(out)


# ---------------------------------------------------------------- 主循环

def ask(item, no_input=False):
    print("\n" + "─" * 62)
    print(item["q"])
    if no_input:
        return ""
    try:
        return input("你的答案 > ")
    except (EOFError, KeyboardInterrupt):
        return "__quit__"


def judge(item, lid, st, card):
    """问一题、判分、讲解。返回 (得分 0/1, 是否退出)。"""
    p = item.get("plate")
    while True:
        a = ask(item)
        if a == "__quit__" or norm(a) in ("q", "quit", "退出"):
            return 0, True
        if norm(a) in ("?", "？", "提示", "hint"):
            print(f"提示：回看 六壬vault/{card}　｜　{item['src']}")
            continue
        break

    alt = item.get("alt") or {}
    if ok(a, item["ans"]):
        print("✅ 对")
        lv_state(st, lid)["hist"].append(1)
        _dequeue(st, lid, item)
        score = 1
    elif norm(a) in alt:
        dv = alt[norm(a)]
        print(f"◐ 半对 —— 你走的是另一说。底本这里自相矛盾。\n"
              f"   排盘器默认取 {dv['本盘取']}（{dv['依据']}）\n"
              f"   你答的 {dv['另一说']}（{dv['另说依据']}）\n"
              f"   这条不算你错，但要记住它是分歧点。")
        lv_state(st, lid)["hist"].append(1)
        score = 1
    else:
        print(f"❌ 错。正确答案：{item['ans'][0]}")
        lv_state(st, lid)["hist"].append(0)
        _enqueue(st, lid, item, a)
        score = 0
    print(explain(item, p))
    return score, False


def run(lid, n, st, rng):
    lvl = LV[lid]
    print(f"\n{'=' * 62}\n关卡 {lid}｜{lvl['name']}　（阶段 {lvl['stage']}）")
    print(f"参考：六壬vault/{lvl['card']}")
    print(f"{'=' * 62}\n答「?」看提示、「q」退出。")

    right = asked = 0
    for _ in range(n):
        item = lvl["gen"](rng)
        s, quit_ = judge(item, lid, st, lvl["card"])
        if quit_:
            print("\n中断。已答部分照常计入。")
            break
        right += s
        asked += 1
        print(f"　　进度 {right}/{asked}")
    return right, asked


def due_items(st, today=None):
    today = today or date.today().isoformat()
    return [w for w in st["wrong"] if w.get("due", "") <= today]


def run_review(n, st, force=False):
    """错题复现 —— 跨关卡，重问原题。"""
    pool = st["wrong"] if force else due_items(st)
    if not pool:
        nxt = min((w.get("due", "") for w in st["wrong"]), default=None)
        print(f"\n没有到期错题。队列里共 {len(st['wrong'])} 条"
              + (f"，最近一条到期日 {nxt}。" if nxt else "。")
              + "\n想强行全刷：加 --force。")
        return 0, 0
    pool = sorted(pool, key=lambda w: (w.get("due", ""), -w.get("streak", 0)))[:n]
    print(f"\n{'=' * 62}\n错题复现　{len(pool)} 题（跨关卡，重问原题）\n{'=' * 62}")

    right = asked = 0
    for w in pool:
        try:
            item = replay(w["key"].split("|") if "spec" not in w else w["spec"])
        except Exception as e:
            print(f"（跳过一条无法重建的旧错题：{type(e).__name__} {e}）")
            st["wrong"].remove(w)
            continue
        lid = w["level"]
        print(f"\n[关{lid}｜首错 {w['first']}｜已连对 {w.get('streak', 0)}]")
        s, quit_ = judge(item, lid, st, LV[lid]["card"])
        if quit_:
            print("\n中断。已答部分照常计入。")
            break
        right += s
        asked += 1
        print(f"　　进度 {right}/{asked}")
    return right, asked


def _key(item):
    return "|".join(map(str, item["spec"]))


def _enqueue(st, lid, item, given):
    k = _key(item)
    for w in st["wrong"]:
        if w["key"] == k:
            w["streak"] = 0
            w["due"] = (date.today() + timedelta(days=1)).isoformat()
            return
    st["wrong"].append({
        "key": k, "spec": list(item["spec"]), "level": lid,
        "q": item["q"].replace("\n", " ⏎ ")[:80],
        "ans": item["ans"][0], "given": norm(given)[:20],
        "first": date.today().isoformat(), "streak": 0,
        "due": (date.today() + timedelta(days=1)).isoformat(),
    })


def _dequeue(st, lid, item):
    k = _key(item)
    for w in list(st["wrong"]):
        if w["key"] == k:
            w["streak"] = w.get("streak", 0) + 1
            if w["streak"] >= 2:
                st["wrong"].remove(w)
            else:
                d = INTERVALS[min(w["streak"], len(INTERVALS) - 1)]
                w["due"] = (date.today() + timedelta(days=d)).isoformat()
            return


# ---------------------------------------------------------------- 回写

def write_back(st):
    lines = ["---", "tags: [掌握度/训练]", "---", "",
             "# 训练记录", "",
             "> 本文件由 `tools/tutor.py` 自动生成，不要手改。",
             f"> 最后更新：{datetime.now():%Y-%m-%d %H:%M}", "",
             "| 关卡 | 名称 | 阶段 | 已答 | 近 12 题正确率 | 状态 |",
             "| :---: | :--- | :---: | :---: | :---: | :---: |"]
    for l in LEVELS:
        s = lv_state(st, l["id"])
        h = s["hist"]
        r = rate(h)
        done = len(h) >= PASS_WINDOW and r >= PASS_RATE
        badge = "✅ 通关" if done else ("🔸 在练" if h else "⬜ 未开")
        lines.append(f"| {l['id']} | {l['name']} | {l['stage']} | {len(h)} | "
                     f"{r * 100:.0f}% | {badge} |")
    tot = sum(len(lv_state(st, l['id'])['hist']) for l in LEVELS)
    lines += ["", f"累计答题 **{tot}** 题　待复现错题 **{len(st['wrong'])}** 条", "",
              "## 下一步", "",
              f"建议练关卡 **{pick_level(st)}**："
              f"`python3 tools/tutor.py --level {pick_level(st)}`", "",
              "错题复现：`python3 tools/tutor.py --review`", ""]
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text("\n".join(lines), "utf-8")

    rows = ["| 题目 | 你答 | 正解 | 首错日 | 下次复现 | 连对 |",
            "| :--- | :---: | :---: | :---: | :---: | :---: |"]
    for w in sorted(st["wrong"], key=lambda x: x.get("due", "")):
        rows.append(f"| 关{w['level']}｜{w['q']} | {w['given']} | {w['ans']} | "
                    f"{w['first']} | {w['due']} | {w.get('streak', 0)} |")
    block = f"{MARK_B}\n\n### 机器判分错题（tutor 自动维护）\n\n" + \
            "\n".join(rows) + f"\n\n{MARK_E}"
    old = WRONGQ.read_text("utf-8") if WRONGQ.exists() else \
        "---\ntags: [掌握度/错题]\n---\n\n# 错题队列\n"
    if MARK_B in old and MARK_E in old:
        pre, rest = old.split(MARK_B, 1)
        new = pre + block + rest.split(MARK_E, 1)[1]
    else:
        new = old.rstrip() + "\n\n" + block + "\n"
    WRONGQ.write_text(new, "utf-8")


def show_status(st):
    print("\n关卡进度")
    print("─" * 62)
    for l in LEVELS:
        s = lv_state(st, l["id"])
        h = s["hist"]
        r = rate(h)
        done = len(h) >= PASS_WINDOW and r >= PASS_RATE
        bar = "█" * int(r * 10) + "·" * (10 - int(r * 10)) if h else "·" * 10
        print(f"  {l['id']}. {pad(l['name'], 26)} {bar} {r * 100:3.0f}%  "
              f"{len(h):>3}题  {'✅' if done else ''}")
    due = [w for w in st["wrong"] if w.get("due", "") <= date.today().isoformat()]
    print("─" * 62)
    print(f"  待复现错题 {len(due)} / {len(st['wrong'])} 条")
    print(f"  建议下一关：{pick_level(st)}\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="六壬交互式教学器")
    ap.add_argument("--level", "-l", type=int, help="指定关卡 1-9")
    ap.add_argument("--n", type=int, default=10, help="本轮题量（默认 10）")
    ap.add_argument("--review", action="store_true", help="只做到期错题（跨关卡，重问原题）")
    ap.add_argument("--force", action="store_true", help="配合 --review：不管到期日全刷")
    ap.add_argument("--status", action="store_true", help="看进度")
    ap.add_argument("--list", action="store_true", help="列关卡")
    ap.add_argument("--seed", type=int, help="固定随机种子（复现题目）")
    a = ap.parse_args(argv)

    st = load_state()
    if a.list:
        for l in LEVELS:
            print(f"  {l['id']}. {l['name']}（阶段 {l['stage']}）→ 六壬vault/{l['card']}")
        return 0
    if a.status:
        show_status(st)
        return 0

    if a.review:
        lid = None
        r, n = run_review(a.n, st, force=a.force)
    else:
        rng = random.Random(a.seed)
        lid = a.level or pick_level(st)
        if lid not in LV:
            print(f"没有关卡 {lid}。用 --list 看。")
            return 2
        r, n = run(lid, a.n, st, rng)

    if n:
        st["sessions"].append({"date": date.today().isoformat(),
                               "level": lid or "review", "right": r, "n": n})
        print(f"\n{'=' * 62}\n本轮 {r}/{n}　正确率 {r / n * 100:.0f}%")
        if lid:
            s = lv_state(st, lid)
            if len(s["hist"]) >= PASS_WINDOW and rate(s["hist"]) >= PASS_RATE:
                print(f"🎉 关卡 {lid} 达标（近 {PASS_WINDOW} 题 "
                      f"{rate(s['hist']) * 100:.0f}%）。下一关：{pick_level(st)}")
            else:
                print(f"关卡 {lid} 近 {PASS_WINDOW} 题正确率 "
                      f"{rate(s['hist']) * 100:.0f}%，达标线 {PASS_RATE * 100:.0f}%。")
        else:
            print(f"错题队列剩 {len(st['wrong'])} 条，"
                  f"其中今日到期 {len(due_items(st))} 条。")
        save_state(st)
        write_back(st)
        print("已回写 六壬vault/60-掌握度/训练记录.md 与 错题队列.md")
        print("把错题贴给 Trae 里的 agent，它会按 AGENTS.md 的四拍循环给你讲。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
