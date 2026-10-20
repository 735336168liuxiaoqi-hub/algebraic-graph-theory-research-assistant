"""Load only an extracted installed wheel package, then block Sage/process use."""
import builtins
from contextlib import contextmanager
import json
import os
import re
import shutil
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import patch

target=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(target))
import graph_research
from graph_research.workflow import build_workflow
from graph_research.registry import ToolRegistry
from graph_research.runtime.storage import io_path


@contextmanager
def verification_directory():
    folder=Path(tempfile.mkdtemp()).resolve()
    try:yield str(folder)
    finally:
        # Delete only this fresh synthetic directory, using native long paths.
        if folder.parent!=Path(tempfile.gettempdir()).resolve():raise RuntimeError('Unexpected verification cleanup root')
        shutil.rmtree(io_path(folder))

assert Path(graph_research.__file__).resolve().is_relative_to(target)
reference=json.loads((Path(graph_research.__file__).parent/"data/sage_reference.json").read_text(encoding="utf-8"))
real_import=builtins.__import__
def no_sage(name,*args,**kwargs):
    if name=="sage" or name.startswith("sage."): raise AssertionError("Sage dependency detected")
    return real_import(name,*args,**kwargs)

with patch("builtins.__import__",side_effect=no_sage),patch("subprocess.run",side_effect=AssertionError("External process dependency")):
    result=build_workflow().invoke({"task":reference["task"]})
    assert result["status"]=="complete"
    assert all(abs(row["result"]["rho"]-rho)<1e-8 for row,rho in zip(result["rows"],reference["rho_values"]))
    tools=ToolRegistry()
    from graph_research.graph_input import parse_graph,GraphLibrary
    from graph_research.graph_input.adapters import graph_patch
    input_graph=parse_graph('a b\nb c',vertices_text='a b c isolated')
    assert input_graph.order==4 and graph_patch(input_graph,tools.describe('graph_invariants'))['patch']['n']==4
    assert tools.call("graph_invariants",{"kind":"path","n":5})["diameter"]==4
    assert 'lookup_legacy' not in tools.tools
    assert not (Path(graph_research.__file__).parent/'data/migration_catalog.json').exists()
    quotient=tools.call("hypergraph_quotient_spectrum",{"edges":[[0,1,2],[2,3,4],[4,5,6]],"alpha":0.3})
    assert quotient["absolute_difference"]<1e-8
    assert tools.call("graph_construction",{"family":"theta","lengths":[2,2,2]})["size"]==6
    assert tools.call("graph_symmetry",{"kind":"star","n":5})["equitable"]
    recurrence=tools.call('linear_recurrence',{'coefficients':[-1,-1,1],'initial_values':[0,1],'terms':8})
    assert recurrence['recurrence_verified'] and recurrence['terms']==['0','1','1','2','3','5','8','13']
    integers=tools.call('integer_linear_system',{'matrix':[[2,4]],'rhs':[6]})
    assert integers['status']=='solved' and integers['kernel_verified']
    assert tools.call('integer_linear_system',{'matrix':[[2]],'rhs':[1]})['status']=='no_solution'
    assert tools.call('generate_hypergraph',{'family':'gee','m':2,'k':3,'left_lengths':[1],'right_lengths':[1]})['size']==4
    endpoint=tools.call('hypergraph_spectrum',{'edges':[[0,1,2]],'alpha':1,'vertex_degrees':[1,7,2]})
    assert endpoint['rho']==7 and endpoint['perron_vector'] is None and endpoint['verification']['passed']
    reduced=tools.call('hypergraph_spectrum',{'edges':[[0,1,2],[2,3,4]],'alpha':.9,'method':'auto'})
    from graph_research.hypergraphs.spectral_certificate import verify_spectrum_certificate
    assert verify_spectrum_certificate([[0,1,2],[2,3,4]],reduced)['passed']
    nni=tools.call('hypergraph_spectrum',{'edges':[[0,1,2],[2,3,4],[4,5,6]],'alpha':.999,'method':'newton_noda','weighted_incidence':True})
    assert nni['verification']['passed'] and nni['method']=='newton_noda'
    assert nni['weighted_incidence_computation'].startswith('logsumexp')
    assert all(abs(sum(row)-1)<1e-9 for row in nni['weighted_incidence'])
    from graph_research.schematics import template,expand,to_tikz,to_svg
    diagram=template('H');assert '$P_{a}$' in to_tikz(diagram) and '<svg' in to_svg(diagram)
    concrete=expand(diagram,{'k':4,'a':1,'b':2,'c':3,'d':4});assert concrete.size==11
    expanded=tools.call('hypergraph_schematic',{'diagram':template('E').to_dict(),'operation':'expand','parameters':{'k':3,'a':1,'b':2,'c':3}})
    assert tools.call('hypergraph_spectrum',{'edges':expanded['hypergraph_spec']['edges'],'alpha':.3})['verification']['passed']
    replacement=tools.call('graph_edit',{'operation':'replace_edge','n':3,'edit_edges':[[0,1]],'replacement':{'kind':'path','n':3},'endpoints':[0,2]})
    assert replacement['order']==4 and replacement['size']==3
    action=tools.call('exact_matrix_operation',{'matrix':[[1,2],[3,4]],'operation':'elementary','actions':[{'kind':'add_row','target':1,'source':0,'factor':-3}]})
    assert action['matrix']==[['1','2'],['0','-2']]
    assert tools.call('combinatorial_calculation',{'operation':'cycle_index','generators':[[1,0,2],[1,2,0]]})['group_order']==6
    assert tools.call('hypergraph_transform',{'edges':[[0,1,2]],'operation':'attach_star','roots':[0,1],'count':2})['size']==3
    for name in ('weighted_graph_spectrum','graph_recipe','hypergraph_path_analysis','graph_batch_study','symbolic_analysis','block_matrix_analysis','graph_class_certificate','graph_energy_study','research_environment'):
        for example in tools.describe(name)['documentation']['examples']:
            research_result=tools.call(name,example['arguments'])
            assert set(example['expected_keys'])<=set(research_result)
    from graph_research import Hypergraph
    assert Hypergraph([[0,1,2]]).characteristic_polynomial().degree()==12

# Run this verification from a cwd outside the source checkout package. The
# child worker resolves its package through the explicitly installed wheel.
with patch.dict(os.environ,{"PYTHONPATH":str(target)}):
    exact=tools.call("hypergraph_tensor_charpoly",{"edges":[[0,1,2]]})
    assert exact["degree"]==12
    from graph_research.assistant import ResearchSession,UserMemoryStore
    with verification_directory() as temporary:
        root=Path(temporary)
        memory=UserMemoryStore(root/'memory')
        memory.set_preference('wheel-alice','language','en')
        class OfflineModel:
            def __init__(self):self.contexts=[]
            def complete(self,messages):
                self.contexts.append(json.loads(messages[1]['content']))
                return {'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':4}} if len(self.contexts)==1 else {'action':'final','answer':'Diameter is 3.'}
        model=OfflineModel()
        first=ResearchSession(root/'first',root/'packages',user_id='wheel-alice',memory_directory=root/'memory')
        answer=first.ask('Find the diameter of P4',model)
        assert answer['status']=='tool_results_available'
        assert answer['observations'][0]['result']['diameter']==3
        from graph_research.assistant import verify_bundle
        assert first.result_bundle is not None and first.export_error is None
        verified_results=verify_bundle(first.result_bundle['archive'],first.result_bundle['sha256'])
        assert verified_results['summary']['verified_calls']==1
        assert verified_results['summary']['turn_count']==1
        assert model.contexts[0]['user_memory']['preferences']=={'language':'en'}
        second=ResearchSession(root/'second',root/'packages',user_id='wheel-alice',memory_directory=root/'memory')
        assert second.memory.context('wheel-alice')['frequently_used_tools']==[{'tool':'graph_invariants','successful_calls':1}]
        assert second.memory.context('wheel-bob')=={'preferences':{},'frequently_used_tools':[]}
        memory.set_enabled('wheel-alice',False)
        assert second.memory.context('wheel-alice')=={'preferences':{},'frequently_used_tools':[]}
        memory.clear('wheel-alice')
        assert memory.profile('wheel-alice')['preferences']=={}
        from graph_research.runtime.runner import run_worker,run_tool
        from graph_research.runtime.integrity import verify,backup,restore
        canary=root/'canary';canary.write_text('preserve',encoding='utf-8')
        assert run_worker('probe',{'operation':'native_write','path':str(canary)},directory=root/'tasks')['write_denied_by_os']
        assert canary.read_text()=='preserve'
        assert run_tool('graph_tikz',{'edges':[[0,1],[1,2]]},root/'packages',directory=root/'tasks')['order']==3
        snapshot=backup(root/'core.zip')
        assert restore(snapshot['archive'],snapshot['sha256'],root/'recovered')['verified']
        assert verify()['ok']
        from graph_research.assistant.model_config import save_configuration,configuration_status
        from graph_research.assistant.model import ConfiguredModel
        import httpx
        config=root/'public-model.json'
        settings,_=save_configuration({'base_url':'https://example.invalid/v1','model':'wheel-test','mode':'chat_completions'},config)
        environment={k:v for k,v in os.environ.items() if not k.startswith('RESEARCH_')}
        environment['RESEARCH_API_KEY']='WHEEL_OFFLINE_FAKE_KEY'
        def handle_model_probe(request):
            body=json.loads(request.content)
            assert body['max_tokens']==128 and 'tools' not in body
            return httpx.Response(200,json={'choices':[{'message':{'content':'{"action":"final","answer":"连接成功"}'}}]})
        client=httpx.Client(transport=httpx.MockTransport(handle_model_probe))
        with patch.dict(os.environ,environment,clear=True),patch('graph_research.assistant.model.httpx.Client',return_value=client):
            assert configuration_status(config)['connection_tested'] is False
            assert ConfiguredModel(settings).test_connection()['structured_json_verified']
        assert 'WHEEL_OFFLINE_FAKE_KEY' not in config.read_text(encoding='utf-8')
        from graph_research.assistant import create_subagent,subagent_contracts,subagent_tool_definition
        import jsonschema
        direct,_=create_subagent(root/'subagent',user_id='wheel-parent')
        task={'version':1,'request_id':'wheel-direct','objective':'计算P3的直径','execution':{'mode':'tools','steps':[
            {'id':'diameter','tool':'graph_invariants','arguments':{'kind':'path','n':3}}]}}
        response=direct.submit(task)
        assert response['status']=='completed' and response['results'][0]['data']['diameter']==2
        assert response['budget']['used']=={'model_calls':0,'tool_calls':1}
        replayed=direct.submit(task)
        stable=lambda value:{**value,'summary':{k:v for k,v in value['summary'].items() if k!='reuse'}}
        assert stable(replayed)==stable(response)
        assert replayed['summary']['reuse']=={**response['summary']['reuse'],'task_reused':1}
        from graph_research.assistant.experience import ExperienceStore,search_experiences
        from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
        experience_store=ExperienceStore(root/'subagent/memory')
        candidates=search_experiences(root/'subagent/memory','wheel-parent',reviewed_only=False,status='candidate')['records']
        assert len(candidates)==1
        case=candidates[0]
        experience_store.review('wheel-parent',case['id'],case['content_sha256'],'approved','合成安装包验收，模拟用户审阅')
        memory_reader=MCPResearchRuntime(HostConfiguration(str(root/'subagent'),'wheel-parent'))
        read_case=memory_reader.call('research_experience',{'id':case['id']})
        assert read_case['records'][0]['source_state']=='verified' and read_case['records'][0]['current_core_matches']
        assert memory_reader.call('research_memory',{})['experience_counts']['approved']==1
        assert memory_reader.call('research_experience',{'id':case['id'],'decision':'approve'})['status']=='protocol_error'
        from graph_research.assistant.development import from_host
        from graph_research.tools.library import ToolLibrary
        generated=json.loads((target/'graph_research/data/h_index_proposal.json').read_text(encoding='utf-8'))
        development_request={'name':generated['name'],'goal':'计算度序列h指数','requirements':'最多128项非负整数，空序列为0',
            'checked_tools':[{'tool':'graph_invariants','reason':'提供度序列，不含h指数算法'}],'composition_possible':False,
            'why_not_composition':'需要按h指数定义扫描序列','new_algorithm':'排序后逐项比较h阈值','parameters':generated['parameters'],
            'acceptance_tests':[{**case,'basis':'按h指数定义手工复核的小例'} for case in generated['tests']],'complexity':'small',
            'library_metadata':{'title':'度序列h指数','preconditions':['非负整数序列'],'limitations':['仅通过所列验收样例']}}
        growth=from_host(root/'growth','wheel-growth');request=growth.assess('wheel-growth',development_request)
        assert request['status']=='waiting_for_approval'
        try:growth.submit(request['id'],'one',generated)
        except PermissionError:pass
        else:raise AssertionError('Unapproved development was executed')
        growth.approve(request['id'],request['assessment']['scope_sha256'])  # synthetic trusted-user fixture
        growth.submit(request['id'],'one',generated)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            developed=growth.get(request['id'],2)
            if not developed['active']:break
        assert developed['status']=='installed' and developed['budget']['local_model_calls']==0
        library=ToolLibrary(growth.store.directory);entry=library.catalog()['records'][0]
        assert entry['version']==developed['result']['package_id'] and entry['state']=='enabled'
        library.select(entry['name'],entry['version'],enabled=False)
        probe=ToolRegistry();growth.store.load_into(probe);assert entry['name'] not in probe.tools
        library.select(entry['name'],entry['version'])
        from graph_research.runtime.runner import run_tool
        hvalue=run_tool(entry['name'],{'degrees':[3,2,2,1]},growth.store.directory,directory=root/'growth-runs',include_receipt=True)
        assert hvalue['result']=={'h_index':2}
        actual_receipt=json.loads((Path(hvalue['execution']['directory'])/'execution.json').read_text(encoding='utf-8'))
        assert actual_receipt['tool_provenance']['package_id']==entry['version']
        installed_metadata=json.loads((Path(developed['result']['path'])/'tool.json').read_text(encoding='utf-8'))
        assert all(row['execution_evidence']['protection']=='windows_low_integrity_and_job' for row in installed_metadata['test_results'])
        batch_task={'version':1,'request_id':'wheel-batch','objective':'批量核验P3/P4的基本性质',
            'execution':{'mode':'batch','batch':{'cases':[{'id':'P3','inputs':{'n':3}},{'id':'P4','inputs':{'n':4}}],
                'steps':[{'id':'structure','tool':'graph_invariants','arguments':{'kind':'path'},'bindings':{'n':{'case':['n']}}}],
                'outputs':{'diameter':{'step':'structure','path':['diameter']}}}},
            'constraints':{'max_model_calls':0,'max_tool_calls':2,'allow_extensions':False}}
        batched=direct.submit(batch_task)
        assert batched['status']=='completed' and batched['budget']['used']=={'model_calls':0,'tool_calls':2}
        assert [row['outputs']['diameter']['value'] for row in batched['summary']['batch']['rows']]==[2,3]
        assert verify_bundle(batched['artifacts'][0]['path'],batched['artifacts'][0]['sha256'])['ok']
        import zipfile
        with zipfile.ZipFile(batched['artifacts'][0]['path']) as archive:
            assert {'batch-summary.json','batch-results.csv','batch-plan.json'}<=set(archive.namelist())
        jsonschema.validate(response,subagent_contracts()['task_result'])
        assert subagent_tool_definition()['name']=='graph_research_subagent'
        class PauseModel:
            calls=0
            def complete(self,messages):
                self.calls+=1
                return {'action':'clarify','questions':['确认P3？']} if self.calls==1 else {'action':'final','answer':'已收到用户回复，未执行新计算。'}
        paused_model=PauseModel()
        parent,portal=create_subagent(root/'subagent',user_id='wheel-parent',model_factory=lambda:paused_model)
        waiting=parent.submit({'version':1,'request_id':'wheel-pause','objective':'确认问题','execution':{'mode':'agent'}})
        assert waiting['status']=='waiting_for_user'
        assert parent.dispatch({'operation':'approve','task_id':waiting['task_id'],'approved':True})['status']=='protocol_error'
        p=waiting['interaction'];event=portal.answer(waiting['task_id'],p['interaction_id'],waiting['revision'],'确认。')
        parent,_=create_subagent(root/'subagent',user_id='wheel-parent',model_factory=lambda:paused_model)
        resumed=parent.resume(waiting['task_id'],event['event_id'])
        assert resumed['status']=='analysis_only' and paused_model.calls==2
        assert parent.resume(waiting['task_id'],event['event_id'])==resumed and paused_model.calls==2
        from graph_research.assistant.onboarding import run_console
        independent=ResearchSession(root/'independent-console',root/'independent-packages')
        independent_model=OfflineModel();answers=iter(['计算P4的直径','/退出']);lines=[]
        with patch('graph_research.assistant.host_events.HostEventStore',side_effect=AssertionError('No parent required')):
            run_console(independent,model_factory=lambda:independent_model,input_fn=lambda _:next(answers),print_fn=lines.append)
        assert independent.state['observations'][0]['result']['diameter']==3
        assert independent.result_bundle['summary']['verified_calls']==1
        assert any('独立模式，无需主agent' in line for line in lines)
        assert not (independent.directory/'.host-events.key').exists()
        from graph_research.assistant import OfflineToolSession
        from graph_research.assistant.offline import run_offline_console,grouped_tools
        manual=OfflineToolSession(root/'manual',root/'manual-packages')
        choices=iter(['普通图','graph_invariants','4','{"kind":"path","n":3}','1','0','0'])
        with patch('graph_research.assistant.model.ConfiguredModel',side_effect=AssertionError('No model API')):
            run_offline_console(manual,input_fn=lambda _:next(choices),print_fn=lambda _:None)
        assert manual.state['observations'][0]['result']['diameter']==2
        assert manual.result_bundle['summary']['verified_calls']==1
        assert sum(len(g['tools']) for g in grouped_tools(manual._registry()))==43
        from graph_research.tools.input_guides import input_guide,show_input_guide
        from graph_research.assistant.offline import parse_parameter
        field_count=0
        for definition in tools.catalog():
            guide=input_guide(definition)
            for field in guide['fields']:
                assert parse_parameter(field['input_example'],definition['parameters']['properties'][field['name']])==field['example']
                field_count+=1
        assert field_count==238
        input_help=[];show_input_guide(tools.describe('graph_invariants'),input_help.append)
        assert any('完整参数输入例子' in line for line in input_help)
        assert verify_bundle(manual.result_bundle['archive'],manual.result_bundle['sha256'])['ok']
        before_view=len(manual.state['observations'])
        viewed=manual.view_results()
        viewed_html=Path(viewed['html']).read_text(encoding='utf-8')
        assert 'result-card' in viewed_html and '图的基本信息' in viewed_html and 'script-src' in viewed_html
        assert len(manual.state['observations'])==before_view
        os.environ['QT_QPA_PLATFORM']='offscreen'
        from PySide6.QtCore import Qt
        from graph_research.desktop.localization import parameter_title
        from PySide6.QtWidgets import QApplication
        from graph_research.desktop.app import DesktopWindow
        from graph_research.desktop.service import DesktopWorkspace
        qt=QApplication.instance() or QApplication([]);qt.setQuitOnLastWindowClosed(False)
        from PySide6.QtCore import QPointF
        from PySide6.QtTest import QTest
        from graph_research.schematics import SchematicDocument
        from graph_research.schematics.geometry import primitives
        from graph_research.desktop.schematic import SchematicDialog
        paper_scene=SchematicDocument({'vertices':[{'id':0,'xy':[0,0]},{'id':1,'xy':[0,2]}],
                                        'edges':[{'vertices':[0,1],'vertex_ellipsis':True}]})
        paper=SchematicDialog(paper_scene);paper.show();qt.processEvents();canvas=paper.canvas
        canvas.mode.setCurrentIndex(canvas.mode.findData('edge'));qt.processEvents()
        assert canvas.core_settings.isVisible() and not canvas.path_settings.isVisible() and not canvas.apply_button.isEnabled()
        geometry=primitives(paper_scene);dots=[p for p in geometry if p.get('role')=='dot']
        assert len(dots)==3 and all(abs(p['xy'][0])<1e-12 for p in dots)
        outline=next(p for p in geometry if p['kind']=='path' and p['stroke']!='none')
        x,y=outline['commands'][1][-2:];point=canvas.view.mapFromScene(QPointF(x*160,-y*160))
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=point);qt.processEvents();assert canvas.selected_core==0
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=point);qt.processEvents();assert canvas.selected_core is None
        scale=canvas.view.transform().m11();canvas.add_vertex(2,[3,0]);qt.processEvents();assert canvas.view.transform().m11()==scale
        code=to_tikz(paper_scene);assert code.rfind(r'\path[draw=none,fill=grsfill]')<code.find(r'\draw[')
        paper.close();paper.deleteLater();qt.processEvents()
        desktop=DesktopWindow(DesktopWorkspace(root/'native-desktop',session_directory=manual.directory))
        assert len(desktop.items)==37 and "hypergraph_editor" not in desktop.items
        for tool_name in desktop.items:
            desktop.select_tool(tool_name);desktop.apply_example()
            jsonschema.validate(desktop.collect_arguments(),desktop.definition['parameters'])
            for parameter,field in desktop.fields.items():
                assert re.search(r'[\u4e00-\u9fff]',parameter_title(desktop.definition,parameter))
                if 'enum' in field.schema:
                    for index,value in enumerate(field.schema['enum']):
                        assert field.editor.itemData(index)==value
                        assert re.search(r'[\u4e00-\u9fff]',field.editor.itemText(index))
                        assert field.editor.itemData(index,Qt.ItemDataRole.ToolTipRole)
            qt.processEvents()
        desktop.show_observation(manual.state['observations'][0])
        assert desktop.observation['result']['diameter']==2 and 'diameter' in desktop.raw.toPlainText()
        desktop.close();desktop.deleteLater();qt.processEvents()
        from graph_research.desktop.shell import IntegratedWindow
        shell=IntegratedWindow(DesktopWorkspace(root/'dual-desktop'))
        shell.offline.fields['n'].set_value(6);shell.modes.setCurrentIndex(1)
        assert shell.chat is not None and not shell.chat.workspace.session.state
        shell.chat.model=OfflineModel();shell.chat.composer.setPlainText('计算P4的直径');shell.chat.send_message()
        import time
        deadline=time.monotonic()+30
        while shell.chat.thread is not None and time.monotonic()<deadline:
            qt.processEvents();time.sleep(.01)
        assert shell.chat.thread is None and shell.chat.last_error is None
        assert shell.chat.observation['result']['diameter']==3
        assert shell.chat.workspace.session.result_bundle['summary']['verified_calls']==1
        shell.modes.setCurrentIndex(0);assert shell.offline.collect_arguments()['n']==6
        assert shell.chat.workspace.session.directory!=shell.offline.workspace.session.directory
        from graph_research.desktop.configuration import ModelDialog
        dialog=ModelDialog(config_path=config);assert dialog.password.text()==''
        managed=shell.chat.workspace
        dialog.close();dialog.deleteLater();shell.close();shell.deleteLater();qt.processEvents()
        from graph_research.assistant.result_catalog import ResultCatalog,resolve_bundle
        from graph_research.assistant.result_cleanup import ResultCleanup
        from graph_research.desktop.results_center import ResultsCenter
        original=dict(managed.session.result_bundle);catalog=ResultCatalog(managed.session.results_directory)
        snapshot=managed.session.export_results();catalog.rename(managed.session.session_id,'安装包成果验证','科研')
        located=resolve_bundle(original,source_directory=managed.session.directory)
        assert located['sha256']==original['sha256'] and verify_bundle(located['archive'],located['sha256'])['ok']
        center=ResultsCenter(managed);deadline=time.monotonic()+15
        while center.thread is not None and time.monotonic()<deadline:qt.processEvents();time.sleep(.01)
        assert center.thread is None and center.table.rowCount()==1
        center.close();center.deleteLater();qt.processEvents()
        cleaner=ResultCleanup(catalog);operation=cleaner.apply(cleaner.preview([managed.session.session_id],'task')['plans'][0]['id'])
        assert not Path(located['archive']).exists();cleaner.restore(operation['id'])
        assert verify_bundle(located['archive'],located['sha256'])['ok'] and not snapshot['automatic']
        from graph_research.assistant.model_profiles import save_profiles,load_profiles
        from graph_research.assistant.model_config import validate_settings
        from graph_research.desktop.chat import ChatWindow
        from graph_research.desktop.model_service import ModelWorkspace
        installed_settings=validate_settings({'base_url':'https://api.openai.com/v1','model':'gpt-6.1-sol','auth_required':False,'reasoning_effort':'high'})
        profiles_config=root/'installed-model-profiles.json'
        save_profiles({'科研':{'settings':installed_settings.public(),'models':['gpt-6.1-sol','gpt-5.4']}},profiles_config)
        assert load_profiles(profiles_config)['科研']['settings']['reasoning_effort']=='high'
        profile_chat=ChatWindow(ModelWorkspace(root/'installed-profile-chat'),config_path=profiles_config)
        profile_chat.activate_selection(installed_settings,'科研');profile_chat.model_choice.setText('gpt-5.4');profile_chat.switch_model()
        assert profile_chat.model.settings.model=='gpt-5.4' and profile_chat.model.settings.reasoning_effort=='high'
        profile_chat.effort_choice.setCurrentIndex(profile_chat.effort_choice.findData('low'));profile_chat.switch_model()
        assert profile_chat.model.settings.reasoning_effort=='low'
        profile_chat.close();profile_chat.deleteLater();qt.processEvents()
        import asyncio
        from mcp.client import Client
        from mcp.client.stdio import StdioServerParameters
        async def installed_mcp():
            bootstrap='import sys;sys.path.insert(0,'+repr(str(target))+');from graph_research.cli import main;sys.exit(main())'
            deep_root=root/('d'*max(1,92-len(str(root))-1))
            parameters=StdioServerParameters(command=sys.executable,args=['-I','-B','-X','utf8','-c',bootstrap,'mcp','--root',str(deep_root),'--user','wheel-mcp','--results-root',str(root/'installed-results')])
            task={'version':1,'request_id':'wheel-mcp','objective':'计算P3直径','execution':{'mode':'tools','steps':[{'id':'structure','tool':'graph_invariants','arguments':{'n':3}}]}}
            async with Client(parameters,mode='legacy',cache=None,read_timeout_seconds=30) as client:
                definitions=await client.list_tools();assert len(definitions.tools)==13
                submitted=await client.call_tool('research_submit',{'task':task});assert not submitted.is_error
                identifier=submitted.structured_content['task_id'];deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    queried=await client.call_tool('research_get',{'task_id':identifier,'wait_seconds':1});snapshot=queried.structured_content
                    if not snapshot.get('transport',{}).get('active'):break
                assert snapshot['status']=='completed' and snapshot['results'][0]['data']['diameter']==2
                assert snapshot['results'][0]['timing_summary'] and len(snapshot['results'][0]['diagnostic_id'])==32
                full=(await client.call_tool('research_get',{'task_id':identifier,'detail':'full'})).structured_content
                assert full['results'][0]['timings']['worker']['stages']['worker.registry']['seconds']>0
                bad=(await client.call_tool('research_catalog',{'name':'unknown_for_diagnostics'})).structured_content
                assert bad['error']['phase']=='mcp.catalog' and len(bad['error']['diagnostic_id'])==32
                assert snapshot['budget']['used']=={'model_calls':0,'tool_calls':1}
                assert verify_bundle(snapshot['artifacts'][0]['path'],snapshot['artifacts'][0]['sha256'])['ok']
                repeated=await client.call_tool('research_submit',{'task':task})
                assert repeated.structured_content['task_id']==identifier and repeated.structured_content['budget']['used']['tool_calls']==1
                scan={'version':1,'request_id':'wheel-scan','objective':'固定超图参数扫描','execution':{'mode':'scan','scan':{'edges':[[0,1,2],[2,3,4]],'alphas':[0,.9,1]}}}
                submitted=await client.call_tool('research_submit',{'task':scan,'wait_seconds':10});scanned=submitted.structured_content;deadline=time.monotonic()+30
                while not scanned.get('terminal') and time.monotonic()<deadline:
                    queried=await client.call_tool('research_get',{'task_id':scanned['task_id'],'wait_seconds':3,'until':'terminal'});scanned=queried.structured_content
                assert scanned['status']=='completed' and scanned['budget']['used']['tool_calls']==3
                assert scanned['summary']['scan']['successful_points']==3 and all('perron_vector' not in row.get('data',{}) for row in scanned['results'])
                batch={'version':1,'request_id':'wheel-deep-exports','objective':'深目录单工具批量导出',
                       'execution':{'mode':'tools','steps':[{'id':'batch','tool':'graph_batch_study','arguments':{
                           'cases':[{'name':'P'+str(i),'input':{'kind':'path','n':3+i%6}} for i in range(12)],
                           'calculations':['structure','spectrum','charpoly'],'plot':True}}]}}
                submitted=await client.call_tool('research_submit',{'task':batch,'wait_seconds':5,'detail':'full'});exported=submitted.structured_content;deadline=time.monotonic()+35
                while exported.get('transport',{}).get('active') and time.monotonic()<deadline:
                    queried=await client.call_tool('research_get',{'task_id':exported['task_id'],'wait_seconds':2,'until':'terminal','detail':'full'});exported=queried.structured_content
                data=exported['results'][0]['data']
                assert exported['status']=='completed' and exported['summary']['output_complete'] and data['export_status']=='complete' and data['calculation_status']=='complete'
                assert len(data['rows'])==12 and len(data['files']['csv'])>=260 and set(data['files'])=={'json','csv','md','png','svg','pdf'}
                assert verify_bundle(exported['artifacts'][0]['path'],exported['artifacts'][0]['sha256'])['ok']
        asyncio.run(installed_mcp())
        from graph_research.desktop.graph_input import GraphInputDialog
        prepared=graph_patch(input_graph,tools.describe('graph_invariants'))
        source={k:prepared[k] for k in ('target','patch','vertex_mapping')};source['document']=input_graph.to_dict()
        called=manual.call_tool('graph_invariants',prepared['patch'],graph_inputs=[source])
        assert called['ok'] and called['graph_inputs'][0]['document']['vertices'][-1]=='isolated'
        assert verify_bundle(manual.result_bundle['archive'],manual.result_bundle['sha256'])['ok']
        library=GraphLibrary(root/'installed-graph-library');identifier=library.save(input_graph)
        graph_dialog=GraphInputDialog(library,library.load(identifier));assert graph_dialog.canvas.current_graph().order==4
        graph_dialog.tabs.setCurrentIndex(3);graph_dialog.canvas.add_vertex('new',[3,3]);assert graph_dialog.prepared_graph().order==5
        from PySide6.QtTest import QTest
        graph_dialog.show();qt.processEvents();canvas=graph_dialog.canvas;before_delete=canvas.current_graph()
        canvas.mode.setCurrentIndex(canvas.mode.findData('delete'));point=canvas.view.mapFromScene(canvas.vertices[0].pos())
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=point)
        assert canvas.current_graph()==before_delete and canvas._delete_target==('vertex','a')
        assert canvas.paths[0].pen().style()==Qt.PenStyle.DashLine
        QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=point)
        assert canvas.current_graph().order==4 and canvas.current_graph().size==1
        canvas.undo();assert canvas.current_graph()==before_delete
        graph_dialog.close();graph_dialog.deleteLater();qt.processEvents()
        from graph_research.assistant.session import ResearchSession
        from graph_research.assistant.model_context import inspect_data
        from graph_research.assistant.research_objects import get_object
        planned=ResearchSession(root/'installed-plans',root/'installed-plan-packages');ref=planned.bind_graph(parse_graph('a b\nb c'));planned.set_plan_review(True)
        class InstalledPlanModel:
            def __init__(self):self.calls=0
            def complete(self,messages):
                self.calls+=1;context=json.loads(messages[1]['content']);assert context['research_objects']['active']
                if self.calls==1:return {'action':'plan','plan':{'title':'图幂后检查','steps':[
                    {'id':'power','description':'计算平方图','tool':'graph_edit','arguments':{'operation':'power'},'graph_refs':{'graph':ref}},
                    {'id':'structure','description':'检查新版本','tool':'graph_invariants','arguments':{},'graph_refs':{'graph':{'step':'power'}}}]}}
                return {'action':'final','answer':'已完成真实本地计算。'}
        planned_model=InstalledPlanModel();state=planned.ask('计算G1平方图的结构',planned_model)
        assert state['status']=='awaiting_plan' and not state.get('observations')
        plan=state['plan'];state=planned.accept_plan(plan['id'],plan['scope_sha256'],planned_model)
        assert state['plan']['status']=='completed' and planned_model.calls==2 and state['observations'][-1]['result']['size']==3
        assert get_object(planned.research_objects,ref)['document']['vertices']==['a','b','c']
        assert get_object(planned.research_objects,{'id':'G1','version':2})['document']['vertices']==['a','b','c']
        assert inspect_data({'result':{'observation':1,'path':['size']}},tools,set(tools.tools),planned.research_objects,state['observations'])['result']==3
        assert verify_bundle(planned.result_bundle['archive'],planned.result_bundle['sha256'])['ok']
        from graph_research.assistant.evaluation import evaluation_cases,run_evaluation
        from graph_research.assistant.streaming import partial_final_answer
        from graph_research.desktop.research_view import AnswerView
        assert len(evaluation_cases())==12
        assert partial_final_answer('{"action":"final","answer":"安装包')=='安装包'
        scientific=ResearchSession(root/'installed-evidence',root/'installed-empty-tools')
        class InstalledEvidenceModel:
            last_usage=None
            def __init__(self):self.calls=0
            def complete(self,messages):
                self.calls+=1;self.last_usage={'input_tokens':12,'output_tokens':8}
                if self.calls==1:return {'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':3}}
                return {'action':'final','answer':'直径为2。','claims':[{'text':'直径2','kind':'exact','sources':[{'observation':0,'path':['diameter'],'expected':2}]}]}
        scientific_model=InstalledEvidenceModel();state=scientific.ask('核对P3直径',scientific_model)
        assert state['audited_claims'][0]['status']=='field_matched' and scientific.workflow_usage()['known_input_tokens']==24
        assert verify_bundle(scientific.result_bundle['archive'],scientific.result_bundle['sha256'])['ok']
        accepted=run_evaluation(root/'installed-acceptance',case_ids=['manual-capability','ambiguous-graph'])
        assert accepted['passed']==2 and accepted['real_model_requests']==0
        answer_view=AnswerView('**结果** $x^2-1$');assert answer_view._images;answer_view.close();answer_view.deleteLater();qt.processEvents()
        budgeted=ResearchSession(root/'installed-budget',root/'installed-budget-tools',auto_export=False);budgeted.set_workflow_budget({'max_model_calls':1})
        class InstalledClarification:
            def complete(self,messages):return {'action':'clarify','questions':['请选择研究对象。']}
        budgeted.ask('预算验证',InstalledClarification());budgeted=ResearchSession(budgeted.directory)
        state=budgeted.reply('P3',InstalledClarification());assert state['status']=='budget_exhausted' and budgeted.workflow_usage()['model_calls']==1
        assert verify()['ok']
print(json.dumps({"package_loaded_from":str(Path(graph_research.__file__).resolve()),
                  "version":graph_research.__version__,"native_cases_passed":len(result["rows"]),
                  "core_tool_entries":len(tools.catalog()),"kernel_sage_and_external_processes_blocked":True,
                  "installed_recurrence_integer_lattice_and_research_family_verified":True,
                  "installed_graph_replacement_matrix_actions_group_index_and_shared_root_star_verified":True,
                  "installed_nine_research_workflows_and_documented_examples_verified":True,
                  "installed_unified_graph_input_library_canvas_and_execution_bound_mapping_verified":True,
                  "installed_two_click_delete_preview_and_undo_verified":True,
                  "installed_api_graph_versions_reviewed_plan_dependencies_context_and_receipts_verified":True,
                  "installed_claim_evidence_durable_usage_budget_formula_stream_parser_and_acceptance_verified":True,
                  "installed_model_profiles_reasoning_and_native_quick_switch_verified":True,
                  "installed_mcp_official_client_stdio_async_real_calculation_idempotence_and_bundle_verified":True,
                  "installed_field_feedback_endpoint_independent_certificate_summary_and_budgeted_scan_verified":True,
                  "installed_managed_result_center_rename_snapshot_preview_recycle_and_restore_verified":True,
                  "isolated_python_elimination_tool_passed":True,"installed_memory_and_session_verified":True,
                  "installed_os_write_protection_and_recovery_verified":True,"installed_result_bundle_verified":True,
                  "installed_model_onboarding_and_mock_probe_verified":True,
                  "installed_subagent_fixed_task_pause_restart_host_event_replay_verified":True,
                  "installed_batch_case_bindings_budget_outputs_and_bundle_verified":True,
                  "installed_readonly_user_memory_reviewed_experience_and_evidence_verified":True,
                  "installed_persistent_extension_library_external_development_and_versions_verified":True,
                  "installed_deep_mcp_batch_all_exports_verified":True,
                  "installed_phase_timings_and_correlated_diagnostics_verified":True,
                  "installed_standalone_console_without_parent_verified":True,
                  "installed_offline_category_menu_real_calculation_and_bundle_verified":True,
                  "installed_input_guides_tools":43,"installed_parameter_examples_verified":field_count,
                  "installed_verified_result_view_without_reexecution":True,
                  "installed_native_desktop_visible_forms_and_result_view_verified":True,
                  "installed_native_chinese_choices_parameter_values_and_tooltips_verified":True,
                  "installed_paper_camera_selection_context_layers_and_direction_verified":True,
                  "installed_dual_mode_native_chat_tool_result_and_configuration_verified":True}))
