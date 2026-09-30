"""Conservative, character-exact retrieval ranges for the annotated Duanan.

The legacy line ranges swallow original prose after short inline comments. This
overlay leaves the source untouched. Explicit speaker paragraphs and only the
first complete sentence of each annotation are attributed; the full note remains
mixed context, available to the reviewer and post-submission comparison.
"""
from __future__ import annotations
from collections import Counter
import re

MARKERS = re.compile(r'(爱函按|缘生谛|邵先生曰|先生曰|邵先生云|先生云)[：:]')
AUTHORS = {'爱函按': '阿甲', '缘生谛': '林景行', '邵先生曰': '邵彦和',
           '先生曰': '邵彦和', '邵先生云': '邵彦和', '先生云': '邵彦和'}


def ranges(body: str, chapter_slug: str) -> list[dict]:
    matches = list(MARKERS.finditer(body))
    counters = Counter({'邵彦和': 1})  # 001 is the existing whole-note context.
    result = []
    for n, marker in enumerate(matches):
        author = AUTHORS[marker[1]]
        ceiling = matches[n + 1].start() if n + 1 < len(matches) else len(body)
        tail = body[marker.end():ceiling]
        if author == '邵彦和':
            # A labelled speaker paragraph, never the following narrative.
            boundary = re.search(r'(?<=[。！？])\n|\n\s*\n', tail)
            end = marker.end() + (boundary.start() if boundary else len(tail))
        else:
            # Safe minimum: do not infer ownership of following unlabelled prose.
            boundary = re.search(r'[。！？]', tail)
            if not boundary:
                continue  # no complete sentence => reviewer context only
            end = marker.end() + boundary.end()
        text = body[marker.start():end].strip()
        if len(text) <= len(marker[0]):
            continue
        counters[author] += 1
        result.append({'anchor_id': f'{author}-{chapter_slug}-{counters[author]:03d}',
                       'author': author, 'start_char': marker.start(), 'end_char': end,
                       'text': text, 'layer': {'邵彦和': '显式署名原辞段',
                           '阿甲': '清人爱函按·显式首句', '林景行': '现代缘生谛·显式首句'}[author],
                       'attribution': '仅按当前录文显式标记；未核原刻'})
    return result
