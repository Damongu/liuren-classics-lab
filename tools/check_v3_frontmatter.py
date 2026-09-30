#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v3 frontmatter 检查器。

对 `六壬vault/10-底本/**/*.md` 与 `六壬vault/90-禄命辅助/**/*.md` 逐条 md
校验 v3 spec 的四类字段：`anchor_id` / `作者` / `与六壬关系` / `状态`。

用法：
  python3 tools/check_v3_frontmatter.py
  python3 tools/check_v3_frontmatter.py --vault 六壬vault
  python3 tools/check_v3_frontmatter.py --vault 六壬vault --json

退出码：0 = 无 error；2 = 有 error。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, namedtuple
from pathlib import Path

import yaml


Issue = namedtuple("Issue", "path field severity message")


VALID_AUTHORS = {
    "凝神子", "略决", "太白", "心镜", "景祐", "武经",
    "邵彦和", "阿甲", "林景行", "壬归", "卜筮残", "大全查手",
    # 系统角色作者（排盘器 --card 落卡、导读/复盘产物）
    "排盘守卫", "导读官", "复盘官",
}

# `与六壬关系` 采用开放集（甲方案）：沿用上游 build_vault.py 已写入的
# 细粒度分类（如「本体规则 / 兵占背景 / 同源三式·共用神名」等），也接受
# v3 提出的粗粒度取值。checker 只校验字段存在与类型是字符串，不做 enum 校验。
# 常见取值（供参考，不构成白名单）：
#   上游细粒度：兵占背景 / 同源三式 / 同源三式·共用神名 / 同源三式·穷举立成表 /
#              本体规则 / 术语共享·干支分野 / 术语共享·德刑杀墓纳音 /
#              编纂背景·同编者杨维德 / 配套表·用禽法
#   v3 粗粒度：主体 / 旁证 / 遁甲 / 太乙 / 占候旁证 / N/A / 字典

# anchor_id 规约：<花名>-<卷篇 slugified>-<段序 3 位>
# 允许花名与卷篇中出现中文与常见符号，仅要求整体最后一段是三位数字，
# 且至少存在两个 '-' 分隔符。
ANCHOR_ID_RE = re.compile(r"^.+-.+-\d{3}$")

# 扫描根目录（相对 vault）
SCAN_ROOTS = ["10-底本", "30-课例", "90-禄命辅助"]


def split_fm(raw: str):
    """把 md 拆成 (frontmatter 原文, body)；无 frontmatter 时返回 (None, raw)。"""
    if not raw.startswith("---"):
        return None, raw
    lines = raw.split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    return None, raw


def _is_missing(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    return False


def check_file(path: Path) -> list[Issue]:
    """校验单个 md 文件；返回 Issue 列表（可能为空）。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        return [Issue(str(path), "frontmatter", "error", f"读取失败: {e}")]

    fm_text, _body = split_fm(raw)
    if fm_text is None:
        return [Issue(str(path), "frontmatter", "error", "缺 YAML frontmatter")]

    try:
        data = yaml.safe_load(fm_text) or {}
    except yaml.YAMLError as e:
        return [Issue(str(path), "frontmatter", "error", f"YAML 解析失败: {e}")]

    if not isinstance(data, dict):
        return [Issue(str(path), "frontmatter", "error",
                      f"frontmatter 顶层不是 mapping，实为 {type(data).__name__}")]

    # stub 命中时所有 v3 字段检查降级为 info（骨架文件不计 error/warn）
    is_stub = isinstance(data.get("状态"), str) and data["状态"].strip() == "stub"

    def sev(base: str) -> str:
        return "info" if is_stub else base

    issues: list[Issue] = []

    # ---- anchor_id ----
    anchor = data.get("anchor_id")
    if _is_missing(anchor):
        issues.append(Issue(str(path), "anchor_id", sev("error"), "缺 anchor_id"))
    else:
        if not isinstance(anchor, str):
            issues.append(Issue(str(path), "anchor_id", sev("error"),
                                f"anchor_id 类型必须是字符串，实为 {type(anchor).__name__}"))
        elif not ANCHOR_ID_RE.match(anchor):
            issues.append(Issue(str(path), "anchor_id", sev("error"),
                                f"anchor_id 格式不符规约 ^[^-]+-[^-]+-\\d{{3}}$: {anchor!r}"))

    # ---- 作者 ----
    author = data.get("作者")
    if _is_missing(author):
        issues.append(Issue(str(path), "作者", sev("error"), "缺 作者"))
    else:
        if not isinstance(author, str):
            issues.append(Issue(str(path), "作者", sev("error"),
                                f"作者 类型必须是字符串，实为 {type(author).__name__}"))
        elif author.strip() not in VALID_AUTHORS:
            issues.append(Issue(str(path), "作者", sev("error"),
                                f"作者 不在花名枚举中: {author!r}"))

    # ---- 与六壬关系 ----
    relation = data.get("与六壬关系")
    if _is_missing(relation):
        issues.append(Issue(str(path), "与六壬关系", sev("warn"), "缺 与六壬关系"))

    return issues


def check_vault(root: Path) -> list[Issue]:
    """遍历 vault 下 SCAN_ROOTS 所指目录内所有 md，返回全部 Issue。"""
    issues: list[Issue] = []
    for sub in SCAN_ROOTS:
        d = root / sub
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.md")):
            # 跳过目录卡与内部辅助文件（与 selfcheck.py 保持一致）
            if p.name.startswith("00-") or p.name.startswith("_"):
                continue
            issues.extend(check_file(p))
    return issues


def _summary(issues: list[Issue]) -> dict:
    by_severity: Counter = Counter(i.severity for i in issues)
    by_field: Counter = Counter(i.field for i in issues if i.severity == "error")
    return {
        "total": len(issues),
        "error": by_severity.get("error", 0),
        "warn": by_severity.get("warn", 0),
        "info": by_severity.get("info", 0),
        "error_by_field": dict(by_field),
    }


def _to_dict(issue: Issue) -> dict:
    return {
        "path": issue.path,
        "field": issue.field,
        "severity": issue.severity,
        "message": issue.message,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="v3 frontmatter 检查器")
    ap.add_argument("--vault", default="六壬vault", help="vault 根目录（默认 六壬vault）")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出全部 Issue")
    ap.add_argument("--quiet", action="store_true", help="仅打印汇总，不打印每条 Issue")
    args = ap.parse_args()

    vault = Path(args.vault)
    if not vault.is_dir():
        print(f"找不到 vault：{vault}", file=sys.stderr)
        return 2

    issues = check_vault(vault)
    summary = _summary(issues)

    if args.json:
        payload = {
            "vault": str(vault),
            "summary": summary,
            "issues": [_to_dict(i) for i in issues],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        if not args.quiet:
            for i in issues:
                if i.severity == "info":
                    continue
                marker = "❌" if i.severity == "error" else "⚠️ "
                print(f"{marker} [{i.severity}] {i.path}  ·  {i.field}: {i.message}")
        print(
            f"\nv3 frontmatter 检查："
            f"{summary['error']} error / {summary['warn']} warn / {summary['info']} info"
        )
        if summary["error_by_field"]:
            print("error 分布：" + ", ".join(
                f"{k}={v}" for k, v in sorted(summary["error_by_field"].items())
            ))

    return 2 if summary["error"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
