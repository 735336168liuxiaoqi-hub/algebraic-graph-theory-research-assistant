"""Evidence, durable budgets and crash recovery without a paid model service."""
import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from graph_research.assistant import ResearchSession
from graph_research.assistant.governance import WorkflowJournal,RecoveryRequired,validate_policy
from graph_research.assistant.claims import audit_claims
from graph_research.tools import ToolRegistry
from graph_research.runtime.runner import run_tool
from graph_research.graph_input import parse_graph
from tests.test_feature_workflow import ScriptedModel


class BudgetAndClaimsTests(unittest.TestCase):
    def test_missing_durable_journal_does_not_reset_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'s',Path(tmp)/'t',auto_export=False);s.set_workflow_budget({'max_model_calls':1})
            s.ask('测试',ScriptedModel([{'action':'final','answer':'完成。'}]));s.workflow.path.unlink()
            with self.assertRaisesRegex(ValueError,'日志缺失'):ResearchSession(s.directory)
    def test_clarification_and_restart_keep_same_model_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'session',Path(tmp)/'tools',auto_export=False);s.set_workflow_budget({'max_model_calls':1})
            s.ask('图研究',ScriptedModel([{'action':'clarify','questions':['选择哪张图？']}]))
            task=s.state['workflow_task_id'];s=ResearchSession(s.directory)
            model=ScriptedModel([{'action':'final','answer':'不应发送。'}]);result=s.reply('研究P3',model)
            self.assertEqual(result['status'],'budget_exhausted');self.assertEqual(model.contexts,[])
            self.assertEqual(result['workflow_task_id'],task);self.assertEqual(s.workflow_usage()['model_calls'],1)

    def test_unknown_failure_usage_remains_reserved_after_manual_continue(self):
        class Failure:
            def complete(self,messages):raise RuntimeError('network interrupted')
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'s',Path(tmp)/'t',auto_export=False);s.ask('测试',Failure())
            self.assertEqual(s.workflow_usage()['unknown_usage_requests'],1)
            s=ResearchSession(s.directory);s.continue_run(ScriptedModel([{'action':'final','answer':'恢复完成。'}]))
            self.assertEqual(s.workflow_usage()['model_calls'],2);self.assertEqual(s.workflow_usage()['unknown_usage_requests'],2)
            self.assertGreater(s.workflow_usage()['reserved_input_tokens'],0)

    def test_token_budget_blocks_before_request_and_host_change_does_not_reset_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'s',Path(tmp)/'t',auto_export=False);s.set_workflow_budget({'max_input_tokens':1})
            model=ScriptedModel([{'action':'final','answer':'完成。'}]);s.ask('测试',model)
            self.assertEqual(model.contexts,[]);self.assertEqual(s.state['status'],'budget_exhausted')
            s.set_workflow_budget({'max_input_tokens':200000});s.continue_run(model)
            self.assertEqual(s.workflow_usage()['model_calls'],1)
            with self.assertRaises(ValueError):validate_policy({'max_cost':1})

    def test_reported_usage_replaces_reservation_and_is_cumulative(self):
        class Model:
            last_usage=None
            def complete(self,messages,*,max_output_tokens=None):
                self.last_usage={'input_tokens':25,'output_tokens':7};return {'action':'final','answer':'完成。'}
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'s',Path(tmp)/'t',auto_export=False)
            s.set_workflow_budget({'input_per_million':2,'output_per_million':3,'currency':'TEST'})
            s.ask('测试',Model());usage=s.workflow_usage()
            self.assertEqual(usage['known_input_tokens'],25);self.assertEqual(usage['unknown_usage_requests'],0)
            self.assertAlmostEqual(usage['known_cost'],(25*2+7*3)/1000000)

    def test_claims_distinguish_value_match_inference_proof_and_numeric_results(self):
        observations=[{'tool':'graph_invariants','ok':True,'result':{'diameter':2}},
                      {'tool':'graph_spectrum','ok':True,'result':{'rho':1.41421356}}]
        values=[{'text':'直径为2','kind':'exact','sources':[{'observation':0,'path':['diameter'],'expected':2}]},
                {'text':'一般证明','kind':'proof','sources':[{'observation':0,'path':['diameter']}]},
                {'text':'近似谱半径','kind':'exact','sources':[{'observation':1,'path':['rho'],'expected':1.41421356}]},
                {'text':'错误字段值','kind':'exact','sources':[{'observation':0,'path':['diameter'],'expected':3}]}]
        result=audit_claims(values,observations,lambda _:True)
        self.assertEqual([r['status'] for r in result],['field_matched','unverified_proof','field_matched','invalid_reference'])
        self.assertEqual(result[2]['kind'],'numerical')
        self.assertEqual(audit_claims(values[:1],observations,lambda _:False)[0]['status'],'invalid_reference')

    @unittest.skipUnless(os.name=='nt','Windows protected tools')
    def test_identical_bound_transform_reuses_receipt_without_extra_graph_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'s',Path(tmp)/'t');ref=s.bind_graph(parse_graph('a b\nb c'))
            call={'action':'call','tool':'graph_edit','arguments':{'operation':'power'},'graph_refs':{'graph':ref}}
            state=s.ask('重复读取同一变换',ScriptedModel([copy.deepcopy(call),copy.deepcopy(call),{'action':'final','answer':'已读取。'}]))
            self.assertTrue(all(o['ok'] for o in state['observations']),state)
            self.assertEqual(s.workflow_usage()['tool_calls'],1);self.assertEqual(len(s.research_objects['versions']),2)
            self.assertIn('reused_execution',state['observations'][1]);self.assertIsNone(s.export_error)

    @unittest.skipUnless(os.name=='nt','Windows protected tools')
    def test_claim_source_is_verified_against_real_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'s',Path(tmp)/'t')
            state=s.ask('直径',ScriptedModel([{'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':3}},
                {'action':'final','answer':'直径2。','claims':[{'text':'直径2','kind':'exact','sources':[{'observation':0,'path':['diameter'],'expected':2}]}]}]))
            self.assertEqual(state['audited_claims'][0]['status'],'field_matched');self.assertIsNone(s.export_error)


@unittest.skipUnless(os.name=='nt','Windows protected tools')
class JournalRecoveryTests(unittest.TestCase):
    def test_completed_plan_then_model_failure_does_not_reappend_last_step_on_resume(self):
        from tests.test_api_workflow import sample_plan
        class Model:
            calls=0
            def complete(self,messages):
                self.calls+=1
                if self.calls==1:return {'action':'plan','plan':sample_plan()}
                if self.calls==2:raise RuntimeError('simulated response failure')
                return {'action':'final','answer':'已保留完整计划结果。'}
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'s',Path(tmp)/'t');model=Model();s.ask('先执行计划',model)
            self.assertEqual(s.state['status'],'execution_error');self.assertEqual(len(s.state['observations']),2)
            s=ResearchSession(s.directory);s.continue_run(model)
            self.assertEqual(len(s.state['observations']),2);self.assertEqual(s.workflow_usage()['tool_calls'],2)

    def test_other_input_receipt_cannot_be_substituted_for_pending_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=WorkflowJournal(root);task=uuid.uuid4().hex;key=uuid.uuid4().hex;registry=ToolRegistry()
            observation={'tool':'graph_invariants','arguments':{'n':3}}
            _,operation=j.tool_call(task,key,observation,registry,lambda op:run_tool('graph_invariants',{'n':3},root/'t',directory=root/'tasks',operation_id=op,include_receipt=True))
            foreign=uuid.uuid4().hex;run_tool('graph_invariants',{'n':4},root/'t',directory=root/'tasks',operation_id=foreign,include_receipt=True)
            j.data['tasks'][task]['tool_calls'][key]['operation_id']=foreign;j.save()
            with self.assertRaises(RecoveryRequired):WorkflowJournal(root).tool_call(task,key,observation,registry,lambda _:self.fail('no implicit recomputation'))
    def test_complete_receipt_is_recovered_after_host_state_was_not_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=WorkflowJournal(root);task=uuid.uuid4().hex;key=uuid.uuid4().hex;registry=ToolRegistry()
            observation={'tool':'graph_invariants','arguments':{'kind':'path','n':3}}
            def invoke(operation):return run_tool('graph_invariants',observation['arguments'],root/'tools',directory=root/'tasks',operation_id=operation,include_receipt=True)
            value,operation=j.tool_call(task,key,observation,registry,invoke)
            entry=j.data['tasks'][task]['tool_calls'][key];entry.pop('observation',None);entry['status']='inflight';j.save()
            reloaded=WorkflowJournal(root)
            with patch('graph_research.runtime.runner.run_tool',side_effect=AssertionError('must not recompute')):
                recovered,again=reloaded.tool_call(task,key,observation,registry,lambda _:self.fail('replayed'))
            self.assertEqual(recovered['result']['diameter'],2);self.assertEqual(operation,again);self.assertEqual(reloaded.summary(task)['tool_calls'],1)

    def test_uncertain_workspace_requires_explicit_retry_and_retains_attempt_charge(self):
        class Crash(BaseException):pass
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);j=WorkflowJournal(root);task=uuid.uuid4().hex;key=uuid.uuid4().hex;registry=ToolRegistry()
            observation={'tool':'graph_invariants','arguments':{'n':3}}
            def crash(operation):(root/'tasks'/('task_'+operation)).mkdir(parents=True);raise Crash()
            with self.assertRaises(Crash):j.tool_call(task,key,observation,registry,crash)
            j=WorkflowJournal(root)
            with self.assertRaises(RecoveryRequired):j.tool_call(task,key,observation,registry,lambda _:self.fail('replayed'))
            with self.assertRaises(RecoveryRequired):j.tool_call(task,uuid.uuid4().hex,observation,registry,lambda _:self.fail('new key must not bypass uncertainty'))
            j.permit_retry(task,key)
            value,_=j.tool_call(task,key,observation,registry,lambda operation:run_tool('graph_invariants',{'n':3},root/'tools',directory=root/'tasks',operation_id=operation,include_receipt=True))
            self.assertEqual(value['result']['diameter'],2);self.assertEqual(j.summary(task)['tool_calls'],2)


class StreamingAndRoutesTests(unittest.TestCase):
    def test_incomplete_stream_cannot_execute_an_otherwise_valid_tool_json(self):
        import httpx,json
        from graph_research.assistant.model import ConfiguredModel
        from graph_research.assistant.model_config import validate_settings
        raw='data: '+json.dumps({'type':'response.output_text.delta','delta':'{"action":"call","tool":"graph_invariants","arguments":{"n":3}}'})+'\n\n'
        original=httpx.Client;model=ConfiguredModel(validate_settings({'base_url':'https://test.invalid/v1','model':'fake','auth_required':False,'stream':True}))
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'s',Path(tmp)/'t',auto_export=False)
            with patch('httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(lambda _:httpx.Response(200,headers={'content-type':'text/event-stream'},content=raw)),**kw)),patch('graph_research.runtime.runner.run_tool',side_effect=AssertionError('no partial execution')):
                state=s.ask('测试不完整指令',model)
            self.assertEqual(state['status'],'execution_error');self.assertFalse(state.get('observations'));self.assertEqual(s.workflow_usage()['model_calls'],1)
    def test_partial_json_only_previews_final_answer_and_handles_split_unicode(self):
        from graph_research.assistant.streaming import partial_final_answer
        self.assertIsNone(partial_final_answer('{"action":"call","arguments":{"answer":"not a final answer"}}'))
        self.assertEqual(partial_final_answer('{"action":"final","answer":"A\\u4e2d'),'A中')
        self.assertEqual(partial_final_answer('{"action":"final","answer":"A\\ud83d'),'A')
        self.assertEqual(partial_final_answer('{"action":"final","answer":"A\\ud83d\\ude00'),'A😀')
        self.assertEqual(partial_final_answer('{"answer":"hello","action":"final"}'),'hello')

    def test_both_protocol_streams_report_usage_and_reject_incomplete_decisions(self):
        import httpx,json
        from graph_research.assistant.model import ConfiguredModel,ModelAPIError
        from graph_research.assistant.model_config import validate_settings
        original=httpx.Client
        class Chunks(httpx.SyncByteStream):
            def __init__(self,chunks):self.chunks=chunks
            def __iter__(self):yield from self.chunks
        for mode in ('responses','chat_completions'):
            decision='{"action":"final","answer":"公式 x²，结果已收到。"}'
            if mode=='responses':events=[{'type':'response.output_text.delta','delta':decision[:30]}, {'type':'response.output_text.delta','delta':decision[30:]},{'type':'response.completed','response':{'status':'completed','usage':{'input_tokens':10,'output_tokens':6}}}]
            else:events=[{'choices':[{'delta':{'content':decision},'finish_reason':None}]},{'choices':[{'delta':{},'finish_reason':'stop'}]},{'choices':[],'usage':{'prompt_tokens':10,'completion_tokens':6}}]
            raw=(''.join('data: '+json.dumps(event,ensure_ascii=False)+'\n\n' for event in events)+'data: [DONE]\n\n').encode('utf-8')
            model=ConfiguredModel(validate_settings({'base_url':'https://test.invalid/v1','model':'fake','mode':mode,'auth_required':False,'stream':True}))
            def response(request):
                self.assertTrue(json.loads(request.content)['stream'])
                return httpx.Response(200,headers={'content-type':'text/event-stream'},stream=Chunks([raw[:11],raw[11:33],raw[33:]]))
            with patch('httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(response),**kw)):
                answer=model.complete([{'role':'user','content':'test'}]);self.assertEqual(answer['action'],'final');self.assertTrue(model.last_usage)
            incomplete=('data: '+json.dumps(events[0],ensure_ascii=False)+'\n\n').encode('utf-8')
            with patch('httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(lambda _:httpx.Response(200,headers={'content-type':'text/event-stream'},content=incomplete)),**kw)):
                with self.assertRaises(ModelAPIError):model.complete([{'role':'user','content':'test'}])

    def test_manual_feature_never_creates_approval_or_source_and_exports_brief(self):
        from tests.feature_helpers import proposal,request_for
        import zipfile,json
        request=request_for(proposal());request.update(implementation_mode='manual',required_libraries=['networkx'])
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'s',Path(tmp)/'t');result=s.ask('需要复杂新算法',ScriptedModel([{'action':'assess','request':request}]))
            self.assertEqual(result['status'],'manual_development_required');self.assertFalse(s.store.directory.exists());self.assertFalse(list((s.directory/'changes').glob('*/approval.json')))
            self.assertEqual(result['development_brief']['authorization'],'none')
            with zipfile.ZipFile(s.result_bundle['archive']) as archive:
                self.assertIn('development-briefs/turn-1.json',archive.namelist());self.assertIn('workflow-usage.json',archive.namelist())
                self.assertEqual(json.loads(archive.read('results.json'))['turns'][0]['development_brief']['kind'],'manual_development')

    def test_uncertain_definitions_are_clarified_before_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'s',Path(tmp)/'t',auto_export=False)
            result=s.ask('新算法',ScriptedModel([{'action':'assess','request':{'composition_possible':False,'implementation_mode':'uncertain'}}]))
            self.assertEqual(result['status'],'awaiting_clarification');self.assertFalse((s.directory/'changes').exists())


os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QTextDocument
    from PySide6.QtCore import QUrl,Qt
    from graph_research.desktop.research_view import AnswerView,BudgetDialog
    QT=True
except ImportError:QT=False


@unittest.skipUnless(QT,'Optional desktop')
class ReliabilityDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def test_answer_renders_math_and_tables_without_loading_model_html_or_file_images(self):
        view=AnswerView('## 计算\n**结果** $x^2-1$\n\n|a|b|\n|---|---|\n|1|2|\n<img src="file:///secret"><script>bad()</script>')
        try:
            self.assertTrue(view._images);self.assertIn('结果',view.toPlainText());self.assertIn('<script>',view.toPlainText())
            self.assertTrue(view.loadResource(QTextDocument.ResourceType.ImageResource,QUrl('file:///secret')).isNull())
        finally:view.close();view.deleteLater();self.app.processEvents()

    def test_budget_dialog_saves_explicit_limits_without_a_model_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=ResearchSession(Path(tmp)/'s',Path(tmp)/'t');dialog=BudgetDialog(s)
            try:
                dialog.spins['max_model_calls'].setValue(3)
                with patch('httpx.Client',side_effect=AssertionError('no request')):dialog.save_budget()
                self.assertEqual(s.workflow.data['policy']['max_model_calls'],3);self.assertFalse(s.state)
            finally:dialog.close();dialog.deleteLater();self.app.processEvents()

    def test_global_tex_preference_cannot_launch_external_tex_for_answer_formulas(self):
        import matplotlib
        from graph_research.desktop.research_view import formula_png
        with matplotlib.rc_context({'text.usetex':True}),patch('subprocess.Popen',side_effect=AssertionError('answer formulas must stay internal')):
            self.assertTrue(formula_png('x^{17}+37'))
            self.assertTrue(matplotlib.rcParams['text.usetex'])

    def test_native_evaluation_defaults_offline_and_report_is_available(self):
        from graph_research.desktop.evaluation import EvaluationDialog
        import time
        with tempfile.TemporaryDirectory() as tmp:
            dialog=EvaluationDialog(Path(tmp));dialog.show()
            try:
                for index in range(dialog.cases.count()):dialog.cases.item(index).setCheckState(Qt.CheckState.Checked if dialog.cases.item(index).data(Qt.ItemDataRole.UserRole)=='ambiguous-graph' else Qt.CheckState.Unchecked)
                with patch('httpx.Client',side_effect=AssertionError('must stay offline')):
                    dialog.start();deadline=time.monotonic()+20
                    while dialog.thread is not None and time.monotonic()<deadline:self.app.processEvents();time.sleep(.01)
                self.assertIsNone(dialog.thread);self.assertEqual(dialog.report_result['real_model_requests'],0);self.assertEqual(dialog.report_result['passed'],1)
                dialog.live.setChecked(True);self.assertTrue(dialog.fields['max_model_calls'].isEnabled())
            finally:dialog.close();dialog.deleteLater();self.app.processEvents()


class AcceptanceSuiteTests(unittest.TestCase):
    def test_live_authentication_failure_stops_later_cases_without_retrying(self):
        import httpx
        from graph_research.assistant.evaluation import run_evaluation
        from graph_research.assistant.model import ConfiguredModel
        from graph_research.assistant.model_config import validate_settings
        model=ConfiguredModel(validate_settings({'base_url':'https://test.invalid/v1','model':'fake','auth_required':False}));original=httpx.Client;requests=[]
        def denied(request):requests.append(request);return httpx.Response(401,json={'error':{'message':'not stored'}})
        limits={'max_model_calls':3,'max_tool_calls':2,'max_input_tokens':200000,'max_output_tokens':10000,'request_output_tokens':512}
        with tempfile.TemporaryDirectory() as tmp:
            with patch('httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(denied),**kw)):
                result=run_evaluation(tmp,live=True,model=model,case_ids=['ambiguous-graph','undefined-acceptance'],limits=limits)
            self.assertEqual(len(requests),1);self.assertEqual(result['failed'],1);self.assertEqual(result['not_run'],1)
    @unittest.skipUnless(os.name=='nt','Protected native tool cases')
    def test_all_twelve_offline_acceptance_cases_pass_without_http(self):
        from graph_research.assistant.evaluation import run_evaluation
        with tempfile.TemporaryDirectory() as tmp:
            with patch('httpx.Client',side_effect=AssertionError('offline suite cannot bill')):result=run_evaluation(tmp)
            self.assertEqual(result['passed'],12);self.assertEqual(result['failed'],0);self.assertEqual(result['real_model_requests'],0)

    def test_live_mode_requires_explicit_caps_and_caps_apply_across_cases(self):
        from graph_research.assistant.evaluation import run_evaluation
        with tempfile.TemporaryDirectory() as tmp:
            model=ScriptedModel([{'action':'clarify','questions':['请补充输入。']},{'action':'clarify','questions':['不会发送第二次请求。']}])
            with self.assertRaises(ValueError):run_evaluation(tmp,live=True,model=model)
            caps={'max_model_calls':1,'max_tool_calls':2,'max_input_tokens':200000,'max_output_tokens':10000,'request_output_tokens':512}
            with patch('httpx.Client',side_effect=AssertionError('test model only')):result=run_evaluation(tmp,live=True,model=model,case_ids=['ambiguous-graph','undefined-acceptance'],limits=caps)
            self.assertEqual(len(model.contexts),1);self.assertEqual(result['real_model_requests'],1);self.assertEqual(result['failed'],1)


if __name__=='__main__':unittest.main()
