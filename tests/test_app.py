"""Dependency-free HTTP integration and agent tests. Uses a temporary database."""
import http.cookiejar
import json
import os
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from backend import storage
from backend.server import Handler
from backend.domain import (risk_for,validate_evidence,orchestrate,evaluate_progress,DomainError,validate_plan,today)

class Client:
    def __init__(self,base):
        self.base=base;self.csrf=''
        self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def call(self,path,data=None,method=None,headers=None):
        h={'Content-Type':'application/json','X-Nexora-Request':'1','X-CSRF-Token':self.csrf,**(headers or {})}
        req=urllib.request.Request(self.base+'/api'+path,data=json.dumps(data).encode() if data is not None else None,headers=h,method=method or ('POST' if data is not None else 'GET'))
        try:
            with self.opener.open(req,timeout=20) as response:
                raw=response.read();status=response.status
                value=json.loads(raw.decode('utf-8')) if raw else {}
        except urllib.error.HTTPError as e:
            status=e.code;raw=e.read();
            try:value=json.loads(raw.decode('utf-8'))
            except Exception:value={}
        if isinstance(value,dict) and value.get('csrf'):self.csrf=value['csrf']
        return status,value
    def call_raw(self,path,method='GET',headers=None):
        h={'X-Nexora-Request':'1','X-CSRF-Token':self.csrf,**(headers or {})}
        req=urllib.request.Request(self.base+'/api'+path,headers=h,method=method)
        try:
            with self.opener.open(req,timeout=20) as response:return response.status,response.headers, response.read()
        except urllib.error.HTTPError as e:return e.code,e.headers,e.read()

class AgentTests(unittest.TestCase):
    def setUp(self):
        self.row={'id':1,'course':'DSA','score':40,'attendance':65,'completion':50,'topic':'Recursion','notes':'','recorded_on':today()}
    def test_explainable_risk(self):
        r=risk_for([self.row]);self.assertEqual(r['index'],51);self.assertEqual(r['level'],'Needs Attention')
        self.assertIsNone(risk_for([])['index'])
    def test_latest_record_and_thresholds(self):
        improved={**self.row,'id':2,'score':100,'attendance':100,'completion':100}
        self.assertEqual(risk_for([self.row,improved])['index'],0)
        self.assertEqual(risk_for([improved])['level'],'On Track')
    def test_input_validation(self):
        for bad in [-1,101,float('nan'),True,'abc']:
            with self.assertRaises(DomainError):validate_evidence({**self.row,'score':bad})
    def test_rules_agent_pipeline(self):
        p=orchestrate([self.row],'DSA',4,{'provider':'rules'})
        self.assertEqual(p['source'],'Local rules');self.assertEqual(len(p['trace']),5)
        self.assertEqual(p['trace'][-1]['status'],'awaiting');self.assertIn('E-1',p['rationale'])
        self.assertTrue(all(1<=a['week']<=4 for a in p['activities']))
        self.assertTrue(all(not a['completed'] for a in p['activities']))
    def test_missing_evidence_rejected(self):
        with self.assertRaises(DomainError):orchestrate([],'DSA',4,{'provider':'rules'})
    def test_adjustment_rules(self):
        p={'id':1,'recorded_on':today(),'score':42,'attendance':75,'completion':60}
        self.assertEqual(evaluate_progress(self.row,[p])['decision'],'Adjust approach')
        self.assertEqual(evaluate_progress(self.row,[{**p,'score':60}])['decision'],'Continue & review')
        self.assertEqual(evaluate_progress(self.row,[{**p,'score':30}])['decision'],'Revise support')
    def test_gemini_payload_is_minimized(self):
        rule=orchestrate([self.row],'DSA',4,{'provider':'rules'})
        model={k:rule[k] for k in ['title','objective','rationale','target_score','activities']}
        with patch('backend.domain.request_json',return_value={'candidates':[{'content':{'parts':[{'text':json.dumps(model)}]}}]}) as request:
            out=orchestrate([{**self.row,'notes':'PRIVATE NOTE','name':'PRIVATE NAME','roll':'PRIVATE ROLL'}],'DSA',4,{'provider':'gemini','model':'test-flash','consent':True},'TEST_KEY')
            args=request.call_args.args
            self.assertTrue(args[0].startswith('https://generativelanguage.googleapis.com/'))
            self.assertNotIn('PRIVATE',json.dumps(args[1]));self.assertEqual(out['source'],'Gemini')
            self.assertEqual(args[2]['x-goog-api-key'],'TEST_KEY')
    def test_cloud_consent_required(self):
        with self.assertRaises(DomainError):orchestrate([self.row],'DSA',4,{'provider':'gemini','model':'test-flash','consent':False},'TEST_KEY')
    def test_model_failure_does_not_fallback(self):
        with patch('backend.domain.request_json',side_effect=DomainError('quota',429)):
            with self.assertRaises(DomainError):orchestrate([self.row],'DSA',4,{'provider':'gemini','model':'test-flash','consent':True},'TEST_KEY')
    def test_ollama_structured_adapter(self):
        rule=orchestrate([self.row],'DSA',2,{'provider':'rules'})
        with patch('backend.domain.request_json',return_value={'response':json.dumps(rule)}) as req:
            result=orchestrate([self.row],'DSA',2,{'provider':'ollama','model':'qwen2.5:3b'})
            self.assertTrue(req.call_args.args[0].endswith('/api/generate'))
            self.assertFalse(req.call_args.args[1]['stream']);self.assertEqual(result['source'],'Ollama')
    def test_unsafe_model_output_rejected(self):
        p=orchestrate([self.row],'DSA',4,{'provider':'rules'});p['objective']='Expel the student immediately.'
        with self.assertRaises(DomainError):validate_plan(p,4)

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.prior=os.environ.get('AXIOM_DB');os.environ['AXIOM_DB']=cls.temp.name+'/test.sqlite3';storage.init_db()
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.temp.cleanup()
        if cls.prior:os.environ['AXIOM_DB']=cls.prior
        else:os.environ.pop('AXIOM_DB',None)
    def test_complete_workflow_and_security(self):
        a=Client(self.base);b=Client(self.base)
        self.assertEqual(a.call('/workspace')[0],401)
        self.assertEqual(a.call('/auth/signup',{'name':'Faculty One','email':'one@example.test','password':'StrongPass123','institution':'CSE Institute'})[0],201)
        self.assertEqual(b.call('/auth/signup',{'name':'Faculty Two','email':'two@example.test','password':'StrongPass123','institution':'CSE Institute'})[0],201)
        self.assertEqual(len(a.call('/workspace')[1]['students']),0)
        student={'name':'Test Student','roll':'CS001','semester':5,'section':'A','email':''}
        self.assertEqual(a.call('/students',student,headers={'X-CSRF-Token':'wrong'})[0],403)
        self.assertEqual(a.call('/students',student,headers={'Origin':'https://evil.example'})[0],403)
        status,s=a.call('/students',student);self.assertEqual(status,201);sid=s['id']
        self.assertEqual(b.call(f'/students/{sid}',student,'PATCH')[0],404)
        ev={'course':'DSA','score':40,'attendance':70,'completion':50,'topic':'Recursion','recorded_on':today()}
        self.assertEqual(a.call(f'/students/{sid}/evidence',ev)[0],201)
        st,p=a.call('/plans/generate',{'student_id':sid,'course':'DSA','weeks':4});self.assertEqual(st,201,p);pid=p['id']
        self.assertEqual(a.call(f'/plans/{pid}',{'action':'task','index':0,'completed':True},'PATCH')[0],409)
        self.assertEqual(a.call(f'/plans/{pid}',{'action':'edit','title':'DSA Support Plan','target_score':72},'PATCH')[0],200)
        self.assertEqual(a.call(f'/plans/{pid}',{'action':'approve'},'PATCH')[0],200)
        self.assertEqual(a.call(f'/plans/{pid}',{'action':'complete'},'PATCH')[0],400)
        self.assertEqual(a.call(f'/plans/{pid}/progress',{**ev,'score':60,'attendance':80})[0],201)
        st,rev=a.call('/plans/generate',{'student_id':sid,'course':'DSA','weeks':4,'parent_id':pid});self.assertEqual(st,201,rev)
        self.assertEqual(a.call(f'/plans/{rev["id"]}',{'action':'approve'},'PATCH')[0],200)
        ws=a.call('/workspace')[1];old=next(p for p in ws['plans'] if p['id']==pid);self.assertEqual(old['status'],'Archived')
        active=next(p for p in ws['plans'] if p['id']==rev['id'])
        for i in range(len(active['data']['activities'])):self.assertEqual(a.call(f'/plans/{active["id"]}',{'action':'task','index':i,'completed':True,'faculty_note':'Reviewed in lab.'},'PATCH')[0],200)
        self.assertEqual(a.call(f'/plans/{active["id"]}',{'action':'complete'},'PATCH')[0],200)
        self.assertEqual(a.call('/settings',{'provider':'gemini','model':'test-model','consent':True,'api_key':'secret-key-for-test'},'PATCH')[0],200)
        self.assertNotIn('secret-key-for-test',json.dumps(a.call('/settings')[1]))
        with storage.connect() as db:self.assertNotIn('secret-key-for-test',db.execute('SELECT settings FROM users WHERE email=?',('one@example.test',)).fetchone()[0])
        self.assertEqual(a.call('/settings',{'provider':'rules','model':'test-model','consent':False},'PATCH')[0],200)
        self.assertEqual(a.call('/settings/test',{})[0],200)
        self.assertEqual(a.call('/profile',{'name':'Updated Faculty','institution':'CSE','department':'Computer Science','bio':'Mentor'},'PATCH')[0],200)
        self.assertEqual(a.call('/auth/password',{'current_password':'StrongPass123','new_password':'NewStrongPass123'})[0],200)
        self.assertEqual(a.call('/auth/logout',{})[0],200)
        self.assertEqual(a.call('/auth/login',{'email':'one@example.test','password':'StrongPass123'})[0],401)
        self.assertEqual(a.call('/auth/login',{'email':'one@example.test','password':'NewStrongPass123'})[0],200)
        self.assertEqual(a.call(f'/students/{sid}',{'confirm':'DELETE'},'DELETE')[0],200)
        self.assertEqual(len(a.call('/workspace')[1]['plans']),0)
    def test_csv_atomic_import(self):
        a=Client(self.base);a.call('/auth/signup',{'name':'CSV Faculty','email':'csv@example.test','password':'StrongPass123','institution':'CSE Institute'})
        header='name,roll,semester,section,course,score,attendance,completion\n'
        bad=header+'Test One,A1,5,A,DSA,45,75,55\nTest Two,A2,5,A,DSA,999,75,55\n'
        self.assertEqual(a.call('/students/import',{'csv':bad})[0],400)
        self.assertEqual(len(a.call('/workspace')[1]['students']),0)
        good=header+'Test One,A1,5,A,DSA,45,75,55\nTest One,A1,5,A,DBMS,55,80,60\n'
        st,result=a.call('/students/import',{'csv':good});self.assertEqual(st,200);self.assertEqual(result['students_created'],1)
        self.assertEqual(a.call('/students/import',{'csv':good})[0],400)
    def test_demo_workspace(self):
        a=Client(self.base);st,user=a.call('/auth/demo',{});self.assertEqual(st,201,user)
        ws=a.call('/workspace')[1];self.assertEqual(len(ws['students']),12);self.assertEqual(len(ws['plans']),6)
        self.assertTrue(all(s['synthetic'] for s in ws['students']))
        self.assertEqual(a.call('/auth/password',{'current_password':'a','new_password':'abcdef12345'})[0],400)

    def test_student_portal_role_files_reports_and_tasks(self):
        faculty=Client(self.base)
        self.assertEqual(faculty.call('/auth/signup',{'name':'Portal Faculty','email':'portal@example.test','password':'StrongPass123','institution':'KITS, Singapur'})[0],201)
        student={'name':'Portal Student','roll':'CS902','semester':5,'section':'A','email':'student@example.test','current_cgpa':7.4,'target_cgpa':8.5,'portal_password':'StudentPass123'}
        st,created=faculty.call('/students',student);self.assertEqual(st,201,created);sid=created['id']
        ev={'course':'DSA','assessment_type':'MID-II','score':48,'attendance':72,'completion':60,'topic':'Recursion','notes':'','recorded_on':today()}
        self.assertEqual(faculty.call(f'/students/{sid}/evidence',ev)[0],201)
        st,plan=faculty.call('/plans/generate',{'student_id':sid,'course':'DSA','weeks':2});self.assertEqual(st,201,plan);pid=plan['id']
        self.assertEqual(faculty.call(f'/plans/{pid}',{'action':'approve'},'PATCH')[0],200)
        st,student_user=Client(self.base).call('/auth/student-login',{'roll':'CS902','password':'StudentPass123'});self.assertEqual(st,200,student_user)
        student_client=Client(self.base);st,student_user=student_client.call('/auth/student-login',{'roll':'CS902','password':'StudentPass123'});self.assertEqual(st,200)
        ws=student_client.call('/workspace')[1];self.assertEqual(ws['student']['id'],sid);self.assertEqual(ws['student']['roll'],'CS902');self.assertEqual(len(ws['plans']),1)
        self.assertEqual(student_client.call('/students')[0],403)
        self.assertEqual(student_client.call('/settings')[0],403)
        self.assertEqual(student_client.call('/student/target',{'target_cgpa':8.8},'PATCH')[0],200)
        active=next(p for p in ws['plans'] if p['status']=='Active')
        self.assertEqual(student_client.call('/student/tasks',{'plan_id':active['id'],'index':0,'completed':True,'difficulty':'Difficult'},'PATCH')[0],200)
        # faculty report -> share -> student inbox/report access
        st,rep=faculty.call('/reports',{'student_id':sid,'plan_id':pid});self.assertEqual(st,201,rep);rid=rep['id']
        self.assertEqual(student_client.call(f'/reports/{rid}')[0],404)
        self.assertEqual(faculty.call(f'/reports/{rid}/share',{},'POST')[0],200)
        self.assertEqual(student_client.call(f'/reports/{rid}')[0],200)
        self.assertTrue(any(n['entity_id']==rid for n in student_client.call('/student/notifications')[1]['notifications']))
        raw=b'KITS R23 CSE syllabus demo'
        import base64
        st,file_resp=faculty.call('/files',{'file_name':'syllabus.pdf','mime_type':'application/pdf','category':'Syllabus','audience':'student','student_id':sid,'content_b64':base64.b64encode(raw).decode()});self.assertEqual(st,201,file_resp);fid=file_resp['id']
        files=student_client.call('/files')[1]['files'];self.assertTrue(any(f['id']==fid for f in files))
        # legacy/orphan file cannot be downloaded by a different student; ownership is enforced by visibility.
        status,headers,body=student_client.call_raw(f'/files/{fid}/download')
        self.assertEqual(status,200)
        self.assertEqual(body,raw)
        self.assertEqual(headers.get_content_type(),'application/pdf')

    def test_faculty_reset_student_password_never_reveals_it(self):
        faculty=Client(self.base)
        self.assertEqual(faculty.call('/auth/signup',{'name':'Reset Faculty','email':'reset@example.test','password':'StrongPass123','institution':'KITS, Singapur'})[0],201)
        st,created=faculty.call('/students',{'name':'Reset Student','roll':'CS903','semester':5,'section':'A','portal_password':'StudentPass123'});self.assertEqual(st,201);sid=created['id']
        self.assertNotIn('current_password',json.dumps(created).lower())
        self.assertEqual(faculty.call(f'/students/{sid}/reset-password',{'new_password':'NewStudent123'},'POST')[0],200)
        old=Client(self.base);self.assertEqual(old.call('/auth/student-login',{'roll':'CS903','password':'StudentPass123'})[0],401)
        fresh=Client(self.base);self.assertEqual(fresh.call('/auth/student-login',{'roll':'CS903','password':'NewStudent123'})[0],200)
    def test_static_security_headers(self):
        with urllib.request.urlopen(self.base+'/') as r:
            self.assertEqual(r.status,200);self.assertIn("default-src 'self'",r.headers['Content-Security-Policy']);self.assertEqual(r.headers['X-Frame-Options'],'DENY')

if __name__=='__main__':unittest.main()
