"""MCP scheduling, trust boundaries and official SDK wire interoperability."""
import asyncio
import base64
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import tomllib
import unittest
from unittest.mock import patch,Mock

from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
from graph_research.mcp.contracts import tool_definitions
from graph_research.assistant import create_subagent,SubagentLimits,verify_bundle
from graph_research.runtime.storage import atomic_text
from graph_research.assistant.task_contract import TaskProtocolError
from tests.test_subagent import direct_task,agent_task
from tests.test_feature_workflow import ScriptedModel

try:
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters
    from graph_research.mcp.server import create_server
    SDK=True
except ImportError:SDK=False


def small_task(request_id='mcp-p3'):
    return {'version':1,'request_id':request_id,'objective':'计算P3直径','execution':{'mode':'tools','steps':[{'id':'structure','tool':'graph_invariants','arguments':{'n':3}}]}}


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.runtimes=[];self.addCleanup(self.cleanup)
    def runtime(self,user='a',**kw):
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root),user,**kw));self.runtimes.append(runtime);return runtime
    def cleanup(self):
        for runtime in self.runtimes:
            for process in list(runtime.children.values()):
                if not isinstance(process,subprocess.Popen):continue
                if process.poll() is None:
                    entry=runtime._current_job()
                    if entry:runtime.cancel(entry[1]['task_id'])
                    try:process.wait(10)
                    except subprocess.TimeoutExpired:process.kill();process.wait(5)
        self.temp.cleanup()
    def wait(self,runtime,task_id):
        deadline=time.monotonic()+35
        while time.monotonic()<deadline:
            result=runtime.get(task_id,wait_seconds=.2)
            if not result.get('transport',{}).get('active'):
                if result.get('status')=='interrupted':print('MCP interrupted diagnostic:',json.dumps({'error':result.get('error'),'transport':result.get('transport')},ensure_ascii=False),file=sys.stderr)
                return result
        self.fail('Background task did not finish')

    def test_deferred_registration_does_not_compute_and_start_is_idempotent(self):
        parent,_=create_subagent(self.root,user_id='defer',limits=SubagentLimits(max_model_calls=0,allow_extensions=False))
        with patch('graph_research.assistant.subagent._Service.drive',side_effect=AssertionError('Registration must not execute')):
            queued=parent.submit(small_task(),defer=True);again=parent.submit(small_task(),defer=True)
        self.assertEqual(queued['status'],'queued')
        strip=lambda r:{**r,'summary':{k:v for k,v in r['summary'].items() if k!='reuse'}}
        self.assertEqual(strip(queued),strip(again));self.assertEqual(again['summary']['reuse']['task_reused'],1)
        done=parent.start_queued(queued['task_id']);self.assertEqual(done['status'],'completed')
        self.assertEqual(parent.start_queued(queued['task_id']),done);self.assertEqual(done['budget']['used']['tool_calls'],1)

    def test_cancel_arriving_after_queued_lock_is_not_cleared_by_initial_drive(self):
        parent,_=create_subagent(self.root,user_id='cancel-race',limits=SubagentLimits(max_model_calls=0,allow_extensions=False))
        queued=parent.submit(small_task(),defer=True);drive=parent._service.drive
        def inject(record,*args,**kw):
            atomic_text(parent._service.task_dir(record['task_id'])/'session/.cancel','cancel',overwrite=True)
            return drive(record,*args,**kw)
        with patch.object(parent._service,'drive',side_effect=inject):result=parent.start_queued(queued['task_id'])
        self.assertEqual(result['status'],'cancelled');self.assertEqual(result['budget']['used']['tool_calls'],0)

    def test_submit_is_fast_and_preserves_real_chained_results_and_bundle(self):
        runtime=self.runtime();started=time.monotonic();initial=runtime.submit(direct_task('mcp-chain'))
        self.assertLess(time.monotonic()-started,3);self.assertIn(initial['status'],('queued','running','completed'))
        done=self.wait(runtime,initial['task_id']);self.assertEqual(done['status'],'completed')
        self.assertEqual(done['results'][1]['data']['rank'],2);self.assertEqual(done['budget']['used'],{'model_calls':0,'tool_calls':2})
        self.assertEqual(done['operation']['usage']['tool_calls'],2)
        self.assertEqual(done['operation']['status'],'succeeded')
        bundle=done['artifacts'][0];self.assertTrue(verify_bundle(bundle['path'],bundle['sha256'])['ok'])
        self.assertTrue(bundle['uri'].startswith('graph-research://tasks/'))
        replay=runtime.submit(direct_task('mcp-chain'))
        self.assertEqual(replay['task_id'],done['task_id'])
        self.assertEqual(replay['request_effect']['new_tool_calls'],0)
        self.assertFalse(replay['request_effect']['new_worker_started'])
        self.assertEqual(replay['summary']['reuse']['cumulative']['steps_executed'],2)
        self.assertEqual(replay['artifacts'],done['artifacts'])
        changed=direct_task('mcp-chain');changed['inputs']['n']=4
        self.assertEqual(runtime.call('research_submit',{'task':changed})['error']['code'],'request_id_conflict')
        field=runtime.inspect_result(done['task_id'],'call-0002',path=['rank']);self.assertEqual(field['value'],2)
        rows=runtime.inspect_result(done['task_id'],'call-0001',path=['matrix'],offset=1,limit=1)
        self.assertEqual(rows['total_items'],3);self.assertEqual(len(rows['value']),1);self.assertEqual(rows['next_offset'],2)
        raw=bytearray();offset=0
        while True:
            part=runtime.read_artifact(done['task_id'],0,offset=offset,length=32768);raw.extend(base64.b64decode(part['data_base64']))
            if part['eof']:break
            offset=part['next_offset']
        self.assertEqual(hashlib.sha256(raw).hexdigest(),bundle['sha256'])
        self.assertEqual(runtime.list_tasks()['tasks'][0]['task_id'],done['task_id'])

    def test_busy_task_admission_and_repeated_request_are_distinct(self):
        runtime=self.runtime();fake=Mock();fake.poll.return_value=None
        with patch('graph_research.mcp.runtime.subprocess.Popen',return_value=fake):first=runtime.submit(small_task())
        self.assertEqual(runtime.submit(small_task())['task_id'],first['task_id'])
        refused=runtime.call('research_submit',{'task':small_task('second')});self.assertEqual(refused['error']['code'],'mcp_busy')
        self.assertEqual(len(list((runtime.service.directory/'tasks').glob('*/task.json'))),1)
        self.assertEqual(runtime.call('research_recover',{'task_id':first['task_id']})['error']['code'],'worker_still_active')
        self.assertEqual(runtime.cancel(first['task_id'])['status'],'cancelled');fake.poll.return_value=0

    def test_launch_failure_survives_restart_and_never_automatically_reexecutes(self):
        runtime=self.runtime()
        with patch('graph_research.mcp.runtime.subprocess.Popen',side_effect=OSError('PRIVATE_ERROR')):initial=runtime.submit(small_task())
        self.assertEqual(initial['transport']['worker_state'],'interrupted');self.assertNotIn('PRIVATE_ERROR',json.dumps(initial))
        restarted=self.runtime()
        with patch('subprocess.Popen',side_effect=AssertionError('No automatic replay')):
            again=restarted.submit(small_task());self.assertEqual(again['task_id'],initial['task_id'])
            recovered=restarted.recover(initial['task_id'])
        self.assertEqual(recovered['status'],'interrupted');self.assertEqual(recovered['budget']['used']['tool_calls'],0)
        portal=create_subagent(self.root,user_id='a',limits=runtime.configuration.limits())[1]
        p=recovered['interaction'];event=portal.continue_task(initial['task_id'],p['interaction_id'],recovered['revision'])
        restarted.resume(initial['task_id'],event['event_id']);done=self.wait(restarted,initial['task_id'])
        self.assertEqual(done['status'],'completed');self.assertEqual(done['budget']['used']['tool_calls'],1)
        self.assertEqual(restarted.resume(initial['task_id'],event['event_id'])['budget']['used']['tool_calls'],1)

    def test_default_rejects_agent_mode_and_authority_override_without_network(self):
        runtime=self.runtime()
        with patch('httpx.Client',side_effect=AssertionError('No API')):
            denied=runtime.call('research_submit',{'task':agent_task()});self.assertEqual(denied['error']['code'],'agent_mode_disabled')
            for name,args in [('research_approve',{}),('research_submit',{'task':small_task(),'user_id':'other'}),
                              ('research_resume',{'task_id':'a'*32,'event_id':'b'*32,'approved':True}),('research_read_artifact',{'task_id':'a'*32,'index':0,'path':'C:/secret'})]:
                self.assertEqual(runtime.call(name,args)['status'],'protocol_error')
        self.assertEqual(runtime.list_tasks()['tasks'],[])
        invalid=runtime.call('research_get',{'task_id':'a'*32,'wait_seconds':99})
        self.assertEqual(invalid['error']['field_path'],['wait_seconds']);self.assertEqual(invalid['error']['validation']['maximum'],10)

    def test_worker_environment_forwards_only_explicit_model_secret_and_job_has_no_secret(self):
        from graph_research.assistant.model_config import ModelSettings
        settings=ModelSettings('https://example.invalid/v1','mock',key_env='SELECTED_KEY').public()
        runtime=self.runtime(model_settings=settings,max_model_calls=1);fake=Mock();fake.poll.return_value=0
        with patch.dict(os.environ,{'SELECTED_KEY':'SELECTED_PRIVATE','OTHER_API_KEY':'OTHER_PRIVATE','RESEARCH_API_KEY':'UNRELATED','DSH_TEST':'PRIVATE_DSH'}),patch('graph_research.mcp.runtime.subprocess.Popen',return_value=fake) as spawn:
            result=runtime.submit(agent_task());env=spawn.call_args.kwargs['env'];self.assertEqual(env['SELECTED_KEY'],'SELECTED_PRIVATE')
            self.assertNotIn('OTHER_API_KEY',env);self.assertNotIn('RESEARCH_API_KEY',env);self.assertNotIn('DSH_TEST',env)
        _,job=runtime._current_job(result['task_id']);text=json.dumps(job)
        for private in ('SELECTED_PRIVATE','OTHER_PRIVATE','PRIVATE_DSH'):self.assertNotIn(private,text)
        runtime.recover(result['task_id'])

    def test_catalog_is_compact_full_contract_is_on_demand_and_whitelist_is_enforced(self):
        runtime=self.runtime(allowed_tools=('graph_spectrum',))
        catalog=runtime.catalog();self.assertEqual([t['name'] for t in catalog['tools']],['graph_spectrum']);self.assertNotIn('parameters',catalog['tools'][0])
        from graph_research import __version__
        from graph_research.runtime.integrity import verify
        self.assertEqual(catalog['service']['version'],__version__)
        self.assertEqual(catalog['service']['core_manifest_sha256'],verify()['manifest_sha256'])
        full=runtime.catalog('graph_spectrum');cached=runtime.catalog('graph_spectrum',full['schema_hash'])
        self.assertTrue(cached['unchanged']);self.assertEqual(cached['service'],catalog['service'])
        self.assertIn('parameters',runtime.catalog('graph_spectrum')['tool']);self.assertFalse(catalog['capabilities']['agent_mode'])
        self.assertEqual(runtime.call('research_catalog',{'name':'graph_invariants'})['error']['code'],'tool_not_permitted')
        initial=runtime.submit(small_task());done=self.wait(runtime,initial['task_id']);self.assertEqual(done['status'],'blocked');self.assertEqual(done['budget']['used']['tool_calls'],0)

    def test_task_budget_cannot_be_increased_through_transport(self):
        runtime=self.runtime(max_tool_calls=1);initial=runtime.submit(direct_task());done=self.wait(runtime,initial['task_id'])
        self.assertEqual(done['status'],'budget_exhausted',done.get('transport'));self.assertEqual(done['budget']['used']['tool_calls'],1)
        other=small_task('raised');other['constraints']={'max_tool_calls':2}
        self.assertEqual(runtime.call('research_submit',{'task':other})['error']['code'],'host_limit_exceeded')
        self.assertEqual(done['budget']['admission_policy'],'execute_until_budget_exhausted')
        strict=direct_task('strict-budget');strict['constraints']={'max_tool_calls':1,'fail_fast':True}
        before=runtime.list_tasks()
        refused=runtime.call('research_submit',{'task':strict})
        self.assertEqual(refused['error']['code'],'tools_budget_insufficient')
        self.assertEqual(runtime.list_tasks(),before)

    def test_result_paths_and_registered_artifacts_are_bounded_and_user_scoped(self):
        runtime=self.runtime();initial=runtime.submit(small_task());done=self.wait(runtime,initial['task_id']);task=done['task_id']
        other=self.runtime(user='other');self.assertEqual(other.call('research_get',{'task_id':task})['status'],'protocol_error')
        self.assertEqual(runtime.call('research_inspect_result',{'task_id':task,'call_id':'call-0001','path':['missing']})['error']['code'],'invalid_result_path')
        target=Path(done['artifacts'][0]['path']);target.write_bytes(target.read_bytes()+b'changed')
        self.assertEqual(runtime.call('research_read_artifact',{'task_id':task,'index':0})['error']['code'],'artifact_changed')

    def test_resume_has_no_event_minting_and_does_not_consume_forged_event(self):
        from graph_research.assistant.model_config import ModelSettings
        model=ScriptedModel([{'action':'clarify','questions':['是P3吗？']}])
        runtime=self.runtime(model_settings=ModelSettings('https://example.invalid/v1','mock',auth_required=False).public(),max_model_calls=1)
        parent,portal=create_subagent(self.root,user_id='a',model_factory=lambda:model,limits=runtime.configuration.limits())
        waiting=parent.submit(agent_task('clarify'));runtime.resume(waiting['task_id'],'b'*32)
        result=self.wait(runtime,waiting['task_id']);self.assertEqual(result['status'],'waiting_for_user')
        self.assertIsNotNone(result['transport']['error']);self.assertEqual(result['budget']['used']['model_calls'],1)
        from graph_research.mcp.server import response_is_error
        self.assertEqual(result['operation']['status'],'failed');self.assertTrue(response_is_error(result))
        self.assertEqual(result['operation']['error']['code'],'event_not_found')
        self.assertEqual(result['operation']['usage']['tool_calls'],0)
        self.assertEqual(result['operation']['usage']['model_calls'],0)
        self.assertEqual(len(model.contexts),1)
        self.assertTrue(all('approve' not in d['name'] and 'answer' not in d['name'] for d in tool_definitions()))

    def test_repeated_cancel_preserves_revision_interaction_and_exact_archive(self):
        runtime=self.runtime();queued=runtime.parent.submit(small_task('cancel-noop'),defer=True)
        first=runtime.cancel(queued['task_id']);archive=Path(first['artifacts'][0]['path'])
        before=(archive.read_bytes(),archive.stat().st_mtime_ns,runtime.service.record_path(first['task_id']).read_bytes())
        with patch('graph_research.assistant.session.ResearchSession._finalize_output',side_effect=AssertionError('Must reuse the original bundle')):
            again=runtime.cancel(first['task_id'])
        for key in ('status','revision','interaction','artifacts','budget','updated_at'):self.assertEqual(again[key],first[key])
        self.assertEqual(again['request_effect']['disposition'],'unchanged')
        self.assertEqual((archive.read_bytes(),archive.stat().st_mtime_ns,runtime.service.record_path(first['task_id']).read_bytes()),before)

    def test_cancel_after_resume_launch_is_not_cleared_by_worker_startup(self):
        from graph_research.mcp.worker import run_job
        runtime=self.runtime();queued=runtime.parent.submit(small_task('resume-cancel-race'),defer=True)
        stopped=runtime.cancel(queued['task_id'])
        portal=create_subagent(self.root,user_id='a',limits=runtime.configuration.limits())[1]
        event=portal.continue_task(stopped['task_id'],stopped['interaction']['interaction_id'],stopped['revision'])
        fake=Mock();fake.poll.return_value=None
        with patch('graph_research.mcp.runtime.subprocess.Popen',return_value=fake):runtime.resume(stopped['task_id'],event['event_id'])
        runtime.cancel(stopped['task_id']);path,_=runtime._current_job(stopped['task_id'])
        run_job(path);fake.poll.return_value=0
        done=runtime.get(stopped['task_id'])
        self.assertEqual(done['status'],'cancelled');self.assertEqual(done['budget']['used']['tool_calls'],0)

    def test_style_error_survives_protected_worker_and_identifies_field(self):
        from graph_research.graph_input.document import document
        graph=document([0,1],[{'vertices':[0,1]}]).to_dict();graph['style']={'font_size':99}
        task=small_task('bad-style');task['execution']['steps']=[{'id':'tex','tool':'graph_tikz','arguments':{'edges':[[0,1]],'vertices':[0,1],'graph_document':graph}}]
        runtime=self.runtime();initial=runtime.submit(task);done=self.wait(runtime,initial['task_id'])
        row=done['results'][0];self.assertEqual(row['status'],'failed')
        detail=row['error_details'];self.assertEqual(detail['field_path'],['style','font_size'])
        self.assertEqual(detail['cause_code'],'invalid_field');self.assertEqual(detail['validation']['minimum'],6);self.assertEqual(detail['validation']['maximum'],36)

    def test_connection_snippets_preserve_paths_and_do_not_write_or_connect(self):
        from graph_research.mcp.cli import connection_configuration
        base=['--root',str(self.root/'有 空格'),'--user','researcher']
        for format in ('json','codex','dsh'):
            output=io.StringIO()
            with redirect_stdout(output),patch('httpx.Client',side_effect=AssertionError('No API')):connection_configuration([*base,'--format',format])
            text=output.getvalue();self.assertIn('graph_research',text)
            if format=='codex':self.assertEqual(tomllib.loads(text)['mcp_servers']['graph_research']['command'],str(Path(sys.executable).resolve()))
            elif format=='json':self.assertIn(str(self.root/'有 空格'),json.loads(text)['args'])
            else:self.assertIn('@deepseek-ai/dsh-mcp-client',text)
        self.assertFalse((self.root/'有 空格').exists())

    def test_configuration_rejects_implicit_model_and_persistent_keys(self):
        with self.assertRaises(ValueError):HostConfiguration(str(self.root),'a',max_model_calls=1)
        with self.assertRaises(ValueError):HostConfiguration(str(self.root),'a',allow_extensions=True)
        document=HostConfiguration(str(self.root),'a').public();document['api_key']='PRIVATE'
        with self.assertRaises(ValueError):HostConfiguration.from_public(document)

    def test_atomic_state_read_race_retries_reads_without_restarting_work(self):
        runtime=self.runtime();parent=runtime.parent
        with patch.object(parent,'get',side_effect=[TaskProtocolError('task_not_found','瞬时读取失败'),{'task_id':'a'*32,'status':'queued','revision':1}]) as get:
            with patch('subprocess.Popen',side_effect=AssertionError('A read must not start work')):snapshot=runtime._snapshot('a'*32)
        self.assertEqual(snapshot['revision'],1);self.assertEqual(get.call_count,2)

    def test_trusted_reply_crosses_mcp_queue_and_returns_real_computation(self):
        from graph_research.assistant.model_config import ModelSettings
        from graph_research.mcp.worker import run_job
        model=ScriptedModel([{'action':'clarify','questions':['路径图有多少个顶点？']},
            {'action':'call','tool':'graph_invariants','arguments':{'n':3}}, {'action':'final','answer':'直径为2。'}])
        runtime=self.runtime(model_settings=ModelSettings('https://example.invalid/v1','mock',auth_required=False).public(),max_model_calls=4)
        parent,portal=create_subagent(self.root,user_id='a',limits=runtime.configuration.limits(),model_factory=lambda:model)
        fake=Mock();fake.poll.return_value=None
        with patch('graph_research.mcp.runtime.subprocess.Popen',return_value=fake):queued=runtime.submit(agent_task('trusted-reply'))
        path,_=runtime._current_job(queued['task_id'])
        with patch('graph_research.mcp.worker.HostConfiguration.parent',return_value=parent):run_job(path)
        fake.poll.return_value=0;waiting=runtime.get(queued['task_id']);self.assertEqual(waiting['status'],'waiting_for_user')
        pending=waiting['interaction'];event=portal.answer(waiting['task_id'],pending['interaction_id'],waiting['revision'],'3个顶点')
        fake.poll.return_value=None
        with patch('graph_research.mcp.runtime.subprocess.Popen',return_value=fake):runtime.resume(waiting['task_id'],event['event_id'])
        path,_=runtime._current_job(waiting['task_id'])
        with patch('graph_research.mcp.worker.HostConfiguration.parent',return_value=parent):run_job(path)
        fake.poll.return_value=0;done=runtime.get(waiting['task_id'])
        self.assertEqual(done['status'],'completed');self.assertEqual(done['results'][0]['data']['diameter'],2)
        self.assertEqual(done['budget']['used'],{'model_calls':3,'tool_calls':1})

    def test_background_process_crash_keeps_original_id_and_requires_recovery(self):
        runtime=self.runtime();fake=Mock();fake.poll.return_value=None
        with patch('graph_research.mcp.runtime.subprocess.Popen',return_value=fake):initial=runtime.submit(small_task('crashed'))
        fake.poll.return_value=1;state=runtime.get(initial['task_id']);self.assertEqual(state['transport']['worker_state'],'interrupted')
        self.assertEqual(state['next_actions'],['get','recover']);self.assertEqual(state['budget']['used']['tool_calls'],0)
        runtime.recover(initial['task_id']);self.assertEqual(runtime.submit(small_task('crashed'))['task_id'],initial['task_id'])

    def test_extension_approval_uses_only_trusted_portal_event_through_mcp_queue(self):
        from graph_research.assistant.model_config import ModelSettings
        from graph_research.mcp.worker import run_job
        from tests.feature_helpers import proposal,request_for
        tool=proposal();model=ScriptedModel([{'action':'assess','request':request_for(tool)},{'action':'extend','proposal':tool},{'action':'final','answer':'实验扩展已完成样例验收。'}])
        runtime=self.runtime(model_settings=ModelSettings('https://example.invalid/v1','mock',auth_required=False).public(),max_model_calls=8,allow_extensions=True)
        parent,portal=create_subagent(self.root,user_id='a',limits=runtime.configuration.limits(),model_factory=lambda:model)
        fake=Mock();fake.poll.return_value=None
        with patch('graph_research.mcp.runtime.subprocess.Popen',return_value=fake):initial=runtime.submit(agent_task('approval'))
        path,_=runtime._current_job(initial['task_id'])
        with patch('graph_research.mcp.worker.HostConfiguration.parent',return_value=parent):run_job(path)
        fake.poll.return_value=0;waiting=runtime.get(initial['task_id']);self.assertEqual(waiting['status'],'waiting_for_approval')
        self.assertFalse(list(parent._service.tool_directory.glob('*/tool.py')))
        pending=waiting['interaction'];event=portal.approve(waiting['task_id'],pending['interaction_id'],waiting['revision'],pending['assessment_id'],pending['scope_sha256'])
        fake.poll.return_value=None
        with patch('graph_research.mcp.runtime.subprocess.Popen',return_value=fake):runtime.resume(waiting['task_id'],event['event_id'])
        path,_=runtime._current_job(waiting['task_id'])
        with patch('graph_research.mcp.worker.HostConfiguration.parent',return_value=parent):run_job(path)
        fake.poll.return_value=0;done=runtime.get(waiting['task_id']);self.assertEqual(done['status'],'completed')
        self.assertTrue(list(parent._service.tool_directory.glob('*/tool.py')))
        self.assertTrue(any(a['kind']=='experimental_extension' for a in done['artifacts']))


@unittest.skipUnless(SDK,'Optional official MCP SDK is not installed')
class SDKTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    async def asyncTearDown(self):self.temp.cleanup()

    async def test_official_sdk_marks_rejected_async_resume_as_error_but_keeps_task_state(self):
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root),'sdk-resume-error'))
        queued=runtime.parent.submit(small_task('sdk-cancelled'),defer=True);stopped=runtime.cancel(queued['task_id'])
        async with Client(create_server(runtime),mode='legacy',cache=None) as client:
            response=await client.call_tool('research_resume',{'task_id':stopped['task_id'],'event_id':'b'*32})
            deadline=time.monotonic()+30
            while response.structured_content.get('transport',{}).get('active') and time.monotonic()<deadline:
                response=await client.call_tool('research_get',{'task_id':stopped['task_id'],'wait_seconds':1})
            self.assertTrue(response.is_error)
            result=response.structured_content;self.assertEqual(result['status'],'cancelled')
            self.assertEqual(result['operation']['error']['code'],'event_not_found')
            self.assertEqual(result['interaction'],stopped['interaction']);self.assertEqual(result['revision'],stopped['revision'])
            cancelled=await client.call_tool('research_cancel',{'task_id':stopped['task_id']})
            self.assertFalse(cancelled.is_error)

    async def test_official_sdk_modern_and_legacy_discovery_validation_and_resources(self):
        for mode in ('auto','legacy'):
            runtime=MCPResearchRuntime(HostConfiguration(str(self.root/mode),'sdk'))
            async with Client(create_server(runtime),mode=mode,cache=None) as client:
                listed=await client.list_tools();self.assertEqual(len(listed.tools),13)
                self.assertTrue(all('approve' not in t.name for t in listed.tools))
                cancel=next(tool for tool in listed.tools if tool.name=='research_cancel')
                self.assertTrue(cancel.annotations.idempotent_hint)
                result=await client.call_tool('research_catalog',{});self.assertFalse(result.is_error);self.assertEqual(len(result.structured_content['tools']),47)
                invalid=await client.call_tool('research_read_artifact',{'task_id':'a'*32,'index':0,'path':'C:/private'})
                self.assertTrue(invalid.is_error)
                resources=await client.list_resources();self.assertEqual(len(resources.resources),2)
                guide=await client.read_resource('graph-research://guide');self.assertIn('research_submit',guide.contents[0].text)
                from mcp.shared.exceptions import MCPError
                with self.assertRaises(MCPError) as caught:await client.read_resource('file:///C:/private')
                self.assertEqual(caught.exception.code,-32602)

    async def test_real_stdio_handshake_async_execution_and_cross_connection_reuse(self):
        args=['-I','-X','utf8','-m','graph_research','mcp','--root',str(self.root),'--user','wire','--results-root',str(self.root/'results')]
        parameters=StdioServerParameters(command=sys.executable,args=args)
        async with Client(parameters,mode='legacy',cache=None,read_timeout_seconds=20) as client:
            listed=await client.list_tools();self.assertEqual(len(listed.tools),13)
            initial=await client.call_tool('research_submit',{'task':direct_task('wire-chained')});self.assertFalse(initial.is_error)
            task_id=initial.structured_content['task_id'];deadline=time.monotonic()+35
            while time.monotonic()<deadline:
                current=await client.call_tool('research_get',{'task_id':task_id,'wait_seconds':1})
                done=current.structured_content
                if not done.get('transport',{}).get('active'):break
            self.assertEqual(done['status'],'completed');self.assertEqual(done['results'][1]['data']['rank'],2)
            artifact=await client.read_resource(done['artifacts'][0]['uri']);raw=base64.b64decode(artifact.contents[0].blob)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),done['artifacts'][0]['sha256'])
            inspected=await client.call_tool('research_inspect_result',{'task_id':task_id,'call_id':'call-0002','path':['rank']})
            self.assertEqual(inspected.structured_content['value'],2)
        async with Client(parameters,mode='auto',cache=None,read_timeout_seconds=20) as client:
            again=await client.call_tool('research_submit',{'task':direct_task('wire-chained')})
            self.assertEqual(again.structured_content['task_id'],task_id);self.assertEqual(again.structured_content['budget']['used']['tool_calls'],2)
            tasks=await client.call_tool('research_list_tasks',{});self.assertEqual(len(tasks.structured_content['tasks']),1)


    async def test_real_stdio_batch_cases_outputs_inspect_and_idempotent_replay(self):
        from tests.test_batch_workflow import batch_task
        parameters=StdioServerParameters(command=sys.executable,args=['-I','-X','utf8','-m','graph_research','mcp',
            '--root',str(self.root),'--user','wire-batch','--max-tool-calls','8','--results-root',str(self.root/'results')])
        task=batch_task('wire-batch')
        async with Client(parameters,mode='legacy',cache=None,read_timeout_seconds=30) as client:
            submitted=await client.call_tool('research_submit',{'task':task,'wait_seconds':2});self.assertFalse(submitted.is_error)
            identifier=submitted.structured_content['task_id'];deadline=time.monotonic()+45;done=submitted.structured_content
            while done.get('transport',{}).get('active') and time.monotonic()<deadline:
                got=await client.call_tool('research_get',{'task_id':identifier,'wait_seconds':2,'until':'terminal','detail':'full'})
                done=got.structured_content
            self.assertEqual(done['status'],'completed',done);self.assertEqual(done['budget']['used']['tool_calls'],4)
            batch=done['summary']['batch'];self.assertEqual(batch['successful_cases'],2)
            row=batch['rows'][0];output=row['outputs']['rank']
            inspected=await client.call_tool('research_inspect_result',{'task_id':identifier,'call_id':output['call_id'],
                'path':batch['output_definitions']['rank']['path']})
            self.assertEqual(inspected.structured_content['value'],2)
            repeated=await client.call_tool('research_submit',{'task':task})
            self.assertEqual(repeated.structured_content['task_id'],identifier);self.assertEqual(repeated.structured_content['budget']['used']['tool_calls'],4)
            resource=await client.read_resource(done['artifacts'][0]['uri']);raw=base64.b64decode(resource.contents[0].blob)
            import io,zipfile
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:self.assertIn('batch-results.csv',archive.namelist())


    async def test_real_stdio_readonly_memory_reviewed_cases_and_user_scope(self):
        from graph_research.assistant.memory import UserMemoryStore
        from graph_research.assistant.experience import ExperienceStore,search_experiences
        memory=UserMemoryStore(self.root/'memory');memory.set_preference('wire-memory','language','zh-CN');memory.set_preference('another','language','en')
        parameters=StdioServerParameters(command=sys.executable,args=['-I','-X','utf8','-m','graph_research','mcp',
            '--root',str(self.root),'--user','wire-memory','--results-root',str(self.root/'results')])
        async with Client(parameters,mode='legacy',cache=None,read_timeout_seconds=30) as client:
            tools=await client.list_tools();self.assertEqual(len(tools.tools),13)
            for name in ('research_memory','research_experience'):
                item=next(item for item in tools.tools if item.name==name);self.assertTrue(item.annotations.read_only_hint)
            profile=await client.call_tool('research_memory',{});self.assertEqual(profile.structured_content['preferences'],{'language':'zh-CN'})
            submitted=await client.call_tool('research_submit',{'task':small_task('wire-experience'),'wait_seconds':5})
            done=submitted.structured_content;deadline=time.monotonic()+35
            while done.get('transport',{}).get('active') and time.monotonic()<deadline:
                result=await client.call_tool('research_get',{'task_id':done['task_id'],'wait_seconds':2,'until':'terminal'});done=result.structured_content
            self.assertEqual(done['status'],'completed',done)
            hidden=await client.call_tool('research_experience',{});self.assertEqual(hidden.structured_content['records'],[])
            candidates=search_experiences(self.root/'memory','wire-memory',reviewed_only=False,status='candidate')['records'];self.assertEqual(len(candidates),1)
            record=candidates[0]
            ExperienceStore(self.root/'memory').review('wire-memory',record['id'],record['content_sha256'],'approved','合成验收样例，模拟用户审阅')
            read=await client.call_tool('research_experience',{'id':record['id']})
            self.assertEqual(read.structured_content['records'][0]['source_state'],'verified')
            denied=await client.call_tool('research_memory',{'user_id':'another'});self.assertTrue(denied.is_error)
            write=await client.call_tool('research_experience',{'id':record['id'],'decision':'approve'});self.assertTrue(write.is_error)
            current=await client.call_tool('research_get',{'task_id':done['task_id']})
            self.assertEqual(current.structured_content['budget']['used'],{'model_calls':0,'tool_calls':1})


    async def test_real_stdio_external_development_host_approval_library_and_reuse_without_api(self):
        from graph_research.assistant.development import from_host
        from tests.feature_helpers import proposal,request_for
        tool=proposal();request=request_for(tool)
        parameters=StdioServerParameters(command=sys.executable,args=['-I','-X','utf8','-m','graph_research','mcp',
            '--root',str(self.root),'--user','wire-library','--allow-development','--results-root',str(self.root/'results')])
        async with Client(parameters,mode='legacy',cache=None,read_timeout_seconds=30) as client:
            initial=await client.call_tool('research_development',{'operation':'assess','request_id':'sdk-development','request':request})
            self.assertFalse(initial.is_error);value=initial.structured_content;identifier=value['id'];self.assertEqual(value['status'],'waiting_for_approval')
            submit={'operation':'submit','development_id':identifier,'implementation_id':'sdk-source-1','proposal':tool,'wait_seconds':5}
            denied=await client.call_tool('research_development',submit);self.assertTrue(denied.is_error)
            from_host(self.root,'wire-library').approve(identifier,value['assessment']['scope_sha256'])  # synthetic trusted-user fixture
            started=await client.call_tool('research_development',submit);self.assertFalse(started.is_error,started.structured_content);done=started.structured_content
            deadline=time.monotonic()+30
            while done.get('active') and time.monotonic()<deadline:
                found=await client.call_tool('research_development',{'operation':'get','development_id':identifier,'wait_seconds':2});done=found.structured_content
            self.assertEqual(done['status'],'installed',done);self.assertEqual(done['budget']['local_model_calls'],0)
            catalog=await client.call_tool('research_library',{});self.assertEqual(catalog.structured_content['records'][0]['name'],tool['name'])
            contract=await client.call_tool('research_catalog',{'name':tool['name']});self.assertIn('tool',contract.structured_content)
            task={'version':1,'request_id':'sdk-reuse','objective':'复用独立新工具','execution':{'mode':'tools','steps':[{'id':'h','tool':tool['name'],'arguments':{'degrees':[3,2,2,1]}}]}}
            calculation=await client.call_tool('research_submit',{'task':task,'wait_seconds':5,'detail':'full'})
            result=calculation.structured_content;deadline=time.monotonic()+30
            while result.get('transport',{}).get('active') and time.monotonic()<deadline:
                queried=await client.call_tool('research_get',{'task_id':result['task_id'],'wait_seconds':2,'until':'terminal','detail':'full'});result=queried.structured_content
            self.assertEqual(result['results'][0]['data'],{'h_index':2});self.assertEqual(result['budget']['used'],{'model_calls':0,'tool_calls':1})


if __name__=='__main__':unittest.main()
