import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_remaining_content as content
import catalogue
from check_tutor_output import check_output
from duanan_layers import ranges
from launch_book import BOOKS, command
import model_acceptance
import guide_v3
import curriculum_v3
import pi_tools
import vault_sources as sources


class RemainingTests(unittest.TestCase):
    def test_all_profiles_cards_have_real_source_and_complete_sections(self):
        self.assertEqual(content.build(check=True), [])
        inventory = json.loads((ROOT / 'docs/content-inventory.json').read_text(encoding='utf-8'))
        self.assertEqual(set(inventory['profiles']), set(BOOKS))
        self.assertEqual(len(inventory['cards']), 8)
        for name in BOOKS:
            raw = (ROOT / f'agents/{name}.md').read_text(encoding='utf-8')
            for heading in content.HEADINGS:
                self.assertIn(f'## {heading}', raw)
            self.assertEqual(len(inventory['profiles'][name]), 2)
            for ref in inventory['profiles'][name]:
                item = sources.get_source(ref['anchor_id'])
                self.assertEqual(item['author'], name)
                self.assertIn(ref['quote'], item['text'])
        for name in inventory['cards']:
            raw = (sources.VAULT / f'90-禄命辅助/{name}.md').read_text(encoding='utf-8')
            self.assertNotIn('TODO', raw)
            self.assertNotIn('状态: stub', raw)
            self.assertIn('宋本硬证: []', raw)

    def test_short_gloss_never_swallows_following_original(self):
        body = '邵先生曰：主失鹅。缘生谛：申，象鹅。原案后文不明。\n爱函按：盖申为用。后面仍待核。'
        result = ranges(body, '验收')
        modern = next(s for s in result if s['author']=='林景行')
        qing = next(s for s in result if s['author']=='阿甲')
        self.assertEqual(modern['text'], '缘生谛：申，象鹅。')
        self.assertEqual(qing['text'], '爱函按：盖申为用。')
        for segment in result:
            self.assertEqual(body[segment['start_char']:segment['end_char']].strip(), segment['text'])

    def test_mixed_context_cannot_be_cited_as_a_single_author(self):
        context = next(i for i in sources.index().values() if i.get('citation_allowed') is False)
        self.assertEqual(context['author'], '复盘官')
        with self.assertRaises(ValueError):
            sources.validate_citation({'anchor_id':context['anchor_id'],'quote':'己酉年十月','claim':'原辞'})
        for author in ('阿甲','林景行','邵彦和'):
            self.assertTrue(any(i['author']==author for i in sources.index().values()))

    def test_all_book_launch_commands_and_sources_are_scoped(self):
        for name in BOOKS:
            self.assertIn(str(ROOT / f'agents/{name}.md'), command(name,'/usr/bin/pi'))
            self.assertIn('--no-extensions', command(name,'/usr/bin/pi'))
            pointer = next(i for i in sources.index().values() if i['author']==name)
            result = pi_tools.handle('source', {'anchor':pointer['anchor_id']}, name)
            self.assertTrue(result['accepted'])
            self.assertEqual(result['source']['author'],name)
        guide = pi_tools.handle('source', {'query':'己身'}, '导读官')
        self.assertTrue(guide['sources'])
        self.assertTrue(all(s['author']=='凝神子' for s in guide['sources']))

    def test_four_cross_book_attempts_create_only_temporary_pending_logs(self):
        inventory = json.loads((ROOT / 'docs/content-inventory.json').read_text(encoding='utf-8'))
        foreign = inventory['profiles']['景祐'][0]['anchor_id']
        with tempfile.TemporaryDirectory() as temp, patch.object(pi_tools,'PENDING_DIR',Path(temp)):
            for name in ('凝神子','阿甲','林景行','大全查手'):
                result = pi_tools.handle('source', {'anchor':foreign}, name)
                self.assertFalse(result['accepted'])
            text = (Path(temp)/'v3跨书请求.md').read_text(encoding='utf-8')
            self.assertEqual(text.count('当前书魂拒绝越界'),4)

    def test_annotation_cannot_be_claimed_as_song_and_reviewer_max_three_books(self):
        items = [next(i for i in sources.index().values() if i['author']==name)
                 for name in ('阿甲','林景行','大全查手','景祐')]
        refs = [{'anchor_id':i['anchor_id'],'quote':i['text'][-15:].strip(),'claim':'核对原句'} for i in items]
        data = {'profile':'复盘官','explanation':'只核引文，保留层次边界。','evidence_label':'宋证',
                'source_warning':'未核原刻','citations':refs}
        self.assertTrue(check_output(data))
        ref = content.ref(*content.PROFILE_REFS['阿甲'][0])
        data.update(profile='阿甲',evidence_label='旁通',citations=[{'anchor_id':ref['anchor_id'],
                    'quote':ref['quote'],'claim':'清按首句'}])
        self.assertEqual(check_output(data),[])

    def test_training_search_does_not_reveal_duanan_answers_or_pollution(self):
        self.assertTrue(sources.training_search('己身'))
        self.assertTrue(all(s['book']!='六壬断案' and not s['polluted'] for s in sources.training_search('邵先生曰')))

    def test_readonly_catalogue_and_live_cases_are_complete(self):
        data = catalogue.catalogue()
        self.assertEqual(len(data['books']),12)
        self.assertEqual(len(data['cards']),8)
        prepared=model_acceptance.cases()
        self.assertEqual(len(prepared),24)
        self.assertEqual(sum(c['kind']=='reject' for c in prepared),12)

    def test_missing_credentials_are_blocked_without_running_any_model(self):
        with patch.object(model_acceptance,'readiness',return_value={'status':'not_ready','reason':'credentials_not_configured'}), \
             patch.object(model_acceptance.subprocess,'run') as call:
            report = model_acceptance.run(live=True)
            self.assertEqual(report['status'],'blocked')
            self.assertEqual(report['cases'],[])
            call.assert_not_called()

    def test_guide_budget_partition_and_source_hash_are_checked(self):
        item={'text':'甲'*3100,'note_sha256':'hash'}
        raw='源hash: hash\n'+''.join(f'## {n} 事项\n说明。\n' for n in range(1,8))
        self.assertTrue(any('分区表' in e for e in guide_v3.check_guide(raw,item)))
        raw+='| 块 | 读法 |\n| --- | --- |\n| 经文 | 精读 |\n'
        self.assertEqual(guide_v3.check_guide(raw,item),[])
        self.assertTrue(guide_v3.check_guide(raw.replace('hash','old'),item))
        self.assertTrue(guide_v3.check_guide(raw+'甲'*1001,item))

    def test_open_answers_cannot_use_modern_comments_or_duplicate_quotes(self):
        ref=content.ref(*content.PROFILE_REFS['阿甲'][0])
        citation={'anchor_id':ref['anchor_id'],'quote':ref['quote'],'claim':'不能当宋原辞'}
        payload={'prose':'按课式独立断辞','reasoning':'条件和理由分开讲','boundary':'未核原刻和清按'}
        with self.assertRaises(ValueError):
            curriculum_v3._validate_open({**payload,'citations':[citation]*3})
        ref=content.ref(*content.PROFILE_REFS['景祐'][0])
        citation={'anchor_id':ref['anchor_id'],'quote':ref['quote'],'claim':'不能重复凑数'}
        with self.assertRaises(ValueError):
            curriculum_v3._validate_open({**payload,'citations':[citation]*3})

    def test_reviewer_rejects_four_books_even_with_real_quotes(self):
        refs=[]
        for name in ('景祐','武经','太白','略决'):
            pointer=content.ref(*content.PROFILE_REFS[name][0])
            refs.append({'anchor_id':pointer['anchor_id'],'quote':pointer['quote'],'claim':'本轮对校'})
        data={'profile':'复盘官','explanation':'本轮分层核对。','evidence_label':'旁通',
              'source_warning':'未核原刻','citations':refs}
        self.assertTrue(any('三部书' in e for e in check_output(data)))


if __name__ == '__main__':
    unittest.main()
