"""Graph identity and deterministic model workflows; fake models, real local tools."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from graph_research.assistant import ResearchSession
from graph_research.assistant.research_objects import add_graph,empty_objects,get_object,prepare_call,validate_objects
from graph_research.graph_input import parse_graph
from graph_research.tools import ToolRegistry
from tests.test_feature_workflow import ScriptedModel
from graph_research.assistant.planning import new_plan,validate_saved_plan
from graph_research.assistant.model_context import model_catalog,observations_context,inspect_data


class ResearchObjectsTests(unittest.TestCase):
    def test_versions_are_pinned_and_old_snapshots_are_immutable(self):
        graph=parse_graph('a b\nb c',vertices_text='a b c isolated')
        objects,ref=add_graph(empty_objects(),graph)
        objects,new=add_graph(objects,parse_graph('a b\nb c\nc a'),ref['id'])
        self.assertEqual(ref,{'id':'G1','version':1});self.assertEqual(new['version'],2)
        self.assertEqual(len(get_object(objects,ref)['document']['vertices']),4)
        changed=get_object(objects,ref);changed['document']['vertices'].clear()
        self.assertEqual(len(get_object(objects,ref)['document']['vertices']),4)
        with self.assertRaises(ValueError):get_object(objects,{'id':'G1','version':3})
        bad=copy.deepcopy(objects);bad['versions'][0]['document']['vertices'].clear()
        with self.assertRaises(ValueError):validate_objects(bad)

    def test_host_builds_parameters_and_rejects_conflicting_model_edges(self):
        objects,ref=add_graph(empty_objects(),parse_graph('b a',vertices_text='b a isolated'))
        definition=ToolRegistry().describe('graph_invariants')
        args,sources,refs=prepare_call(definition,{}, {'graph':ref},objects)
        self.assertEqual(args,{'kind':'edges','n':3,'edges':[[0,1]]})
        self.assertEqual(sources[0]['document']['vertices'],['b','a','isolated']);self.assertEqual(refs[0]['id'],'G1')
        with self.assertRaisesRegex(ValueError,'冲突'):prepare_call(definition,{'n':2},{'graph':ref},objects)
        with self.assertRaises(ValueError):prepare_call(definition,{}, {'left':ref},objects)

    def test_object_binding_is_durable_without_model_or_user_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=ResearchSession(Path(tmp)/'session',Path(tmp)/'packages')
            with patch('httpx.Client',side_effect=AssertionError('no model')):ref=session.bind_graph(parse_graph('a b'))
            self.assertFalse(session.state);self.assertEqual(session.turns,[])
            resumed=ResearchSession(session.directory)
            self.assertEqual(resumed.research_objects['active'],ref)
            self.assertEqual(get_object(resumed.research_objects,ref)['document']['vertices'],['a','b'])

    @unittest.skipUnless(os.name=='nt','Protected Windows workers')
    def test_graph_call_receipt_export_and_result_version_preserve_original_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=ResearchSession(Path(tmp)/'session',Path(tmp)/'packages')
            ref=session.bind_graph(parse_graph('a b\nb c'))
            model=ScriptedModel([
                {'action':'call','tool':'graph_edit','arguments':{'operation':'power','power':2},'graph_refs':{'graph':ref}},
                {'action':'call','tool':'graph_invariants','arguments':{},'graph_refs':{'graph':{'id':'G1','version':2}}},
                {'action':'final','answer':'图幂为三角形。'}])
            state=session.ask('求G1的平方并检查结构',model)
            self.assertEqual(state['status'],'tool_results_available')
            self.assertEqual(state['observations'][1]['result']['size'],3)
            self.assertEqual(state['observations'][0]['output_graph_ref'],{'id':'G1','version':2})
            self.assertEqual(get_object(session.research_objects,ref)['document']['edges'],parse_graph('a b\nb c').to_dict()['edges'])
            self.assertEqual(get_object(session.research_objects,{'id':'G1','version':2})['document']['vertices'],['a','b','c'])
            self.assertIsNone(session.export_error)
            with zipfile.ZipFile(session.result_bundle['archive']) as archive:
                data=json.loads(archive.read('results.json'))
                self.assertEqual(data['calculations'][0]['research_refs'][0]['version'],1)
                self.assertIn('research-objects.json',archive.namelist())
            session.state['observations'][0]['research_refs'][0]['version']=9
            with self.assertRaisesRegex(ValueError,'source'):session.export_results()

    def test_unbound_or_conflicting_call_never_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=ResearchSession(Path(tmp)/'session',Path(tmp)/'packages',auto_export=False)
            ref=session.bind_graph(parse_graph('a b'))
            model=ScriptedModel([
                {'action':'call','tool':'graph_invariants','arguments':{'n':3}},
                {'action':'call','tool':'graph_invariants','arguments':{'n':3},'graph_refs':{'graph':ref}},
                {'action':'final','answer':'参数需要修正。'}])
            with patch('graph_research.runtime.runner.run_tool',side_effect=AssertionError('must reject')):
                result=session.ask('计算这张图',model)
            self.assertTrue(all(not o['ok'] for o in result['observations']))


def sample_plan(ref=None,pause=False):
    binding={'graph_refs':{'graph':ref}} if ref else {}
    return {'title':'检查结构并计算谱','pause':pause,'steps':[
        {'id':'structure','description':'核对图结构','tool':'graph_invariants','arguments':{} if ref else {'kind':'path','n':3},**binding},
        {'id':'spectrum','description':'计算邻接谱','tool':'graph_spectrum','arguments':{} if ref else {'kind':'path','n':3},**binding}]}


class PlanTests(unittest.TestCase):
    def test_preflight_rejects_invalid_later_step_before_any_execution(self):
        registry=ToolRegistry();spec=sample_plan();spec['steps'][1]['arguments']['unknown']=4
        with self.assertRaises(ValueError):new_plan(spec,registry,empty_objects())
        spec=sample_plan();spec['steps'][1]['bindings']={'n':{'step':'future','path':['order']}}
        with self.assertRaises(ValueError):new_plan(spec,registry,empty_objects())
        spec=sample_plan();spec['steps'][1]['id']='structure'
        with self.assertRaises(ValueError):new_plan(spec,registry,empty_objects())
        spec=sample_plan();spec['steps'][1]['tool']='not_a_tool'
        with self.assertRaises((ValueError,KeyError)):new_plan(spec,registry,empty_objects())

    def test_plan_scope_cannot_be_changed_after_display(self):
        plan=new_plan(sample_plan(),ToolRegistry(),empty_objects());validate_saved_plan(plan)
        plan['steps'][0]['arguments']['n']=5
        with self.assertRaises(ValueError):validate_saved_plan(plan)

    def test_plan_cannot_exceed_delegated_budget_or_allowed_tools(self):
        from graph_research.assistant.task_control import TaskExecutionControl
        record={'policy':{'max_tool_calls':1,'allowed_tools':['graph_invariants']},'usage':{'tool_calls':0}}
        control=TaskExecutionControl(record,lambda _:None)
        with self.assertRaises(ValueError):new_plan(sample_plan(),ToolRegistry(),empty_objects(),control)
        record['policy']['max_tool_calls']=5
        with self.assertRaises(ValueError):new_plan(sample_plan(),ToolRegistry(),empty_objects(),control)

    @unittest.skipUnless(os.name=='nt','Protected Windows workers')
    def test_plan_visible_before_calculation_then_two_steps_use_only_two_model_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=ResearchSession(Path(tmp)/'session',Path(tmp)/'packages')
            ref=session.bind_graph(parse_graph('a b\nb c'));updates=[]
            model=ScriptedModel([{'action':'plan','plan':sample_plan(ref)},{'action':'final','answer':'结构与谱已计算。'}])
            result=session.ask('计算结构和谱',model,on_update=lambda s:updates.append(copy.deepcopy(s)))
            self.assertEqual(len(model.contexts),2);self.assertEqual(len(result['observations']),2)
            self.assertEqual(result['plan']['status'],'completed')
            prepared=next(s for s in updates if s.get('plan'))
            self.assertFalse(prepared.get('observations'));self.assertEqual(prepared['plan']['cursor'],0)
            with zipfile.ZipFile(session.result_bundle['archive']) as archive:
                data=json.loads(archive.read('results.json'));self.assertEqual(data['turns'][0]['plan']['status'],'completed')

    @unittest.skipUnless(os.name=='nt','Protected Windows workers')
    def test_review_persists_and_requires_current_plan_then_executes_without_replanning(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=ResearchSession(Path(tmp)/'session',Path(tmp)/'packages');session.set_plan_review(True)
            model=ScriptedModel([{'action':'plan','plan':sample_plan()}])
            result=session.ask('先看计划',model);plan=result['plan']
            self.assertEqual(result['status'],'awaiting_plan');self.assertFalse(result.get('observations'))
            resumed=ResearchSession(session.directory)
            with self.assertRaises(ValueError):resumed.accept_plan('stale',plan['scope_sha256'],model)
            model=ScriptedModel([{'action':'final','answer':'已执行。'}])
            result=resumed.accept_plan(plan['id'],plan['scope_sha256'],model)
            self.assertEqual(len(model.contexts),1);self.assertEqual(result['plan']['status'],'completed')

    def test_changed_requirements_invalidate_old_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=ResearchSession(Path(tmp)/'session',Path(tmp)/'packages',auto_export=False)
            result=session.ask('先看计划',ScriptedModel([{'action':'plan','plan':sample_plan(pause=True)}]));plan=result['plan']
            session.reply('改为只画图',ScriptedModel([{'action':'clarify','questions':['选择哪个图对象？']}]))
            with self.assertRaises(ValueError):session.accept_plan(plan['id'],plan['scope_sha256'],None)
            self.assertNotIn('plan',session.state)

    @unittest.skipUnless(os.name=='nt','Protected Windows workers')
    def test_result_binding_and_new_graph_version_are_resolved_without_model_copying(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=ResearchSession(Path(tmp)/'session',Path(tmp)/'packages');ref=session.bind_graph(parse_graph('a b\nb c'))
            plan={'title':'图幂后检查','steps':[
                {'id':'power','description':'求平方图','tool':'graph_edit','arguments':{'operation':'power'},'graph_refs':{'graph':ref}},
                {'id':'structure','description':'计算新图结构','tool':'graph_invariants','arguments':{},'graph_refs':{'graph':{'step':'power'}}},
                {'id':'compare','description':'用顶点数构造圈图','tool':'graph_invariants','arguments':{'kind':'cycle'},'independent_graph':True,'bindings':{'n':{'step':'structure','path':['order']}}}]}
            result=session.ask('按计划计算',ScriptedModel([{'action':'plan','plan':plan},{'action':'final','answer':'完成。'}]))
            detail=str({'plan_error':result['plan'].get('error'),'observations':[(o.get('tool'),o.get('ok'),o.get('error')) for o in result.get('observations',[])]})[:800]
            self.assertEqual(result['plan']['status'],'completed',detail);self.assertEqual(result['observations'][1]['result']['size'],3)
            self.assertEqual(result['observations'][2]['arguments']['n'],3)

    def test_missing_dependency_stops_plan_without_starting_later_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=ResearchSession(Path(tmp)/'session',Path(tmp)/'packages',auto_export=False)
            plan=sample_plan();plan['steps'][1]['arguments']={};plan['steps'][1]['bindings']={'n':{'step':'structure','path':['missing']}}
            def worker(*args,**kwargs):return {'result':{'order':3},'execution':{}}
            with patch('graph_research.runtime.runner.run_tool',side_effect=worker) as run:
                result=session.ask('试验缺失路径',ScriptedModel([{'action':'plan','plan':plan},{'action':'clarify','questions':['前序结果没有此字段，是否改用order？']}]))
            self.assertEqual(run.call_count,1);self.assertEqual(result['plan']['status'],'failed')
            self.assertEqual(result['status'],'awaiting_clarification')

    @unittest.skipUnless(os.name=='nt','Protected Windows workers')
    def test_interrupted_plan_resumes_at_next_step_without_repeating_completed_calls(self):
        from threading import Event
        with tempfile.TemporaryDirectory() as tmp:
            session=ResearchSession(Path(tmp)/'session',Path(tmp)/'packages');cancel=Event()
            def update(state):
                if len([o for o in state.get('observations',[]) if o.get('ok')])==1:cancel.set()
            state=session.ask('连续计算',ScriptedModel([{'action':'plan','plan':sample_plan()}]),cancel_event=cancel,on_update=update)
            self.assertEqual(state['status'],'cancelled');self.assertEqual(state['plan']['cursor'],1)
            first=state['observations'][0]['execution']['task_id']
            resumed=ResearchSession(session.directory)
            state=resumed.continue_run(ScriptedModel([{'action':'final','answer':'完成剩余步骤。'}]))
            self.assertEqual(state['plan']['status'],'completed');self.assertEqual(len(state['observations']),2)
            self.assertEqual(state['observations'][0]['execution']['task_id'],first)


class ContextTests(unittest.TestCase):
    def test_full_catalog_can_be_inspected_and_selected_schema_payload_is_smaller(self):
        registry=ToolRegistry();catalog=registry.catalog(detail='model')
        inventory,selected=model_catalog(catalog,'计算图的直径和邻接谱',[])
        self.assertEqual(len(inventory),len(catalog));self.assertEqual({t['name'] for t in inventory},{t['name'] for t in catalog});self.assertLessEqual(len(selected),6)
        self.assertLess(len(json.dumps([inventory,selected])),len(json.dumps(catalog)))
        name=next(t['name'] for t in catalog if t['name'] not in {s['name'] for s in selected})
        inspected=inspect_data({'tools':[name]},registry,set(registry.tools),empty_objects(),[])
        self.assertEqual(inspected['tools'][0]['parameters'],registry.tools[name].definition(detail='model')['parameters'])
        with self.assertRaises(ValueError):inspect_data({'tools':[name]},registry,{'graph_invariants'},empty_objects(),[])

    def test_large_result_is_explicit_summary_and_exact_path_read_is_local_only(self):
        registry=ToolRegistry();observations=[{'tool':'matrix_analysis','ok':True,'arguments':{},'result':{'matrix':[[i+j for j in range(128)] for i in range(128)]}}]
        snapshot=copy.deepcopy(observations);view=observations_context(observations)
        self.assertIn('_truncated',view[0]['result']['matrix'])
        result=inspect_data({'result':{'observation':0,'path':['matrix',127,127]}},registry,set(registry.tools),empty_objects(),observations)
        self.assertEqual(result['result'],254);self.assertEqual(observations,snapshot)
        with self.assertRaises((KeyError,ValueError)):inspect_data({'result':{'observation':0,'path':['missing']}},registry,set(registry.tools),empty_objects(),observations)

    def test_inspect_action_does_not_call_worker_or_install_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            session=ResearchSession(Path(tmp)/'session',Path(tmp)/'packages',auto_export=False)
            ref=session.bind_graph(parse_graph('a b'))
            model=ScriptedModel([{'action':'inspect','query':{'object':{'ref':ref,'path':['vertices']},'tools':['graph_invariants']}},{'action':'final','answer':'已查看对象与契约。'}])
            with patch('graph_research.runtime.runner.run_tool',side_effect=AssertionError('no computation')):session.ask('查看图对象',model)
            self.assertEqual(model.contexts[-1]['inspection']['object'],['a','b']);self.assertFalse(session.store.directory.exists())

    @unittest.skipUnless(os.name=='nt','Protected Windows workers')
    def test_both_http_protocols_parse_plan_and_run_real_local_tools_without_paid_api(self):
        import httpx
        from graph_research.assistant.model import ConfiguredModel
        from graph_research.assistant.model_config import validate_settings
        original=httpx.Client
        with tempfile.TemporaryDirectory() as tmp:
            for protocol in ('responses','chat_completions'):
                session=ResearchSession(Path(tmp)/protocol,Path(tmp)/'packages');decisions=[{'action':'plan','plan':sample_plan()},{'action':'final','answer':'已完成。'}];requests=[]
                def respond(request):
                    requests.append(request);decision=decisions.pop(0)
                    body={'output':[{'content':[{'type':'output_text','text':json.dumps(decision)}]}]} if protocol=='responses' else {'choices':[{'message':{'content':json.dumps(decision)}}]}
                    return httpx.Response(200,json=body)
                model=ConfiguredModel(validate_settings({'base_url':'https://model.invalid/v1','model':'fake','mode':protocol,'auth_required':False}))
                with patch('httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(respond),**kw)):
                    state=session.ask('核对结构和谱',model)
                self.assertEqual(len(requests),2);self.assertEqual(state['plan']['status'],'completed');self.assertEqual(len(state['observations']),2)


os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from graph_research.desktop.chat import ChatWindow
    from graph_research.desktop.model_service import ModelWorkspace
    import time
    QT=True
except ImportError:QT=False


@unittest.skipUnless(QT,'Optional Qt desktop')
class WorkflowDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def test_bound_object_choice_review_plan_and_explicit_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);window=ChatWindow(ModelWorkspace(root/'workspace',tool_directory=root/'packages'));window.show()
            def wait():
                deadline=time.monotonic()+30
                while window.thread is not None and time.monotonic()<deadline:self.app.processEvents();time.sleep(.01)
                self.assertIsNone(window.thread)
            try:
                with patch('httpx.Client',side_effect=AssertionError('no network')):window.insert_graph(parse_graph('a b\nb c'))
                self.assertEqual(window.object_choice.currentData(),{'id':'G1','version':1})
                window.review_plan.setChecked(True);self.assertTrue(window.workspace.session.review_plans)
                window.model=ScriptedModel([{'action':'plan','plan':sample_plan({'id':'G1','version':1})},{'action':'final','answer':'完成。'}])
                window.composer.setPlainText('计算这张图的结构和谱');window.send_message();wait()
                self.assertTrue(window.plan_panel.isVisible());self.assertIn('核对图结构',window.plan_detail.text())
                self.assertFalse(window.workspace.history());window.run_plan_button.click();wait()
                self.assertEqual(len(window.workspace.history()),2);self.assertFalse(window.plan_panel.isVisible())
                window.object_choice.setCurrentIndex(0);self.assertIsNone(window.workspace.session.research_objects['active'])
            finally:window.close();window.deleteLater();self.app.processEvents()


if __name__=='__main__':unittest.main()
