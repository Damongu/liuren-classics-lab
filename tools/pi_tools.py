"""JSON stdin bridge for Pi's source and output-validation tools."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys

from check_tutor_output import check_output, in_scope
from import_zhonghuang import verify_import
from vault_sources import VAULT, get_source, search

PENDING_DIR = Path(os.environ.get('LIUREN_PENDING_DIR', str(VAULT / '70-待查')))


def handle(mode: str, payload: dict, profile: str) -> dict:
    errors = verify_import(VAULT)
    if errors:
        return {'accepted': False, 'errors': errors}
    if mode == 'discuss':
        from classroom import discuss
        return discuss(payload, profile)
    if mode == 'source':
        if payload.get('anchor'):
            source = get_source(payload['anchor'])
            if not in_scope(profile, source):
                if os.environ.get('LIUREN_DISCUSSION_CHILD') == '1':
                    return {'accepted': False, 'errors': ['独立讨论书魂只能读自己的底本，不写挂号或开递归讨论']}
                # Separate append-only pending log; do not edit an existing user's list.
                pending = PENDING_DIR / 'v3跨书请求.md'
                pending.parent.mkdir(parents=True, exist_ok=True)
                if not pending.exists():
                    pending.write_text('---\ntags: [待查, v3]\n---\n\n# v3跨书请求\n\n', encoding='utf-8')
                line = f'- {profile} 请求 `{source["anchor_id"]}`，须移交复盘官独立会话；当前书魂拒绝越界。\n'
                with pending.open('a', encoding='utf-8') as stream:
                    stream.write(line)
                return {'accepted': False, 'errors': ['单书魂不能直接解释他书；已挂号。请在当前会话调用liuren_discuss自动邀请相关书魂，无须让用户切换'],
                        'next_tool': 'liuren_discuss', 'suggested_profile': source['author']}
            return {'accepted': True, 'source': source}
        items = search(payload.get('query', ''), author=None if profile == '复盘官' else
                       ('凝神子' if profile == '导读官' else profile))
        if profile == '复盘官':
            books = []
            for item in items:
                if item['book'] not in books and len(books) < 3:
                    books.append(item['book'])
            items = [s for s in items if s['book'] in books]
        return {'accepted': True, 'sources': items}
    if mode == 'validate':
        data = dict(payload)
        data['profile'] = profile  # the model cannot impersonate a different book
        authorized = None
        if payload.get('_discussion_proof') is not None:
            from classroom import approved_quotes
            authorized = approved_quotes(payload['_discussion_proof'], profile)
        errors = check_output(data, authorized_quotes=authorized)
        return {'accepted': not errors, 'errors': errors,
                'boundary': '仅结构、出处和义项检查；用户仍须核文义与原刻'}
    raise ValueError('未知 Pi 工具模式')


if __name__ == '__main__':
    try:
        payload = json.load(sys.stdin)
        result = handle(sys.argv[1], payload, os.environ.get('LIUREN_PROFILE', '凝神子'))
    except (ValueError, KeyError, OSError) as exc:
        result = {'accepted': False, 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False))
