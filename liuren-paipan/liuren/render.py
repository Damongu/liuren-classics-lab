"""输出：文本盘、JSON、Obsidian 课例卡。"""
from __future__ import annotations

import json
import unicodedata

from .ganzhi import ZHI, ZHI_SHEN, xun_shou
from .plate import Plate

# 地盘固定方位（四孟居四角），行内自左至右
GRID = [
    ["巳", "午", "未", "申"],
    ["辰", None, None, "酉"],
    ["卯", None, None, "戌"],
    ["寅", "丑", "子", "亥"],
]
CW = 8  # 单格显示宽度（半角列数）


def dw(s: str) -> int:
    """字符串显示宽度（东亚全角计 2）。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def pad(s: str, width: int, align: str = "<") -> str:
    space = max(0, width - dw(s))
    if align == "<":
        return s + " " * space
    if align == ">":
        return " " * space + s
    left = space // 2
    return " " * left + s + " " * (space - left)


def _cell(p: Plate, di: str) -> tuple[str, str]:
    t = p.tian[di]
    mark = "空" if p.is_kong(t) else ""
    return pad(f"{p.jiang_on(t)}{t}{mark}", CW, "^"), pad(di, CW, "^")


def render_plate(p: Plate) -> str:
    """四行四列的天地盘：每格上行为天将＋天盘神，下行为地盘宫。"""
    center = [
        f"{p.day_gz}日　{p.shi}时　{p.jiang}将({ZHI_SHEN[p.jiang]})",
        f"{p.daynight}贵{p.guiren}　{p.guiren_dir}行　旬空{p.kong[0]}{p.kong[1]}",
        f"{p.keshi}·{p.keshi_sub}",
        f"三传　{'→'.join(p.chuan)}",
    ]
    mid_w = CW * 2 + 1
    lines = []
    for r, row in enumerate(GRID):
        cells = [_cell(p, di) for di in row if di is not None]
        if r in (0, 3):
            lines.append("│" + "│".join(c[0] for c in cells) + "│")
            lines.append("│" + "│".join(c[1] for c in cells) + "│")
        else:
            i = (r - 1) * 2
            m1 = center[i] if i < len(center) else ""
            m2 = center[i + 1] if i + 1 < len(center) else ""
            lines.append(f"│{cells[0][0]}│{pad(m1, mid_w, '^')}│{cells[1][0]}│")
            lines.append(f"│{cells[0][1]}│{pad(m2, mid_w, '^')}│{cells[1][1]}│")
    bar = "─" * (CW * 4 + 3)
    return "\n".join(["┌" + bar + "┐"] + lines + ["└" + bar + "┘"])


def render_kes(p: Plate) -> str:
    """四课，依古式自右向左排（第一课在右）。"""
    heads, ups, lows = [], [], []
    for k in reversed(p.kes):
        heads.append(f"{'一二三四'[k.idx - 1]}课")
        ups.append(f"{k.up}{p.jiang_on(k.up)}")
        lows.append(k.low if k.idx != 1 else f"{k.low}({k.low_zhi})")

    def row(cells):
        return "".join(pad(c, 10) for c in cells)

    return "\n".join(["四课（右起第一课）",
                      "  " + row(heads), "  " + row(ups), "  " + row(lows)])


def render_chuan(p: Plate) -> str:
    out = ["三传"]
    for d in p.chuan_detail():
        dun = d["遁干"] or "—"
        kong = "　○空亡" if d["空亡"] else ""
        out.append(f"  {d['位']}　{d['支']}（{d['神']}）{pad(d['将'], 5)}"
                   f"遁干{dun}　临{d['临宫']}　{d['五行']}　对日干{d['对日干']}{kong}")
    return "\n".join(out)


def render_meta(p: Plate) -> str:
    lines = ["口径与依据"]
    if p.when and p.place:
        lines.append(f"  时空　{p.when:%Y-%m-%d %H:%M} {p.place.name}"
                     f"（{p.place.lon:.3f}E {p.place.lat:.3f}N，行政时区 UTC{p.place.tz:+g}）")
        lines.append(f"  地方平太阳时　{p.place.lmt_offset_minutes:+.1f} 分钟，"
                     f"不做均时差修正")
    lines.append(f"  月将　{p.jiang_source}")
    lines.append(f"  昼夜　{p.daynight}（{p.daynight_why}）")
    lines.append(f"  贵人　{p.opts.guiren}表：{p.gan}日{p.daynight}贵在{p.guiren}，"
                 f"临地盘{p.di[p.guiren]}故{p.guiren_dir}行")
    lines.append(f"  日界　{p.opts.day_boundary}【规格待考项】")
    lines.append(f"  旬首　{xun_shou(p.day_gz)}旬，旬空 {p.kong[0]}{p.kong[1]}")
    if p.reason:
        lines.append("  取用　" + "；".join(p.reason))
    for d in p.divergences:
        lines.append(f"  ⚠ 分歧　{d['规则']}：本盘取{d['本盘取']}，另一说取{d['另一说']}")
        lines.append(f"      本盘依据　{d['依据']}")
        lines.append(f"      另说依据　{d['另说依据']}")
    return "\n".join(lines)


def render_text(p: Plate) -> str:
    return "\n\n".join([render_plate(p), render_kes(p), render_chuan(p), render_meta(p)])


def to_dict(p: Plate) -> dict:
    return {
        "日干支": p.day_gz,
        "占时": p.shi,
        "月将": p.jiang,
        "局": f"{p.jiang}加{p.shi}",
        "昼夜": p.daynight,
        "课式": p.keshi,
        "课式细分": p.keshi_sub,
        "三传": list(p.chuan),
        "四课": [{"课": k.idx, "下": k.low, "下宫": k.low_zhi, "上": k.up,
                  "关系": k.rel, "将": p.jiang_on(k.up)} for k in p.kes],
        "天盘": {di: p.tian[di] for di in ZHI},
        "天将": {t: p.jiang_on(t) for t in ZHI},
        "贵人": {"支": p.guiren, "顺逆": p.guiren_dir, "表": p.opts.guiren},
        "旬空": list(p.kong),
        "三传详": p.chuan_detail(),
        "取用依据": p.reason,
        "分歧": p.divergences,
        "时空": ({"时刻": p.when.strftime("%Y-%m-%d %H:%M"), "地点": p.place.name,
                  "经度": p.place.lon, "纬度": p.place.lat, "时区": p.place.tz}
                 if p.when and p.place else None),
        "月将依据": p.jiang_source,
        "昼夜依据": p.daynight_why,
    }


def to_json(p: Plate) -> str:
    return json.dumps(to_dict(p), ensure_ascii=False, indent=2)


def render_card(p: Plate, *, title: str | None = None, tags: str = "",
                question: str = "", stage: str = "3") -> str:
    """Obsidian 课例卡（可直接落到 30-课例/）。"""
    t = title or f"{p.day_gz}日{p.shi}时{p.jiang}将 {p.keshi}"
    fm = [
        "---",
        f"课式: {p.keshi}", f"细分: {p.keshi_sub}", f"日干支: {p.day_gz}",
        f"占时: {p.shi}", f"月将: {p.jiang}", f"局: {p.jiang}加{p.shi}",
        f"昼夜: {p.daynight}", f"三传: [{', '.join(p.chuan)}]",
        f"贵人表: {p.opts.guiren}", f"日界: {p.opts.day_boundary}",
        "mastery: 生", f"阶段: {stage}",
        f"tags: [课例/{p.keshi}{(', ' + tags) if tags else ''}]",
        "---", "", f"# {t}", "",
    ]
    body = ["## 盘", "```", render_plate(p), "```", "",
            "## 四课三传", "```", render_kes(p), "", render_chuan(p), "```", "",
            "## 口径与依据", "```", render_meta(p), "```", ""]
    if question:
        body += ["## 作业", question, ""]
    body += ["## 我的推演", "", "## 批改", "", "## 追问", ""]
    return "\n".join(fm + body)
