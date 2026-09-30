#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Selftest for tools/generate_anchor_ids.py (Task 3a).

TDD:
  RED  → run without implementation → ModuleNotFoundError
  GREEN→ run after implementation   → OK
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

# 允许从 tools/ 目录直接 import
HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from generate_anchor_ids import (  # noqa: E402
    slugify,
    book_to_penname,
    compute_anchor_id,
    backfill,
)


SAMPLE_FM = (
    "---\n"
    "类型: 底本条目\n"
    "书: 太白阴经\n"
    "版本: 卷十\n"
    "卷篇: 玄女式\n"
    "断代: 唐\n"
    "证据等级: 一手·基准层\n"
    "tags: [底本, 唐宋层, 太白阴经]\n"
    "---\n"
    "\n"
    "# 太白阴经 玄女式\n"
    "正文正文\n"
)


class T(unittest.TestCase):
    def test_slugify_keeps_hanzi(self):
        self.assertEqual(slugify("玄女式"), "玄女式")

    def test_slugify_replaces_spaces(self):
        self.assertEqual(slugify("推 五 帝 法"), "推-五-帝-法")

    def test_book_to_penname_taibai(self):
        self.assertEqual(book_to_penname("太白阴经"), "太白")

    def test_book_to_penname_zhongshan(self):
        # 中黄经 / 大六壬五变中黄经 都映射到 凝神子
        self.assertEqual(book_to_penname("大六壬五变中黄经"), "凝神子")
        self.assertEqual(book_to_penname("中黄经"), "凝神子")

    def test_book_to_penname_wuji(self):
        self.assertEqual(book_to_penname("武经总要"), "武经")

    def test_anchor_id_shape(self):
        self.assertEqual(compute_anchor_id("太白", "玄女式", 1), "太白-玄女式-001")

    def test_anchor_id_stable_for_same_inputs(self):
        a = compute_anchor_id("壬归", "总说", 42)
        b = compute_anchor_id("壬归", "总说", 42)
        self.assertEqual(a, b)

    def test_idempotent_backfill(self):
        # 骨架 pass —— 幂等实测放在下一个 test。
        pass

    def test_idempotent_backfill_real_file(self):
        """真实文件：backfill(dry_run=False) 二次调用第二次 changed=False，磁盘无变化。"""
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "太白阴经-玄女式.md"
            p.write_text(SAMPLE_FM, encoding="utf-8")

            r1 = backfill(p, dry_run=False)
            self.assertTrue(r1.changed, "首次回填应 changed=True")
            content_after_first = p.read_text(encoding="utf-8")
            self.assertIn("anchor_id: 太白-玄女式-001", content_after_first)
            self.assertIn("作者: 太白", content_after_first)

            r2 = backfill(p, dry_run=False)
            self.assertFalse(r2.changed, "二次调用应幂等 changed=False")
            content_after_second = p.read_text(encoding="utf-8")
            self.assertEqual(
                content_after_first,
                content_after_second,
                "二次调用磁盘内容必须完全一致",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
