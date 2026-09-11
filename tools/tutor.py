#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""六壬交互式训练器 —— 关卡制练习 + 确定性判分 + 掌握度回写。

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
    python3 tools/tutor.py -l 1 --topic 遁干  # 只练关卡 1 的一个概念
    python3 tools/tutor.py --n 20         # 本轮题量
    python3 tools/tutor.py --review       # 只做错题复现
    python3 tools/tutor.py --teachback-pass 1  # agent 验收复述后记录
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

INTERVALS = [1, 3, 7, 21]          # 间隔重复节奏（天）
PASS_WINDOW, PASS_CORRECT = 12, 11  # 12 题至少答对 11 题
PASS_RATE = PASS_CORRECT / PASS_WINDOW
ERROR_REASONS = (
    "待归因", "概念缺失", "步骤遗漏", "辨析错误", "计算失误",
    "输入失误", "另一口径", "教学前基线", "题目失效", "重复过量",
)

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

def g_jigong(rng, topic=None):
    """L1 地基：寄宫 / 旬空 / 遁干。"""
    kind = topic or rng.choice(["寄宫", "旬空", "遁干"])
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
        return dict(q=f"{head(gz, shi, jiang)}\n"
                      f"问：天盘 {jiang} 应放在哪个地盘宫？",
                    ans=[shi], plate=p, src="20-概念卡/天地盘",
                    spec=("加时", gz, shi, jiang))
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


def g_zeike(rng):
    """L4 贼克专项：只练元首、重审及发用上神。"""
    ks = rng.choice(["元首", "重审"])
    gz, shi, jiang, p = rnd_case(rng, keshi=ks)
    why = "有下贼取下贼" if p.keshi == "重审" else "无下贼取上克"
    return dict(q=f"{head(gz, shi, jiang)}\n{render_kes(p)}\n"
                  "问：按贼克法，此课是元首还是重审？初传取谁？"
                  "并说明判断依据。"
                  f"（如「{p.keshi} {p.chuan[0]} {why}」）",
                ans=[
                    p.keshi + p.chuan[0] + why,
                    p.keshi + "课" + p.chuan[0] + why,
                ],
                plate=p,
                src="第一册 003-贼克法｜《占事略决》第一、二章",
                spec=("贼克", gz, shi, jiang))


def g_biyong(rng):
    """L4 比用专项：只练知一课及发用上神。"""
    gz, shi, jiang, p = rnd_case(rng, keshi="知一")
    why = "阳日取阳神" if p.is_gang else "阴日取阴神"
    return dict(q=f"{head(gz, shi, jiang)}\n{render_kes(p)}\n"
                  "问：按比用法，初传取谁？并说明判断依据。"
                  f"（如「戌 {why}」）",
                ans=[p.chuan[0] + why, why + p.chuan[0]],
                plate=p,
                src="第一册 004-比用法｜《太白阴经·推四课法》｜"
                    "《占事略决·课用九法》第二法",
                spec=("比用", gz, shi, jiang))


def g_zeike_biyong(rng):
    """L4 贼克＋比用杂糅：等概率抽元首、重审、知一。"""
    ks = rng.choice(["元首", "重审", "知一"])
    if ks == "知一":
        return g_biyong(rng)
    return g_zeike(rng)


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
    """L7 涉害专项：按《六壬大全》涉归本家逐位计重。"""
    gz, shi, jiang, p = rnd_case(rng, keshi="涉害")
    depth = p.shehai_depth(p.chuan[0])
    why = f"{depth}重"
    d = dict(q=f"{head(gz, shi, jiang)}\n{render_kes(p)}\n"
               "问：按涉归本家逐位计重法，初传取谁？该候选计几重？"
               f"（如「{p.chuan[0]} {why}」）",
             ans=[p.chuan[0] + why, why + p.chuan[0]],
             plate=p, src="《六壬大全·涉害课》｜"
                          "20-概念卡/涉害涉归本家",
             spec=("涉害", gz, shi, jiang))
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

LEVEL1_TOPICS = ("寄宫", "旬空", "遁干")
LEVEL4_TOPICS = ("贼克", "比用", "贼克＋比用")
TOPIC_CHOICES = LEVEL1_TOPICS + LEVEL4_TOPICS
LEVEL1_BRIEF = {
    "寄宫": "十干按六壬寄宫表落到地支宫；这是固定表，不按日旬变化。",
    "旬空": "先定六甲旬首；从旬首支起配甲至癸，十干配完后余下两支为空亡。",
    "遁干": "先定六甲旬首；在旬首支起甲，干支同步顺行，十干配完即止，空亡支答「无」。",
}


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
    if kind in ("局", "加时", "天盘", "四课", "课体", "贼克", "比用",
                "三传", "涉害"):
        gz, shi, jiang = spec[1], spec[2], spec[3]
        p = from_ganzhi(gz, shi, jiang)
        base = dict(plate=p, spec=tuple(spec))
        if kind in ("局", "加时"):
            return base | dict(
                q=f"{head(gz, shi, jiang)}\n"
                  f"问：天盘 {jiang} 应放在哪个地盘宫？",
                ans=[shi], src="20-概念卡/天地盘")
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
        if kind == "贼克":
            why = "有下贼取下贼" if p.keshi == "重审" else "无下贼取上克"
            return base | dict(
                q=f"{head(gz, shi, jiang)}\n{render_kes(p)}\n"
                  "问：按贼克法，此课是元首还是重审？初传取谁？"
                  "并说明判断依据。",
                ans=[
                    p.keshi + p.chuan[0] + why,
                    p.keshi + "课" + p.chuan[0] + why,
                ],
                src="第一册 003-贼克法｜《占事略决》第一、二章")
        if kind == "比用":
            why = "阳日取阳神" if p.is_gang else "阴日取阴神"
            return base | dict(
                q=f"{head(gz, shi, jiang)}\n{render_kes(p)}\n"
                  "问：按比用法，初传取谁？并说明判断依据。",
                ans=[p.chuan[0] + why, why + p.chuan[0]],
                src="第一册 004-比用法｜《太白阴经·推四课法》｜"
                    "《占事略决·课用九法》第二法")
        if kind == "三传":
            return base | dict(
                q=f"{head(gz, shi, jiang)}\n问：三传是什么？（三个字，初→中→末）",
                ans=["".join(p.chuan)], alt=_alt_chuan(p),
                src="20-概念卡/三传主干（贼克与比用）")
        why = f"{p.shehai_depth(p.chuan[0])}重"
        return base | dict(
            q=f"{head(gz, shi, jiang)}\n{render_kes(p)}\n"
              "问：按涉归本家逐位计重法，初传取谁？该候选计几重？"
              f"（如「{p.chuan[0]} {why}」）",
            ans=[p.chuan[0] + why, why + p.chuan[0]],
            src="《六壬大全·涉害课》｜20-概念卡/涉害涉归本家")
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
            state = json.loads(STATE.read_text("utf-8"))
            state.setdefault("wrong_archive", [])
            state.setdefault("weak_groups", {})
            state.setdefault("unscored_sessions", [])
            state.setdefault("progression_waivers", {})
            for w in state.setdefault("wrong", []):
                w.setdefault("reasons", ["待归因"])
                w.setdefault("diagnosis", "")
                w.setdefault("baseline_pending", False)
            return state
        except Exception:
            pass
    return {
        "levels": {}, "wrong": [], "wrong_archive": [],
        "weak_groups": {}, "sessions": [], "unscored_sessions": [],
        "progression_waivers": {},
    }


def save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=2), "utf-8")


def lv_state(st, lid):
    state = st["levels"].setdefault(
        str(lid), {"hist": [], "teachback": False, "passed": False}
    )
    state.setdefault("teachback", False)
    state.setdefault("passed", False)
    if lid in (1, 4):
        state.setdefault("topics", {})
    if lid == 1:
        state.setdefault("mixed", {"hist": []})
    return state


def topic_state(s, topic):
    state = s["topics"].setdefault(
        topic, {"hist": [], "teachback": False, "passed": False}
    )
    state.setdefault("teachback", False)
    state.setdefault("passed", False)
    return state


def rate(hist, n=PASS_WINDOW):
    w = hist[-n:]
    return (sum(w) / len(w)) if w else 0.0


def score_ready(s):
    h = s.get("hist", [])
    return len(h) >= PASS_WINDOW and sum(h[-PASS_WINDOW:]) >= PASS_CORRECT


def topic_passed(s, topic):
    ts = topic_state(s, topic)
    return score_ready(ts) and bool(ts.get("teachback"))


def practice_ready(s, lid=None):
    if lid == 1:
        return (all(topic_passed(s, topic) for topic in LEVEL1_TOPICS)
                and score_ready(s["mixed"]))
    return score_ready(s)


def final_passed(s, lid=None):
    return practice_ready(s, lid) and bool(s.get("teachback"))


def pick_level(st):
    for l in LEVELS:
        s = lv_state(st, l["id"])
        waived = str(l["id"]) in st.get("progression_waivers", {})
        if not final_passed(s, l["id"]) and not waived:
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


def record_result(st, lid, score, topic=None):
    state = lv_state(st, lid)
    if not (lid == 4 and topic):
        state["hist"].append(score)  # 专项不冒充完整九宗门成绩。
    if lid == 1:
        bucket = topic_state(state, topic) if topic else state["mixed"]
        bucket["hist"].append(score)
        if score == 0:
            if topic:
                bucket["teachback"] = False
                bucket["passed"] = False
            state["teachback"] = False
            state["passed"] = False
    elif lid == 4 and topic:
        bucket = topic_state(state, topic)
        bucket["hist"].append(score)
        if score == 0:
            bucket["teachback"] = False
            bucket["passed"] = False
    elif score == 0:
        state["teachback"] = False
        state["passed"] = False


def record_external_session(lid, scores, source, session_id, topic=None, details=None):
    """Record a deterministically judged session from another local UI."""
    if lid not in LV:
        raise ValueError(f"没有关卡 {lid}")
    if not isinstance(scores, list) or not scores or any(s not in (0, 1) for s in scores):
        raise ValueError("外部训练成绩无效")
    if not isinstance(source, str) or not source.strip():
        raise ValueError("外部训练来源无效")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("外部训练会话编号无效")
    if topic is not None and not (
        (lid == 1 and topic in LEVEL1_TOPICS)
        or (lid == 4 and topic in LEVEL4_TOPICS)
    ):
        raise ValueError("专项训练类型无效")
    if details is not None and (
        not isinstance(details, list) or len(details) != len(scores)
        or any(not isinstance(row, dict) for row in details)
    ):
        raise ValueError("外部训练明细无效")

    st = load_state()
    imported = st.setdefault("external_sessions", {})
    if session_id in imported:
        return {
            "recorded": False,
            "right": sum(scores),
            "n": len(scores),
            "ready": (score_ready(topic_state(lv_state(st, lid), topic))
                      if topic else practice_ready(lv_state(st, lid), lid)),
        }

    for score in scores:
        record_result(st, lid, score, topic=topic)
    right = sum(scores)
    session = {
        "date": date.today().isoformat(),
        "level": lid,
        "right": right,
        "n": len(scores),
        "source": source,
        "session_id": session_id,
        "topic": topic,
    }
    if details is not None:
        session["details"] = details
    st["sessions"].append(session)
    imported_session = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "level": lid,
        "right": right,
        "n": len(scores),
        "source": source,
        "topic": topic,
    }
    if details is not None:
        imported_session["details"] = details
    imported[session_id] = imported_session
    save_state(st)
    write_back(st)
    return {
        "recorded": True,
        "right": right,
        "n": len(scores),
        "ready": (score_ready(topic_state(lv_state(st, lid), topic))
                  if topic else practice_ready(lv_state(st, lid), lid)),
    }


def record_unscored_session(lid, n, source, session_id, note):
    """Preserve completed work when a system fault destroyed the score."""
    if lid not in LV or not isinstance(n, int) or n <= 0:
        raise ValueError("未计分训练记录无效")
    if not all(isinstance(v, str) and v.strip()
               for v in (source, session_id, note)):
        raise ValueError("未计分训练记录信息不完整")
    st = load_state()
    rows = st.setdefault("unscored_sessions", [])
    if any(row.get("session_id") == session_id for row in rows):
        return False
    rows.append({
        "date": date.today().isoformat(),
        "level": lid,
        "n": n,
        "source": source,
        "session_id": session_id,
        "note": note,
    })
    save_state(st)
    write_back(st)
    return True


def waive_level_progression(lid, reason):
    """Allow progression after an agent-caused loss without fabricating a pass."""
    if lid not in LV or not isinstance(reason, str) or not reason.strip():
        raise ValueError("进度豁免信息无效")
    st = load_state()
    st.setdefault("progression_waivers", {})[str(lid)] = {
        "date": date.today().isoformat(),
        "reason": reason,
    }
    save_state(st)
    write_back(st)


def judge(item, lid, st, card, topic=None, count_practice=True,
          track_queue=True):
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
        if count_practice:
            record_result(st, lid, 1, topic)
        if track_queue:
            _dequeue(st, lid, item)
        score = 1
    elif norm(a) in alt:
        dv = alt[norm(a)]
        print(f"◐ 半对 —— 你走的是另一说。底本这里自相矛盾。\n"
              f"   排盘器默认取 {dv['本盘取']}（{dv['依据']}）\n"
              f"   你答的 {dv['另一说']}（{dv['另说依据']}）\n"
              f"   这条不算你错，但要记住它是分歧点。")
        if count_practice:
            record_result(st, lid, 1, topic)
        if track_queue:
            _archive_by_item(st, item, "另一口径", ["另一口径"])
        score = 1
    else:
        print(f"❌ 错。正确答案：{item['ans'][0]}")
        if count_practice:
            record_result(st, lid, 0, topic)
        if track_queue:
            _enqueue(st, lid, item, a)
        score = 0
    print(explain(item, p))
    return score, False


def learning_gate(lid, topic=None, assume_learned=False):
    """练习前置闸门：训练器不替代 agent 的四拍教学。"""
    lvl = LV[lid]
    print("\n训练前检查")
    print("  正确顺序：agent 解释与佐证 → 你复述 → 质疑来源 → Terminal 练习")
    if lid == 1:
        topics = [topic] if topic else list(LEVEL1_TOPICS)
        for name in topics:
            print(f"  {name}：{LEVEL1_BRIEF[name]}")
        if topic is None:
            print("  本关默认混合三类题；首次学习请加 --topic 逐项练。")
    print(f"  参考：六壬vault/{lvl['card']}")
    if assume_learned:
        return True
    try:
        a = input("已完成上述概念的四拍教学？按 Enter 开始，输入 q 退出 > ")
    except (EOFError, KeyboardInterrupt):
        return False
    return norm(a) not in ("q", "quit", "退出")


def run(lid, n, st, rng, topic=None, assume_learned=False):
    lvl = LV[lid]
    if lid == 1:
        n = PASS_WINDOW
        state = lv_state(st, lid)
        if topic is None:
            missing = [name for name in LEVEL1_TOPICS
                       if not topic_passed(state, name)]
            if missing:
                print("关卡 1 混合验收尚未开放。先完成专项练习与白话复述："
                      + "、".join(missing))
                return 0, 0
    print(f"\n{'=' * 62}\n关卡 {lid}｜{lvl['name']}　（阶段 {lvl['stage']}）")
    if topic:
        print(f"单项：{topic}")
    print("=" * 62)
    if not learning_gate(lid, topic, assume_learned):
        print("\n未开始练习，训练记录不变。")
        return 0, 0
    print("\n答「?」看提示、「q」退出。")

    right = asked = 0
    for _ in range(n):
        if lid == 1:
            item = lvl["gen"](rng, topic)
        elif lid == 4 and topic in LEVEL4_TOPICS:
            item = {
                "贼克": g_zeike,
                "比用": g_biyong,
                "贼克＋比用": g_zeike_biyong,
            }[topic](rng)
        else:
            item = lvl["gen"](rng)
        s, quit_ = judge(item, lid, st, lvl["card"], topic=topic)
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
            archive_wrong(st, w, "题目失效", ["题目失效"])
            continue
        lid = w["level"]
        print(f"\n[关{lid}｜首错 {w['first']}｜已连对 {w.get('streak', 0)}]")
        s, quit_ = judge(item, lid, st, LV[lid]["card"],
                         count_practice=False)
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
            if w.get("baseline_pending"):
                w["baseline_pending"] = False
                w["reasons"] = [
                    r for r in w.get("reasons", []) if r != "教学前基线"
                ] or ["待归因"]
                w["diagnosis"] = (
                    w.get("diagnosis", "") + "；教学后复现仍错，转为正式薄弱项"
                ).strip("；")
            return
    st["wrong"].append({
        "key": k, "spec": list(item["spec"]), "level": lid,
        "q": item["q"].replace("\n", " ⏎ ")[:80],
        "ans": item["ans"][0], "given": norm(given)[:20],
        "first": date.today().isoformat(), "streak": 0,
        "due": (date.today() + timedelta(days=1)).isoformat(),
        "reasons": ["待归因"], "diagnosis": "", "baseline_pending": False,
    })


def archive_wrong(st, wrong, exit_reason, add_reasons=None):
    """退出活跃队列但保留完整审计记录。"""
    if wrong not in st["wrong"]:
        return
    archived = dict(wrong)
    reasons = list(archived.get("reasons", ["待归因"]))
    for reason in add_reasons or []:
        if reason not in reasons:
            reasons.append(reason)
    archived["reasons"] = reasons
    archived["archived"] = date.today().isoformat()
    archived["exit_reason"] = exit_reason
    st["wrong"].remove(wrong)
    st.setdefault("wrong_archive", []).append(archived)


def _archive_by_item(st, item, exit_reason, add_reasons=None):
    k = _key(item)
    for w in list(st["wrong"]):
        if w["key"] == k:
            archive_wrong(st, w, exit_reason, add_reasons)
            return


def _dequeue(st, lid, item):
    k = _key(item)
    for w in list(st["wrong"]):
        if w["key"] == k:
            w["streak"] = w.get("streak", 0) + 1
            if w.get("baseline_pending"):
                archive_wrong(st, w, "教学后首次复现答对，基线题退出")
            elif w["streak"] >= 2:
                archive_wrong(st, w, "连续两次答对，完成复现")
            else:
                d = INTERVALS[min(w["streak"], len(INTERVALS) - 1)]
                w["due"] = (date.today() + timedelta(days=d)).isoformat()
            return


def classify_wrong(st, index, reasons, diagnosis="", archive=False):
    if not 1 <= index <= len(st["wrong"]):
        raise ValueError(f"错题编号应在 1..{len(st['wrong'])} 之间")
    w = st["wrong"][index - 1]
    w["reasons"] = list(dict.fromkeys(reasons))
    w["diagnosis"] = diagnosis
    w["baseline_pending"] = "教学前基线" in reasons
    if archive:
        archive_wrong(st, w, "人工归档")


def weak_items(st, reason):
    return [w for w in st["wrong"] if reason in w.get("reasons", [])]


def weak_variant(w, rng):
    kind = w.get("spec", [""])[0]
    if w.get("level") == 1 and kind in LEVEL1_TOPICS:
        return g_jigong(rng, kind)
    return LV[w["level"]]["gen"](rng)


def run_weak(reason, n, st, rng):
    pool = weak_items(st, reason)
    if not pool:
        print(f"没有标记为「{reason}」的活跃错题。")
        return 0, 0
    n = max(3, min(5, n))
    print(f"\n{'=' * 62}\n薄弱训练｜{reason}　最多 {n} 题\n{'=' * 62}")
    right = asked = streak = 0
    for _ in range(n):
        source = rng.choice(pool)
        item = weak_variant(source, rng)
        lid = source["level"]
        s, quit_ = judge(
            item, lid, st, LV[lid]["card"], count_practice=False,
            track_queue=False,
        )
        if quit_:
            break
        right += s
        asked += 1
        streak = streak + 1 if s else 0
        print(f"　　进度 {right}/{asked}　连续答对 {streak}")
        if asked >= 3 and streak >= 2:
            print("已连续答对两题，停止即时加题；原错题仍按计划复现。")
            break
    group = st.setdefault("weak_groups", {}).setdefault(
        reason, {"sessions": [], "last": None}
    )
    group["sessions"].append({
        "date": date.today().isoformat(), "right": right, "n": asked,
    })
    group["last"] = date.today().isoformat()
    return right, asked


# ---------------------------------------------------------------- 回写

def _recent_score(hist):
    if len(hist) >= PASS_WINDOW:
        return f"{sum(hist[-PASS_WINDOW:])}/{PASS_WINDOW}"
    return f"{len(hist)}/{PASS_WINDOW} 题" if hist else "—"


def _topic_status(state):
    if score_ready(state) and state.get("teachback"):
        return "✅ 通过"
    if score_ready(state):
        return "🗣 待复述"
    return "🔸 在练" if state.get("hist") else "⬜ 未开"


def _level_status(st, level):
    state = lv_state(st, level["id"])
    waived = st.get("progression_waivers", {}).get(str(level["id"]))
    if final_passed(state, level["id"]):
        return "✅ 过关"
    if waived:
        return "⚠ 已完成·成绩遗失·不阻断"
    if practice_ready(state, level["id"]):
        return "🗣 待复述"
    return "🔸 在练" if state["hist"] else "⬜ 未开"


def _next_step(st):
    for lid, topics in ((1, LEVEL1_TOPICS), (4, LEVEL4_TOPICS)):
        level_state = lv_state(st, lid)
        for topic in topics:
            state = topic_state(level_state, topic)
            if state["hist"] and not topic_passed(level_state, topic):
                if score_ready(state):
                    return f"完成「{topic}」白话复述验收。"
                return (f"继续「{topic}」专项："
                        f"`python3 tools/tutor.py --level {lid} --topic {topic}`")
    lid = pick_level(st)
    return f"建议练关卡 **{lid}**：`python3 tools/tutor.py --level {lid}`"


def _session_errors(row):
    if row.get("right") == row.get("n"):
        return "—"
    details = row.get("details")
    if not isinstance(details, list):
        return "旧记录未保存"
    stage_names = {
        "tianpan": "天地盘", "sike": "四课", "zeike": "贼克",
        "keshi": "课体", "chuan": "三传", "tianjiang": "天将",
    }
    errors = []
    for index, detail in enumerate(details, 1):
        if detail.get("clean"):
            continue
        stages = "、".join(dict.fromkeys(
            stage_names.get(item.get("stage"), str(item.get("stage")))
            for item in detail.get("mistakes", [])
        )) or "未保存"
        errors.append(f"第{index}题：{stages}")
    return "；".join(errors) or "旧记录未保存"


def write_back(st):
    lines = ["---", "tags: [掌握度/训练]", "---", "",
             "# 训练记录", "",
             "> 本文件由 `tools/tutor.py` 自动生成，不要手改。",
             f"> 最后更新：{datetime.now():%Y-%m-%d %H:%M}", "",
             "## 已学与当前", "",
             "| 学习单元 | 训练范围 | 最近 12 题 | 白话复述 | 状态 |",
             "| :--- | :--- | :---: | :---: | :---: |"]
    l1 = lv_state(st, 1)
    for topic in LEVEL1_TOPICS:
        ts = topic_state(l1, topic)
        lines.append(f"| {topic} | 关卡 1 单项 | {_recent_score(ts['hist'])} | "
                     f"{'✅' if ts.get('teachback') else '—'} | {_topic_status(ts)} |")
    mh = l1["mixed"]["hist"]
    lines.append(f"| 地基混合验收 | 关卡 1 综合 | {_recent_score(mh)} | — | "
                 f"{'✅ 达标' if score_ready(l1['mixed']) else '🔒 未开放' if not all(topic_passed(l1, t) for t in LEVEL1_TOPICS) else '🔸 待练'} |")
    for lid in (2, 3):
        level = LV[lid]
        state = lv_state(st, lid)
        waived = st.get("progression_waivers", {}).get(str(lid))
        score = (f"{waived.get('date')} 完成 12 题，分数遗失"
                 if waived and not state["hist"] else _recent_score(state["hist"]))
        lines.append(
            f"| {level['name']} | 关卡 {lid} 完整 | {score} | "
            f"{'✅' if state.get('teachback') else '—'} | {_level_status(st, level)} |"
        )
    l4 = lv_state(st, 4)
    for topic in LEVEL4_TOPICS:
        ts = topic_state(l4, topic)
        lines.append(f"| {topic} | 关卡 4 前置单项 | {_recent_score(ts['hist'])} | "
                     f"{'✅' if ts.get('teachback') else '—'} | {_topic_status(ts)} |")

    lines += ["", "## 后续完整关卡", "",
              "> 单项成绩不冒充完整关卡成绩；未教学内容不提前开放。",
              "",
              "| 关卡 | 完整范围 | 完整关卡成绩 | 状态 |",
              "| :---: | :--- | :---: | :---: |"]
    for level in LEVELS[3:]:
        state = lv_state(st, level["id"])
        note = ""
        if level["id"] == 4 and any(
            topic_state(state, topic)["hist"] for topic in LEVEL4_TOPICS
        ):
            note = "（已有前置分项记录）"
        lines.append(
            f"| {level['id']} | {level['name']} | {_recent_score(state['hist'])} | "
            f"{_level_status(st, level)}{note} |"
        )

    tot = sum(len(lv_state(st, l['id'])['hist']) for l in LEVELS)
    tot += sum(len(topic_state(l4, topic)["hist"]) for topic in LEVEL4_TOPICS)
    unscored = st.get("unscored_sessions", [])
    unscored_n = sum(row["n"] for row in unscored)
    lines += ["", "## 训练流水", "",
              f"累计计分 **{tot}** 题；未计分完成 **{unscored_n}** 题；"
              f"待复现错题 **{len(st['wrong'])}** 条。", "",
              "| 日期 | 训练项 | 成绩 | 错误阶段 | 来源 |",
              "| :---: | :--- | :---: | :--- | :--- |"]
    for row in st.get("sessions", [])[-10:]:
        lid = row.get("level")
        item = row.get("topic") or (
            LV[lid]["name"] if isinstance(lid, int) and lid in LV else str(lid)
        )
        lines.append(
            f"| {row.get('date', '—')} | {item} | "
            f"{row.get('right', 0)}/{row.get('n', 0)} | {_session_errors(row)} | "
            f"{row.get('source', '终端训练器')} |"
        )
    if unscored:
        lines += ["", "## 未计分完成记录", "",
                  "| 日期 | 关卡 | 题数 | 来源 | 说明 |",
                  "| :---: | :---: | :---: | :--- | :--- |"]
        for row in unscored:
            lines.append(
                f"| {row['date']} | {row['level']} | {row['n']} | "
                f"{row['source']} | {row['note']} |"
            )
    lines += ["",
              "## 下一步", "",
              _next_step(st), "",
              "错题复现：`python3 tools/tutor.py --review`", ""]
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text("\n".join(lines), "utf-8")

    rows = ["| 编号 | 题目 | 原因 | 诊断 | 下次复现 | 连对 |",
            "| ---: | :--- | :--- | :--- | :---: | :---: |"]
    for i, w in enumerate(st["wrong"], 1):
        reasons = "＋".join(w.get("reasons", ["待归因"]))
        diagnosis = w.get("diagnosis") or "待 agent 归因"
        rows.append(f"| {i} | 关{w['level']}｜{w['q']}（答 `{w['given']}`，"
                    f"正解 `{w['ans']}`） | {reasons} | {diagnosis} | "
                    f"{w['due']} | {w.get('streak', 0)} |")
    archive_rows = ["| 题目 | 原因 | 退出原因 | 归档日 |",
                    "| :--- | :--- | :--- | :---: |"]
    for w in reversed(st.get("wrong_archive", [])):
        archive_rows.append(
            f"| 关{w['level']}｜{w['q']} | "
            f"{'＋'.join(w.get('reasons', []))} | "
            f"{w.get('exit_reason', '')} | {w.get('archived', '')} |"
        )
    block = f"{MARK_B}\n\n### 机器判分错题（tutor 自动维护）\n\n" + \
            "\n".join(rows) + "\n\n### 已归档（保留审计记录）\n\n" + \
            "\n".join(archive_rows) + f"\n\n{MARK_E}"
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
        ready = practice_ready(s, l["id"])
        done = final_passed(s, l["id"])
        waived = str(l["id"]) in st.get("progression_waivers", {})
        if l["id"] == 1:
            summary = "　".join(
                f"{name}:{sum(topic_state(s, name)['hist'][-PASS_WINDOW:])}/12"
                if len(topic_state(s, name)["hist"]) >= PASS_WINDOW
                else f"{name}:{len(topic_state(s, name)['hist'])}/12题"
                for name in LEVEL1_TOPICS
            )
            print(f"  1. {pad(l['name'], 26)} 旧制{len(h)}题｜{summary}")
        else:
            bar = "█" * int(r * 10) + "·" * (10 - int(r * 10)) if h else "·" * 10
            print(f"  {l['id']}. {pad(l['name'], 26)} {bar} {r * 100:3.0f}%  "
                  f"{len(h):>3}题  "
                  f"{'✅ 过关' if done else '⚠ 未计分完成·不阻断' if waived else '🗣 待复述' if ready else ''}")
    due = [w for w in st["wrong"] if w.get("due", "") <= date.today().isoformat()]
    print("─" * 62)
    print(f"  待复现错题 {len(due)} / {len(st['wrong'])} 条")
    print(f"  建议下一关：{pick_level(st)}\n")


def show_wrong_list(st):
    print("\n活跃错题")
    print("─" * 62)
    for i, w in enumerate(st["wrong"], 1):
        reasons = "＋".join(w.get("reasons", ["待归因"]))
        print(f"  {i}. [{reasons}] 关{w['level']} {w['q']}")
    print(f"归档 {len(st.get('wrong_archive', []))} 条")


def main(argv=None):
    ap = argparse.ArgumentParser(description="六壬交互式训练器（先教学，后练习）")
    ap.add_argument("--level", "-l", type=int, help="指定关卡 1-9")
    ap.add_argument("--topic", choices=TOPIC_CHOICES,
                    help="分项练习：关卡1寄宫/旬空/遁干，"
                         "关卡4贼克/比用/贼克＋比用")
    ap.add_argument("--n", type=int, default=PASS_WINDOW,
                    help=f"本轮题量（默认 {PASS_WINDOW}，与达标窗口对齐：一轮跑完即可判定）")
    ap.add_argument("--review", action="store_true", help="只做到期错题（跨关卡，重问原题）")
    ap.add_argument("--weak", choices=ERROR_REASONS,
                    help="按已归因的错误原因做 3-5 道变式训练")
    ap.add_argument("--wrong-list", action="store_true", help="列出活跃错题及编号")
    ap.add_argument("--classify-wrong", type=int, metavar="N",
                    help="按编号给错题归因（配合 --reason）")
    ap.add_argument("--archive-wrong", type=int, metavar="N",
                    help="按编号归档错题（保留审计记录）")
    ap.add_argument("--reason", action="append", choices=ERROR_REASONS,
                    help="错误原因，可重复指定")
    ap.add_argument("--note", default="", help="错误诊断或归档说明")
    ap.add_argument("--teachback-pass", type=int, metavar="LEVEL",
                    help="仅供 agent：白话复述验收通过后记录")
    ap.add_argument("--force", action="store_true", help="配合 --review：不管到期日全刷")
    ap.add_argument("--status", action="store_true", help="看进度")
    ap.add_argument("--list", action="store_true", help="列关卡")
    ap.add_argument("--seed", type=int, help="固定随机种子（复现题目）")
    ap.add_argument("--yes", action="store_true",
                    help="确认已完成教学，跳过训练前交互确认")
    a = ap.parse_args(argv)

    st = load_state()
    if a.list:
        for l in LEVELS:
            print(f"  {l['id']}. {l['name']}（阶段 {l['stage']}）→ 六壬vault/{l['card']}")
        return 0
    if a.status:
        show_status(st)
        return 0
    if a.wrong_list:
        show_wrong_list(st)
        return 0
    if a.classify_wrong is not None or a.archive_wrong is not None:
        index = a.classify_wrong if a.classify_wrong is not None else a.archive_wrong
        reasons = a.reason or ["待归因"]
        try:
            classify_wrong(
                st, index, reasons, a.note, archive=a.archive_wrong is not None
            )
        except ValueError as e:
            print(e)
            return 2
        save_state(st)
        write_back(st)
        print(f"错题 {index} 已{'归档' if a.archive_wrong is not None else '归因'}。")
        return 0
    if a.teachback_pass is not None:
        lid = a.teachback_pass
        if lid not in LV:
            print(f"没有关卡 {lid}。用 --list 看。")
            return 2
        s = lv_state(st, lid)
        if a.topic:
            if not ((lid == 1 and a.topic in LEVEL1_TOPICS)
                    or (lid == 4 and a.topic in LEVEL4_TOPICS)):
                print("该关卡不支持这个 --topic。")
                return 2
            ts = topic_state(s, a.topic)
            if not score_ready(ts):
                print(f"关卡 {lid}「{a.topic}」专项尚未达到 "
                      f"{PASS_CORRECT}/{PASS_WINDOW}，不能记录复述通过。")
                return 2
            ts["teachback"] = True
            ts["passed"] = True
            msg = f"关卡 {lid}「{a.topic}」：专项练习 + 白话复述通过。"
        else:
            if not practice_ready(s, lid):
                print(f"关卡 {lid} 的练习尚未达标，不能记录整关复述通过。")
                return 2
            s["teachback"] = True
            s["passed"] = True
            msg = f"关卡 {lid}：练习达标 + 白话复述验收通过，最终过关。"
        save_state(st)
        write_back(st)
        print(msg)
        return 0

    if a.weak:
        rng = random.Random(a.seed)
        lid = None
        r, n = run_weak(a.weak, a.n or 5, st, rng)
    elif a.review:
        lid = None
        r, n = run_review(a.n or 10, st, force=a.force)
    else:
        rng = random.Random(a.seed)
        lid = a.level or pick_level(st)
        if lid not in LV:
            print(f"没有关卡 {lid}。用 --list 看。")
            return 2
        if a.topic and not ((lid == 1 and a.topic in LEVEL1_TOPICS)
                            or (lid == 4 and a.topic in LEVEL4_TOPICS)):
            print("该关卡不支持这个 --topic。")
            return 2
        r, n = run(lid, a.n or 10, st, rng, topic=a.topic,
                   assume_learned=a.yes)

    if n:
        st["sessions"].append({"date": date.today().isoformat(),
                               "level": lid or "review", "right": r, "n": n})
        print(f"\n{'=' * 62}\n本轮 {r}/{n}　正确率 {r / n * 100:.0f}%")
        if lid:
            s = lv_state(st, lid)
            if a.topic:
                ts = topic_state(s, a.topic)
                if score_ready(ts):
                    print(f"「{a.topic}」专项达标（至少 "
                          f"{PASS_CORRECT}/{PASS_WINDOW}），回到 agent 做该专项白话复述。")
                else:
                    print(f"「{a.topic}」专项未达标；先回到 agent 讲解错题，"
                          "不要继续机械刷题。")
            elif practice_ready(s, lid):
                print(f"关卡 {lid} 练习达标，但尚未最终过关。")
                print("回到 agent 做整关白话复述验收。")
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
