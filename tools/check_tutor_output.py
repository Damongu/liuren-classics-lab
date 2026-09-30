"""Deterministic validation of structured tutoring output; no semantic LLM grading."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re

from vault_sources import VAULT, validate_citation

SHARED_TERMS = ('用神', '命宫', '納音', '纳音', '大运', '大運')
ZP_INTERPRETATIONS = ('扶抑用神', '调候用神', '身强身弱取用', '喜用神补救命局', '子平十神格局')


def in_scope(profile: str, source: dict) -> bool:
    return profile == '复盘官' or source['author'] == ('凝神子' if profile == '导读官' else profile)


def check_output(data: dict, *, vault: Path = VAULT, authorized_quotes: set[tuple[str, str]] | None = None) -> list[str]:
    errors = []
    if not isinstance(data, dict):
        return ['输出必须是结构化对象']
    profile = data.get('profile', '')
    text = data.get('explanation', '')
    if not isinstance(text, str) or not text.strip():
        errors.append('缺解释正文')
        text = ''
    if any(term in text for term in ZP_INTERPRETATIONS):
        errors.append('出现子平义项；拒收并要求按六壬原文重写')
    label = data.get('evidence_label')
    if label not in ('宋证', '唐证', '旁通', '无宋据'):
        errors.append('缺合法证据标签')
    citations = data.get('citations', [])
    if not isinstance(citations, list):
        return errors + ['citations 必须是列表']
    checked = []
    for citation in citations:
        try:
            source = validate_citation(citation, vault=vault)
            if not in_scope(profile, source):
                if (citation.get('anchor_id'), citation.get('quote')) not in (authorized_quotes or set()):
                    errors.append('单书魂越界引他书；须通过课堂讨论协调并取得已核发言')
                elif citation.get('speaker') != source['author']:
                    errors.append('讨论引文须用speaker注明实际书魂，主讲不能冒充他书作者')
            checked.append(source)
        except ValueError as exc:
            errors.append(str(exc))
    if label in ('宋证', '唐证', '旁通') and not checked:
        errors.append('证据标签必须附可核验原文引文')
    if label in ('宋证', '唐证'):
        era = '北宋' if label == '宋证' else '唐'
        if not any(era in s['dating'] and '一手' in s['evidence'] and s['relation'].startswith(('主体', '本体规则', '术语共享')) for s in checked):
            errors.append('当前引文不能支持所称证据等级；题宋/存疑/注家不可自动认证硬据')
    if any(s['pending'] for s in checked) and data.get('source_warning') != '未核原刻':
        errors.append('待核整理录文须显式标未核原刻')
    if profile == '复盘官' and len({s['book'] for s in checked}) > 3:
        errors.append('一次校勘超过三部书，须拆轮')
    if authorized_quotes and len({s['book'] for s in checked}) > 3:
        errors.append('当前主讲及讨论依据超过三部书，须拆轮')
    if label != '旁通' and any(s['author'] in ('阿甲', '林景行', '大全查手') for s in checked):
        errors.append('清按、今注、明本字典只能作旁通参考')
    if label in ('宋证', '唐证') and any(not s['relation'].startswith(('主体', '本体规则', '术语共享')) for s in checked):
        errors.append('旁通关系条不能混入主体硬证标签')
    senses = data.get('term_senses', {})
    if not isinstance(senses, dict):
        senses = {}
        errors.append('term_senses 必须是对象')
    for term in SHARED_TERMS:
        if term in text:
            sense = senses.get(term, {})
            if not isinstance(sense, dict) or sense.get('sense') != '六壬义':
                errors.append(f'{term} 未标此处取六壬义')
                continue
            if not sense.get('no_song_evidence') and sense.get('anchor_id') not in {s['anchor_id'] for s in checked}:
                errors.append(f'{term} 缺本句出处或无宋据说明')
    digressions = data.get('digressions', [])
    if not isinstance(digressions, list):
        errors.append('digressions 必须是列表')
    elif len(digressions) > 3:
        errors.append('旁通超过三条')
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path)
    args = ap.parse_args()
    errors = check_output(json.loads(args.input.read_text(encoding='utf-8')))
    print(json.dumps({'accepted': not errors, 'errors': errors,
                      'boundary': '仅确定性结构与出处检查，不认证解释文义'}, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
