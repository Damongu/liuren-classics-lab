#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""训练器自测：9 关各出若干题，验证出题、判分、讲解、错题重建全链路。

不需要人工输入。判分用「标准答案答自己」，只要有一关自答不过就是逻辑坏了。
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tutor  # noqa: E402

ROUNDS = 40   # 每关轮数


def main() -> int:
    bad = []
    for lvl in tutor.LEVELS:
        for s in range(ROUNDS):
            rng = random.Random(s * 131 + lvl["id"])
            tag = f"关{lvl['id']}·seed{s}"
            try:
                item = lvl["gen"](rng)
            except Exception as e:
                bad.append(f"{tag} 出题失败：{type(e).__name__} {e}")
                continue
            # 1. 标准答案必须能通过自己的判分
            if not tutor.ok(item["ans"][0], item["ans"]):
                bad.append(f"{tag} 标准答案自判不过：{item['ans']}")
            # 2. 空答案不能被判对
            if tutor.ok("", item["ans"]):
                bad.append(f"{tag} 空答案被判对")
            # 3. 讲解不能抛异常
            try:
                tutor.explain(item, item.get("plate"))
            except Exception as e:
                bad.append(f"{tag} 讲解失败：{type(e).__name__} {e}")
            # 4. 错题必须能由规格原样重建，且答案一致
            try:
                back = tutor.replay(list(item["spec"]))
            except Exception as e:
                bad.append(f"{tag} 错题重建失败：{type(e).__name__} {e}")
                continue
            if set(map(tutor.norm, back["ans"])) != set(map(tutor.norm, item["ans"])):
                bad.append(f"{tag} 重建后答案不一致：{item['ans']} vs {back['ans']}")
            if tutor.norm(back["q"]) != tutor.norm(item["q"]):
                bad.append(f"{tag} 重建后题干不一致")
            if set(back.get("alt") or {}) != set(item.get("alt") or {}):
                bad.append(f"{tag} 重建后「另一说」键不一致："
                           f"{sorted(item.get('alt') or {})} vs "
                           f"{sorted(back.get('alt') or {})}")
            # 5. 另一说不得与正解相撞
            for k in (item.get("alt") or {}):
                if tutor.ok(k, item["ans"]):
                    bad.append(f"{tag} 另一说键 {k} 与正解重叠")

    n = len(tutor.LEVELS) * ROUNDS
    if bad:
        print(f"❌ 训练器自测失败 {len(bad)} 项 / 共 {n} 题：")
        for b in bad[:15]:
            print("   ·", b)
        if len(bad) > 15:
            print(f"   … 其余 {len(bad) - 15} 项")
        return 1
    print(f"✅ 训练器自测通过：{len(tutor.LEVELS)} 关 × {ROUNDS} 题 = {n} 题，"
          f"出题／判分／讲解／错题重建全链路正常")
    return 0


if __name__ == "__main__":
    sys.exit(main())
