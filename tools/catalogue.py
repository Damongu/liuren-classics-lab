"""Read-only book/profile and auxiliary-card catalogue for local acceptance."""
from collections import Counter
import json
from launch_book import ROOT, BOOKS, PROFILES
from vault_sources import VAULT, index


def catalogue() -> dict:
    inventory = json.loads((ROOT / 'docs/content-inventory.json').read_text(encoding='utf-8'))
    counts = Counter(item['author'] for item in index().values())
    books = [{'name': name, 'text': PROFILES[name].read_text(encoding='utf-8'),
              'source_count': counts[name], 'examples': inventory['profiles'][name],
              'command': f'.\\启动六壬.ps1 -Book {name}'} for name in BOOKS]
    cards = [{'name': name, 'text': (VAULT / f'90-禄命辅助/{name}.md').read_text(encoding='utf-8')}
             for name in inventory['cards']]
    report_path = ROOT / 'docs/acceptance-results.json'
    report = json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {}
    return {'books': books, 'cards': cards, 'verification': {
        'engineering': report.get('engineering_status', 'not_run'),
        'model': report.get('model', {}).get('status', 'not_run'),
        'model_reason': report.get('model', {}).get('reason', ''), 'at': report.get('at', '')}}
