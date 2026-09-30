import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from urllib.parse import quote
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
sys.path.insert(0, str(ROOT / 'liuren-paipan'))
import webapp
import curriculum_v3 as c


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.patcher=patch.object(c,'STATE',Path(self.temp.name)/'60-掌握度/_tutor_v3_state.json')
        self.patcher.start()
        self.server=ThreadingHTTPServer(('127.0.0.1',0),webapp.TrainerHandler)
        self.thread=Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base=f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        self.patcher.stop();self.temp.cleanup()

    def call(self,path,body=None):
        request=Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,
                        headers={'Content-Type':'application/json'})
        with urlopen(request,timeout=5) as response:
            return json.load(response)

    def test_browser_routes_submission_and_resume_contract(self):
        with urlopen(self.base+'/curriculum.html') as response:
            self.assertIn('六关训练',response.read().decode())
        session=self.call('/api/v3/start',{'level':0})
        public=self.call('/api/v3/session?id='+session['id'])
        self.assertNotIn('answers',public['questions'][0])
        q=public['questions'][0]
        private=c._load()['sessions'][session['id']]['questions'][0]
        result=self.call('/api/v3/submit',{'session_id':session['id'],'question_id':q['id'],'answer':private['answers']})
        self.assertEqual(result['score'],1)
        restored=self.call('/api/v3/session?id='+session['id'])
        self.assertEqual(len(restored['results']),1)
        self.assertNotIn('answers',restored['questions'][1])
        self.assertTrue(self.call('/api/v3/sources?q='+quote('己身'))['sources'])
        catalogue = self.call('/api/v3/catalogue')
        self.assertEqual(len(catalogue['books']),12)
        self.assertEqual(len(catalogue['cards']),8)
        hits = self.call('/api/v3/sources?q='+quote('邵先生曰'))['sources']
        self.assertTrue(all(s['book']!='六壬断案' for s in hits))

    def test_invalid_payload_and_prerequisites_return_json_400(self):
        for payload in ({'level':1}, []):
            with self.assertRaises(HTTPError) as error:
                self.call('/api/v3/start',payload)
            self.assertEqual(error.exception.code,400)
            self.assertIn('error',json.load(error.exception))
