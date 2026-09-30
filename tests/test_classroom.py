import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import classroom as c
from check_tutor_output import check_output

PAYLOAD={'topic':'行年与天乙','question':'行年临天乙就一定好吗？各书的限制在哪里？',
         'main_claim':'尚须核原文和边界','keywords':['行年','天乙'],'profiles':['景祐','武经']}


def fake_runner(profile,prompt,model):
    data=json.loads(prompt.split('\n',1)[1])
    if profile=='复盘官':
        refs=[r for v in data['checked_voices'] for r in v['output']['citations']]
    else:
        source=data['sources'][0]
        text=source['text']
        at=max(text.find('行年'),text.find('天乙'),0)
        refs=[{'anchor_id':source['anchor_id'],'quote':text[at:at+30],'claim':'只核本句条件'}]
    return {'explanation':profile+'：原句有条件，不能一概推断。','evidence_label':'旁通',
            'source_warning':'未核原刻','citations':refs,'term_senses':{},
            'challenge':'哪一个课中条件还没有考虑？'}


class ClassroomTests(unittest.TestCase):
    def test_auto_plan_preserves_main_and_assigns_complement_and_challenge(self):
        plan=c.plan(PAYLOAD,'凝神子')
        self.assertEqual([p['profile'] for p in plan],['景祐','武经'])
        self.assertEqual([p['role'] for p in plan],['补证','质疑与边界'])
        self.assertTrue(all(p['sources'] for p in plan))
        self.assertNotIn('凝神子',[p['profile'] for p in plan])

    def test_independent_voices_reviewer_and_return_to_main(self):
        calls=[]
        def runner(profile,prompt,model):
            calls.append(profile)
            return fake_runner(profile,prompt,model)
        result=c.discuss(PAYLOAD,'凝神子',runner)
        self.assertTrue(result['accepted'],result)
        self.assertEqual(set(calls),{'景祐','武经','复盘官'})
        self.assertEqual(result['main_profile'],'凝神子')
        self.assertEqual(result['status'],'complete')
        self.assertTrue(result['question'])
        self.assertTrue(result['source_checks'])

    def test_only_checked_and_attributed_foreign_quote_can_return_to_main(self):
        result=c.discuss(PAYLOAD,'凝神子',fake_runner)
        authorized=c.approved_quotes(result,'凝神子')
        voice=result['voices'][0]
        ref={**voice['output']['citations'][0],'speaker':voice['profile']}
        data={'profile':'凝神子','explanation':'景祐指出适用边界，主讲仍回到本书。',
              'source_warning':'未核原刻','evidence_label':'旁通','citations':[ref]}
        self.assertTrue(check_output(data))
        self.assertEqual(check_output(data,authorized_quotes=authorized),[])
        ref.pop('speaker')
        self.assertTrue(check_output(data,authorized_quotes=authorized))
        with self.assertRaises(ValueError):c.approved_quotes(result,'壬归')

    def test_invalid_citations_are_not_presented_as_voices(self):
        def bad(profile,prompt,model):
            result=fake_runner(profile,prompt,model)
            result['citations'][0]['quote']='虚构原文不能支持发言'
            return result
        result=c.discuss(PAYLOAD,'凝神子',bad)
        self.assertFalse(result['accepted'])
        self.assertIsNone(result['moderator'])
        self.assertTrue(all(v['output'] is None for v in result['voices']))
        def malformed(profile,prompt,model):
            data=fake_runner(profile,prompt,model)
            data.update(citations=['非引文对象'],digressions=None)
            return data
        result=c.discuss(PAYLOAD,'凝神子',malformed)
        self.assertFalse(result['accepted'])
        self.assertTrue(all(v['errors'] for v in result['voices']))

    def test_model_failure_is_explicit_and_no_fake_discussion(self):
        def fail(*args):raise ValueError('模型凭据不可用')
        result=c.discuss(PAYLOAD,'凝神子',fail)
        self.assertEqual(result['status'],'blocked')
        self.assertFalse(result['accepted'])
        self.assertIsNone(result['question'])

    def test_recursion_budget_and_no_evidence_guards(self):
        with patch.dict(c.os.environ,{'LIUREN_DISCUSSION_CHILD':'1'}):
            result=c.discuss(PAYLOAD,'凝神子',fake_runner)
            self.assertFalse(result['accepted'])
        with self.assertRaises(ValueError):c.plan({**PAYLOAD,'profiles':['景祐','武经','太白']},'凝神子')
        result=c.discuss({**PAYLOAD,'topic':'无原文条目','question':'找不到任何原句怎么办',
                          'keywords':['无匹配测试字串'],'profiles':['景祐']},'凝神子',fake_runner)
        self.assertEqual(result['status'],'no_evidence')

    def test_child_command_uses_same_model_readonly_no_session_and_no_recursion(self):
        final={'explanation':'验收JSON'}
        stdout=json.dumps({'type':'message_end','message':{'role':'assistant','content':[
            {'type':'text','text':json.dumps(final)}]}})
        with patch.object(c,'command',return_value=['pi','--provider','deepseek']), \
             patch.object(c.subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout,'')) as run:
            self.assertEqual(c.invoke('景祐','测试',{'provider':'deepseek','id':'deepseek-chat'}),final)
            args=run.call_args
            self.assertIn('--no-session',args.args[0])
            self.assertIn('liuren_source,liuren_validate_output',args.args[0])
            self.assertEqual(args.kwargs['env']['LIUREN_DISCUSSION_CHILD'],'1')
            self.assertIn('deepseek-chat',args.args[0])


if __name__=='__main__':unittest.main()
