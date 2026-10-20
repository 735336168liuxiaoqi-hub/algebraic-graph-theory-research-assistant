"""Persistent approved tools, immutable versions and API-free host development."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from graph_research.tools.library import ToolLibrary,package_id
from graph_research.tools.registry import ToolRegistry
from graph_research.tools.extensions import ToolStore
from graph_research.tools.change_control import ChangeController
from graph_research.assistant.development import from_host
from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
from tests.feature_helpers import proposal,request_for


class ReadOnlyLibraryTests(unittest.TestCase):
    def test_malformed_manifest_is_quarantined_without_hiding_native_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'bad/tool.json';path.parent.mkdir();path.write_text('[]',encoding='utf-8')
            library=ToolLibrary(tmp);self.assertEqual(library.catalog()['records'][0]['state'],'quarantined')
            registry=ToolRegistry();store=ToolStore(tmp);store.load_into(registry)
            self.assertTrue(store.load_errors);self.assertIn('graph_invariants',registry.tools)
    def test_empty_library_read_does_not_create_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'missing';library=ToolLibrary(path)
            self.assertEqual(library.catalog()['records'],[]);self.assertFalse(path.exists())
            self.assertEqual(library.selected(),([],[]))

    def test_host_can_opt_into_development_and_shared_directory_without_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            host=HostConfiguration(tmp,'a',allow_development=True,tool_directory=str(Path(tmp)/'project-tools'))
            self.assertIsNone(host.model_settings);self.assertEqual(host.max_model_calls,0)
            restored=HostConfiguration.from_public(host.public());self.assertEqual(restored,host)
            runtime=MCPResearchRuntime(host)
            self.assertEqual(runtime.call('research_library',{})['records'],[])
            self.assertEqual(runtime.call('research_library',{'tool_directory':tmp})['status'],'protocol_error')
            self.assertEqual(runtime.call('research_development',{'operation':'approve','development_id':'a'*32})['status'],'protocol_error')


@unittest.skipUnless(os.name=='nt','Actual protected extension validation')
class LibraryExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.directory=self.root/'packages';self.library=ToolLibrary(self.directory);self.store=ToolStore(self.directory)

    def install(self,tool=None,replaces=None):
        tool=copy.deepcopy(tool or proposal());registry=ToolRegistry();self.store.load_into(registry)
        request=request_for(tool);request['library_metadata']={'title':'度序列h指数','summary':'按给定序列计算h指数','preconditions':['非负整数序列'],
            'limitations':['仅覆盖批准的规模和验收输入'],'returns':'h_index为整数','tags':['图论','度序列']}
        if replaces:request['replaces']=replaces
        changes=ChangeController(self.root/('change-'+str(len(list(self.root.glob('change-*'))))))
        assessment=changes.assess(request,registry);auth=changes.approve(assessment['id'],registry)
        return self.store.install(tool,registry,auth),registry

    def test_persistent_discovery_metadata_native_offline_and_mcp(self):
        result,registry=self.install();name=result['name'];record=self.library.catalog('度序列')['records'][0]
        self.assertEqual(record['version'],result['package_id']);self.assertEqual(record['state'],'enabled')
        self.assertEqual(registry.describe(name)['documentation']['title'],'度序列h指数')
        self.assertEqual(registry.describe(name)['documentation']['returns'],'h_index为整数')
        from graph_research.assistant.offline import OfflineToolSession,grouped_tools
        session=OfflineToolSession(self.root/'offline',self.directory)
        self.assertTrue(any(group['name']=='已安装的实验工具' for group in grouped_tools(session._registry())))
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root/'host'),'a',tool_directory=str(self.directory)))
        self.assertEqual(runtime.call('research_catalog',{'name':name})['tool']['status'],'fixture_tested_experimental')
        self.assertEqual(runtime.call('research_library',{})['records'][0]['experience_lookup']['tool'],name)

    def test_immutable_upgrade_rollback_disable_and_version_bound_receipt(self):
        first,_=self.install();old=(Path(first['path'])/'tool.py').read_bytes();tool=proposal();tool['source']+='\n'
        second,_=self.install(tool,replaces=first['package_id'])
        self.assertNotEqual(first['path'],second['path']);self.assertEqual((Path(first['path'])/'tool.py').read_bytes(),old)
        rows=self.library.catalog()['records'];self.assertEqual(len(rows),2);self.assertEqual(sum(row['state']=='enabled' for row in rows),1)
        self.library.select(first['name'],first['package_id'])
        from graph_research.runtime.runner import run_tool
        result=run_tool(first['name'],{'degrees':[3,2,2,1]},self.directory,directory=self.root/'runs',include_receipt=True)
        receipt=json.loads((Path(result['execution']['directory'])/'execution.json').read_text(encoding='utf-8'))
        self.assertEqual(receipt['tool_provenance']['package_id'],first['package_id'])
        self.library.select(first['name'],first['package_id'],enabled=False)
        fresh=ToolRegistry();self.store.load_into(fresh);self.assertNotIn(first['name'],fresh.tools)
        self.assertEqual(fresh.call('graph_invariants',{'kind':'path','n':3})['diameter'],2)
        self.library.select(second['name'],second['package_id']);self.assertEqual(self.library.catalog()['records'][1]['state'],'enabled')

    def test_corrupt_version_is_quarantined_and_never_falls_back(self):
        first,_=self.install();path=Path(first['path'])/'tool.py';path.write_text('def run(args):\n    return 999\n',encoding='utf-8')
        self.assertEqual(self.library.catalog()['records'][0]['state'],'quarantined')
        fresh=ToolRegistry();self.store.load_into(fresh);self.assertNotIn(first['name'],fresh.tools);self.assertTrue(self.store.load_errors)
        with self.assertRaises(ValueError):self.library.select(first['name'],first['package_id'])
        self.assertIn('graph_invariants',fresh.tools)

    def test_metadata_and_native_replacement_require_approved_scope(self):
        first,_=self.install();record=Path(first['path'])/'tool.json';data=json.loads(record.read_text(encoding='utf-8'));data['library_metadata']['title']='改变含义'
        record.write_text(json.dumps(data),encoding='utf-8');self.assertEqual(self.library.catalog()['records'][0]['state'],'quarantined')
        request=request_for(proposal());request['name']='graph_invariants';request['replaces']='a'*64
        with self.assertRaises(ValueError):ChangeController(self.root/'native').assess(request,ToolRegistry())

    def test_library_state_corruption_preserves_native_computation(self):
        self.install();self.library.path.write_text('{}',encoding='utf-8')
        registry=ToolRegistry();self.store.load_into(registry);self.assertTrue(self.store.load_errors)
        from graph_research.runtime.runner import run_tool
        self.assertEqual(run_tool('graph_invariants',{'kind':'path','n':3},self.directory,directory=self.root/'runs')['diameter'],2)

    def test_version_change_between_dispatch_and_execution_fails_closed(self):
        first,_=self.install();tool=proposal();tool['source']+='\n';second,_=self.install(tool,replaces=first['package_id'])
        self.library.select(first['name'],first['package_id'])
        from graph_research.runtime.runner import run_tool,run_worker
        def changed(*args,**kwargs):
            self.library.select(second['name'],second['package_id']);return run_worker(*args,**kwargs)
        with patch('graph_research.runtime.runner.run_worker',side_effect=changed),self.assertRaisesRegex(Exception,'version changed'):
            run_tool(first['name'],{'degrees':[]},self.directory,directory=self.root/'runs')


@unittest.skipUnless(os.name=='nt','Actual protected development worker')
class ExternalDevelopmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        from graph_research.assistant.development import _CHILDREN
        self.previous_children=set(_CHILDREN);self.addCleanup(self.wait_for_test_children)
        self.service=from_host(self.root,'a');self.tool=proposal();self.request=request_for(self.tool)

    def wait_for_test_children(self):
        # A completed record/closed worker lock can precede interpreter exit.
        # Windows keeps a process working directory busy until that exit.
        from graph_research.assistant.development import _CHILDREN
        for key in set(_CHILDREN)-self.previous_children:
            child=_CHILDREN[key];child.wait(timeout=5);_CHILDREN.pop(key,None)

    def wait(self,identifier):
        end=time.monotonic()+30
        while time.monotonic()<end:
            state=self.service.get(identifier,2)
            if not state['active']:return state
        self.fail('Development worker did not finish')

    def test_external_workflow_waits_for_human_then_installs_reuses_and_learns(self):
        initial=self.service.assess('first',self.request);identifier=initial['id']
        self.assertEqual(initial['status'],'waiting_for_approval')
        with self.assertRaises(PermissionError):self.service.submit(identifier,'one',self.tool)
        self.assertFalse(self.service.store.directory.exists())
        with self.assertRaises(ValueError):self.service.approve(identifier,'0'*64)
        self.service.approve(identifier,initial['assessment']['scope_sha256'])
        with patch('graph_research.assistant.model.ConfiguredModel',side_effect=AssertionError('No internal API')):
            queued=self.service.submit(identifier,'one',self.tool);self.assertIn(queued['status'],('queued','validating','installed'))
            done=self.wait(identifier)
        self.assertEqual(done['status'],'installed',done);self.assertEqual(done['budget']['implementation_attempts_used'],1)
        replay=self.service.submit(identifier,'one',self.tool);self.assertEqual(replay['budget']['implementation_attempts_used'],1)
        changed=copy.deepcopy(self.tool);changed['source']+='\n'
        with self.assertRaises(ValueError):self.service.submit(identifier,'one',changed)
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root),'a'))
        self.assertIn('tool',runtime.call('research_catalog',{'name':self.tool['name']}))
        task={'version':1,'request_id':'reuse-new','objective':'复用新工具','execution':{'mode':'tools','steps':[{'id':'h','tool':self.tool['name'],'arguments':{'degrees':[3,2,2,1]}}]}}
        result=runtime.parent.submit(task);self.assertEqual(result['results'][0]['data'],{'h_index':2})
        from graph_research.assistant.experience import search_experiences
        cases=search_experiences(self.root/'memory','a',reviewed_only=False)['records'];self.assertEqual(len(cases),1)
        self.assertEqual(cases[0]['content']['facts']['extension_h_index'],2)
        self.assertEqual(cases[0]['content']['evidence']['tool_package_id'],done['result']['package_id'])
        from graph_research.assistant.experience import ExperienceStore
        entry=cases[0];ExperienceStore(self.root/'memory').review('a',entry['id'],entry['content_sha256'],'approved','合成案例验收')
        ToolLibrary(self.service.store.directory).select(self.tool['name'],done['result']['package_id'],enabled=False)
        historical=runtime.call('research_experience',{'id':entry['id']})
        self.assertFalse(historical['records'][0]['current_tool_package_matches'])

    def test_scope_changed_source_rejected_and_failed_attempts_remain_charged(self):
        initial=self.service.assess('budget',self.request);identifier=initial['id'];self.service.approve(identifier,initial['assessment']['scope_sha256'])
        bad=copy.deepcopy(self.tool);bad['source']='def run(args):\n    return {"h_index": -1}\n'
        for implementation in ('bad-one','bad-two'):
            self.service.submit(identifier,implementation,bad);done=self.wait(identifier);self.assertEqual(done['status'],'validation_failed')
        self.assertEqual(done['budget']['implementation_attempts_used'],2)
        with self.assertRaises(RuntimeError):self.service.submit(identifier,'third',self.tool)
        self.assertEqual(self.service.get(identifier)['budget']['implementation_attempts_used'],2)
        self.assertFalse((self.service.store.directory/self.tool['name']).exists())

    def test_idempotency_user_isolation_routes_and_no_model_approval(self):
        initial=self.service.assess('same',self.request);self.assertEqual(self.service.assess('same',self.request)['id'],initial['id'])
        changed=copy.deepcopy(self.request);changed['goal']='another'
        with self.assertRaises(ValueError):self.service.assess('same',changed)
        with self.assertRaises(OSError):from_host(self.root,'b').get(initial['id'])
        composition=self.service.assess('reuse',{**self.request,'composition_possible':True});self.assertEqual(composition['status'],'composition')
        unclear=self.service.assess('clarify',{**self.request,'validation_ready':False});self.assertEqual(unclear['status'],'waiting_for_user')
        manual=self.service.assess('manual',{**self.request,'required_libraries':['networkx']});self.assertEqual(manual['status'],'manual_development')
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root),'a',allow_development=True))
        denied=runtime.call('research_development',{'operation':'get','development_id':initial['id'],'approved':True})
        self.assertEqual(denied['error']['code'],'invalid_arguments')

    def test_worker_start_failure_is_charged_and_never_silently_retried(self):
        initial=self.service.assess('spawn',self.request);identifier=initial['id'];self.service.approve(identifier,initial['assessment']['scope_sha256'])
        with patch('graph_research.assistant.development.subprocess.Popen',side_effect=OSError('synthetic spawn failure')) as launch:
            result=self.service.submit(identifier,'one',self.tool);replay=self.service.submit(identifier,'one',self.tool)
        self.assertEqual(launch.call_count,1);self.assertEqual(result['status'],'interrupted');self.assertEqual(replay['budget']['implementation_attempts_used'],1)
        with self.assertRaises(PermissionError):self.service.submit(identifier,'two',self.tool)

    def test_concurrent_validation_rejected_before_charging_second_request(self):
        first=self.service.assess('parallel-first',self.request);second=self.service.assess('parallel-second',self.request)
        for item in (first,second):self.service.approve(item['id'],item['assessment']['scope_sha256'])
        with patch('graph_research.assistant.development.subprocess.Popen') as launch:
            launch.return_value.poll.return_value=None
            self.service.submit(first['id'],'one',self.tool)
            with self.assertRaises(RuntimeError):self.service.submit(second['id'],'one',self.tool)
            self.assertEqual(self.service.get(second['id'])['budget']['implementation_attempts_used'],0)
            launch.return_value.poll.return_value=0;self.service.get(first['id'])

    def test_host_limit_tightening_requires_reassessment_and_reads_preserve_original_limits(self):
        from graph_research.runtime.runner import TaskLimits
        initial=self.service.assess('limits',self.request);self.service.approve(initial['id'],initial['assessment']['scope_sha256'])
        tighter=from_host(self.root,'a',limits=TaskLimits(wall_seconds=2))
        with self.assertRaises(PermissionError):tighter.submit(initial['id'],'one',self.tool)
        self.assertEqual(self.service.get(initial['id'])['budget']['implementation_attempts_used'],0)
        small=tighter.assess('small-limits',self.request)
        self.assertEqual(self.service.get(small['id'])['budget']['fixture_timeout_seconds'],2)

    def test_stale_approved_scope_is_reported_before_source_generation_or_submission(self):
        initial=self.service.assess('stale',self.request);identifier=initial['id'];self.service.approve(identifier,initial['assessment']['scope_sha256'])
        for changed in ('core_fingerprint','catalog_fingerprint'):
            with patch('graph_research.assistant.development.'+changed,return_value='0'*64):
                result=self.service.get(identifier);self.assertEqual(result['status'],'stale_assessment');self.assertTrue(result['terminal'])
                with self.assertRaises(PermissionError):self.service.submit(identifier,'not-run',self.tool)
        self.assertEqual(self.service.get(identifier)['budget']['implementation_attempts_used'],0)

    def test_disabled_existing_tool_is_discovered_instead_of_redeveloped(self):
        item=self.service.assess('install-existing',self.request);self.service.approve(item['id'],item['assessment']['scope_sha256'])
        self.service.submit(item['id'],'one',self.tool);done=self.wait(item['id']);self.assertEqual(done['status'],'installed')
        ToolLibrary(self.service.store.directory).select(self.tool['name'],done['result']['package_id'],enabled=False)
        existing=self.service.assess('should-reuse',self.request)
        self.assertEqual(existing['status'],'existing_tool');self.assertEqual(existing['existing_versions'][0]['state'],'disabled')

    def test_development_under_long_root_uses_short_worker_directory(self):
        from graph_research.assistant.development import from_host
        service=from_host(self.root/('long-project-'+'x'*52),'a');initial=service.assess('long-root',self.request)
        service.approve(initial['id'],initial['assessment']['scope_sha256']);service.submit(initial['id'],'one',self.tool)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            done=service.get(initial['id'],2)
            if not done['active']:break
        self.assertEqual(done['status'],'installed',done)


try:
    from PySide6.QtWidgets import QApplication
    QT=True
except ImportError:QT=False


@unittest.skipUnless(QT,'Optional native desktop')
class LibraryDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_empty_manager_is_native_readonly_and_unknown_names_stay_recognizable(self):
        from graph_research.desktop.service import DesktopWorkspace
        from graph_research.desktop.tool_library import ToolLibraryDialog
        from graph_research.desktop.localization import parameter_title,option_presentation
        with tempfile.TemporaryDirectory() as tmp:
            workspace=DesktopWorkspace(Path(tmp)/'desktop');dialog=ToolLibraryDialog(workspace)
            self.assertEqual(dialog.table.rowCount(),0);self.assertFalse(dialog.activate.isEnabled());dialog.close()
        definition={'parameters':{'properties':{'x':{'title':'顶点参数','x-enum-labels':{'p':'路径'},'x-enum-descriptions':{'p':'选择路径'}}}},'documentation':{}}
        self.assertEqual(parameter_title(definition,'x'),'顶点参数');self.assertEqual(option_presentation(definition,'x','p'),('路径','选择路径'))
        self.assertEqual(parameter_title(definition,'unknown'),'unknown')

    def test_catalog_refresh_preserves_json_draft_and_selected_input_tab(self):
        from graph_research.desktop.service import DesktopWorkspace
        from graph_research.desktop.app import DesktopWindow
        from graph_research.assistant.offline import grouped_tools
        from graph_research.tools.registry import Tool
        with tempfile.TemporaryDirectory() as tmp:
            workspace=DesktopWorkspace(Path(tmp)/'desktop');window=DesktopWindow(workspace)
            raw='{"kind":"cycle","n":7}';window.input_tabs.setCurrentIndex(1);window.json_editor.setPlainText(raw)
            window.refresh_tool_catalog();self.assertEqual(window.json_editor.toPlainText(),raw);self.assertEqual(window.input_tabs.currentIndex(),1)
            def added_tool():
                registry=ToolRegistry();registry.register(Tool('new_visible_tool','UI-only test fixture',{'type':'object','properties':{}},lambda:0,'fixture_tested_experimental'))
                workspace.registry=registry;workspace.groups=grouped_tools(registry)
            with patch.object(workspace,'refresh_tools',side_effect=added_tool):window.refresh_tool_catalog()
            self.assertIn('new_visible_tool',window.items);self.assertEqual(window.json_editor.toPlainText(),raw);self.assertEqual(window.input_tabs.currentIndex(),1)
            window.close()

    @unittest.skipUnless(os.name=='nt','Protected native install')
    def test_installed_tool_appears_in_native_form_with_chinese_title_and_version_controls(self):
        from graph_research.desktop.service import DesktopWorkspace
        from graph_research.desktop.app import DesktopWindow
        from graph_research.desktop.tool_library import ToolLibraryDialog
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=ToolStore(root/'packages');tool=proposal();tool['parameters']['properties']['degrees']['title']='度序列'
            request=request_for(tool);request['library_metadata']={'title':'度序列h指数'};registry=ToolRegistry();changes=ChangeController(root/'changes')
            assessment=changes.assess(request,registry);result=store.install(tool,registry,changes.approve(assessment['id'],registry))
            workspace=DesktopWorkspace(root/'desktop',tool_directory=store.directory);window=DesktopWindow(workspace);window.select_tool(tool['name'])
            self.assertEqual(window.tool_title.text(),'度序列h指数');window.apply_example();self.assertEqual(window.collect_arguments(),tool['tests'][0]['arguments'])
            dialog=ToolLibraryDialog(workspace,window);self.assertEqual(dialog.table.rowCount(),1);self.assertTrue(dialog.disable.isEnabled())
            dialog.select_version(False);self.assertNotIn(tool['name'],workspace.registry.tools)
            dialog.select_version(True);self.assertIn(tool['name'],workspace.registry.tools)
            self.assertEqual(workspace.registry.describe(tool['name'])['documentation']['package_id'],result['package_id'])
            dialog.close();window.close()
