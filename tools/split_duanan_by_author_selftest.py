#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Selftest for tools/split_duanan_by_author.py (Task 3b).

TDD:
  RED  → run without implementation → ModuleNotFoundError
  GREEN→ run after implementation   → OK
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from split_duanan_by_author import (  # noqa: E402
    detect_segments,
    Segment,
    backfill,
    extract_body,
)


# ---------- 段边界样本 ----------
BODY_1 = (
    "庚戌年八月十五日癸丑日辰将辰时。甲辰旬，寅卯空。缘生谛：占于 1125\n"
    "年 9 月 13 日，乙巳年乙酉月癸丑日，八月十五。1130 年庚戌八月十五日为甲申日，非癸丑日。\n"
    "贵后阴玄"
)

BODY_2 = (
    "己酉年正月二十三壬寅日子将寅时。甲午旬，辰巳空。爱函按：郑四月\n"
    "一日未时生。缘生谛：占于 1129 年 2 月 13 日，己酉年丙寅月壬寅日，正月二十三。\n"
    "贵后阴玄"
)

BODY_3 = "纯原辞正文,没有任何注家标记。\n第二段仍是原辞。"

# 真实文件片段（六壬断案-01 缩略）：缘生谛 mid-line，爱函按 行首
BODY_REAL_01 = (
    "己酉年十月初四己卯日寅将酉时。甲戌旬，申酉空。缘生谛：占于 1129 年\n"
    "\n"
    "11 月 17 日，己酉年乙亥月己卯日，十月初四。结合断语可知，邵公用的活时。\n"
    "\n"
    "邵先生曰：数日来，天气和暖。今日雪从何来？\n"
    "爱函按：盖此课，火伏于下，水升乎上。\n"
)


class TestDetectSegments(unittest.TestCase):
    # === Plan 规定 5 条 ===

    def test_body_1_two_segments(self):
        segs = detect_segments(BODY_1)
        authors = [s.author for s in segs]
        self.assertEqual(authors, ["邵彦和", "林景行"])

    def test_body_2_three_segments(self):
        segs = detect_segments(BODY_2)
        authors = [s.author for s in segs]
        self.assertEqual(authors, ["邵彦和", "阿甲", "林景行"])

    def test_body_3_single_segment(self):
        segs = detect_segments(BODY_3)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0].author, "邵彦和")

    def test_false_match_not_at_line_start(self):
        # "缘生谛" 后无冒号 → 不切段
        body = "此处提到缘生谛校本云云,但非注段"
        segs = detect_segments(body)
        self.assertEqual(len(segs), 1)
        self.assertEqual(segs[0].author, "邵彦和")

    def test_multibyte_colon(self):
        # 全角:半角冒号都能识别
        body = "原辞\n爱函按:半角冒号\n爱函按：全角冒号"
        segs = detect_segments(body)
        self.assertEqual(len(segs), 3)
        self.assertEqual([s.author for s in segs], ["邵彦和", "阿甲", "阿甲"])

    # === 覆盖真实文件边界 3 条 ===

    def test_real_file_01_pattern(self):
        # 缘生谛 mid-line（跟在 `。` 后）+ 爱函按 line-start
        segs = detect_segments(BODY_REAL_01)
        authors = [s.author for s in segs]
        self.assertEqual(authors, ["邵彦和", "林景行", "阿甲"])

    def test_segment_text_captures_till_next_marker(self):
        # 林景行 段应从 `缘生谛：` 起,一直吃到下一个 marker 或文末
        segs = detect_segments(BODY_2)
        # 段 1: 邵彦和 (date+ganzhi)
        self.assertIn("己酉年正月", segs[0].text)
        self.assertNotIn("爱函按", segs[0].text)
        # 段 2: 阿甲, 从 `爱函按：` 起
        self.assertTrue(segs[1].text.startswith("爱函按"))
        self.assertNotIn("缘生谛", segs[1].text)
        # 段 3: 林景行, 从 `缘生谛：` 起到文末
        self.assertTrue(segs[2].text.startswith("缘生谛"))
        self.assertIn("贵后阴玄", segs[2].text)

    def test_start_line_indexes_are_within_body(self):
        segs = detect_segments(BODY_REAL_01)
        for s in segs:
            self.assertIsInstance(s, Segment)
            self.assertGreaterEqual(s.start_line, 0)
            self.assertGreaterEqual(s.end_line, s.start_line)


# ---------- 完整 md 回填 ----------
SAMPLE_MD = (
    "---\n"
    "类型: 底本条目\n"
    "书: 六壬断案\n"
    "版本: 缘生谛校注本\n"
    "卷篇: 40 郑三公辛亥生五十九岁占坟地（第二章 宅墓）\n"
    "断代: 记录层：南宋建炎间；文字层：清嘉庆辑校\n"
    "tags: [底本, 唐宋层, 六壬断案]\n"
    "---\n"
    "\n"
    "# 六壬断案 40 郑三公辛亥生五十九岁占坟地（第二章 宅墓）\n"
    "\n"
    "> ⚠️ 机器切分的录文，**未核原刻**。引用具体字句前须回原书影。\n"
    "己酉年正月二十三壬寅日子将寅时。爱函按：郑四月一日未时生。缘生谛：占于 1129 年。\n"
    "邵先生曰：此课艮山行龙。\n"
    "爱函按：左边无者，传不行也。\n"
)


class TestBackfillMd(unittest.TestCase):
    def test_extract_body_strips_h1_and_blockquote(self):
        body = extract_body(SAMPLE_MD)
        self.assertNotIn("---", body)
        self.assertNotIn("# 六壬断案", body)
        self.assertNotIn("⚠️", body)
        self.assertTrue(body.lstrip().startswith("己酉年"))

    def test_backfill_writes_main_anchor_and_segments(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "六壬断案-40.md"
            p.write_text(SAMPLE_MD, encoding="utf-8")
            r = backfill(p, dry_run=False)
            self.assertTrue(r.changed)
            new = p.read_text(encoding="utf-8")
            # 主段 anchor_id 与作者写入
            self.assertIn("anchor_id: 邵彦和-40-郑三公辛亥生五十九岁占坟地-第二章-宅墓-001", new)
            self.assertIn("作者: 邵彦和", new)
            # 含内嵌注家 应含 阿甲 与 林景行
            self.assertIn("含内嵌注家:", new)
            self.assertIn("阿甲", new)
            self.assertIn("林景行", new)
            # 段索引
            self.assertIn("段索引:", new)
            # 正文未被改动（`己酉年正月二十三` 原样保留）
            self.assertIn("己酉年正月二十三壬寅日子将寅时。爱函按：郑四月一日未时生。", new)

    def test_backfill_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "六壬断案-40.md"
            p.write_text(SAMPLE_MD, encoding="utf-8")
            r1 = backfill(p, dry_run=False)
            self.assertTrue(r1.changed)
            c1 = p.read_text(encoding="utf-8")
            r2 = backfill(p, dry_run=False)
            self.assertFalse(r2.changed)
            c2 = p.read_text(encoding="utf-8")
            self.assertEqual(c1, c2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
