"""Read-only source retrieval with stable anchors, layers and evidence boundaries."""
from __future__ import annotations
import argparse
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re

import yaml
from duanan_layers import ranges as duanan_ranges

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT / '六壬vault'


def split_note(raw: str) -> tuple[dict, str]:
    if not raw.startswith('---\n'):
        return {}, raw
    _, front, body = raw.split('---', 2)
    return yaml.safe_load(front) or {}, body.lstrip('\n')


@lru_cache(maxsize=4)
def index(vault: str = str(VAULT)) -> dict[str, dict]:
    base = Path(vault)
    result = {}
    for path in sorted((base / '10-底本').rglob('*.md')):
        if path.name.startswith(('00-', '_')):
            continue
        raw = path.read_text(encoding='utf-8')
        fm, body = split_note(raw)
        anchor = fm.get('anchor_id')
        if not anchor:
            continue
        common = {'path': str(path.relative_to(base)), 'book': fm.get('书'),
                  'author': fm.get('作者'), 'dating': fm.get('断代', ''),
                  'evidence': fm.get('证据等级', ''), 'pending': bool(fm.get('待核', True)),
                  'polluted': bool(fm.get('污染', False)), 'annotations': bool(fm.get('今注', False)),
                  'relation': fm.get('与六壬关系', ''),
                  'note_sha256': sha256(raw.encode('utf-8')).hexdigest()}
        if anchor in result:
            raise ValueError(f'重复原文锚点：{anchor}')
        if fm.get('书') == '六壬断案':
            result[anchor] = {**common, 'author': '复盘官', 'anchor_id': anchor,
                              'layer': '混排上下文·不作单作者引证', 'text': body,
                              'citation_allowed': False, 'legacy_author': fm.get('作者')}
            slug = anchor.removeprefix('邵彦和-').rsplit('-', 1)[0]
            for segment in duanan_ranges(body, slug):
                bid = segment['anchor_id']
                if bid in result:
                    raise ValueError(f'重复断案段锚点：{bid}')
                result[bid] = {**common, **segment, 'citation_allowed': True,
                               'evidence': {'邵彦和': '二手·南宋记录传本', '阿甲': '清校旁证',
                                            '林景行': '现代今注·仅参考'}[segment['author']],
                               'dating': {'邵彦和': '南宋记录／清辑传本', '阿甲': '清人按语',
                                          '林景行': '现代今注'}[segment['author']]}
            continue
        if '本篇已废弃，不要引用' in body:
            continue
        result[anchor] = {**common, 'anchor_id': anchor, 'layer': '整条（原注混排待核）', 'text': body}
        matches = list(re.finditer(r'^## (.+?) · (凝神子-.+-\d{3})\s*$', body, re.M))
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            part = body[match.end():end].strip()
            part = re.sub(r'^<!-- source-block:.*?-->\s*', '', part)
            bid = match[2]
            if bid in result:
                raise ValueError(f'重复段锚点：{bid}')
            result[bid] = {**common, 'anchor_id': bid, 'layer': match[1], 'text': part}
    return result


def get_source(anchor: str, vault: Path = VAULT) -> dict:
    item = index(str(vault)).get(anchor)
    if item is None:
        raise ValueError(f'不存在的出处锚点：{anchor}')
    path = vault / item['path']
    current = sha256(path.read_text(encoding='utf-8').encode('utf-8')).hexdigest()
    if current != item['note_sha256']:
        index.cache_clear()
        raise ValueError('源文在检索后发生改变，请重新检索并核对')
    return dict(item)


def search(query: str, *, author: str | None = None, limit: int = 20, vault: Path = VAULT) -> list[dict]:
    if not query.strip():
        return []
    found = []
    for item in index(str(vault)).values():
        if author and item['author'] != author:
            continue
        if query in item['text'] or query in item['anchor_id']:
            snippet = item['text']
            at = max(0, snippet.find(query) - 80)
            found.append({**item, 'text': snippet[at:at + 500]})
            if len(found) == limit:
                break
    return found


def validate_citation(citation: dict, *, allowed_books: set[str] | None = None, vault: Path = VAULT) -> dict:
    if not isinstance(citation, dict):
        raise ValueError('出处须为包含 anchor_id、quote、claim 的对象')
    item = get_source(str(citation.get('anchor_id', '')), vault)
    if item.get('citation_allowed') is False:
        raise ValueError('断案整条是混排上下文，请改引显式署名段锚点；不能把整条归给邵氏')
    quote = citation.get('quote', '')
    if not isinstance(quote, str) or len(quote.strip()) < 4 or quote not in item['text']:
        raise ValueError(f'{item["anchor_id"]} 引文不是该锚点内的原文片段（至少四字）')
    if allowed_books is not None and item['book'] not in allowed_books:
        raise ValueError('该关要求宋本原文，当前引文不在允许书目中')
    if item['polluted']:
        raise ValueError('当前条目有改字污染，须先句级人工核查，不能自动通过引证')
    if not isinstance(citation.get('claim'), str) or not citation['claim'].strip():
        raise ValueError('出处须说明支持哪一步判断')
    return item


def training_search(query: str, *, limit: int = 20, vault: Path = VAULT) -> list[dict]:
    """Rule sources only: an unfinished case's annotated answer is not a hint."""
    return [s for s in search(query, limit=1000, vault=vault)
            if s['book'] != '六壬断案' and not s['polluted']][:limit]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--query', default='')
    ap.add_argument('--author')
    ap.add_argument('--anchor')
    args = ap.parse_args()
    data = get_source(args.anchor) if args.anchor else search(args.query, author=args.author)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
