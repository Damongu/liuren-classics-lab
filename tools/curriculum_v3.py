"""Six-stage browser curriculum with server-owned questions and durable review.

Mechanical marks come from the existing plate engine. Open prose receives source
validation and an explicit human rubric, never a simulated LLM correctness mark.
Old tutor state is neither read as a passing grade nor modified.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import random
import re
import sys
from threading import RLock
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'liuren-paipan'))
from liuren import Options, from_ganzhi, to_dict
from liuren.ganzhi import GAN, ZHI, gz_index, gz_name, shift
from liuren.search import enumerate720
from vault_sources import VAULT, get_source, index, validate_citation
from check_tutor_output import ZP_INTERPRETATIONS

VERSION = 'v3-2026-09-30.1'
STATE = VAULT / '60-掌握度/_tutor_v3_state.json'
INTERVALS = (1, 3, 7, 21)
WINDOW, CORRECT = 12, 11
LOCK = RLock()
METHODS = ('贼克', '比用', '涉害', '遥克', '昴星', '别责', '八专', '伏吟', '返吟')
LEVELS = {
    0: '基础排盘体检', 1: '九宗门课体识别',
    2: '涉害、口径分歧与贵人天将', 3: '遥克、别责、伏吟与返吟',
    4: '本命、行年与年命上神', 5: '断辞组织与原文锚定', 6: '南宋断案复盘',
}
SONG_BOOKS = {'大六壬五变中黄经', '景祐六壬神定经', '武经总要', '六壬断案'}
RUBRIC = ('原文义与术语', '判断依据与反例', '证据层次与边界')


def today():
    return datetime.now(timezone(timedelta(hours=8))).date()


def _load() -> dict:
    if not STATE.exists():
        return {'version': VERSION, 'sessions': {}, 'levels': {}, 'reviews': []}
    data = json.loads(STATE.read_text(encoding='utf-8'))
    if data.get('version') != VERSION:
        raise ValueError('训练状态版本不匹配；保留原状态，请显式迁移')
    return data


def _save(data: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(STATE)
    _write_records(data)


def _write_records(data: dict) -> None:
    folder = STATE.parent
    lines = ['---', 'tags: [训练, v3]', '---', '', '# v3训练记录', '',
             '程序维护；旧九关成绩不计入。半对保留为分歧，不计满分；开放文义需人工验收。', '']
    for sid, session in data['sessions'].items():
        results = session['results']
        exact = sum(r['score'] == 1 for r in results.values())
        pending = sum(r.get('needs_human', False) for r in results.values())
        lines += [f'- {session["created"]} · {sid} · {session["title"]}：'
                  f'{len(results)}/{len(session["questions"])} 题，正确 {exact}，待人工 {pending}。']
    (folder / 'v3训练记录.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    wrong = ['---', 'tags: [错题, v3]', '---', '', '# v3错题队列', '']
    for item in data['reviews']:
        wrong += [f'- {item["id"]} · L{item["level"]} · {item["question"]["prompt"]} · '
                  f'原答 `{json.dumps(item["answer"], ensure_ascii=False)}` · '
                  f'归因 {item.get("reason", "待归因")} · 到期 {item["due"]} · '
                  f'{"已归档" if item["archived"] else "待复现"}']
    (folder / 'v3错题队列.md').write_text('\n'.join(wrong) + '\n', encoding='utf-8')


def method(plate) -> str:
    return {'元首': '贼克', '重审': '贼克', '知一': '比用'}.get(plate.keshi, plate.keshi)


def field(key: str, label: str, options=None) -> dict:
    return {'key': key, 'label': label, 'options': list(options or [])}


def course(rng: random.Random, target: str | None = None):
    choices = enumerate720()
    if target:
        choices = [c for c in choices if method(c.plate) == target]
    c = rng.choice(choices)
    shi = rng.choice(ZHI)
    jiang = shift(shi, c.k)
    dn = rng.choice(('昼', '夜'))
    return from_ganzhi(c.day_gz, shi, jiang, daynight=dn)


def plate_question(level: int, rng: random.Random, number: int) -> dict:
    p = course(rng, METHODS[number % len(METHODS)] if level == 1 else
               ('遥克', '别责', '伏吟', '返吟')[number % 4] if level == 3 else
               '涉害' if level == 2 and number % 3 == 0 else None)
    prompt = f'{p.day_gz}日，{p.shi}时，{p.jiang}将，{p.daynight}贵人。'
    answers, fields, alternative = {}, [], []
    if level == 0:
        di = rng.choice(ZHI)
        fields = [field('sky', f'地盘{di}宫的天盘神', ZHI)]
        answers['sky'] = p.tian[di] if hasattr(p, 'tian') else p.up(di)
        # Reverse display order, first lesson on the right, without changing keys.
        for i in range(3, -1, -1):
            fields.append(field(f'ke{i+1}', f'第{i+1}课上神', ZHI))
            answers[f'ke{i+1}'] = p.kes[i].up
        prompt += '填写天盘与四课；首答统计用于免修体检。'
    elif level in (1, 3):
        fields = [field('method', '取用宗门', METHODS), field('chuan', '三传（初→中→末）')]
        answers = {'method': method(p), 'chuan': ''.join(p.chuan)}
        if level == 1:
            prompt += '辨认宗门并写出三传；不同宗门按等概率轮换。'
        else:
            prompt += '辨认入口边界并写出三传。'
    elif level == 2:
        if number % 3 == 0:
            fields = [field('initial', '纯计重法初传', ZHI), field('depth', '该候选涉害重数')]
            answers = {'initial': p.chuan[0], 'depth': str(p.shehai_depth(p.chuan[0]))}
            direct = from_ganzhi(p.day_gz, p.shi, p.jiang, daynight=p.daynight,
                                 opts=Options(shehai_method='direct'))
            if direct.chuan[0] != p.chuan[0]:
                alternative = [{'initial': direct.chuan[0], 'depth': str(p.shehai_depth(direct.chuan[0]))}]
            prompt += '按涉归本家纯计重填写；直取法异说并列反馈，不据明细法冒称宋据。'
        elif number % 3 == 1:
            fields = [field('guiren', '贵人天盘支', ZHI), field('direction', '贵人顺逆', ('顺', '逆'))]
            answers = {'guiren': p.guiren, 'direction': p.guiren_dir}
            prompt += '填写贵人与顺逆。'
        else:
            z = rng.choice(ZHI)
            fields = [field('general', f'天盘{z}乘何将', list(dict.fromkeys(p.jiang12.values())))]
            answers = {'general': p.jiang12[z]}
            prompt += '将名由程序判分；吉凶义与出处在复述验收中解释，不能只背吉凶标签。'
    elif level == 4:
        age, sex = rng.randrange(1, 91), rng.choice(('男', '女'))
        birth = gz_name(rng.randrange(60))
        xing = shift('寅' if sex == '男' else '申', (age - 1) * (1 if sex == '男' else -1))
        up = p.up if hasattr(p, 'up') else lambda z: p.tian[z]
        fields = [field('birth', '本命支', ZHI), field('xing', '行年支', ZHI),
                  field('birth_sky', '本命上神', ZHI), field('xing_sky', '行年上神', ZHI)]
        answers = {'birth': birth[1], 'xing': xing, 'birth_sky': up(birth[1]), 'xing_sky': up(xing)}
        prompt += f'教学设例：{sex}，{birth}生，虚岁{age}。男一岁寅顺行、女一岁申逆行，按虚岁逐支推。'
        prompt += '依据《景祐·释行年》；这里只判支位，不臆造年命断辞。'
        if sex == '女':
            prompt += '当前录文“女十一岁壬午”与前句逆行不一致，尚待核原刻；本题明确按逆行规定计算，不掩盖例句冲突。'
            if age == 11:
                alternative = [{**answers, 'xing': '午', 'xing_sky': up('午')}]
    return {'id': str(uuid.uuid4()), 'prompt': prompt, 'fields': fields, 'answers': answers,
            'alternatives': alternative, 'plate': to_dict(p), 'reason': p.reason,
            'open': False, 'case': {'day': p.day_gz, 'shi': p.shi, 'jiang': p.jiang, 'daynight': p.daynight}}


def _duanan_split() -> tuple[list[dict], list[dict]]:
    cases = json.loads((ROOT / 'liuren-paipan/tests/duanan_cases.json').read_text(encoding='utf-8'))
    valid = [c for c in cases if c.get('日干支') and c.get('占时') and c.get('月将')]
    # Fixed 5 unseen cases; never included in L6/review sampling.
    holdout = valid[-5:]
    return valid[:-5], holdout


def _case_source(case: dict) -> dict:
    for item in index().values():
        if item['book'] == '六壬断案' and case['案'] in item['text']:
            return get_source(item['anchor_id'])
    raise ValueError(f'断案正文缺失：{case["案"]}')


def open_question(level: int, rng: random.Random, number: int, exam: bool = False) -> dict:
    source = None
    if level == 6:
        training, holdout = _duanan_split()
        case = holdout[number] if exam else rng.choice(training)
        p = from_ganzhi(case['日干支'], case['占时'], case['月将'])
        source = _case_source(case)
        prompt = f'断案 {case["案"]}。{case["日干支"]}日、{case["占时"]}时、{case["月将"]}将。'
        prompt += '先独立起课、识别取用和组织断辞，再提交对照底本。原案昼夜/年命缺信息时明确写未定，不臆补。'
        source_anchor = source['anchor_id']
    else:
        p = course(rng)
        prompt = f'{p.day_gz}日、{p.shi}时、{p.jiang}将、{p.daynight}。'
        prompt += '用毕法组织一段有条件、有边界的断辞；毕法只作明本字典，至少三步判断各锚回宋本录文。'
        source_anchor = None
    return {'id': str(uuid.uuid4()), 'prompt': prompt, 'open': True,
            'fields': [field('method', '取用宗门', METHODS), field('chuan', '三传（初→中→末）')],
            'answers': {'method': method(p), 'chuan': ''.join(p.chuan)}, 'alternatives': [],
            'plate': to_dict(p), 'reason': p.reason,
            'source_anchor': source_anchor, 'source_sha256': source['note_sha256'] if source else None,
            'case': {'day': p.day_gz, 'shi': p.shi, 'jiang': p.jiang, 'daynight': p.daynight},
            'requirements': '断辞、判断理由、证据边界、至少三条 anchor_id＋原文引句＋支持哪一步；完成后人工文义验收。'}


def _public_question(q: dict) -> dict:
    return {k: deepcopy(v) for k, v in q.items() if k not in (
        'answers', 'alternatives', 'plate', 'reason', 'source_anchor', 'source_sha256', 'review_id')}


def _public_session(sid: str, session: dict) -> dict:
    return {'id': sid, 'level': session['level'], 'title': session['title'],
            'mode': session['mode'], 'questions': [_public_question(q) for q in session['questions']],
            'results': deepcopy(session['results']), 'created': session['created']}


def start_session(payload: dict) -> dict:
    try:
        level = int(payload.get('level', 1))
    except (ValueError, TypeError):
        raise ValueError('关卡必须为 0–6')
    if level not in LEVELS:
        raise ValueError('关卡必须为 0–6')
    mode = payload.get('mode', 'practice')
    if mode not in ('practice', 'review', 'exam'):
        raise ValueError('训练模式无效')
    with LOCK:
        state = _load()
        if mode == 'review':
            due = [x for x in state['reviews'] if not x['archived'] and x['due'] <= today().isoformat()]
            if not due:
                raise ValueError('没有到期复现')
            questions = []
            for item in due[:12]:
                q = deepcopy(item['question'])
                q['id'] = str(uuid.uuid4())
                q['review_id'] = item['id']
                questions.append(q)
        else:
            if mode == 'exam':
                if level != 6 or not all(state['levels'].get(str(i), {}).get('passed') for i in range(1, 7)):
                    raise ValueError('结课测需 L1–L6 全部练习与复述通过')
            if level > 1 and not state['levels'].get(str(level - 1), {}).get('passed'):
                raise ValueError(f'先完成 L{level-1} 练习及白话复述验收')
            if level == 1 and not state['levels'].get('0', {}).get('passed'):
                raise ValueError('先做基础体检；全对后免修机械排盘关')
            rng = random.Random(uuid.uuid4().int)
            count = 5 if mode == 'exam' else 12
            # Offset chosen uniformly, then cycle each method; no natural-frequency bias.
            offset = rng.randrange(9)
            questions = [(open_question(level, rng, n, mode == 'exam') if level >= 5 else
                          plate_question(level, rng, n + offset)) for n in range(count)]
        sid = str(uuid.uuid4())
        session = {'level': level, 'title': LEVELS[level], 'created': today().isoformat(),
                   'mode': mode, 'questions': questions, 'results': {}}
        state['sessions'][sid] = session
        _save(state)
        return _public_session(sid, session)


def get_session(sid: str) -> dict:
    with LOCK:
        session = _load()['sessions'].get(sid)
        if session is None:
            raise ValueError('训练会话不存在')
        return _public_session(sid, session)


def _normalize(value) -> str:
    return re.sub(r'[\s，,、。→>\-]', '', str(value))


def _validate_open(answer: dict) -> list[dict]:
    for key in ('prose', 'reasoning', 'boundary'):
        if not isinstance(answer.get(key), str) or len(answer[key].strip()) < 5:
            raise ValueError(f'开放题缺 {key}（至少五字）')
        if any(term in answer[key] for term in ZP_INTERPRETATIONS):
            raise ValueError('断辞含子平义项；请按六壬原文解释')
    refs = answer.get('citations')
    if not isinstance(refs, list) or len(refs) < 3 or len(refs) > 12:
        raise ValueError('至少三条、至多十二条原文依据')
    checked = [validate_citation(c, allowed_books=SONG_BOOKS) for c in refs]
    if any(s['author'] in ('阿甲', '林景行') for s in checked):
        raise ValueError('清按和今注不计入宋系原辞三条依据，可另作旁通；请换原辞锚点')
    if len({(r['anchor_id'], r['quote']) for r in refs}) < 3:
        raise ValueError('至少三条不同的原文依据，重复引句不能凑数')
    return checked


def _update_level(state: dict, session: dict) -> None:
    if session['mode'] != 'practice' or len(session['results']) != 12:
        return
    if any(r.get('needs_human') for r in session['results'].values()):
        return
    slot = state['levels'].setdefault(str(session['level']), {})
    hist = slot.setdefault('hist', [])
    if not session.get('recorded'):
        hist.extend(session['results'][q['id']]['score'] for q in session['questions'])
        session['recorded'] = True
    slot['ready'] = sum(v == 1 for v in hist[-12:]) >= (12 if session['level'] == 0 else 11)
    if session['level'] == 0:
        slot['passed'] = slot['ready']
    else:
        slot['passed'] = bool(slot['ready'] and slot.get('teachback'))


def _record_review(state: dict, session: dict, question: dict, answer: dict, result: dict) -> None:
    if question.get('review_id'):
        item = next(x for x in state['reviews'] if x['id'] == question['review_id'])
        if result['score'] == 1:
            item['step'] += 1
            item['archived'] = item['step'] >= len(INTERVALS)
        else:
            item['step'] = 0
            slot = state['levels'].setdefault(str(item['level']), {})
            slot['teachback'] = False
            slot['passed'] = False
        item['due'] = (today() + timedelta(days=INTERVALS[min(item['step'], 3)])).isoformat()
        item.setdefault('history', []).append({'date': today().isoformat(), 'score': result['score']})
    elif result['score'] == 0 and session['mode'] == 'practice':
        state['reviews'].append({'id': str(uuid.uuid4()), 'level': session['level'],
                                 'question': deepcopy(question), 'answer': deepcopy(answer),
                                 'step': 0, 'archived': False, 'reason': '待归因', 'first': today().isoformat(),
                                 'due': (today() + timedelta(days=1)).isoformat()})
        slot = state['levels'].setdefault(str(session['level']), {})
        slot['teachback'] = False
        slot['passed'] = False


def submit(payload: dict) -> dict:
    with LOCK:
        state = _load()
        sid, qid = payload.get('session_id'), payload.get('question_id')
        session = state['sessions'].get(sid)
        if session is None:
            raise ValueError('训练会话不存在')
        question = next((q for q in session['questions'] if q['id'] == qid), None)
        if question is None:
            raise ValueError('题号不属于当前会话')
        if qid in session['results']:
            return deepcopy(session['results'][qid])  # first answer wins, retry-safe
        answer = payload.get('answer')
        if not isinstance(answer, dict):
            raise ValueError('答案必须为对象')
        sources = _validate_open(answer) if question['open'] else []
        if question.get('source_anchor'):
            current = get_source(question['source_anchor'])
            if current['note_sha256'] != question['source_sha256']:
                raise ValueError('出题后原案已变更；拒绝旧题判分，请重新开题')
        expected = question['answers']
        exact = all(_normalize(answer.get(k, '')) == _normalize(v) for k, v in expected.items())
        alternate = any(all(_normalize(answer.get(k, '')) == _normalize(v) for k, v in alt.items())
                        for alt in question['alternatives'])
        result = {'score': 1 if exact else 0.5 if alternate else 0,
                  'label': '结构正确' if exact else '半对／另一口径' if alternate else '结构错误',
                  'expected': expected, 'reason': question['reason'], 'plate': question['plate'],
                  'answer': deepcopy(answer), 'needs_human': bool(question['open'] and exact),
                  'source_checks': [{'anchor_id': s['anchor_id'], 'pending': s['pending'],
                                     'layer': s['layer'], 'note_sha256': s['note_sha256']} for s in sources]}
        if question['open'] and exact:
            result['score'] = None
            result['label'] = '结构与引文通过，断辞文义待人工验收'
        if question.get('source_anchor'):
            result['comparison'] = get_source(question['source_anchor'])
            result['comparison_warning'] = '完整校注本上下文；自动段作者边界待核，不认证全部为南宋原辞'
        session['results'][qid] = result
        if not result['needs_human']:
            _record_review(state, session, question, answer, result)
        _update_level(state, session)
        _save(state)
        return deepcopy(result)


def human_review(payload: dict) -> dict:
    with LOCK:
        state = _load()
        session = state['sessions'].get(payload.get('session_id'))
        if session is None:
            raise ValueError('训练会话不存在')
        qid = payload.get('question_id')
        result = session['results'].get(qid)
        if result is None or not result.get('needs_human'):
            raise ValueError('该题没有待人工文义验收')
        rubric, note = payload.get('rubric'), payload.get('note', '')
        if not isinstance(rubric, dict) or any(type(rubric.get(k)) is not bool for k in RUBRIC):
            raise ValueError('须逐项给出原文义、理由边界、证据层次的人工结论')
        if not isinstance(note, str) or len(note.strip()) < 5:
            raise ValueError('人工验收须留具体说明（至少五字）')
        for source in result['source_checks']:
            if get_source(source['anchor_id'])['note_sha256'] != source['note_sha256']:
                raise ValueError('验收前原文发生改变，须重新核查')
        result['score'] = 1 if all(rubric.values()) else 0
        result['needs_human'] = False
        result['human_review'] = {'rubric': rubric, 'note': note, 'date': today().isoformat()}
        result['label'] = '结构与人工文义验收通过' if result['score'] else '人工文义验收未通过'
        question = next(q for q in session['questions'] if q['id'] == qid)
        _record_review(state, session, question, result['answer'], result)
        _update_level(state, session)
        _save(state)
        return deepcopy(result)


def teachback(payload: dict) -> dict:
    try:
        level = int(payload.get('level'))
    except (ValueError, TypeError):
        raise ValueError('复述关卡必须为 1–6')
    if level not in range(1, 7) or len(str(payload.get('note', '')).strip()) < 5:
        raise ValueError('需提供 1–6 关卡和具体复述验收说明')
    with LOCK:
        state = _load()
        slot = state['levels'].get(str(level), {})
        if not slot.get('ready'):
            raise ValueError('练习尚未达标，不能记录复述过关')
        slot.update(teachback=True, passed=True, teachback_note=payload['note'], teachback_date=today().isoformat())
        _save(state)
        return {'level': level, 'passed': True}


def status() -> dict:
    with LOCK:
        state = _load()
        levels = [{'id': n, 'name': title, **state['levels'].get(str(n), {})} for n, title in LEVELS.items()]
        due = sum(not r['archived'] and r['due'] <= today().isoformat() for r in state['reviews'])
        exams = [s for s in state['sessions'].values() if s['mode'] == 'exam']
        exam_passed = any(len(s['results']) == 5 and sum(r['score'] == 1 for r in s['results'].values()) >= 4
                          and all(r['score'] == 1 or r.get('human_review') and
                                  r['human_review']['rubric']['证据层次与边界'] and
                                  r['human_review']['rubric']['原文义与术语'] for r in s['results'].values()) for s in exams)
        return {'version': VERSION, 'levels': levels, 'due': due, 'exam_passed': exam_passed,
                'recent_sessions': [{'id': sid, 'title': s['title'], 'done': len(s['results'])}
                                    for sid, s in list(state['sessions'].items())[-10:]]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--list', action='store_true')
    args = ap.parse_args()
    print(json.dumps(status() if args.status else LEVELS, ensure_ascii=False, indent=2))
    print('正式作答入口：http://127.0.0.1:8765/curriculum.html')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
