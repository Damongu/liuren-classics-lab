"""Read-only projection of v3 learning data into the existing proposal engine."""
from __future__ import annotations
from datetime import date, timedelta
import json
from pathlib import Path

import curriculum_v3 as curriculum


def project(state: dict) -> dict:
    topics = {}
    for level in range(1, 7):
        slot = state['levels'].get(str(level), {})
        topics[f'L{level}'] = {'hist': [int(x == 1) for x in slot.get('hist', [])],
                              'teachback': slot.get('teachback', False)}
    sessions = []
    for row in state['sessions'].values():
        results = row['results']
        if row['mode'] != 'practice' or not row.get('recorded'):
            continue
        sessions.append({'level': row['level'], 'date': row['created'],
                         'n': len(results), 'right': sum(r['score'] == 1 for r in results.values())})
    wrong = [{'level': row['level'], 'q': row['question']['prompt'], 'due': row['due'],
              'spec': [f'L{row["level"]}'], 'reasons': [row.get('reason', '待归因')],
              'first': row.get('first', row['due'])} for row in state['reviews'] if not row['archived']]
    projected_levels = {str(n): {'hist': [int(x == 1) for x in s.get('hist', [])], 'teachback': s.get('teachback', False)}
                        for n, s in state['levels'].items()}
    projected_levels.setdefault('1', {})['topics'] = topics
    return {'levels': projected_levels, 'sessions': sessions, 'wrong': wrong}


def guide_rules(receipts: list[dict]) -> list[dict]:
    found = []
    if not receipts:
        return found
    recent = receipts[-2:]
    tests = [('R12', sum(r['result'] == 'fail' for r in receipts if r['at'][:10] == receipts[-1]['at'][:10]) >= 2,
              '同日导读不足至少两次'),
             ('R13', len(recent) == 2 and all(r['result'] == 'fail' for r in recent), '连续两次导读回执失败')]
    grade = receipts[-1]['grade']
    same = [r for r in receipts if r['grade'] == grade][-3:]
    tests.append(('R14', len(same) == 3 and all(r['minutes'] > r['limit'] for r in same), f'{grade}档连续三次导读超时'))
    for rule, hit, evidence in tests:
        if hit:
            found.append({'rule': rule, 'key': f'{rule}|v3|{grade}|{receipts[-1]["anchor"]}',
                          'title': evidence + '，建议检查导读粒度', 'evidence': [evidence, receipts[-1]['anchor']],
                          'suggestion': '减少导读负担或拆分当节精读块，先请用户批准，不先实施。',
                          'benefit': '使导读服务原文阅读', 'risk': '拆节增加课次', 'rollback': '保留旧卡与预算，可恢复原读法'})
    return found


def show_brief(engine, sig, proposals) -> None:
    data = curriculum.status()
    levels = data['levels']
    unfinished = next((x for x in levels if not x.get('passed')), None)
    print('v3 开场简报（旧九关成绩不参与）')
    print('建议内容：', unfinished['name'] if unfinished else '结课测／按需复现')
    print('到期复现：', data['due'])
    for slot in levels:
        print(f'L{slot["id"]} {slot["name"]}：', '通过' if slot.get('passed') else '待复述' if slot.get('ready') else '待练习')
    fresh = engine._fresh_signals(sig)
    print('未处理信号：', len(fresh))
    for signal in fresh[:10]:
        print(signal['type'], signal.get('topic'), signal.get('note'))
    print('未结清提案：')
    for p in engine.open_proposals(proposals):
        print(p['id'], p['status'], p['title'])


def run_rules(engine, sig):
    state = curriculum._load()
    old_topics, old_lv = engine.tutor.LEVEL1_TOPICS, engine.tutor.LV
    try:
        engine.tutor.LEVEL1_TOPICS = tuple(f'L{x}' for x in range(1, 7))
        engine.tutor.LV = {n: {'name': name} for n, name in curriculum.LEVELS.items()}
        found = engine.run_rules(project(state), sig)
    finally:
        engine.tutor.LEVEL1_TOPICS, engine.tutor.LV = old_topics, old_lv
    for item in found:
        item['key'] += '|v3'  # proposals do not collide with old nine-stage findings
        item['suggestion'] = item['suggestion'].replace('tools/tutor.py --weak', 'v3错题队列按原因补强；旧 --weak 不作新成绩；参考')
    path = curriculum.STATE.parent / '_guide_v3_receipts.json'
    receipts = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    return found + guide_rules(receipts)
