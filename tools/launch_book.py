"""Launch Pi with one verified book profile and explicit shared rules."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ('凝神子', '略决', '太白', '心镜', '景祐', '武经', '邵彦和', '阿甲', '林景行', '壬归', '卜筮残', '大全查手')
PROFILES = {**{name: ROOT / f'agents/{name}.md' for name in BOOKS},
            **{name: ROOT / f'agents/_system/{name}.md' for name in ('导读官', '排盘守卫', '复盘官')}}


def command(profile: str, pi_command: str | None = None) -> list[str]:
    if profile not in PROFILES or not PROFILES[profile].is_file():
        raise ValueError(f'未落地的书魂：{profile}')
    executable = pi_command or shutil.which('pi.cmd') or shutil.which('pi')
    if not executable:
        raise ValueError('找不到 Pi，请将 pi 加入 PATH；此工具不自动安装')
    start = [executable]
    if executable.lower().endswith('.cmd'):
        launcher = Path(executable).with_name('pi-launcher.js')
        node = shutil.which('node.exe') or shutil.which('node')
        if launcher.is_file() and node:
            start = [node, str(launcher)]
        else:
            raise ValueError('Windows Pi 需要可用 node 与 pi-launcher.js，避免 shell 参数拼接')
    return [*start, '--provider', 'deepseek', '--no-context-files', '--no-extensions',
            '--no-skills', '--no-prompt-templates',
            '--extension', str(ROOT / 'agents/liuren-extension.ts'),
            '--append-system-prompt', str(ROOT / 'agents/AGENTS.md'),
            '--append-system-prompt', str(PROFILES[profile])]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--book', choices=PROFILES, default='凝神子')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--pi-command')
    args, extra = ap.parse_known_args()
    # One soul per fresh session: continuation across profiles could leak role memory.
    forbidden = ('--resume', '-r', '--continue', '-c', '--session', '--session-id', '--fork',
                 '--append-system-prompt', '--system-prompt', '--provider', '--api-key', '--extension', '-e')
    if any(arg.split('=', 1)[0] in forbidden for arg in extra):
        ap.error('书魂启动器要求新会话；不接受跨书续会话或替换提示词参数')
    cmd = command(args.book, args.pi_command) + extra
    if args.dry_run:
        print(json.dumps({'cwd': str(ROOT), 'profile': args.book, 'argv': cmd}, ensure_ascii=False, indent=2))
        return 0
    env = {**os.environ, 'LIUREN_PYTHON': sys.executable, 'LIUREN_PROFILE': args.book, 'PYTHONUTF8': '1'}
    return subprocess.run(cmd, cwd=ROOT, env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())
