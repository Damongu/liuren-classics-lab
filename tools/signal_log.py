#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对话信号打点器 —— 把「教学过程中的摩擦」变成数据。

为什么需要它：
    tutor.py 只记录「答对没答对」。但真正说明教学方式有问题的证据，几乎全在对话里：
    同一个术语解释了三遍、用户指出 agent 讲错了、复述时才发现前置没教、
    单节拖到两小时。这些信号聊完就消失，下一个会话完全看不见 ——
    结果就是「只有用户记得住问题，只能由用户来指出」。

    本工具让 agent 在**摩擦发生的当场**敲一行命令留痕（成本极低），
    而不是等到收尾靠回忆。retro.py 再从这些留痕里算出该提什么建议。

用法：
    python3 tools/signal_log.py open  --topic 寄宫                # 开一节课
    python3 tools/signal_log.py add --type 卡顿 --topic 寄宫 --note "第三次问天盘神是什么"
    python3 tools/signal_log.py add --type 纠错 --note "用户指出寄宫前置成环"
    python3 tools/signal_log.py close                             # 收课，记时长
    python3 tools/signal_log.py list --days 7                     # 看最近信号
    python3 tools/signal_log.py resolve 3 --note "已插入第0课"     # 标记已处理

打点原则：
    * 宁多勿漏，一条一行，note 写具体现象，不写结论。
    * `纠错` 是最高优先级：用户一旦指出问题，**必须当场打点**，
      retro.py 会强制在本轮生成待确认提案，不允许无声吞掉。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / "六壬vault"
LOG_JSON = VAULT / "60-掌握度" / "_signal_log.json"
LOG_MD = VAULT / "60-掌握度" / "教学互动日志.md"
MARK_B, MARK_E = "<!-- signal:begin -->", "<!-- signal:end -->"

# 信号类型 —— 只收「可观察的现象」，不收主观感受
TYPES = {
    "卡顿": "同一概念需要重复解释，或用户明确表示没跟上",
    "纠错": "用户指出 agent 讲错、算错、流程不对或自相矛盾",
    "重复追问": "同一个点被追问 2 次以上",
    "口径分歧": "用户的答案有文献依据，与程序标准答案不一致",
    "操作摩擦": "命令、输入格式、界面导致时间浪费",
    "前置缺失": "讲到一半才发现依赖尚未教学的概念",
    "图缺失": "纯文字讲不清，需要图或表",
    "跳步": "用户要求跳过某步骤或加快",
    "超时": "单节明显超出 60–90 分钟",
}


def load():
    if LOG_JSON.exists():
        d = json.loads(LOG_JSON.read_text("utf-8"))
    else:
        d = {}
    d.setdefault("signals", [])
    d.setdefault("sessions", [])
    return d


def save(d):
    LOG_JSON.parent.mkdir(parents=True, exist_ok=True)
    LOG_JSON.write_text(json.dumps(d, ensure_ascii=False, indent=2), "utf-8")
    write_md(d)


def cur_session(d):
    """返回当前未收尾的会话；没有就返回 None。"""
    for s in reversed(d["sessions"]):
        if not s.get("end"):
            return s
    return None


def sid_of(d):
    s = cur_session(d)
    return s["id"] if s else "未开课"


# ------------------------------------------------------------------ 命令

def cmd_open(d, args):
    if cur_session(d):
        s = cur_session(d)
        print(f"已有未收尾的会话 {s['id']}（开于 {s['start']}），先 close 再 open。")
        return 1
    today = datetime.now().strftime("%Y-%m-%d")
    n = sum(1 for s in d["sessions"] if s["id"].startswith(today)) + 1
    s = dict(id=f"{today}#{n}", start=datetime.now().strftime("%Y-%m-%d %H:%M"),
             end=None, topic=args.topic or "", minutes=None)
    d["sessions"].append(s)
    save(d)
    print(f"开课 {s['id']}　主题：{s['topic'] or '未指定'}　{s['start']}")
    return 0


def cmd_close(d, args):
    s = cur_session(d)
    if not s:
        print("当前没有开着的会话。")
        return 1
    now = datetime.now()
    s["end"] = now.strftime("%Y-%m-%d %H:%M")
    try:
        start = datetime.strptime(s["start"], "%Y-%m-%d %H:%M")
        s["minutes"] = int((now - start).total_seconds() // 60)
    except ValueError:
        s["minutes"] = None
    save(d)
    print(f"收课 {s['id']}　时长 {s['minutes']} 分钟　"
          f"本节信号 {sum(1 for x in d['signals'] if x.get('session') == s['id'])} 条")
    return 0


def cmd_add(d, args):
    if args.type not in TYPES:
        print(f"未知类型 {args.type}；可选：{'、'.join(TYPES)}")
        return 2
    item = dict(
        ts=datetime.now().strftime("%Y-%m-%d %H:%M"),
        date=datetime.now().strftime("%Y-%m-%d"),
        session=sid_of(d),
        type=args.type,
        topic=args.topic or "",
        note=args.note or "",
        resolved=False,
        resolution="",
    )
    d["signals"].append(item)
    save(d)
    idx = len(d["signals"])
    print(f"#{idx} [{item['type']}] {item['topic'] or '—'}｜{item['note']}")
    if args.type == "纠错":
        print("→ 已记为「纠错」。收尾 retro.py --close 时会强制起草待确认提案。")
    return 0


def cmd_resolve(d, args):
    i = args.index - 1
    if not (0 <= i < len(d["signals"])):
        print(f"编号超范围（共 {len(d['signals'])} 条）")
        return 2
    d["signals"][i]["resolved"] = True
    d["signals"][i]["resolution"] = args.note or "已处理"
    save(d)
    print(f"#{args.index} 已标记处理：{d['signals'][i]['resolution']}")
    return 0


def cmd_list(d, args):
    since = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
    rows = [(i + 1, x) for i, x in enumerate(d["signals"])
            if x["date"] >= since or (args.session and x.get("session") == args.session)]
    if args.unresolved:
        rows = [(i, x) for i, x in rows if not x["resolved"]]
    print(f"\n最近 {args.days} 天信号（{len(rows)} 条）")
    print("─" * 74)
    for i, x in rows:
        flag = " " if x["resolved"] else "!"
        print(f" {flag}#{i:<3} {x['ts']}  [{x['type']:<4}] "
              f"{(x['topic'] or '—'):<8} {x['note']}")
    if not rows:
        print("  （无）")
    s = cur_session(d)
    print("─" * 74)
    print(f"当前会话：{s['id'] + '（进行中）' if s else '未开课'}\n")
    return 0


def cmd_types(d, args):
    print("\n信号类型")
    print("─" * 74)
    for k, v in TYPES.items():
        print(f"  {k:<6} {v}")
    print()
    return 0


# ------------------------------------------------------------------ 回写

def write_md(d):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "---",
        "类型: 教学日志",
        "tags: [掌握度/日志, 流程/信号]",
        "---",
        "",
        "# 教学互动日志",
        "",
        "> 由 `tools/signal_log.py` 自动维护，**不要手改**。",
        f"> 最后更新：{now}",
        "",
        "这里记录的是「教学过程」而不是「答题成绩」。成绩看 [[训练记录]]，",
        "原题看 [[错题队列]]，本页负责回答一个问题：**这节课哪里不顺**。",
        "`tools/retro.py` 按本页数据起草流程改进提案，见 [[教学流程复盘]]。",
        "",
        MARK_B,
        "",
        "## 会话",
        "",
        "| 会话 | 主题 | 开始 | 结束 | 时长(分) | 信号数 |",
        "| :--- | :--- | :--- | :--- | ---: | ---: |",
    ]
    for s in d["sessions"][-20:]:
        cnt = sum(1 for x in d["signals"] if x.get("session") == s["id"])
        lines.append(f"| {s['id']} | {s.get('topic') or '—'} | {s['start']} | "
                     f"{s.get('end') or '进行中'} | {s.get('minutes') if s.get('minutes') is not None else '—'} | {cnt} |")
    if not d["sessions"]:
        lines.append("| — | — | — | — | — | — |")

    # 按类型统计（未处理）
    stat = {}
    for x in d["signals"]:
        if not x["resolved"]:
            stat[x["type"]] = stat.get(x["type"], 0) + 1
    lines += ["", "## 未处理信号统计", "",
              "| 类型 | 条数 | 含义 |", "| :--- | ---: | :--- |"]
    if stat:
        for k in TYPES:
            if stat.get(k):
                lines.append(f"| {k} | {stat[k]} | {TYPES[k]} |")
    else:
        lines.append("| — | 0 | 暂无未处理信号 |")

    lines += ["", "## 明细", "",
              "| 编号 | 时间 | 会话 | 类型 | 概念 | 现象 | 处理 |",
              "| ---: | :--- | :--- | :--- | :--- | :--- | :--- |"]
    for i, x in enumerate(d["signals"], 1):
        note = (x["note"] or "").replace("|", "\\|")
        res = x["resolution"] if x["resolved"] else "未处理"
        lines.append(f"| {i} | {x['ts']} | {x.get('session', '')} | {x['type']} | "
                     f"{x['topic'] or '—'} | {note} | {res} |")
    if not d["signals"]:
        lines.append("| — | — | — | — | — | 暂无 | — |")

    lines += ["", MARK_E, "", "## 关联", "",
              "- [[教学流程复盘]]", "- [[学习画像]]", "- [[训练记录]]",
              "- [[错题队列]]", ""]
    LOG_MD.parent.mkdir(parents=True, exist_ok=True)
    LOG_MD.write_text("\n".join(lines), "utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="对话信号打点器")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("open", help="开一节课")
    p.add_argument("--topic", default="", help="本节主题")

    sub.add_parser("close", help="收一节课，记录时长")

    p = sub.add_parser("add", help="打一个信号点")
    p.add_argument("--type", "-t", required=True, help="、".join(TYPES))
    p.add_argument("--topic", default="", help="相关概念，如 寄宫")
    p.add_argument("--note", "-n", default="", help="具体现象，一句话")

    p = sub.add_parser("resolve", help="标记信号已处理")
    p.add_argument("index", type=int)
    p.add_argument("--note", default="", help="怎么处理的")

    p = sub.add_parser("list", help="列信号")
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--session", default="")
    p.add_argument("--unresolved", action="store_true")

    sub.add_parser("types", help="列信号类型说明")

    args = ap.parse_args(argv)
    if not args.cmd:
        ap.print_help()
        return 0
    d = load()
    return {"open": cmd_open, "close": cmd_close, "add": cmd_add,
            "resolve": cmd_resolve, "list": cmd_list,
            "types": cmd_types}[args.cmd](d, args)


if __name__ == "__main__":
    sys.exit(main())
