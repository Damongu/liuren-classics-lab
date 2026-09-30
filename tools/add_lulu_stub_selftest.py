#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Selftest for tools/add_lulu_stub.py (Task 5).

TDD:
  RED  → run without implementation → ModuleNotFoundError
  GREEN→ run after implementation   → OK (3/3)

覆盖：
  1. 新建不冲突路径 → 成功；文件存在；frontmatter 完整
  2. 已存在时再建   → 退出码非零，不覆盖
  3. 概念名含空格   → slugify（`天医 星` → `天医-星.md`）
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import tempfile
import unittest

import yaml

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from add_lulu_stub import (  # noqa: E402
    create_stub,
    stub_content,
    slugify_concept,
)


TOOL = HERE / "add_lulu_stub.py"


def _make_vault(tmp: pathlib.Path) -> pathlib.Path:
    """构造一个最小 vault，只含 90-禄命辅助/ 目录。"""
    d = tmp / "六壬vault" / "90-禄命辅助"
    d.mkdir(parents=True, exist_ok=True)
    return tmp / "六壬vault"


def _parse_fm(md_text: str) -> dict:
    assert md_text.startswith("---\n"), "缺 frontmatter 开头"
    end = md_text.index("\n---\n", 4)
    fm_raw = md_text[4:end]
    return yaml.safe_load(fm_raw)


class TestAddLuluStub(unittest.TestCase):

    def test_1_create_fresh_stub_success(self):
        with tempfile.TemporaryDirectory() as td:
            vault = _make_vault(pathlib.Path(td))
            path = create_stub("驿马", vault_root=vault)
            self.assertTrue(path.exists(), "文件应已生成")
            text = path.read_text(encoding="utf-8")

            fm = _parse_fm(text)
            self.assertEqual(fm.get("概念名"), "驿马")
            self.assertEqual(fm.get("所属层"), "禄命辅助")
            self.assertEqual(fm.get("状态"), "stub")
            self.assertEqual(fm.get("宋本硬证"), [])
            self.assertIn("禄命辅助", fm.get("tags", []))
            self.assertIn("stub", fm.get("tags", []))

            # 四段模板占位
            for marker in ("一、界说", "二、在断辞中的用法", "三、宋本硬证", "四、易混淆点"):
                self.assertIn(marker, text, f"缺段落 {marker}")
            for todo in ("TODO(D-1)", "TODO(D-2)", "TODO(D-3)", "TODO(D-4)"):
                self.assertIn(todo, text, f"缺 {todo}")

    def test_2_existing_refuses_and_preserves(self):
        with tempfile.TemporaryDirectory() as td:
            vault = _make_vault(pathlib.Path(td))
            target = vault / "90-禄命辅助" / "禄.md"
            target.write_text("---\n概念名: 禄\n状态: draft\n---\n\n原有内容，勿覆盖。\n",
                              encoding="utf-8")
            original = target.read_text(encoding="utf-8")

            # Python API 应抛异常
            with self.assertRaises(FileExistsError):
                create_stub("禄", vault_root=vault)

            # 文件未被覆盖
            self.assertEqual(target.read_text(encoding="utf-8"), original)

            # CLI 应退出码非零
            result = subprocess.run(
                [sys.executable, str(TOOL), "禄", "--vault", str(vault)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(target.read_text(encoding="utf-8"), original)

    def test_3_slugify_concept_with_space(self):
        # 直接函数级
        self.assertEqual(slugify_concept("天医 星"), "天医-星")
        self.assertEqual(slugify_concept("天医  星"), "天医-星")
        self.assertEqual(slugify_concept("天医　星"), "天医-星")

        # 文件名走 slugify
        with tempfile.TemporaryDirectory() as td:
            vault = _make_vault(pathlib.Path(td))
            path = create_stub("天医 星", vault_root=vault)
            self.assertEqual(path.name, "天医-星.md")
            self.assertTrue(path.exists())

            # frontmatter 里的「概念名」保留原始名（带空格），仅文件名 slugified
            fm = _parse_fm(path.read_text(encoding="utf-8"))
            self.assertEqual(fm.get("概念名"), "天医 星")


if __name__ == "__main__":
    unittest.main(verbosity=2)
