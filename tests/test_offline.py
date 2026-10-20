"""No-model navigation, data-only forms and protected scientific calculations."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import jsonschema
from graph_research.assistant import OfflineToolSession,ResearchSession,verify_bundle
from graph_research.assistant.offline import grouped_tools,parse_parameter,collect_arguments,read_arguments,run_offline_console,FormCancelled
from graph_research.tools import ToolRegistry
from graph_research.runtime.integrity import verify
from graph_research.assistant.onboarding import connect_menu
from graph_research.tools.input_guides import input_guide,show_input_guide,render_manual
from tests.test_feature_workflow import ScriptedModel


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def session(self,directory='manual'):
        return OfflineToolSession(self.root/directory,self.root/'packages',user_id='offline-user',memory_directory=self.root/'memory')

    def test_every_native_tool_is_reachable_once_with_reviewed_descriptions(self):
        registry=ToolRegistry();groups=grouped_tools(registry)
        names=[t['name'] for g in groups for t in g['tools']]
        self.assertEqual(len(names),43);self.assertEqual(set(names),set(registry.tools))
        self.assertEqual(len(groups),8)
        for group in groups:
            for tool in group['tools']:
                self.assertTrue(tool['documentation']['summary']);self.assertTrue(tool['documentation']['returns'])
                self.assertTrue(tool['parameters']['properties'] or tool['name']=='research_environment')

    def test_all_native_tools_have_valid_editable_example_forms(self):
        for definition in ToolRegistry().catalog():
            with self.subTest(tool=definition['name']):
                values=iter(['2','']+['']*len(definition['parameters']['properties']))
                arguments=collect_arguments(definition,input_fn=lambda _:next(values),print_fn=lambda _:None)
                jsonschema.validate(arguments,definition['parameters'])
                self.assertTrue(arguments or not definition['parameters']['properties'])

    def test_all_parameter_examples_round_trip_through_the_real_input_parser(self):
        for definition in ToolRegistry().catalog():
            untouched=json.dumps(definition,sort_keys=True,ensure_ascii=False)
            guide=input_guide(definition)
            self.assertEqual(len(guide['fields']),len(definition['parameters']['properties']))
            self.assertTrue(guide['examples'])
            for field in guide['fields']:
                with self.subTest(tool=definition['name'],field=field['name']):
                    self.assertIsNotNone(field['input_example'])
                    parsed=parse_parameter(field['input_example'],definition['parameters']['properties'][field['name']])
                    self.assertEqual(parsed,field['example'])
                    self.assertTrue(field['format']);self.assertTrue(field['omission'])
            for example in guide['examples']:jsonschema.validate(example['arguments'],definition['parameters'])
            self.assertEqual(json.dumps(definition,sort_keys=True,ensure_ascii=False),untouched)

    def test_manual_and_tool_selection_help_include_complete_examples_and_real_limits(self):
        definitions=ToolRegistry().catalog();manual=render_manual(definitions)
        self.assertEqual(manual.count('\n## '),43)
        for definition in definitions:
            lines=[];show_input_guide(definition,lines.append)
            sample=definition['documentation']['examples'][0]['arguments']
            self.assertIn(json.dumps(sample,ensure_ascii=False,separators=(',',':')),'\n'.join(lines))
            for field in definition['parameters']['properties']:self.assertTrue(any(line.startswith(field+'：') for line in lines))
        polynomial=next(d for d in definitions if d['name']=='graph_characteristic_polynomial')
        self.assertTrue(input_guide(polynomial)['limits'])
        self.assertIn('工具限制',manual)

    def test_per_field_help_never_fills_a_required_value_from_the_example(self):
        definition=ToolRegistry().describe('matrix_analysis');lines=[]
        answers=iter(['1','/帮助','','[[1,2],[3,4]]'])
        result=collect_arguments(definition,input_fn=lambda _:next(answers),print_fn=lines.append)
        self.assertEqual(result,{'matrix':[[1,2],[3,4]]})
        self.assertTrue(any('请填写必填项' in line for line in lines))
        self.assertGreaterEqual(sum('当前参数输入例子' in line for line in lines),2)

    def test_describe_is_read_only_without_model_or_session(self):
        from graph_research.assistant.offline import offline_command
        lines=[]
        with patch('graph_research.assistant.offline.OfflineToolSession',side_effect=AssertionError('No session')),patch(
            'graph_research.assistant.offline.run_tool',side_effect=AssertionError('No calculation')):
            self.assertEqual(offline_command(['--describe','graph_invariants'],print_fn=lines.append),0)
        self.assertTrue(any('完整参数输入例子' in line for line in lines))

    def test_data_parser_supports_safe_lists_rows_enums_booleans_and_fractions(self):
        registry=ToolRegistry()
        self.assertEqual(parse_parameter('0,1;1,2',registry.tools['graph_invariants'].parameters['properties']['edges']),[[0,1],[1,2]])
        self.assertEqual(parse_parameter('1，2，3',{'type':'array','items':{'type':'integer'}}),[1,2,3])
        self.assertEqual(parse_parameter('0,1',registry.tools['matrix_analysis'].parameters['properties']['matrix']),[[0,1]])
        self.assertEqual(parse_parameter('6',registry.tools['graph_invariants'].parameters['properties']['kind']),'edges')
        self.assertIs(parse_parameter('否',{'type':'boolean'}),False)
        field=registry.tools['hypergraph_tensor_charpoly'].parameters['properties']['alpha']
        self.assertEqual(parse_parameter('1/3',field),'1/3')
        for text in ('NaN','Infinity','__import__("os").system("bad")','[1,]'):
            with self.assertRaises(ValueError):parse_parameter(text,{'type':'array','items':{'type':'number'}})
        with self.assertRaises(ValueError):parse_parameter('true',{'type':'integer'})
        with self.assertRaises(ValueError):parse_parameter('-1',{'type':'integer','minimum':0})

    def test_json_file_import_rejects_duplicates_nonfinite_oversize_and_nonobjects(self):
        path=self.root/'args.json'
        path.write_text('{"kind":"path","n":3}',encoding='utf-8-sig')
        self.assertEqual(read_arguments(path),{'kind':'path','n':3})
        for raw in ('{"n":2,"n":3}','{"n":NaN}','[]','x'*(256*1024+1)):
            path.write_text(raw,encoding='utf-8')
            with self.assertRaises(ValueError):read_arguments(path)

    def test_bad_or_cancelled_form_never_starts_a_worker(self):
        definition=ToolRegistry().describe('graph_invariants');lines=[]
        values=iter(['4','{"n":0}','4','{"n":3,"unknown":1}','0'])
        with patch('graph_research.assistant.offline.run_tool',side_effect=AssertionError('No execution')):
            with self.assertRaises(FormCancelled):collect_arguments(definition,input_fn=lambda _:next(values),print_fn=lines.append)
        self.assertTrue(any('最小值' in line for line in lines));self.assertTrue(any('未定义字段' in line for line in lines))

    def test_invalid_tool_arguments_or_unavailable_dependency_do_not_change_saved_state(self):
        session=self.session()
        with patch('graph_research.assistant.offline.run_tool',side_effect=AssertionError('No execution')):
            with self.assertRaises(jsonschema.ValidationError):session.call_tool('graph_invariants',{'n':0})
            with self.assertRaises(ValueError):session.call_tool('unregistered_function',{})
            with patch('graph_research.tools.capabilities.find_spec',return_value=None):
                with self.assertRaises(ValueError):session.call_tool('hypergraph_plot',{'edges':[[0,1]]})
        self.assertFalse((session.directory/'session.json').exists());self.assertFalse(session.turns)

    def test_multiple_real_calls_rendering_memory_restart_and_bundle_without_model(self):
        session=self.session();before=verify()['manifest_sha256']
        with patch('graph_research.assistant.model.ConfiguredModel',side_effect=AssertionError('No model')):
            self.assertEqual(session.call_tool('graph_invariants',{'kind':'path','n':3})['result']['diameter'],2)
            self.assertEqual(session.call_tool('matrix_analysis',{'matrix':[[0,1],[1,0]]})['result']['rank'],2)
            drawn=session.call_tool('hypergraph_tikz',{'edges':[[0,1],[1,2,3]]})
        self.assertTrue(drawn['ok']);self.assertTrue(drawn['result']['files'])
        self.assertTrue(verify_bundle(session.result_bundle['archive'],session.result_bundle['sha256'])['ok'])
        self.assertEqual(session.result_bundle['summary']['verified_calls'],3)
        with zipfile.ZipFile(session.result_bundle['archive']) as bundle:
            self.assertTrue(any(name.endswith('.tex') for name in bundle.namelist()))
        restarted=self.session()
        self.assertEqual(len(restarted.turns),3)
        self.assertEqual(len(restarted.state['observations']),3)
        self.assertEqual(restarted.task_context['interaction_mode'],'offline_tools')
        self.assertEqual(len(restarted.memory.context('offline-user')['frequently_used_tools']),3)
        self.assertEqual(verify()['manifest_sha256'],before)

    def test_mathematical_failure_is_recorded_without_losing_earlier_results(self):
        session=self.session()
        self.assertTrue(session.call_tool('graph_invariants',{'kind':'path','n':3})['ok'])
        failed=session.call_tool('graph_invariants',{'kind':'edges','n':2,'edges':[[0,2]]})
        self.assertFalse(failed['ok']);self.assertEqual(session.state['status'],'tool_execution_failed')
        self.assertEqual(session.result_bundle['summary']['verified_calls'],1)
        self.assertEqual(session.result_bundle['summary']['record_status'],'partial')
        self.assertTrue(verify_bundle(session.result_bundle['archive'],session.result_bundle['sha256'])['ok'])

    def test_category_console_runs_two_calls_with_guided_parameters_and_exports(self):
        session=self.session();values=iter([
            '普通图','graph_invariants','2','','','4','','1','0',
            '矩阵','matrix_analysis','1','0,1;1,0','1','0','r','e','0',
        ]);lines=[]
        run_offline_console(session,input_fn=lambda _:next(values),print_fn=lines.append)
        self.assertEqual(len(session.state['observations']),2)
        for observation in session.state['observations']:self.assertTrue(observation.get('ok'),observation)
        self.assertEqual(session.state['observations'][0]['result']['diameter'],3)
        self.assertEqual(session.state['observations'][1]['result']['rank'],2)
        self.assertEqual(session.result_bundle['summary']['verified_calls'],2)
        self.assertTrue(any('模型调用0次' in line for line in lines))

    def test_model_session_cannot_be_reused_as_offline_workspace(self):
        directory=self.root/'model-session';session=ResearchSession(directory,self.root/'packages')
        session.ask('分析问题',ScriptedModel([{'action':'final','answer':'没有计算'}]))
        saved=hashlib.sha256((directory/'session.json').read_bytes()).hexdigest()
        with self.assertRaises(ValueError):OfflineToolSession(directory,self.root/'packages')
        self.assertEqual(hashlib.sha256((directory/'session.json').read_bytes()).hexdigest(),saved)

    def test_offline_session_cannot_silently_switch_to_model_or_change_its_records(self):
        from graph_research.assistant.onboarding import chat_command
        manual=self.session();manual.call_tool('graph_invariants',{'n':3})
        file=manual.directory/'session.json';saved=file.read_bytes()
        regular=ResearchSession(manual.directory)
        with self.assertRaises(ValueError):regular.reply('改为自动研究',ScriptedModel([]))
        self.assertEqual(file.read_bytes(),saved)
        with patch('graph_research.assistant.onboarding.load_settings',side_effect=AssertionError('No model settings')):
            with self.assertRaises(ValueError):chat_command(['--session',str(manual.directory)])
        self.assertEqual(file.read_bytes(),saved)

    def test_new_menu_entry_never_loads_model_settings(self):
        values=iter(['5','0','0']);lines=[]
        with patch('pathlib.Path.cwd',return_value=self.root),patch('graph_research.assistant.onboarding.load_settings',side_effect=AssertionError('No settings')):
            self.assertEqual(connect_menu(input_fn=lambda _:next(values),print_fn=lines.append),0)
        self.assertTrue(any('无API工具模式' in line for line in lines))

    def test_cli_uses_no_model_configuration_sdk_sage_or_parent_agent(self):
        root=Path(__file__).resolve().parents[1];directory=self.root/'cli'
        code="""
import builtins,sys,os
sys.path.insert(0,ROOT)
real=builtins.__import__
def guarded(name,*args,**kwargs):
    if name.split('.')[0] in ('httpx','langgraph','sage') or name.startswith(('graph_research.assistant.model','graph_research.assistant.subagent','graph_research.assistant.host_events')):
        raise AssertionError('Offline mode imported '+name)
    return real(name,*args,**kwargs)
builtins.__import__=guarded
os.environ['RESEARCH_BASE_URL']='intentionally invalid configuration'
from graph_research.cli import main
sys.argv=['graph-research','offline','--session',DIRECTORY,'--results-root',os.path.join(DIRECTORY,'result-center')]
raise SystemExit(main())
""".replace('ROOT',repr(str(root))).replace('DIRECTORY',repr(str(directory)))
        # Select a category/tool, paste data, confirm once, then exit.
        answers='普通图\ngraph_invariants\n4\n{"kind":"path","n":3}\n1\n0\n0\n'
        process=subprocess.run([sys.executable,'-I','-X','utf8','-c',code],input=answers,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(process.returncode,0,process.stderr)
        loaded=OfflineToolSession(directory,self.root/'packages')
        self.assertEqual(loaded.state['observations'][0]['result']['diameter'],2)
        self.assertNotIn('密钥隐藏输入',process.stdout)
        self.assertFalse(list(directory.rglob('.host-events.key')))


if __name__=='__main__':unittest.main()
