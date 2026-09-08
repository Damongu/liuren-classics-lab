"""底本内证自检：把《六壬大全》里"可数的自述"拿来验算法。

这些数字是底本自己给的，能数出来就说明我们的取用规则和底本同构；
数不出来就是一条待查（不许悄悄改代码去凑）。
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from liuren import Options, enumerate720  # noqa: E402
from liuren.ganzhi import JIGONG  # noqa: E402

CHECKS = []


def check(name, got, want, src, note=""):
    ok = got == want
    CHECKS.append((ok, name, got, want, src, note))


def main() -> int:
    rows = enumerate720(Options())
    ks = Counter(r.keshi for r in rows)
    days = {k: sorted({r.day_gz for r in rows if r.keshi == k}) for k in ks}

    check("720 课总数", len(rows), 720,
          "第六册元首课：六壬总计七百二十课", "60 日干支 × 12 局")
    check("元首课数", ks["元首"], 115,
          "第六册元首课：内合元首课凡一百一十有五")
    check("别责课数", ks["别责"], 9,
          "第六册别责课订讹：戊午、戊辰与丙辰…辛丑、辛未各二日…丁酉…辛酉",
          "戊辰 戊午 丙辰 丁酉 辛酉 各1 + 辛丑 辛未 各2 = 9")
    check("别责日", days["别责"],
          sorted(["丙辰", "丁酉", "戊午", "戊辰", "辛丑", "辛未", "辛酉"]),
          "同上")
    check("干支同位日（八专日）数",
          len({d for d in {r.day_gz for r in rows} if JIGONG[d[0]] == d[1]}), 5,
          "第六册八专课：八专日有五")
    check("八专日（无克者）", days["八专"], sorted(["甲寅", "庚申", "己未", "丁未"]),
          "第六册八专课：除癸丑日俱有克，无克者甲寅、庚申…己未、丁未")
    check("伏吟课数", ks["伏吟"], 60, "伏吟即将加时同位，60 日各一局")
    check("返吟课数", ks["返吟"], 60, "返吟即将加时冲位，60 日各一局")
    check("独足格独一无二",
          sum(1 for r in rows if r.day_gz == "己未" and r.keshi == "八专"
              and len(set(r.chuan)) == 1), 1,
          "第十一册第八十一法：于七百二十课中，止有此一课，故名独足",
          "己未日三传皆日上神")

    bad = 0
    print("底本内证自检\n" + "=" * 78)
    for ok, name, got, want, src, note in CHECKS:
        print(f"{'✅' if ok else '❌'} {name}：算得 {got}｜底本 {want}")
        print(f"     底本：{src}")
        if note:
            print(f"     说明：{note}")
        bad += (not ok)
    print("=" * 78)
    print(f"通过 {len(CHECKS) - bad}/{len(CHECKS)}")
    if bad:
        print("\n未通过项 → 写入 vault 70-待查/，禁止改代码凑数。")
    print("\n课式分布（本引擎）")
    for k, v in ks.most_common():
        print(f"  {k:<6}{v:>5}  {v / 720:6.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
