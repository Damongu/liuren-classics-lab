"""Lossless OOXML import of the supplied 中黄经 reading edition.

Preserves paragraph order, source styles, tables and variant apparatus. No OCR,
normalization or unsupported attribution is performed. Rebuilds are idempotent;
changed sources or edited notes are refused unless --force is explicit.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / 'sources' / '大六壬五變中黃經_閱讀整理版.docx'
BOOK = '中黄经'
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
W = '{' + NS['w'] + '}'
LAYERS = {
    '經文': '经文', '異本經文': '异本经文', '眉批': '眉批',
    '行間小注': '行间小注', '盤旁小注': '盘旁小注',
    '校記': '校记', '異本校記': '异本校记', '校記標題': '校记标题',
    '異本標題': '异本标题', '卷尾題': '卷尾题', '圖題': '图题',
}
SKIP_STYLES = {'閱讀目錄', '閱讀說明', '閱讀頁眉', '靜態目錄', '頁碼標識', '頁碼索引', '分面標識'}


def digest(text: str) -> str:
    return sha256(text.encode('utf-8')).hexdigest()


def paragraph_text(node: ET.Element) -> str:
    out = []
    for element in node.iter():
        if element.tag == W + 't':
            out.append(element.text or '')
        elif element.tag == W + 'tab':
            out.append('\t')
        elif element.tag == W + 'br':
            out.append('\n')
    return ''.join(out)


def read_sections(source: Path) -> tuple[list[dict], dict]:
    with ZipFile(source) as archive:
        doc = ET.fromstring(archive.read('word/document.xml'))
        styles = ET.fromstring(archive.read('word/styles.xml'))
        style_names = {s.get(W + 'styleId'): s.find('w:name', NS).get(W + 'val')
                       for s in styles.findall('w:style', NS) if s.find('w:name', NS) is not None}
    sections, current, hierarchy = [], None, {}
    stats = Counter()
    for index, block in enumerate(doc.find('w:body', NS)):
        kind = block.tag.removeprefix(W)
        if kind == 'sectPr':
            continue
        style_node = block.find('w:pPr/w:pStyle', NS)
        style = style_names.get(style_node.get(W + 'val'), '') if style_node is not None else ''
        text = paragraph_text(block)
        if style in SKIP_STYLES or not text.strip():
            continue
        heading = re.fullmatch(r'heading ([1-9])', style)
        if heading:
            if text == '目錄':
                continue
            depth = int(heading[1])
            hierarchy = {k: v for k, v in hierarchy.items() if k < depth}
            hierarchy[depth] = text
            current = {'title': ' / '.join(hierarchy.values()), 'heading': text,
                       'source_block': index, 'blocks': []}
            sections.append(current)
            continue
        if current is None:
            continue  # title and front matter, before the first actual section
        item = {'source_block': index, 'style': style or 'Normal',
                'layer': '课盘表格' if kind == 'tbl' else LAYERS.get(style, '释文／序文（署名待核）'),
                'text': text}
        if kind == 'tbl':
            item['rows'] = []
            for row in block.findall('w:tr', NS):
                cells = []
                for cell in row.findall('w:tc', NS):
                    cells.append('\n'.join(paragraph_text(p) for p in cell.findall('w:p', NS)))
                item['rows'].append(cells)
        current['blocks'].append(item)
        stats[item['layer']] += 1
    return sections, dict(stats)


def slug(text: str) -> str:
    return re.sub(r'[^\w\u3400-\u9fff]+', '-', text).strip('-')


def render_section(section: dict, order: int, source: Path, source_hash: str) -> tuple[str, str, dict]:
    anchor = f'凝神子-{slug(section["title"])}-001'
    lines = [f'# {section["title"]}', '',
             '> 阅读整理版录文；未核原刻。经文、释文、眉批及校记按 Word 样式分层，',
             '> 不据样式推断释文作者或断代。源定位为 OOXML body 块号，不是原书页码。', '']
    blocks = []
    for position, block in enumerate(section['blocks'], 1):
        bid = f'凝神子-{slug(section["title"])}-{position + 1:03d}'
        lines += [f'## {block["layer"]} · {bid}', '',
                  f'<!-- source-block: {block["source_block"]}; style: {block["style"]} -->', '']
        if 'rows' in block:
            # Explicit HTML table preserves ragged rows and multiline cell text;
            # the exact cell matrix is also kept in the import manifest.
            import html
            lines += ['<table>']
            for row in block['rows']:
                lines += ['<tr>' + ''.join('<td>' + html.escape(c).replace('\n', '<br>') + '</td>' for c in row) + '</tr>']
            lines += ['</table>', '']
        else:
            lines += [block['text'], '']
        blocks.append({'anchor_id': bid, **block, 'text_sha256': digest(block['text'])})
    body = '\n'.join(lines).rstrip() + '\n'
    fm = {
        '类型': '底本条目', '书': '大六壬五变中黄经', '版本': '阅读整理版（经文／补完直解／释义分层）',
        '卷篇': section['title'], '断代': '题宋郭凝神；商皓补完直解、释义及现整理层断代待核',
        '证据等级': '待核·须按经文与注释逐层取证', '待核': True,
        '繁简': '保留源文件字形，未转简', '源文件': source.name,
        'source_sha256': source_hash, 'body_sha256': digest(body),
        'anchor_id': anchor, '作者': '凝神子', '与六壬关系': '主体',
        'tags': ['底本', '唐宋层', '中黄经'],
    }
    filename = f'中黄经-{order:03d} {slug(section["title"])}.md'
    raw = '---\n' + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False) + '---\n\n' + body
    entry = {'path': filename, 'anchor_id': anchor, 'body_sha256': digest(body),
             'heading_source_block': section['source_block'], 'blocks': blocks}
    return filename, raw, entry


def import_book(source: Path, vault: Path, *, dry: bool = False, force: bool = False) -> dict:
    sections, stats = read_sections(source)
    if not sections or not any(s['blocks'] for s in sections):
        raise ValueError('未识别正文卷篇，拒绝生成空底本')
    source_hash = sha256(source.read_bytes()).hexdigest()
    target = vault / '10-底本' / '唐宋层' / BOOK
    files = [render_section(s, i, source, source_hash) for i, s in enumerate(sections, 1)]
    # Preflight all paths before making any change; preserve user annotations.
    for name, raw, entry in files:
        path = target / name
        if path.exists() and path.read_text(encoding='utf-8') != raw and not force:
            raise ValueError(f'{path.name} 与重建结果不同；保留批注，需显式 --force')
    report = {'book': BOOK, 'n': len(files), 'source': source.name,
              'source_sha256': source_hash, 'layers': stats,
              'chars': sum(len(b['text']) for s in sections for b in s['blocks']),
              'entries': [e for _, _, e in files]}
    if dry:
        return report
    target.mkdir(parents=True, exist_ok=True)
    for name, raw, _ in files:
        path = target / name
        if not path.exists() or path.read_text(encoding='utf-8') != raw:
            path.write_text(raw, encoding='utf-8')
    (target / '_源文清单.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (target / '00-中黄经目录.md').write_text('---\ntags: [索引, 中黄经]\n---\n\n# 中黄经目录\n\n' + '\n'.join(
        f'{i}. [[{Path(name).stem}]]' for i, (name, _, _) in enumerate(files, 1)) + '\n', encoding='utf-8')
    (target / '00-书卡-中黄经.md').write_text(
        '---\ntags: [书卡, 中黄经]\n---\n\n# 中黄经底本说明\n\n'
        f'源文件：`{source.name}`。{len(files)} 条卷篇，保留繁体、异体字和课盘表格。\n\n'
        '整理说明称“依已校 Word 整理”，并称沿用未署来源的括注；不是原刻影像。'
        '序文记郭凝神、焦休文注、商皓补完直解，不能把整份文件统一认作郭氏宋代原文。'
        '经文仅以原文件样式識别，释文作者与年代仍须对版本、原刻和校记取证。\n\n'
        '每条都有 source_sha256、body_sha256；每段有稳定锚点和 OOXML 块号。'
        '块号只作整理版定位，不冒充书页。`_源文清单.json`保存原段与表格矩阵。\n', encoding='utf-8')
    (target / '_导入报告.md').write_text(
        '# 中黄经导入报告\n\n' + f'源 SHA256：`{source_hash}`\n\n卷篇：{len(files)}；字符：{report["chars"]}。\n\n'
        + '\n'.join(f'- {k}：{v} 块' for k, v in stats.items()) + '\n\n'
        '全文未转简、未校字、未增删；目录与阅读说明不计入底本文本。\n', encoding='utf-8')
    return report


def verify_import(vault: Path) -> list[str]:
    target = vault / '10-底本' / '唐宋层' / BOOK
    manifest = target / '_源文清单.json'
    if not manifest.exists():
        return ['中黄经源文清单缺失']
    data = json.loads(manifest.read_text(encoding='utf-8'))
    errors = []
    anchors = set()
    for entry in data['entries']:
        path = target / entry['path']
        if not path.exists():
            errors.append(f'中黄经条目缺失：{path.name}')
            continue
        raw = path.read_text(encoding='utf-8')
        body = raw.split('---', 2)[2].lstrip('\n')
        if digest(body) != entry['body_sha256']:
            errors.append(f'中黄经原文 hash 改变：{path.name}')
        for block in entry['blocks']:
            if block['anchor_id'] in anchors:
                errors.append(f'中黄经锚点重复：{block["anchor_id"]}')
            anchors.add(block['anchor_id'])
            if f'## {block["layer"]} · {block["anchor_id"]}' not in body:
                errors.append(f'中黄经段锚点缺失：{block["anchor_id"]}')
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--src', type=Path, default=DEFAULT_SOURCE)
    ap.add_argument('--vault', type=Path, default=ROOT / '六壬vault')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--verify', action='store_true')
    args = ap.parse_args()
    if args.verify:
        errors = verify_import(args.vault)
        print('\n'.join(errors) or '中黄经完整性：条目、原文 hash、段锚点通过')
        return 1 if errors else 0
    report = import_book(args.src, args.vault, dry=args.dry_run, force=args.force)
    print(json.dumps({k: v for k, v in report.items() if k != 'entries'}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
