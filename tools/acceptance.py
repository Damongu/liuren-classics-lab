"""One entry point for code, corpus, Pi, browser and model readiness checks."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from launch_book import ROOT
from model_acceptance import run as model_run


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--model', action='store_true')
    ap.add_argument('--only', choices=('python-and-vault','content','pi-loader','browser'),
                    help='只重跑失败或刚改动的项，保留其余已通过结果')
    args = ap.parse_args()
    qa = ROOT / 'artifacts/qa'
    qa.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, 'PYTHONUTF8': '1', 'LIUREN_PYTHON': sys.executable}
    checks = [ ('python-and-vault', [sys.executable, 'tools/validate_delivery.py']),
               ('content', [sys.executable, 'tools/build_remaining_content.py', '--check']) ]
    node = shutil.which('node.exe') or shutil.which('node')
    pi = shutil.which('pi.cmd') or shutil.which('pi')
    package = Path(os.environ['LIUREN_PI_PACKAGE']) if os.environ.get('LIUREN_PI_PACKAGE') else None
    if not package and pi:
        candidates = list((Path(pi).parent.parent / 'install/releases').glob('*/node_modules/@earendil-works/pi-coding-agent'))
        if candidates:
            package = max(candidates, key=lambda p: tuple(int(v) for v in p.parents[2].name.split('.') if v.isdigit()))
    playwright = next((p for p in [os.environ.get('LIUREN_PLAYWRIGHT'), 'D:/Codex/skills/gstack/node_modules/playwright']
                       if p and (Path(p) / 'package.json').is_file()), None)
    report = {'at': datetime.now(timezone.utc).isoformat(), 'branch': 'pi', 'python': sys.executable, 'checks': []}
    previous = ROOT / 'docs/acceptance-results.json'
    if args.only and previous.exists():
        old = json.loads(previous.read_text(encoding='utf-8'))
        report['checks'] = [c for c in old.get('checks', []) if c['name'] != args.only]
    if node and package:
        checks.append(('pi-loader', [node, 'tools/verify_pi.mjs', str(package)]))
    else:
        report['checks'].append({'name': 'pi-loader', 'status': 'blocked', 'reason': '找不到本机Pi/Node包，未安装替代工具'})
    if node and playwright:
        checks.append(('browser', [node, 'tools/browser_smoke.mjs', playwright, sys.executable]))
    else:
        report['checks'].append({'name': 'browser', 'status': 'blocked', 'reason': '找不到本机Playwright，可设置LIUREN_PLAYWRIGHT；未自动下载'})
    for name, cmd in checks:
        if args.only and name != args.only:
            continue
        print('验收', name, flush=True)
        log = qa / f'{name}.log'
        with log.open('w', encoding='utf-8') as stream:
            result = subprocess.run(cmd, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
        status = 'passed' if result.returncode == 0 else 'failed'
        report['checks'].append({'name': name, 'status': status, 'returncode': result.returncode,
                                  'verified_at': datetime.now(timezone.utc).isoformat(),
                                  'log': str(log.relative_to(ROOT))})
        print(name, status, flush=True)
        if result.returncode:
            print(log.read_text(encoding='utf-8')[-5000:], flush=True)
    try:
        report['model'] = model_run(args.model)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        report['model'] = {'status': 'blocked', 'reason': str(exc)}
    (ROOT / 'docs/model-acceptance.json').write_text(json.dumps(report['model'], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    names = {c['name'] for c in report['checks']}
    report['engineering_status'] = 'passed' if names == {'python-and-vault','content','pi-loader','browser'} and all(c['status'] == 'passed' for c in report['checks']) else 'incomplete'
    (ROOT / 'docs/acceptance-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'engineering': report['engineering_status'], 'model': report['model']['status'],
                      'report': str(ROOT / 'docs/acceptance-results.json')}, ensure_ascii=False, indent=2))
    return 1 if report['engineering_status'] != 'passed' else (2 if args.model and report['model']['status'] != 'passed' else 0)


if __name__ == '__main__':
    raise SystemExit(main())
