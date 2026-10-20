"""Delegation contracts, real computations, durable pause/resume and consent."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event,Thread
import unittest
from unittest.mock import patch
import uuid
import zipfile

import jsonschema
from graph_research.assistant import create_subagent,SubagentLimits,subagent_contracts,subagent_tool_definition,verify_bundle
from graph_research.assistant.task_contract import TaskProtocolError,RESULT_SCHEMA
from graph_research.runtime.integrity import CORE,verify
from graph_research.runtime.storage import read_json
from tests.test_feature_workflow import ScriptedModel
from tests.feature_helpers import proposal,request_for


def agent_task(request_id='research-1',**changes):
    task={'version':1,'request_id':request_id,'parent_task_id':'parent-study','objective':'计算P3的直径',
          'inputs':{'n':3},'definitions':['普通无向简单图'],'expected_outputs':['计算结果','执行回执'],
          'execution':{'mode':'agent'}}
    task.update(changes);return task


def direct_task(request_id='direct-1'):
    return {'version':1,'request_id':request_id,'objective':'计算P3邻接谱，并复核邻接矩阵的秩',
            'inputs':{'kind':'path','n':3},'definitions':['普通无向简单图，使用邻接矩阵A'],
            'expected_outputs':['谱半径','矩阵秩','结果包'],
            'execution':{'mode':'tools','steps':[
                {'id':'spectrum','tool':'graph_spectrum','arguments':{},'bindings':{'kind':{'input':['kind']},'n':{'input':['n']}}},
                {'id':'rank','tool':'matrix_analysis','arguments':{},'bindings':{'matrix':{'step':'spectrum','path':['matrix']}}},
            ]}}


class SubagentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def create(self,model=None,**kwargs):
        return create_subagent(self.root,user_id=kwargs.pop('user_id','researcher-a'),model_factory=(lambda:model) if model else None,**kwargs)

    def test_fixed_multi_tool_task_uses_json_bindings_and_no_model(self):
        parent,_=create_subagent(self.root,user_id='a',model_factory=lambda:(_ for _ in ()).throw(AssertionError('No model')))
        response=parent.submit(direct_task())
        jsonschema.validate(response,RESULT_SCHEMA)
        self.assertEqual(response['status'],'completed');self.assertTrue(response['terminal'])
        self.assertEqual(response['summary']['verified_calls'],2)
        self.assertAlmostEqual(response['results'][0]['data']['rho'],2**0.5)
        self.assertEqual(response['results'][1]['data']['rank'],2)
        self.assertEqual(response['budget']['used'],{'model_calls':0,'tool_calls':2})
        bundle=response['artifacts'][0];self.assertTrue(verify_bundle(bundle['path'],bundle['sha256'])['ok'])
        with zipfile.ZipFile(bundle['path']) as archive:
            data=json.loads(archive.read('results.json'))
            self.assertEqual(data['delegated_task']['definitions'],direct_task()['definitions'])
            self.assertFalse(any('host-events' in name or 'task.json' in name for name in archive.namelist()))

    def test_submit_is_idempotent_and_changed_input_cannot_reuse_request_id(self):
        parent,_=self.create();request=direct_task()
        first=parent.submit(request);second=parent.submit(copy.deepcopy(request))
        strip=lambda r:{**r,'summary':{k:v for k,v in r['summary'].items() if k!='reuse'}}
        self.assertEqual(strip(first),strip(second))
        self.assertEqual(second['summary']['reuse']['task_reused'],1)
        self.assertEqual(second['budget']['used']['tool_calls'],2)
        request['inputs']['n']=4
        with self.assertRaises(TaskProtocolError) as caught:parent.submit(request)
        self.assertEqual(caught.exception.code,'request_id_conflict')

    def test_cancellation_before_initial_task_lock_prevents_execution(self):
        from contextlib import contextmanager
        parent,_=self.create();service=parent._service;original=service.task_lock;entered=[]
        @contextmanager
        def cancel_before_lock(task_id):
            if not entered:
                entered.append(True)
                self.assertEqual(parent.cancel(task_id)['status'],'cancelled')
            with original(task_id):yield
        with patch.object(service,'task_lock',cancel_before_lock):
            response=parent.submit(direct_task())
        self.assertEqual(response['status'],'cancelled')
        self.assertEqual(response['budget']['used'],{'model_calls':0,'tool_calls':0})

    def test_invalid_authority_fields_cycles_and_host_budget_escalation_are_rejected(self):
        parent,_=self.create(limits=SubagentLimits(max_model_calls=2))
        for field in ('approved','user_id','api_key','tool_directory','authorization'):
            request=agent_task();request[field]=True
            result=parent.dispatch({'operation':'submit','task':request})
            self.assertEqual(result['status'],'protocol_error')
        request=agent_task(constraints={'max_model_calls':3})
        with self.assertRaises(TaskProtocolError):parent.submit(request)
        cycle=direct_task();cycle['execution']['steps'][0]['bindings']={'n':{'step':'rank','path':['rank']}}
        with self.assertRaises(TaskProtocolError):parent.submit(cycle)
        self.assertEqual(list(self.root.glob('users/*/tasks/*/task.json')),[])

    def test_clarification_pauses_and_signed_user_reply_resumes_across_restart(self):
        model=ScriptedModel([{'action':'clarify','questions':['图是P3吗？使用邻接矩阵吗？']},
                             {'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':3}},
                             {'action':'final','answer':'直径为2。'}])
        parent,portal=self.create(model)
        first=parent.submit(agent_task())
        self.assertEqual(first['status'],'waiting_for_user');self.assertFalse(first['terminal'])
        self.assertEqual(len(model.contexts),1);pending=first['interaction']
        event_id='1'*32
        event=portal.answer(first['task_id'],pending['interaction_id'],first['revision'],'是P3，使用普通无向图定义。',event_id=event_id)
        duplicate=portal.answer(first['task_id'],pending['interaction_id'],first['revision'],'是P3，使用普通无向图定义。',event_id=event_id)
        self.assertEqual(event,duplicate);self.assertEqual(len(model.contexts),1)
        reloaded,_=self.create(model)
        result=reloaded.resume(first['task_id'],event['event_id'])
        self.assertEqual(result['status'],'completed');self.assertEqual(result['results'][0]['data']['diameter'],2)
        self.assertEqual(result['budget']['used'],{'model_calls':3,'tool_calls':1})
        self.assertEqual(reloaded.resume(first['task_id'],event['event_id']),result)
        self.assertEqual(len(model.contexts),3)
        self.assertEqual(model.contexts[0]['delegated_task']['inputs'],{'n':3})

    def test_parent_cannot_approve_with_json_and_host_approval_remains_scope_bound(self):
        tool=proposal();before=verify()['manifest_sha256']
        model=ScriptedModel([{'action':'assess','request':request_for(tool)},
                             {'action':'extend','proposal':tool},
                             {'action':'call','tool':tool['name'],'arguments':{'degrees':[3,2,2,1]}},
                             {'action':'final','answer':'h指数为2，仅通过所列验收。'}])
        parent,portal=self.create(model,limits=SubagentLimits(allowed_tools=('graph_invariants',)))
        first=parent.submit(agent_task(objective='补充度序列h指数算法'))
        self.assertEqual(first['status'],'waiting_for_approval');p=first['interaction']
        self.assertEqual(len(model.contexts),1)
        rejected=parent.dispatch({'operation':'approve','task_id':first['task_id'],'approved':True})
        self.assertEqual(rejected['status'],'protocol_error')
        with self.assertRaises(TaskProtocolError):portal.approve(first['task_id'],p['interaction_id'],first['revision'],p['assessment_id'],'0'*64)
        self.assertFalse(list(self.root.glob('users/*/tool_packages/*/tool.py')))
        event=portal.approve(first['task_id'],p['interaction_id'],first['revision'],p['assessment_id'],p['scope_sha256'])
        self.assertEqual(len(model.contexts),1)  # issuance alone does not generate code
        result=parent.resume(first['task_id'],event['event_id'])
        self.assertEqual(result['status'],'completed');self.assertEqual(result['results'][0]['data'],{'h_index':2})
        self.assertEqual(result['results'][0]['tool_status'],'fixture_tested_experimental')
        self.assertEqual(len(model.contexts),4)
        self.assertEqual(parent.resume(first['task_id'],event['event_id']),result);self.assertEqual(len(model.contexts),4)
        self.assertTrue(any(a['kind']=='experimental_extension' for a in result['artifacts']))
        self.assertEqual(verify()['manifest_sha256'],before)

    def test_rejection_works_without_followup_model_or_key(self):
        model=ScriptedModel([{'action':'assess','request':request_for(proposal())}])
        parent,portal=self.create(model);first=parent.submit(agent_task())
        p=first['interaction'];event=portal.reject(first['task_id'],p['interaction_id'],first['revision'],p['assessment_id'],p['scope_sha256'])
        parent._service.model_factory=lambda:(_ for _ in ()).throw(AssertionError('Must not ask for a key or call model'))
        result=parent.resume(first['task_id'],event['event_id'])
        self.assertEqual(result['status'],'rejected');self.assertEqual(len(model.contexts),1)
        self.assertFalse(list(self.root.glob('users/*/tool_packages/*/tool.py')))

    def test_revising_requirements_invalidates_a_previously_issued_approval_event(self):
        model=ScriptedModel([{'action':'assess','request':request_for(proposal())},
                             {'action':'clarify','questions':['新的输入规模是多少？']}])
        parent,portal=self.create(model);first=parent.submit(agent_task());p=first['interaction']
        approval=portal.approve(first['task_id'],p['interaction_id'],first['revision'],p['assessment_id'],p['scope_sha256'])
        revision=portal.answer(first['task_id'],p['interaction_id'],first['revision'],'先修改输出格式，请重新评估。')
        next_state=parent.resume(first['task_id'],revision['event_id'])
        self.assertEqual(next_state['status'],'waiting_for_user')
        with self.assertRaises(TaskProtocolError) as caught:parent.resume(first['task_id'],approval['event_id'])
        self.assertEqual(caught.exception.code,'stale_interaction');self.assertEqual(len(model.contexts),2)
        self.assertFalse(list(self.root.glob('users/*/tool_packages/*/tool.py')))

    def test_events_cannot_cross_tasks_or_users_and_tampered_or_expired_events_fail(self):
        parent,portal=create_subagent(self.root,user_id='a',model_factory=lambda:ScriptedModel([{'action':'clarify','questions':['请给出顶点数？']}]))
        first=parent.submit(agent_task('one'));second=parent.submit(agent_task('two'));p=first['interaction']
        event=portal.answer(first['task_id'],p['interaction_id'],first['revision'],'3')
        with self.assertRaises(TaskProtocolError) as caught:parent.resume(second['task_id'],event['event_id'])
        self.assertEqual(caught.exception.code,'event_scope_mismatch')
        other,_=create_subagent(self.root,user_id='b')
        with self.assertRaises(TaskProtocolError):other.get(first['task_id'])
        with patch('graph_research.assistant.host_events.time.time',return_value=event['expires_at']+1):
            with self.assertRaises(TaskProtocolError) as caught:parent.resume(first['task_id'],event['event_id'])
            self.assertEqual(caught.exception.code,'event_expired')
        file=next(self.root.glob('users/*/events/'+event['event_id']+'.json'))
        document=json.loads(file.read_text());document['body']['payload']['text']='FORGED';file.write_text(json.dumps(document),encoding='utf-8')
        with self.assertRaises(TaskProtocolError) as caught:parent.resume(first['task_id'],event['event_id'])
        self.assertEqual(caught.exception.code,'invalid_host_event')

    def test_model_budget_survives_clarification_and_replay_does_not_reset_it(self):
        model=ScriptedModel([{'action':'clarify','questions':['确认图的输入？']}])
        parent,portal=self.create(model)
        first=parent.submit(agent_task(constraints={'max_model_calls':1}));p=first['interaction']
        event=portal.answer(first['task_id'],p['interaction_id'],first['revision'],'确认P3。')
        result=parent.resume(first['task_id'],event['event_id'])
        self.assertEqual(result['status'],'budget_exhausted');self.assertTrue(result['terminal'])
        self.assertEqual(len(model.contexts),1);self.assertEqual(result['budget']['used']['model_calls'],1)
        self.assertEqual(parent.resume(first['task_id'],event['event_id']),result)

    def test_tool_budget_and_whitelist_are_enforced_outside_model_prompts(self):
        parent,_=self.create();task=direct_task();task['constraints']={'max_tool_calls':1}
        result=parent.submit(task)
        self.assertEqual(result['status'],'budget_exhausted');self.assertEqual(result['summary']['successful_calls'],1)
        model=ScriptedModel([{'action':'call','tool':'graph_spectrum','arguments':{'kind':'path','n':3}}])
        limited,_=create_subagent(self.root/'restricted',user_id='a',model_factory=lambda:model)
        result=limited.submit(agent_task(constraints={'allowed_tools':['graph_invariants']}))
        self.assertEqual(result['status'],'blocked');self.assertEqual(result['budget']['used']['tool_calls'],0)
        self.assertEqual([t['name'] for t in model.contexts[0]['tools']],['graph_invariants'])
        self.assertEqual(result['error']['code'],'tool_not_permitted')

    def test_tools_mode_reports_required_attempts_and_warns_before_budget_runs_out(self):
        parent,_=self.create();task=direct_task();task['constraints']={'max_tool_calls':1}
        result=parent.submit(task)
        self.assertEqual(result['status'],'budget_exhausted');self.assertEqual(result['summary']['successful_calls'],1)
        self.assertEqual(result['budget']['required_tool_attempts'],2)
        self.assertTrue(any('fail_fast' in warning for warning in result['warnings']))

    def test_fail_fast_rejects_insufficient_tools_budget_without_executing(self):
        parent,_=self.create();task=direct_task()
        task['constraints']={'max_tool_calls':1,'fail_fast':True}
        with self.assertRaises(TaskProtocolError) as caught:parent.submit(task)
        self.assertEqual(caught.exception.code,'tools_budget_insufficient')

    def test_disallowed_extension_cannot_even_create_an_approval_request(self):
        model=ScriptedModel([{'action':'assess','request':request_for(proposal())}])
        parent,_=self.create(model)
        result=parent.submit(agent_task(constraints={'allow_extensions':False}))
        self.assertEqual(result['status'],'blocked');self.assertIsNone(result['interaction'])
        self.assertEqual(result['error']['code'],'extension_not_permitted')
        self.assertFalse(list(self.root.glob('users/*/tasks/*/session/changes/*/assessment.json')))

    def test_running_duplicate_get_cancel_and_recover_do_not_start_another_run(self):
        entered=Event();release=Event();responses=[];errors=[]
        class BlockingModel:
            calls=0
            def complete(self,messages):
                self.calls+=1;entered.set();release.wait(8)
                return {'action':'final','answer':'完成'}
        model=BlockingModel();parent,_=self.create(model);request=agent_task()
        def execute():
            try:responses.append(parent.submit(request))
            except BaseException as exc:errors.append(exc)
        thread=Thread(target=execute);thread.start()
        try:
            self.assertTrue(entered.wait(5))
            current=parent.submit(request);self.assertEqual(current['status'],'running')
            busy=parent.dispatch({'operation':'recover','task_id':current['task_id']})
            self.assertEqual(busy['status'],'protocol_error')
            parent.cancel(current['task_id'])
        finally:release.set();thread.join(8)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(responses[0]['status'],'cancelled');self.assertEqual(model.calls,1)

    def test_orphaned_run_requires_explicit_user_continuation_after_restart(self):
        class CrashedModel:
            def complete(self,messages):raise SystemExit('simulated host crash')
        parent,_=self.create(CrashedModel())
        with self.assertRaises(SystemExit):parent.submit(agent_task())
        task_id=next(self.root.glob('users/*/tasks/*/task.json')).parent.name
        model=ScriptedModel([{'action':'final','answer':'记录已恢复，未声称完成新的计算。'}])
        reloaded,portal=self.create(model)
        self.assertEqual(reloaded.get(task_id)['status'],'running');self.assertEqual(model.contexts,[])
        recovered=reloaded.recover(task_id);self.assertEqual(recovered['status'],'interrupted');self.assertEqual(model.contexts,[])
        p=recovered['interaction'];event=portal.continue_task(task_id,p['interaction_id'],recovered['revision'])
        result=reloaded.resume(task_id,event['event_id'])
        self.assertEqual(result['status'],'analysis_only');self.assertEqual(result['budget']['used']['model_calls'],2)

    def test_persisted_direct_result_is_not_recomputed_after_status_commit_crash(self):
        from graph_research.assistant.subagent import _Service
        parent,_=self.create();original=_Service.save;crashed=[]
        def save(service,record,**kwargs):
            path=service.task_dir(record['task_id'])/'session/session.json'
            if not crashed and record['usage']['tool_calls']==1 and record['cursor']==0 and record.get('inflight_step') is None and path.exists():
                state=read_json(path)[0]['state']
                if state.get('observations'):
                    crashed.append(True);raise SystemExit('simulated crash after persisted calculation')
            return original(service,record,**kwargs)
        with patch.object(_Service,'save',save):
            with self.assertRaises(SystemExit):parent.submit(direct_task())
        task_id=next(self.root.glob('users/*/tasks/*/task.json')).parent.name
        reloaded,portal=self.create();recovered=reloaded.recover(task_id)
        p=recovered['interaction'];event=portal.continue_task(task_id,p['interaction_id'],recovered['revision'])
        result=reloaded.resume(task_id,event['event_id'])
        self.assertEqual(result['status'],'completed',result);self.assertEqual(result['budget']['used']['tool_calls'],2)
        self.assertEqual(len(result['results']),2)

    def test_unknown_model_error_does_not_leak_credentials_into_results(self):
        class UnsafeClient:
            def complete(self,messages):raise RuntimeError('PRIVATE_API_KEY_IN_SDK_ERROR')
        parent,_=self.create(UnsafeClient());result=parent.submit(agent_task())
        self.assertEqual(result['status'],'interrupted')
        self.assertNotIn('PRIVATE_API_KEY_IN_SDK_ERROR',json.dumps(result))
        bundle=next(a for a in result['artifacts'] if a['kind']=='result_bundle')
        with zipfile.ZipFile(bundle['path']) as archive:
            self.assertFalse(any(b'PRIVATE_API_KEY_IN_SDK_ERROR' in archive.read(name) for name in archive.namelist()))

    def test_tightened_host_policy_cannot_resume_old_permissions(self):
        model=ScriptedModel([{'action':'clarify','questions':['输入？']}])
        parent,portal=self.create(model);first=parent.submit(agent_task());p=first['interaction']
        event=portal.answer(first['task_id'],p['interaction_id'],first['revision'],'P3')
        restricted,_=self.create(model,limits=SubagentLimits(max_model_calls=1))
        with self.assertRaises(TaskProtocolError) as caught:restricted.resume(first['task_id'],event['event_id'])
        self.assertEqual(caught.exception.code,'host_policy_changed');self.assertEqual(len(model.contexts),1)

    def test_schema_and_cli_json_transport_are_framework_neutral(self):
        contracts=subagent_contracts()
        self.assertEqual(subagent_tool_definition()['name'],'graph_research_subagent')
        for value in (contracts['task_input'],contracts['task_result'],contracts['parent_dispatch']):jsonschema.Draft202012Validator.check_schema(value)
        request=self.root/'request.json';request.write_text(json.dumps({'operation':'submit','task':direct_task()}),encoding='utf-8')
        process=subprocess.run([sys.executable,'-X','utf8','-m','graph_research','subagent','--root',str(self.root/'cli'),'--user','a','--input',str(request)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(process.returncode,0,process.stderr)
        result=json.loads(process.stdout);self.assertEqual(result['status'],'completed')
        self.assertEqual(result['budget']['used']['model_calls'],0)

    def test_trusted_user_cli_signs_event_and_parent_cli_resumes_without_model(self):
        model=ScriptedModel([{'action':'assess','request':request_for(proposal())}])
        parent,_=self.create(model);waiting=parent.submit(agent_task());p=waiting['interaction']
        prefix=[sys.executable,'-X','utf8','-m','graph_research']
        signed=subprocess.run(prefix+['subagent-user','--root',str(self.root),'--user','researcher-a',
            '--task',waiting['task_id'],'--interaction',p['interaction_id'],'--revision',str(waiting['revision']),
            '--action','reject','--assessment',p['assessment_id'],'--scope',p['scope_sha256'],'--text','先不开发'],
            capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(signed.returncode,0,signed.stderr)
        event=json.loads(signed.stdout)['host_user_event']
        self.assertEqual(parent.get(waiting['task_id'])['status'],'waiting_for_approval')
        resumed=subprocess.run(prefix+['subagent','--root',str(self.root),'--user','researcher-a'],
            input=json.dumps({'operation':'resume','task_id':waiting['task_id'],'event_id':event['event_id']}),
            capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(resumed.returncode,0,resumed.stderr)
        self.assertEqual(json.loads(resumed.stdout)['status'],'rejected')
        self.assertEqual(len(model.contexts),1)

    def test_nested_project_directory_supports_real_calculation_and_bundle(self):
        root=self.root/('nested-project-'+'x'*max(1,90-len(str(self.root))-16))
        parent,_=create_subagent(root,user_id='long-path-researcher')
        result=parent.submit(direct_task())
        self.assertEqual(result['status'],'completed',result)
        bundle=next(a for a in result['artifacts'] if a['kind']=='result_bundle')
        self.assertTrue(verify_bundle(bundle['path'],bundle['sha256'])['ok'])


if __name__=='__main__':unittest.main()
