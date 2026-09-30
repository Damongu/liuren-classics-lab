"""Evidence-bound, independent Pi consultations returned to the same classroom.

The main book remains the teacher. At most two other book profiles respond, then
the reviewer compares their checked statements. No model grades student work;
consultations are ephemeral, read-only and cannot recursively start discussions.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

from check_tutor_output import check_output
from launch_book import BOOKS, ROOT, command
from model_acceptance import event_result
from vault_sources import get_source, search

TERMS = ('行年', '本命', '年命', '贵人', '貴人', '天乙', '用神', '涉害', '伏吟', '返吟',
         '鬼贼', '鬼賊', '己身', '九宗门', '三传', '三傳', '禄', '祿')
PREFER = ('景祐', '武经', '略决', '太白', '邵彦和', '壬归', '心镜', '大全查手', '阿甲', '林景行', '卜筮残', '凝神子')


def direct_cli(cmd: list[str]) -> tuple[list[str], str | None]:
    # The managed Windows launcher uses spawnSync; bypass that extra process so
    # timeout kills the actual model process instead of leaving its child alive.
    if len(cmd)<2 or Path(cmd[1]).name!='pi-launcher.js':
        return cmd, None
    install=Path(cmd[1]).parent.parent/'install'
    version=(install/'current-version').read_text(encoding='utf-8').strip()
    if version in ('.','..') or not re.fullmatch(r'[0-9A-Za-z._+-]+',version):
        raise ValueError('Pi安装版本指针无效')
    package=(install/'releases'/version/'node_modules/@earendil-works/pi-coding-agent').resolve()
    data=json.loads((package/'package.json').read_text(encoding='utf-8'))
    entry=data.get('bin')
    entry=entry.get('pi') if isinstance(entry,dict) else entry
    if not isinstance(entry,str):raise ValueError('Pi安装未声明CLI')
    cli=(package/entry).resolve()
    if not cli.is_relative_to(package) or not cli.is_file():raise ValueError('Pi CLI越界或不存在')
    return [cmd[0],str(cli),*cmd[2:]], str(install)


def keywords(payload: dict) -> list[str]:
    explicit = payload.get('keywords', [])
    if not isinstance(explicit, list) or any(not isinstance(k, str) for k in explicit):
        raise ValueError('keywords须为原文检索词列表')
    context = str(payload.get('topic', '')) + str(payload.get('question', ''))
    words = [k.strip() for k in explicit if k.strip()] + [k for k in TERMS if k in context]
    return list(dict.fromkeys(words))[:8]


def source_bundle(author: str, words: list[str]) -> list[dict]:
    found = {}
    for word in words:
        for hit in search(word, author=author, limit=6):
            item = get_source(hit['anchor_id'])
            if not item['polluted'] and item.get('citation_allowed') is not False:
                found.setdefault(item['anchor_id'], {**item, 'text': hit['text']})
    # Short exact windows keep the context bounded; quotes must fit these windows.
    return list(found.values())[:3]


def plan(payload: dict, main: str) -> list[dict]:
    if main not in BOOKS and main != '复盘官':
        raise ValueError('课堂讨论须由主书魂或复盘官发起')
    if not isinstance(payload.get('topic'), str) or not payload['topic'].strip():
        raise ValueError('讨论须明确当前主题')
    if not isinstance(payload.get('question'), str) or not payload['question'].strip():
        raise ValueError('讨论须明确分歧或追问，不让书魂空谈')
    if len(payload['question']) > 3000 or len(payload['topic']) > 200:
        raise ValueError('讨论过长，请围绕一个缺口拆节')
    if not isinstance(payload.get('main_claim',''),str) or len(payload.get('main_claim',''))>3000:
        raise ValueError('主讲观点须为不超过3000字的当前小节摘要')
    requested = payload.get('profiles', [])
    if not isinstance(requested, list) or any(p not in BOOKS for p in requested):
        raise ValueError('讨论参与者须为已落地书魂')
    if len(set(requested)) > 2:
        raise ValueError('每轮最多两位其他书魂，连主讲最多三书')
    words = keywords(payload)
    if not words:
        raise ValueError('请给一两个原文关键词，不能凭空选发言者')
    people = [p for p in dict.fromkeys(requested or PREFER) if p != main]
    selected = []
    for name in people:
        sources = source_bundle(name, words)
        if sources:
            selected.append({'profile': name, 'role': '补证' if not selected else '质疑与边界', 'sources': sources})
        if len(selected) == 2:
            break
    return selected


def invoke(profile: str, prompt: str, model: dict | None = None) -> dict:
    """Use Pi's configured credentials; no API key is read or exported by us."""
    cmd = command(profile)
    if model:
        provider, identifier = model.get('provider'), model.get('id')
        if not isinstance(provider, str) or not isinstance(identifier, str):
            raise ValueError('当前Pi模型信息无效')
        cmd[cmd.index('--provider') + 1] = provider
        cmd += ['--model', identifier]
    cmd += ['--offline', '--no-session', '--print', '--mode', 'json',
            '--tools', 'liuren_source,liuren_validate_output', '--', prompt]
    cmd,managed_install=direct_cli(cmd)
    env = {**os.environ, 'LIUREN_PROFILE': profile, 'LIUREN_PYTHON': sys.executable,
           'LIUREN_DISCUSSION_CHILD': '1', 'PYTHONUTF8': '1', 'PI_TELEMETRY': '0'}
    if managed_install:env['PI_MANAGED_INSTALL_ROOT']=managed_install
    done = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True,
                          encoding='utf-8', timeout=100)
    if done.returncode:
        # Do not echo a provider's stderr/headers: report the failure without secrets.
        raise ValueError(f'{profile}的Pi调用失败（退出码{done.returncode}）；检查当前模型与Pi凭据')
    value, _ = event_result(done.stdout)
    if not isinstance(value, dict):
        raise ValueError(f'{profile}未返回可验证JSON，不能当作已通过的书魂发言')
    return value


def prompt_for(payload: dict, participant: dict) -> str:
    return ('你正在主讲会话内被自动请来参与一次短讨论，不开自己的课堂，不写日志、文件或成绩。'
            '只解释本书，针对问题补证或指出一个反例/适用边界；不为热闹制造分歧。'
            '主讲观点是待核输入，不能自动当事实。原文仅引用提供窗口或liuren_source核回同一锚点，'
            '不引其他书，不启动新讨论。无合适依据就说明无宋据，不强答。'
            '最终只输出JSON：explanation（不超过600字）、evidence_label（宋证/唐证/旁通/无宋据）、'
            'source_warning（未核原刻）、citations（anchor_id,quote,claim）、term_senses、'
            'challenge（一个追问或边界）。共名词说明六壬义；引文原样摘，不改字。\n' +
            json.dumps({'topic': payload['topic'], 'question': payload['question'],
                        'main_claim': payload.get('main_claim', ''), 'task': participant['role'],
                        'sources': participant['sources']}, ensure_ascii=False))


def checked_voice(profile: str, output: dict, supplied: list[dict]) -> list[str]:
    errors = check_output({**output, 'profile': profile})
    if not isinstance(output.get('explanation'), str) or len(output.get('explanation', '')) > 600:
        errors.append('独立发言缺正文或超过600字')
    allowed = {s['anchor_id']: s for s in supplied}
    for ref in output.get('citations', []) if isinstance(output.get('citations'), list) else []:
        if not isinstance(ref,dict):
            errors.append('引文必须是原句对象')
            continue
        if ref.get('anchor_id') not in allowed or ref.get('quote', '') not in allowed[ref['anchor_id']]['text']:
            errors.append('发言引用不在本轮提供的原文窗口中')
    if not output.get('citations'):
        errors.append('本轮补证发言须有原文，缺据可留问题但不作已核结论')
    return errors


def discuss(payload: dict, main: str, runner=invoke) -> dict:
    if os.environ.get('LIUREN_DISCUSSION_CHILD') == '1':
        return {'accepted': False, 'status': 'blocked', 'errors': ['独立书魂不能递归开讨论']}
    participants = plan(payload, main)
    if not participants:
        return {'accepted': False, 'status': 'no_evidence', 'errors': ['相关底本没有可用原文；保留疑问，不伪造书魂讨论']}
    model = payload.get('_model')
    voices = []
    def one(person):
        try:
            output = runner(person['profile'], prompt_for(payload, person), model)
            errors = checked_voice(person['profile'], output, person['sources'])
            return {'profile': person['profile'], 'role': person['role'], 'verified': not errors,
                    'output': output if not errors else None, 'errors': errors}
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return {'profile': person['profile'], 'role': person['role'], 'verified': False,
                    'output': None, 'errors': [str(exc)]}
    with ThreadPoolExecutor(max_workers=2) as pool:
        voices = list(pool.map(one, participants))
    good = [v for v in voices if v['verified']]
    result = {'accepted': False, 'status': 'blocked', 'discussion_id': str(uuid.uuid4()),
              'main_profile': main, 'topic': payload['topic'], 'voices': voices,
              'moderator': None, 'question': None, 'errors': [],
              'boundary': '原句与角色范围已程序核验，解释文义仍待课堂核阅；未写学习成绩'}
    if not good:
        result['errors'] = ['所有独立发言未通过或模型不可用；不能假装已经讨论']
        return result
    available = []
    for voice in good:
        for citation in voice['output']['citations']:
            item = get_source(citation['anchor_id'])
            if item['note_sha256'] != next(s for p in participants for s in p['sources'] if s['anchor_id']==item['anchor_id'])['note_sha256']:
                raise ValueError('讨论中原文已变更，请重新取证')
            available.append({**item, 'text': citation['quote']})
    result['source_checks'] = {s['anchor_id']: s['note_sha256'] for s in available}
    reviewer_prompt = ('这是主讲课堂的自动短讨论复核，非独立课堂，不写任何文件、日志或成绩。'
        '只总结已通过引用核验的发言；保留分歧，不强行共识，不按多数判真，不替用户回答。'
        '不得引入提供材料外的依据。最终输出与书魂相同的JSON，explanation不超过600字，'
        'challenge为一个向用户提出的理解问题。引用必须从checked_voices的citations原样取，'
        '只核同异和证据边界，混有清按/今注则证据标签用旁通。\n' +
        json.dumps({'topic': payload['topic'], 'question': payload['question'], 'checked_voices': good}, ensure_ascii=False))
    try:
        output = runner('复盘官', reviewer_prompt, model)
        errors = checked_voice('复盘官', output, available)
        if errors:
            result['errors'] = errors
        else:
            result.update(accepted=True, status='complete' if len(good)==len(voices) else 'partial',
                          moderator={'profile': '复盘官', 'verified': True, 'output': output},
                          question=output.get('challenge'))
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result['errors'] = [str(exc)]
    return result


def approved_quotes(proof: dict, main: str) -> set[tuple[str, str]]:
    """The extension supplies proof from its per-session ledger, never the model."""
    if not isinstance(proof, dict) or not proof.get('accepted') or proof.get('main_profile') != main:
        raise ValueError('讨论凭据无效或不属于当前主讲')
    result = set()
    for voice in proof.get('voices', []):
        if not voice.get('verified'):
            continue
        data = voice['output']
        errors = check_output({**data, 'profile': voice['profile']})
        if errors:
            raise ValueError('讨论引用已失效：'+'；'.join(errors))
        for ref in data.get('citations', []):
            item = get_source(ref['anchor_id'])
            if item['note_sha256'] != proof.get('source_checks', {}).get(ref['anchor_id']):
                raise ValueError('讨论后原文发生变化，须重新讨论')
            result.add((ref['anchor_id'], ref['quote']))
    return result
