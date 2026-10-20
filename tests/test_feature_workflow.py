"""End-to-end approval gates, costs, composition and independent packaging."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from graph_research.assistant import ResearchSession
from graph_research.agent import build_agent
from graph_research.tools import ToolRegistry
from graph_research.tools.extensions import ToolStore
from graph_research.tools.change_control import ChangeController,CORE,core_fingerprint
from tests.feature_helpers import proposal,request_for,approve_for_tests


class ScriptedModel:
    def __init__(self,decisions):self.decisions=list(decisions);self.contexts=[]
    def complete(self,messages):
        self.contexts.append(json.loads(messages[1]['content']))
        if not self.decisions:raise AssertionError('Unexpected extra model call')
        return self.decisions.pop(0)


class FeatureWorkflowTests(unittest.TestCase):
    def test_clarify_assess_wait_then_human_approval_generates_separate_package(self):
        tool=proposal();request=request_for(tool);before=core_fingerprint()
        model=ScriptedModel([
            {'action':'clarify','questions':['输入是具体图，还是已知的度序列？空序列如何处理？']},
            {'action':'assess','request':request},
            {'action':'extend','proposal':tool},
            {'action':'call','tool':tool['name'],'arguments':{'degrees':[3,2,2,1]}},
            {'action':'final','answer':'h指数为2；新工具仅通过列出的验收样例。'}])
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);session=ResearchSession(root/'session',root/'packages')
            first=session.ask('增加度序列h指数计算',model)
            self.assertEqual(first['status'],'awaiting_clarification')
            self.assertFalse((root/'packages').exists())
            second=session.reply('输入度序列，空序列约定为0，最多128项。',model)
            self.assertEqual(second['status'],'awaiting_approval')
            self.assertEqual(len(model.contexts),2)
            self.assertIsNone(second['assessment']['estimate']['money'])
            self.assertFalse((root/'packages'/tool['name']).exists())
            # Reload a durable session, then simulate the explicit host button.
            resumed=ResearchSession(root/'session')
            result=resumed.approve(second['assessment_id'],model)
            self.assertEqual(result['status'],'tool_results_available')
            self.assertEqual(result['observations'][-1]['result'],{'h_index':2})
            self.assertIsNone(resumed.export_error)
            with zipfile.ZipFile(resumed.result_bundle['archive']) as bundle:
                snapshot=json.loads(bundle.read('results.json'))
                identity=snapshot['calculations'][-1]['execution']['tool_provenance']
                self.assertEqual(identity['name'],tool['name'])
                self.assertEqual(len(identity['source_sha256']),64)
            installed=root/'packages'/tool['name']
            self.assertTrue((installed/'approval.json').is_file())
            self.assertTrue((installed/'tests.json').is_file())
            self.assertTrue((installed/'ready.json').is_file())
            with zipfile.ZipFile(installed.with_suffix('.zip')) as archive:
                self.assertIn(tool['name']+'/tool.py',archive.namelist())
                self.assertNotIn(tool['name']+'/ready.json',archive.namelist())
            self.assertIn('approved_change',model.contexts[2])
            receipt=json.loads((root/'session/changes'/second['assessment_id']/'approval.json').read_text(encoding='utf-8'))
            self.assertTrue(receipt['consumed']);self.assertEqual(receipt['model_calls_used'],3)
            fresh=ToolRegistry();ToolStore(root/'packages').load_into(fresh)
            self.assertEqual(fresh.call(tool['name'],{'degrees':[]}),{'h_index':0})
        self.assertEqual(core_fingerprint(),before)

    def test_model_cannot_self_approve_or_directly_install(self):
        with tempfile.TemporaryDirectory() as temporary:
            store=ToolStore(Path(temporary)/'packages');registry=ToolRegistry()
            with self.assertRaises(PermissionError):store.install(proposal(),registry)
            model=ScriptedModel([{'action':'extend','approved':True,'authorization':{'approved':True},'proposal':proposal()}])
            result=build_agent(model,registry,store).invoke({'question':'新增一个算法'})
            self.assertEqual(result['status'],'awaiting_assessment')
            self.assertFalse(store.directory.exists())

    def test_rejection_has_no_followup_model_call_or_code_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            model=ScriptedModel([{'action':'assess','request':request_for(proposal())}])
            session=ResearchSession(Path(temporary)/'session',Path(temporary)/'packages')
            state=session.ask('新增算法',model)
            session.reject(state['assessment_id'])
            self.assertEqual(session.state['status'],'extension_rejected')
            self.assertEqual(len(model.contexts),1)
            self.assertFalse(session.store.directory.exists())
            with self.assertRaises(ValueError):session.approve(state['assessment_id'],model)

    def test_composition_only_keeps_using_existing_tools(self):
        model=ScriptedModel([
            {'action':'assess','request':{'composition_possible':True}},
            {'action':'call','tool':'graph_invariants','arguments':{'kind':'cycle','n':5}},
            {'action':'call','tool':'graph_spectrum','arguments':{'kind':'cycle','n':5}},
            {'action':'final','answer':'现有结构与谱工具已完成，无需新包。'}])
        with tempfile.TemporaryDirectory() as temporary:
            store=ToolStore(Path(temporary)/'packages')
            result=build_agent(model,store=store).invoke({'question':'比较图的结构与谱'})
            self.assertEqual(result['status'],'tool_results_available')
            self.assertFalse(store.directory.exists())

    def test_wrapper_is_rejected_even_if_model_claimed_new_algorithm(self):
        old=json.loads((Path(__file__).resolve().parents[1]/'graph_research/data/density_proposal.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as temporary:
            store=ToolStore(temporary);registry=ToolRegistry()
            authorization=approve_for_tests(store,old,registry)
            with self.assertRaisesRegex(ValueError,'composition'):
                store.install(old,registry,authorization)
            self.assertNotIn(old['name'],registry.tools)

    def test_scope_changes_and_changed_core_require_reassessment(self):
        with tempfile.TemporaryDirectory() as temporary:
            registry=ToolRegistry();store=ToolStore(temporary);tool=proposal()
            auth=approve_for_tests(store,tool,registry)
            changed=copy.deepcopy(tool);changed['tests'][0]['expected']={'h_index':1}
            with self.assertRaises(PermissionError):store.install(changed,registry,auth)
            with patch('graph_research.tools.change_control.core_fingerprint',return_value='changed'):
                with self.assertRaises(PermissionError):store.install(tool,registry,auth)
            with self.assertRaises(ValueError):ToolStore(CORE/'new_tools')

    def test_cost_ranges_and_optional_user_rates(self):
        with tempfile.TemporaryDirectory() as temporary:
            controller=ChangeController(temporary,pricing={'input_per_million':1,'output_per_million':2,'currency':'TEST'})
            result=controller.assess(request_for(proposal()),ToolRegistry())
            estimate=result['estimate']
            self.assertEqual(estimate['money']['currency'],'TEST')
            self.assertGreater(estimate['money']['range'][1],estimate['money']['range'][0])
            self.assertEqual(estimate['kind'],'heuristic_not_measured')

    def test_approved_model_budget_cannot_be_silently_exceeded(self):
        request=request_for(proposal())
        model=ScriptedModel([{'action':'assess','request':request}]+[
            {'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':3}} for _ in range(5)])
        with tempfile.TemporaryDirectory() as temporary:
            session=ResearchSession(Path(temporary)/'session',Path(temporary)/'packages')
            state=session.ask('计算新指标',model)
            result=session.approve(state['assessment_id'],model)
            self.assertEqual(result['status'],'approval_or_budget_required')
            self.assertEqual(len(model.contexts),5) # one assessment + four approved calls
            self.assertFalse(session.store.directory.exists())

    def test_cli_can_reject_without_model_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            session=ResearchSession(Path(temporary)/'session',Path(temporary)/'packages')
            result=session.ask('新增算法',ScriptedModel([{'action':'assess','request':request_for(proposal())}]))
            process=subprocess.run([sys.executable,'-X','utf8','-m','graph_research','resume',str(session.directory),'--reject',result['assessment_id']],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(process.returncode,0,process.stderr)
            self.assertEqual(ResearchSession(session.directory).state['status'],'extension_rejected')

    def test_interrupted_model_preserves_completed_tool_results_for_resume(self):
        class Interrupted:
            calls=0
            def complete(self,messages):
                self.calls+=1
                if self.calls==1:return {'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':3}}
                raise RuntimeError('Simulated network interruption')
        with tempfile.TemporaryDirectory() as temporary:
            session=ResearchSession(Path(temporary)/'session',Path(temporary)/'packages')
            result=session.ask('查询图结构',Interrupted())
            self.assertEqual(result['status'],'execution_error')
            self.assertEqual(result['observations'][0].get('result',{}).get('diameter'),2,str(result['observations'])[:800])
            resumed=ResearchSession(session.directory)
            result=resumed.continue_run(ScriptedModel([{'action':'final','answer':'已保留结果，直径为2。'}]))
            self.assertEqual(result['status'],'tool_results_available')

    def test_changing_requirements_does_not_count_as_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            session=ResearchSession(Path(temporary)/'session',Path(temporary)/'packages')
            first=session.ask('新算法',ScriptedModel([{'action':'assess','request':request_for(proposal())}]))
            old=first['assessment_id']
            model=ScriptedModel([{'action':'clarify','questions':['新的输入规模是多少？']}])
            result=session.reply('改变输出和规模，请重新评估。',model)
            self.assertEqual(result['status'],'awaiting_clarification')
            self.assertEqual(result['assessment_id'],'')
            self.assertFalse((session.directory/'changes'/old/'approval.json').exists())
            self.assertFalse(session.store.directory.exists())


if __name__=='__main__':unittest.main()
