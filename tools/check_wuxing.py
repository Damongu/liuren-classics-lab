#!/usr/bin/env python3
"""确定性校验两个天干或地支之间的五行关系。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "liuren-paipan"))

from liuren.ganzhi import relation, wuxing  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="校验两个干支字符的五行关系")
    parser.add_argument("source", help="施加关系的一方，如 甲、申")
    parser.add_argument("target", help="承受关系的一方，如 申、甲")
    args = parser.parse_args()

    try:
        source_wuxing = wuxing(args.source)
        target_wuxing = wuxing(args.target)
        result = relation(args.source, args.target)
    except KeyError:
        parser.error("参数必须是单个天干或地支")

    print(
        f"{args.source}({source_wuxing}) 对 {args.target}({target_wuxing})：{result}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
