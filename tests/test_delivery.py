from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import curriculum_v3 as c
import import_zhonghuang as imp
import launch_book
import vault_sources as sources
import guide_v3
import retro_v3
import retro
from check_tutor_output import check_output


def citations():
    refs = []
    for item in sources.index().values():
        if item['book'] == '景祐六壬神定经' and not item['polluted']:
            refs.append({'anchor_id': item['anchor_id'], 'quote': item['text'][-35:],
                         'claim': '本步判断依据，引用后仍须核原刻与上下文'})
            if len(refs) == 3:
                return refs


class ImportTests(unittest.TestCase):
    def make_doc(self, folder):
        file = folder / 'fixture.docx'
        ns = imp.NS['w']
        with ZipFile(file, 'w') as archive:
            archive.writestr('word/styles.xml', f'<w:styles xmlns:w="{ns}"><w:style w:styleId="h"><w:name w:val="heading 1"/></w:style><w:style w:styleId="e"><w:name w:val="經文"/></w:style></w:styles>')
            archive.writestr('word/document.xml', f'<w:document xmlns:w="{ns}"><w:body><w:p><w:pPr><w:pStyle w:val="h"/></w:pPr><w:r><w:t>卷之一</w:t></w:r></w:p><w:p><w:pPr><w:pStyle w:val="e"/></w:pPr><w:r><w:t>日為己身最要明</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>寅</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>卯</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>')
        return file

    def test_source_layers_tables_and_idempotence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = self.make_doc(root)
            data = imp.import_book(source, root / 'vault')
            self.assertEqual(data['layers'], {'经文': 1, '课盘表格': 1})
            self.assertEqual(data['entries'][0]['blocks'][1]['rows'], [['寅', '卯']])
            self.assertEqual(imp.verify_import(root / 'vault'), [])
            folder = root / 'vault/10-底本/唐宋层/中黄经'
            hashes = {p.name: p.read_bytes() for p in folder.iterdir()}
            imp.import_book(source, root / 'vault')
            self.assertEqual(hashes, {p.name: p.read_bytes() for p in folder.iterdir()})
            note = next(p for p in folder.glob('中黄经-*.md'))
            note.write_text(note.read_text(encoding='utf-8').replace('日為己身最要明', '日為他人'), encoding='utf-8')
            self.assertTrue(imp.verify_import(root / 'vault'))
            with self.assertRaises(ValueError):
                imp.import_book(source, root / 'vault')

    def test_real_source_inventory_and_hash(self):
        data = json.loads((ROOT / '六壬vault/10-底本/唐宋层/中黄经/_源文清单.json').read_text(encoding='utf-8'))
        self.assertEqual(data['n'], 79)
        self.assertEqual(data['layers']['课盘表格'], 49)
        self.assertEqual(data['layers']['经文'], 598)
        self.assertEqual(imp.verify_import(ROOT / '六壬vault'), [])
        anchors = [e['anchor_id'] for e in data['entries']]
        anchors += [b['anchor_id'] for e in data['entries'] for b in e['blocks']]
        self.assertEqual(len(anchors), len(set(anchors)))


class ProfileTests(unittest.TestCase):
    def test_actual_pi_loading_and_one_soul(self):
        cmd = launch_book.command('凝神子', '/usr/bin/pi')
        self.assertIn('--no-context-files', cmd)
        self.assertEqual(cmd.count('--append-system-prompt'), 2)
        self.assertNotIn('--agents-file', cmd)
        self.assertIn(str(ROOT / 'agents/景祐.md'), launch_book.command('景祐', '/usr/bin/pi'))
        with self.assertRaises(ValueError):
            launch_book.command('不存在的书魂', '/usr/bin/pi')

    def base(self):
        ref = citations()[0]
        return {'profile': '复盘官', 'explanation': '本段按原文解释，保留证据边界。',
                'evidence_label': '宋证', 'citations': [ref], 'source_warning': '未核原刻'}

    def test_eight_adversarial_outputs_rejected(self):
        base = self.base()
        cases = []
        for term in ('扶抑用神', '调候用神', '身强身弱取用', '喜用神补救命局', '子平十神格局'):
            cases.append({**base, 'explanation': term + '解释本课'})
        cases += [{**base, 'profile': '凝神子'},
                  {**base, 'explanation': '此课用神直接取补救命局之义'},
                  {**base, 'citations': [{'anchor_id': '景祐-虚构-001', 'quote': '虚构原文', 'claim': '断言'}]}]
        for case in cases:
            with self.subTest(case=case):
                self.assertTrue(check_output(case))

    def test_valid_source_with_pending_warning(self):
        self.assertEqual(check_output(self.base()), [])
        data = self.base(); data['source_warning'] = ''
        self.assertTrue(check_output(data))
        data = self.base(); data['explanation'] = '此处用神取六壬义，按原文查其含义。'
        data['term_senses'] = {'用神': {'sense': '六壬义', 'no_song_evidence': True}}
        self.assertEqual(check_output(data), [])


class CurriculumTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patch = patch.object(c, 'STATE', Path(self.temp.name) / '60-掌握度/_tutor_v3_state.json')
        self.patch.start()

    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()

    def unlock(self, level):
        state = c._load()
        for n in range(level):
            state['levels'][str(n)] = {'passed': True, 'ready': True, 'teachback': True}
        c._save(state)

    def answer(self, sid, qid):
        q = next(q for q in c._load()['sessions'][sid]['questions'] if q['id'] == qid)
        answer = dict(q['answers'])
        if q['open']:
            answer.update(prose='先说明实际课式再条件化断辞', reasoning='每步按原文规定说明理由',
                          boundary='未核原刻且断代层次仍须对校', citations=citations())
        return answer

    def test_questions_hide_answer_and_first_answer_is_authoritative(self):
        session = c.start_session({'level': 0})
        self.assertNotIn('answers', session['questions'][0])
        self.assertNotIn('plate', session['questions'][0])
        q = session['questions'][0]
        wrong = c.submit({'session_id': session['id'], 'question_id': q['id'], 'answer': {'score': 1}})
        self.assertEqual(wrong['score'], 0)
        second = c.submit({'session_id': session['id'], 'question_id': q['id'],
                           'answer': self.answer(session['id'], q['id'])})
        self.assertEqual(second['score'], 0)
        self.assertEqual(len(c._load()['reviews']), 1)

    def test_baseline_and_teachback_gates(self):
        with self.assertRaises(ValueError): c.start_session({'level': 1})
        session = c.start_session({'level': 0})
        for q in session['questions']:
            c.submit({'session_id': session['id'], 'question_id': q['id'], 'answer': self.answer(session['id'], q['id'])})
        self.assertTrue(c._load()['levels']['0']['passed'])
        session = c.start_session({'level': 1})
        with self.assertRaises(ValueError): c.teachback({'level': 1, 'note': '尚未练习不能通过'})
        for q in session['questions']:
            c.submit({'session_id': session['id'], 'question_id': q['id'], 'answer': self.answer(session['id'], q['id'])})
        self.assertFalse(c._load()['levels']['1']['passed'])
        c.teachback({'level': 1, 'note': '用户能独立说明取用与入口边界'})
        self.assertTrue(c._load()['levels']['1']['passed'])

    def test_each_mechanical_stage_and_nine_method_balance(self):
        for level in range(5):
            for n in range(18):
                q = c.plate_question(level, random.Random(n + 30), n)
                self.assertTrue(q['answers'])
        methods = [c.plate_question(1, random.Random(10), n)['answers']['method'] for n in range(9)]
        self.assertEqual(set(methods), set(c.METHODS))

    def test_open_prose_requires_real_quotes_and_human_review(self):
        self.unlock(5)
        session = c.start_session({'level': 5})
        q = session['questions'][0]
        answer = self.answer(session['id'], q['id'])
        bad = deepcopy(answer);bad['citations'][0]['quote'] = '不存在的原文引句'
        with self.assertRaises(ValueError): c.submit({'session_id': session['id'], 'question_id': q['id'], 'answer': bad})
        result = c.submit({'session_id': session['id'], 'question_id': q['id'], 'answer': answer})
        self.assertIsNone(result['score']);self.assertTrue(result['needs_human'])
        reviewed = c.human_review({'session_id': session['id'], 'question_id': q['id'],
                                   'rubric': {k: True for k in c.RUBRIC}, 'note': '已对照原文义与所有判断理由'})
        self.assertEqual(reviewed['score'], 1)
        with self.assertRaises(ValueError): c.human_review({'session_id': session['id'], 'question_id': q['id']})

    def test_review_wrong_revokes_teachback_and_preserves_original(self):
        session = c.start_session({'level': 0});q=session['questions'][0]
        c.submit({'session_id': session['id'], 'question_id': q['id'], 'answer': {}})
        state=c._load();state['reviews'][0]['due']='2020-01-01';state['levels']['0']={'passed':True,'teachback':True};c._save(state)
        review=c.start_session({'level':0,'mode':'review'})
        c.submit({'session_id':review['id'],'question_id':review['questions'][0]['id'],'answer':{}})
        state=c._load();self.assertFalse(state['levels']['0']['passed']);self.assertEqual(state['reviews'][0]['answer'],{})
        self.assertEqual(len(state['reviews']),1)

    def test_holdout_excluded_and_reference_hidden_until_submit(self):
        training, holdout=c._duanan_split()
        self.assertEqual(len(holdout),5)
        self.assertFalse({x['案'] for x in training} & {x['案'] for x in holdout})
        for n in range(5):
            q=c.open_question(6,random.Random(10),n,True)
            public=c._public_question(q)
            self.assertNotIn('source_anchor',public)
            self.assertNotIn('plate',public)
            self.assertIn(holdout[n]['案'],public['prompt'])

    def test_all_six_levels_end_to_end_and_open_pending_gate(self):
        for level in range(7):
            session = c.start_session({'level': level})
            for q in session['questions']:
                result = c.submit({'session_id': session['id'], 'question_id': q['id'],
                                   'answer': self.answer(session['id'], q['id'])})
                if level >= 5:
                    self.assertTrue(result['needs_human'])
                    c.human_review({'session_id': session['id'], 'question_id': q['id'],
                                    'rubric': {k: True for k in c.RUBRIC}, 'note': '对照原文义检查每一步并确认边界'})
            if level:
                self.assertFalse(c._load()['levels'][str(level)]['passed'])
                c.teachback({'level':level,'note':'能独立讲清本关操作单元与反例'})
            self.assertTrue(c._load()['levels'][str(level)]['passed'])
        exam = c.start_session({'level':6,'mode':'exam'})
        self.assertEqual(len(exam['questions']),5)
        for q in exam['questions']:
            c.submit({'session_id':exam['id'],'question_id':q['id'],'answer':self.answer(exam['id'],q['id'])})
            c.human_review({'session_id':exam['id'],'question_id':q['id'],
                            'rubric':{k:True for k in c.RUBRIC},'note':'人工确认无原则错误，引用与理由成立'})
        self.assertTrue(c.status()['exam_passed'])
        self.assertFalse((Path(self.temp.name)/'60-掌握度/_tutor_state.json').exists())

    def test_review_intervals_and_archive_retains_answer(self):
        session=c.start_session({'level':0});q=session['questions'][0]
        c.submit({'session_id':session['id'],'question_id':q['id'],'answer':{}})
        for step in range(4):
            state=c._load();state['reviews'][0]['due']='2020-01-01';c._save(state)
            review=c.start_session({'mode':'review','level':0});q=review['questions'][0]
            c.submit({'session_id':review['id'],'question_id':q['id'],'answer':self.answer(review['id'],q['id'])})
            item=c._load()['reviews'][0]
            self.assertEqual(item['step'],step+1)
            self.assertEqual(item['answer'],{})
        self.assertTrue(item['archived']);self.assertEqual(len(item['history']),4)


class WorkflowTests(unittest.TestCase):
    def test_guide_anchors_and_three_receipt_rules(self):
        source = next(x for x in sources.index().values() if x['author']=='凝神子')
        raw=guide_v3.render(source['anchor_id'])
        self.assertIn(source['note_sha256'],raw)
        self.assertIn('TODO(agent)',raw)
        self.assertIn('## 7 阅读预算',raw)
        receipts=[{'anchor':source['anchor_id'],'grade':'A','result':'fail','minutes':8,'limit':5,'at':'2026-09-30'}]*3
        self.assertEqual({r['rule'] for r in retro_v3.guide_rules(receipts)},{'R12','R13','R14'})
        self.assertEqual(retro_v3.guide_rules(receipts[:1]),[])

    def test_v3_retro_projection_does_not_read_old_scores(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(c,'STATE',Path(temp)/'state.json'):
            projected=retro_v3.project(c._load())
            self.assertEqual(projected['sessions'],[])
            self.assertEqual(projected['wrong'],[])
            sig={'signals':[],'sessions':[]}
            found=retro_v3.run_rules(retro,sig)
            self.assertFalse(any(x['rule']=='ERR' for x in found),found)

    def test_checker_global_duplicate_anchor_detection(self):
        from check_v3_frontmatter import check_vault
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'10-底本';folder.mkdir()
            for name in ('first','second'):
                (folder/f'{name}.md').write_text('---\nanchor_id: 景祐-同名-001\n作者: 景祐\n与六壬关系: 主体\n---\n',encoding='utf-8')
            self.assertTrue(any('重复' in issue.message for issue in check_vault(Path(temp))))


if __name__ == '__main__':
    unittest.main()
