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
    gate = {"hist": [1] * tutor.PASS_WINDOW, "teachback": False}
    if not tutor.practice_ready(gate) or tutor.final_passed(gate):
        bad.append("练习达标不应直接等于最终过关")
    gate["teachback"] = True
    if not tutor.final_passed(gate):
        bad.append("练习达标且白话复述通过后应最终过关")
    for topic in tutor.LEVEL1_TOPICS:
        for s in range(ROUNDS):
            item = tutor.g_jigong(random.Random(s), topic)
            if item["spec"][0] != topic:
                bad.append(f"关1单项 {topic} 混入题型：{item['spec'][0]}")
    level4_generators = {
        "贼克": tutor.g_zeike,
        "比用": tutor.g_biyong,
        "贼克＋比用": tutor.g_zeike_biyong,
        "贼克＋比用＋涉害": tutor.g_zeike_biyong_shehai,
        "遥克": tutor.g_yaoke,
        "贼克＋比用＋涉害＋遥克": tutor.g_four_methods,
        "昴星": tutor.g_maoxing,
        "贼克＋比用＋涉害＋遥克＋昴星": tutor.g_five_methods,
        "别责": tutor.g_bieze,
        "贼克＋比用＋涉害＋遥克＋昴星＋别责": tutor.g_six_methods,
        "八专": tutor.g_bazhuan,
        "贼克＋比用＋涉害＋遥克＋昴星＋别责＋八专": tutor.g_seven_methods,
        "伏吟": tutor.g_fuyin,
        "贼克＋比用＋涉害＋遥克＋昴星＋别责＋八专＋伏吟": tutor.g_eight_methods,
        "返吟": tutor.g_fanyin,
        "贼克＋比用＋涉害＋遥克＋昴星＋别责＋八专＋伏吟＋返吟": tutor.g_nine_methods,
    }
    for topic, generator in level4_generators.items():
        for s in range(ROUNDS):
            item = generator(random.Random(s))
            if topic == "遥克" and item["plate"].keshi != "遥克":
                bad.append(f"关4单项遥克混入课体：{item['plate'].keshi}")
            if topic == "遥克":
                p = item["plate"]
                ups = list(dict.fromkeys(k.up for k in p.kes))
                hao = [u for u in ups if tutor.ke(u, p.gan)]
                cands = hao or [u for u in ups if tutor.ke(p.gan, u)]
                answer = item["ans"][0]
                if len(cands) == 1 and ("阳日取阳神" in answer or "阴日取阴神" in answer):
                    bad.append("遥克单候选题错误启用比用依据")
                if len(cands) > 1 and "取" not in answer:
                    bad.append("遥克多候选题缺少比用依据")
            if topic == "昴星":
                p = item["plate"]
                if p.keshi != "昴星":
                    bad.append(f"关4单项昴星混入课体：{p.keshi}")
                expected = "阳仰酉上先支后干" if p.is_gang else "阴俯酉下先干后支"
                if expected not in item["ans"][0]:
                    bad.append("昴星专项取法依据与刚柔日不符")
            if topic == "别责":
                p = item["plate"]
                if p.keshi != "别责":
                    bad.append(f"关4单项别责混入课体：{p.keshi}")
                expected = "刚日取干合寄宫上神" if p.is_gang else "柔日取支前三合宫上神"
                if expected not in item["ans"][0]:
                    bad.append("别责专项取法依据与刚柔日不符")
            if topic == "八专":
                p = item["plate"]
                if p.keshi != "八专":
                    bad.append(f"关4单项八专混入课体：{p.keshi}")
                expected = tutor.bazhuan_why(p)
                if expected not in item["ans"][0]:
                    bad.append("八专专项取法依据与刚柔日不符")
            if topic == "伏吟":
                p = item["plate"]
                if p.keshi != "伏吟":
                    bad.append(f"关4单项伏吟混入课体：{p.keshi}")
                expected = "有克取克处" if p.keshi_sub.startswith("有克") else (
                    "无克刚取日上" if p.is_gang else "无克柔取辰上"
                )
                if expected not in item["ans"][0]:
                    bad.append("伏吟专项初传依据与有克无克分支不符")
            if topic == "返吟":
                p = item["plate"]
                if p.keshi != "返吟":
                    bad.append(f"关4单项返吟混入课体：{p.keshi}")
                expected = "有克取克处" if p.keshi_sub.startswith("有克") else "无克取马"
                if expected not in item["ans"][0]:
                    bad.append("返吟专项初传依据与有克无克分支不符")
            if not tutor.ok(item["ans"][0], item["ans"]):
                bad.append(f"关4单项 {topic} 标准答案自判不过：{item['ans']}")
            back = tutor.replay(list(item["spec"]))
            if set(map(tutor.norm, back["ans"])) != set(map(tutor.norm, item["ans"])):
                bad.append(f"关4单项 {topic} 重建后答案不一致")
    l1 = {"hist": [], "teachback": False, "topics": {}, "mixed": {"hist": []}}
    for topic in tutor.LEVEL1_TOPICS:
        ts = tutor.topic_state(l1, topic)
        ts["hist"] = [1] * tutor.TOPIC_CORRECT
        ts["teachback"] = True
    l1["mixed"]["hist"] = [1] * tutor.PASS_CORRECT + [0]
    if not tutor.practice_ready(l1, 1) or tutor.final_passed(l1, 1):
        bad.append("关1各专项和混合达标后应待整关复述，不应直接最终过关")
    l1["teachback"] = True
    if not tutor.final_passed(l1, 1):
        bad.append("关1专项、混合及整关复述均通过后应最终过关")
    if tutor.topic_score_ready({"hist": [1] * 5}, "遥克"):
        bad.append("6题专项不应在5题后达标")
    if not tutor.topic_score_ready({"hist": [1] * 6}, "遥克"):
        bad.append("6题专项全对后应达标")
    if tutor.topic_score_ready({"hist": [1] * 10 + [0, 0]}, "贼克＋比用＋涉害＋遥克"):
        bad.append("12题累计混合10/12不应达标")
    if not tutor.topic_score_ready({"hist": [1] * 11 + [0]}, "贼克＋比用＋涉害＋遥克"):
        bad.append("12题累计混合11/12应达标")
    sample_state = {
        "levels": {}, "wrong": [], "wrong_archive": [],
        "weak_groups": {}, "sessions": [],
    }
    sample = tutor.g_jigong(random.Random(7), "遁干")
    tutor._enqueue(sample_state, 1, sample, "错答")
    tutor.classify_wrong(
        sample_state, 1, ["教学前基线", "步骤遗漏"], "自测"
    )
    if not sample_state["wrong"][0].get("baseline_pending"):
        bad.append("教学前基线归因后未设置一次复现标记")
    tutor._dequeue(sample_state, 1, sample)
    if sample_state["wrong"] or len(sample_state["wrong_archive"]) != 1:
        bad.append("教学前基线答对后未退出活跃队列并保留归档")
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
