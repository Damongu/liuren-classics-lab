#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Selftest for tools/check_v3_frontmatter.py.

Run: python3 tools/check_v3_frontmatter_selftest.py
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

# 允许 `python3 tools/check_v3_frontmatter_selftest.py` 直接跑而不用 -m
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from check_v3_frontmatter import check_file  # noqa: E402


VALID_AUTHORS = {"凝神子", "略决", "太白", "心镜", "景祐", "武经",
                 "邵彦和", "阿甲", "林景行", "壬归", "卜筮残", "大全查手",
                 "排盘守卫", "导读官", "复盘官"}


class TestFrontmatterCheck(unittest.TestCase):
    def _write(self, content):
        f = pathlib.Path(tempfile.mkstemp(suffix=".md")[1])
        f.write_text(content, encoding="utf-8")
        return f

    def test_missing_anchor_id_is_error(self):
        f = self._write("---\n书: 太白阴经\n卷篇: 玄女式\n作者: 太白\n---\n正文")
        issues = check_file(f)
        errs = [i for i in issues if i.field == "anchor_id" and i.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_missing_author_is_error(self):
        f = self._write("---\n书: 太白阴经\n卷篇: 玄女式\nanchor_id: 太白-玄女式-001\n---\n正文")
        issues = check_file(f)
        errs = [i for i in issues if i.field == "作者" and i.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_invalid_author_is_error(self):
        f = self._write("---\n作者: 无名氏\nanchor_id: X-Y-001\n---\n正文")
        errs = [i for i in check_file(f) if i.field == "作者" and i.severity == "error"]
        self.assertEqual(len(errs), 1)

    def test_missing_liuren_relation_is_warn(self):
        f = self._write("---\n书: 太白阴经\n卷篇: 玄女式\n作者: 太白\n"
                        "anchor_id: 太白-玄女式-001\n---\n正文")
        warns = [i for i in check_file(f) if i.field == "与六壬关系" and i.severity == "warn"]
        self.assertEqual(len(warns), 1)

    def test_valid_frontmatter_zero_errors(self):
        f = self._write("---\n书: 太白阴经\n卷篇: 玄女式\n作者: 太白\n"
                        "anchor_id: 太白-玄女式-001\n与六壬关系: 主体\n---\n正文")
        errs = [i for i in check_file(f) if i.severity == "error"]
        self.assertEqual(errs, [])

    def test_stub_file_is_info_not_error(self):
        f = self._write("---\n状态: stub\n---\n骨架待填")
        errs = [i for i in check_file(f) if i.severity == "error"]
        self.assertEqual(errs, [])

    def test_anchor_id_format_regex(self):
        # 不合规格式判 error
        f = self._write("---\n作者: 太白\nanchor_id: 无花名格式\n---\n正文")
        errs = [i for i in check_file(f) if i.field == "anchor_id" and i.severity == "error"]
        self.assertGreaterEqual(len(errs), 1)

    def test_paipan_guard_author_is_valid(self):
        """排盘守卫 作为系统角色作者应通过。"""
        f = self._write("---\n作者: 排盘守卫\n"
                        "anchor_id: 排盘守卫-涉害丁卯丑亥-001\n"
                        "与六壬关系: 主体\n---\n课例卡")
        errs = [i for i in check_file(f) if i.severity == "error"]
        self.assertEqual(errs, [])

    def test_kelie_card_missing_anchor_is_error(self):
        """30-课例/ 下缺 anchor_id 应报 error（且非 stub）。"""
        f = self._write("---\n课式: 涉害\n作者: 排盘守卫\n---\n课例卡")
        errs = [i for i in check_file(f) if i.field == "anchor_id" and i.severity == "error"]
        self.assertEqual(len(errs), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
