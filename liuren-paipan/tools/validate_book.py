#!/usr/bin/env python3
"""用底本自身的课例校验排盘器。

原理：天地盘是刚体旋转，书中"某加某为用"一句即确定整盘。
所以从每条课例里抽出（日干支、天盘X加地盘Y），就能反过来检查：
  1. 引擎算出的初传是否等于 X（发用对不对）
  2. 引擎判定的课式是否等于该条所属的课体名（宗门判得对不对）

用法：
  python3 tools/validate_book.py --vault ../六壬vault
  python3 tools/validate_book.py --vault ../六壬vault --sweep
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from liuren import Options, from_jia  # noqa: E402

Z = "子丑寅卯辰巳午未申酉戌亥"
G = "甲乙丙丁戊己庚辛壬癸"

# 例："甲子日卯时子将占……午加酉为用"／"乙未日卯加未"／"壬寅日巳加申发用"
RE_DAY = re.compile(rf"([{G}][{Z}])日")
RE_JIA = re.compile(rf"([{Z}])加([{Z}])(?=[^。；]{{0,6}}?(?:为用|发用|为初|为发用|用神|为用神))")
RE_JIA_LOOSE = re.compile(rf"([{Z}])加([{Z}])")

# 九宗门十课体：note 标题 -> 引擎课式名
KETI_MAP = {
    "元首课": "元首", "重审课": "重审", "知一课": "知一", "涉害课": "涉害",
    "遥克课": "遥克", "昴星课": "昴星", "别责课": "别责", "八专课": "八专",
    "伏吟课": "伏吟", "返吟课": "返吟",
}


def extract(text: str):
    """抽出 (日干支, 天盘支, 地盘支, 置信度)。

    置信度：
      强 —— "某加某"紧跟在日干支之后 10 字内，且 8 字内出现"为用/发用/为初"
      中 —— 紧跟在日干支之后 10 字内（多为"乙未日卯加未"式简写）
      弱 —— 只在 60 字窗口内找到带"为用"的加字句
      讹 —— 出现在订讹语境（时师／妄用／殊不知／非涉害），底本自己说这是错法
    """
    out = []
    for m in RE_DAY.finditer(text):
        gz = m.group(1)
        tail = text[m.end(): m.end() + 60]
        # 订讹语境：底本在转述"时师"错法并加以驳正，这里的"某加某为用"是错说，
        # 不能当标准答案。例：第九十三法"又如甲辰日干上戌，时师皆以戌加寅涉害为
        # 用……殊不知乃择比为用，非涉害也"。标为"讹"，默认不参与命中率统计。
        ctx = text[max(0, m.start() - 40): m.end() + 60]
        if re.search(r"时师|妄用|岂可|殊不知|非涉害|错误", ctx):
            near0 = RE_JIA_LOOSE.search(tail[:12])
            if near0:
                out.append((gz, near0.group(1), near0.group(2), "讹"))
            continue
        near = RE_JIA_LOOSE.search(tail[:12])
        if near:
            after = tail[near.end(): near.end() + 8]
            conf = "强" if re.search(r"为用|发用|为初|用神", after) else "中"
            out.append((gz, near.group(1), near.group(2), conf))
            continue
        anchored = RE_JIA.search(tail)
        if anchored:
            out.append((gz, anchored.group(1), anchored.group(2), "弱"))
    return out


def scan(vault: Path):
    cases = []
    for ce in sorted((vault / "10-底本" / "六壬大全").iterdir()):
        if not ce.is_dir():
            continue
        for md in sorted(ce.glob("*.md")):
            body = md.read_text(encoding="utf-8")
            # 只取原刻正文，剔除今注剥离区
            body = body.split("## 今注剥离区")[0]
            title = md.stem.split("-", 1)[-1]
            for gz, t, d, conf in extract(body):
                cases.append({"册": ce.name, "篇": title, "日": gz, "天": t, "地": d,
                              "置信": conf, "期望课式": KETI_MAP.get(title)})
    return cases


def run(cases, opts: Options, conf: tuple = ("强", "中", "弱")):
    cases = [c for c in cases if c["置信"] in conf]
    stat = Counter()
    bad_chuan, bad_keshi = [], []
    for c in cases:
        try:
            p = from_jia(c["日"], c["天"], c["地"], opts=opts)
        except Exception as e:                     # noqa: BLE001
            stat["异常"] += 1
            bad_chuan.append({**c, "得": f"异常 {e}"})
            continue
        stat["总"] += 1
        if p.chuan[0] == c["天"]:
            stat["发用对"] += 1
        else:
            bad_chuan.append({**c, "得": f"初传{p.chuan[0]}／{p.keshi}·{p.keshi_sub}"})
        if c["期望课式"]:
            stat["有课体标签"] += 1
            if p.keshi == c["期望课式"]:
                stat["课式对"] += 1
            else:
                bad_keshi.append({**c, "得": f"{p.keshi}·{p.keshi_sub}"})
    return stat, bad_chuan, bad_keshi


def report(cases, opts, verbose=True, conf=("强", "中", "弱")):
    stat, bad_chuan, bad_keshi = run(cases, opts, conf)
    n = stat["总"] or 1
    print(f"课例 {stat['总']} 条｜发用命中 {stat['发用对']}／{stat['总']} "
          f"= {stat['发用对'] / n:.1%}")
    if stat["有课体标签"]:
        m = stat["有课体标签"]
        print(f"其中带课体标签 {m} 条｜课式命中 {stat['课式对']}／{m} "
              f"= {stat['课式对'] / m:.1%}")
    if verbose:
        by_pian = defaultdict(lambda: [0, 0])
        for c in cases:
            by_pian[c["篇"]][0] += 1
        for b in bad_chuan:
            by_pian[b["篇"]][1] += 1
        print("\n发用不合的篇（前 15）：")
        rows = sorted(((k, v[0], v[1]) for k, v in by_pian.items() if v[1]),
                      key=lambda x: -x[2])[:15]
        for k, tot, bad in rows:
            print(f"  {k:<12} {bad}/{tot}")
        print("\n发用不合样例（前 12）：")
        for b in bad_chuan[:12]:
            print(f"  {b['册']}·{b['篇']}：{b['日']}日 {b['天']}加{b['地']} -> {b['得']}")
        if bad_keshi:
            print("\n课式不合样例（前 12）：")
            for b in bad_keshi[:12]:
                print(f"  {b['篇']}：{b['日']}日 {b['天']}加{b['地']} -> {b['得']}")
    return stat


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault", default="../六壬vault")
    ap.add_argument("--sweep", action="store_true", help="口径开关全组合对比")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    cases = scan(Path(a.vault))
    dist = Counter(c["置信"] for c in cases)
    print(f"从底本抽出课例 {len(cases)} 条（置信度 "
          f"{'、'.join(f'{k}{v}' for k, v in dist.most_common())}）\n")
    if not a.sweep:
        for conf in (("强",), ("强", "中"), ("强", "中", "弱")):
            print(f"--- 置信度 {'+'.join(conf)} ---")
            report(cases, Options(), verbose=(not a.quiet and len(conf) == 2), conf=conf)
            print()
        return
    print("=== 口径开关对比（看哪套口径更合底本课例）===")
    for gr in ("common", "book"):
        for sc in ("gong", "shen"):
            for br in ("+4", "-4"):
                o = Options(guiren=gr, shehai_class=sc, bieze_rou=br)
                s, _, _ = run(cases, o, ("强", "中"))
                n = s["总"] or 1
                m = s["有课体标签"] or 1
                print(f"贵人{gr:<7}涉害{sc:<5}别责{br:<3}｜发用 "
                      f"{s['发用对']}/{s['总']}={s['发用对'] / n:.1%}｜"
                      f"课式 {s['课式对']}/{s['有课体标签']}={s['课式对'] / m:.1%}")


if __name__ == "__main__":
    main()
