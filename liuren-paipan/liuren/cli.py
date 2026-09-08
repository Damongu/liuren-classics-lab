"""命令行入口：python -m liuren <子命令>

子命令
  pan    排盘（抽象：日+时+将／某加某；真实：时刻+地点）
  find   在 720 课里检索靶盘，并可落到真实时空
  stat   课式分布（720 结构频率 / 真实时间频率）
  ke     列出某日十二局（同一日干支的全部盘）
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import search as S
from .plate import Options, from_ganzhi, from_jia, from_time
from .render import render_card, render_text, to_json
from .timeutil import find_days

DEFAULT_VAULT = Path(__file__).resolve().parents[2] / "六壬vault"


def build_opts(a) -> Options:
    return Options(guiren=a.guiren, daynight=a.daynight,
                   day_boundary=a.day_boundary, shehai_class=a.shehai_class,
                   shehai_bihe=not a.no_shehai_bihe)


def add_opt_args(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("口径开关")
    g.add_argument("--guiren", default="common", choices=["common", "book"],
                   help="贵人表：common=通行（默认，底本课例内证）｜book=底本先天贵神歌")
    g.add_argument("--daynight", default="sun", choices=["sun", "fixed"],
                   help="昼夜界：sun=实际日出日入（默认）｜fixed=卯申界")
    g.add_argument("--day-boundary", default="zi23", choices=["zi23", "midnight"],
                   help="日界：zi23=子时换日（默认）｜midnight=子夜换日")
    g.add_argument("--shehai-class", default="gong", choices=["gong", "shen"],
                   help="涉害孟仲季按：gong=所临地盘宫（默认）｜shen=上神本身")
    g.add_argument("--no-shehai-bihe", action="store_true",
                   help="关闭涉害比用格覆盖（走纯涉害）")


def cmd_pan(a) -> int:
    opts = build_opts(a)
    if a.time:
        clock = datetime.strptime(a.time, "%Y-%m-%d %H:%M")
        p = from_time(clock, a.place, lon=a.lon, lat=a.lat, tz=a.tz, opts=opts)
    elif a.jia:
        t, d = a.jia.split("加") if "加" in a.jia else (a.jia[0], a.jia[1])
        p = from_jia(a.day, t, d, shi=a.shi, daynight=a.dn, opts=opts)
    elif a.day and a.shi and a.jiang:
        p = from_ganzhi(a.day, a.shi, a.jiang, daynight=a.dn, opts=opts)
    else:
        print("用法：--time '2026-09-07 14:30' --place 成都\n"
              "  或 --day 甲子 --shi 卯 --jiang 子\n"
              "  或 --day 甲辰 --jia 戌加寅", file=sys.stderr)
        return 2
    if a.json:
        print(to_json(p))
    else:
        print(render_text(p))
    if a.card:
        vault = Path(a.card) if a.card != "auto" else DEFAULT_VAULT
        d = vault / "30-课例" if (vault / "30-课例").exists() else vault
        d.mkdir(parents=True, exist_ok=True)
        name = f"{p.day_gz}日{p.shi}时{p.jiang}将-{p.keshi}{p.keshi_sub}.md"
        (d / name).write_text(render_card(p, question=a.question or ""),
                              encoding="utf-8")
        print(f"\n课例卡已写入：{d / name}")
    return 0


def cmd_find(a) -> int:
    opts = build_opts(a)
    rows = S.enumerate720(opts)
    rows = S.filter_courses(rows, keshi=a.keshi, sub=a.sub, gan=a.gan, zhi=a.zhi,
                            day_gz=a.day, chuan_has=a.chuan_has, k=a.k,
                            kong_in_chuan=(None if a.kong is None else a.kong == "y"))
    print(f"命中 {len(rows)} 课（共 720）")
    for r in rows[:a.limit]:
        line = f"  {r.desc}"
        if a.realize:
            y = a.year
            hits = S.realize(r.day_gz, r.k, datetime(y, 1, 1), datetime(y + 1, 1, 1),
                             a.place, lon=a.lon, lat=a.lat, tz=a.tz, opts=opts,
                             limit=a.realize)
            line += "".join(f"\n      → {c:%Y-%m-%d %H:%M} {s}时 {j}将"
                            for c, s, j in hits) or "\n      → 该年无真实时刻"
        print(line)
    if len(rows) > a.limit:
        print(f"  …… 余 {len(rows) - a.limit} 课，用 --limit 放开")
    return 0


def cmd_stat(a) -> int:
    opts = build_opts(a)
    if a.real:
        y = a.year
        cnt = S.real_frequency(datetime(y, 1, 1), datetime(y + 1, 1, 1), a.place,
                               lon=a.lon, lat=a.lat, tz=a.tz, opts=opts)
        total = sum(cnt.values())
        print(f"{y} 年 {a.place or '自定义地点'} 真实时辰共 {total} 个")
    else:
        cnt = S.keshi_distribution(opts=opts) if not a.sub else \
            S.sub_distribution(opts=opts)
        total = sum(cnt.values())
        print(f"720 课结构分布（合计 {total}）")
    for k, v in cnt.most_common():
        print(f"  {k:<12}{v:>6}  {v / total:6.2%}")
    return 0


def cmd_ke(a) -> int:
    opts = build_opts(a)
    rows = S.filter_courses(S.enumerate720(opts), day_gz=a.day)
    print(f"{a.day}日十二局")
    for r in rows:
        print(f"  第{r.k:>2}局（将在时前{r.k}位）{r.keshi}·{r.sub}  三传 {''.join(r.chuan)}")
    if a.year:
        days = find_days(a.day, datetime(a.year, 1, 1), datetime(a.year + 1, 1, 1),
                         opts.day_boundary)
        print(f"  {a.year} 年该日干支：" + "、".join(f"{d:%m-%d}" for d in days))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser("liuren", description="六壬排盘器（算法现代·规则宋制）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pan", help="排盘")
    p.add_argument("--time", help="钟表时 '2026-09-07 14:30'（真实时空排盘）")
    p.add_argument("--place", help="地点，如 成都/北京/开封")
    p.add_argument("--lon", type=float), p.add_argument("--lat", type=float)
    p.add_argument("--tz", type=float)
    p.add_argument("--day", help="日干支，如 甲子")
    p.add_argument("--shi", help="占时支")
    p.add_argument("--jiang", help="月将支")
    p.add_argument("--jia", help="某加某，如 戌加寅")
    p.add_argument("--dn", default="昼", choices=["昼", "夜"], help="抽象排盘的昼夜")
    p.add_argument("--json", action="store_true")
    p.add_argument("--card", nargs="?", const="auto",
                   help="写 Obsidian 课例卡，缺省写入 ../六壬vault/30-课例")
    p.add_argument("--question", help="课例卡里的作业题")
    add_opt_args(p)
    p.set_defaults(f=cmd_pan)

    p = sub.add_parser("find", help="在 720 课里检索靶盘")
    p.add_argument("--keshi", help="课式，如 涉害/元首/昴星/别责/八专/伏吟/返吟/遥克/重审/知一")
    p.add_argument("--sub", help="细分，如 见机/察微/缀瑕/蒿矢/弹射")
    p.add_argument("--gan"), p.add_argument("--zhi"), p.add_argument("--day")
    p.add_argument("--k", type=int, help="局：月将在时前几位")
    p.add_argument("--chuan-has", help="三传含某支")
    p.add_argument("--kong", choices=["y", "n"], help="三传是否带空亡")
    p.add_argument("--limit", type=int, default=30)
    p.add_argument("--realize", type=int, nargs="?", const=2, default=0,
                   help="落到真实时空，给出前 N 个时刻")
    p.add_argument("--year", type=int, default=datetime.now().year)
    p.add_argument("--place"), p.add_argument("--lon", type=float)
    p.add_argument("--lat", type=float), p.add_argument("--tz", type=float)
    add_opt_args(p)
    p.set_defaults(f=cmd_find)

    p = sub.add_parser("stat", help="课式分布")
    p.add_argument("--sub", action="store_true", help="按细分统计")
    p.add_argument("--real", action="store_true", help="按真实时间频率统计")
    p.add_argument("--year", type=int, default=datetime.now().year)
    p.add_argument("--place"), p.add_argument("--lon", type=float)
    p.add_argument("--lat", type=float), p.add_argument("--tz", type=float)
    add_opt_args(p)
    p.set_defaults(f=cmd_stat)

    p = sub.add_parser("ke", help="列某日十二局")
    p.add_argument("--day", required=True)
    p.add_argument("--year", type=int, help="并列出该年此日干支的日期")
    add_opt_args(p)
    p.set_defaults(f=cmd_ke)

    a = ap.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    raise SystemExit(main())
