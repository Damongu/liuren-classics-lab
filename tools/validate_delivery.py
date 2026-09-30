"""Import the local reading edition and run the repository's delivery checks."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--import-source', type=Path)
    ap.add_argument('--baseline', action='store_true')
    ap.add_argument('--prepare-rules', action='store_true')
    ap.add_argument('--repair-anchors', action='store_true')
    ap.add_argument('--prepare-docs', action='store_true')
    args = ap.parse_args()
    if args.prepare_rules:
        archive = ROOT / 'docs/history/AGENTS-before-v3.md'
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            shutil.copy2(ROOT / 'AGENTS.md', archive)
        (ROOT / 'AGENTS.md').write_text(
            '# 六壬带读项目指令\n\n'
            '教学、训练、校勘必须先读取 [系统规则](agents/AGENTS.md)，该文件是 v3 教学规则唯一真源。\n'
            'Pi 由 tools/launch_book.py 显式加载系统规则与一个书魂；根目录不重复维护规则正文。\n\n'
            '工程维护正常检查源码和测试，不开课堂、不虚构训练成绩或教学日志。\n'
            '既有九关与 v3 六关状态分开保存，不能自动折算旧成绩。\n'
            '底本原文不可重写；源文本变更需版本、校记与 hash 验证。\n\n'
            '旧完整指令归档于 docs/history/AGENTS-before-v3.md。\n', encoding='utf-8')
    if args.repair_anchors:
        from repair_anchor_collisions import repair
        print('ANCHOR_REPAIRS', repair(ROOT / '六壬vault'), flush=True)
    if args.prepare_docs:
        archive = ROOT / 'docs/history/README-before-v3.md'
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            shutil.copy2(ROOT / 'README.md', archive)
        (ROOT / 'README.md').write_text((ROOT / 'docs/README-v3.md').read_text(encoding='utf-8'), encoding='utf-8')
    if args.import_source:
        from import_zhonghuang import DEFAULT_SOURCE, import_book, verify_import
        DEFAULT_SOURCE.parent.mkdir(exist_ok=True)
        if not DEFAULT_SOURCE.exists():
            shutil.copy2(args.import_source, DEFAULT_SOURCE)
        report = import_book(DEFAULT_SOURCE, ROOT / '六壬vault')
        print('IMPORT', {k: v for k, v in report.items() if k != 'entries'}, flush=True)
        if verify_import(ROOT / '六壬vault'):
            return 1
    env = {**os.environ, 'PYTHONUTF8': '1'}
    checks = [
        ['tools/check_v3_frontmatter.py', '--quiet'],
        ['tools/selfcheck.py', '--v3', '--quiet'],
        ['tools/check_v3_frontmatter_selftest.py'],
        ['tools/tutor_selftest.py'], ['tools/retro_selftest.py'],
        ['liuren-paipan/tests/test_book_cases.py'],
        ['liuren-paipan/tests/test_webapp.py'],
    ]
    if not args.baseline:
        checks.insert(0, ['-m', 'unittest', 'discover', '-s', 'tests', '-v'])
        checks.insert(1, ['tools/build_remaining_content.py', '--check'])
    failed = []
    for command in checks:
        print('CHECK', ' '.join(command), flush=True)
        result = subprocess.run([sys.executable, *command], cwd=ROOT, env=env)
        if result.returncode:
            failed.append((command[0], result.returncode))
    print('FAILED', failed, flush=True)
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
