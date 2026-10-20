"""Model/profile controls with bounded mock HTTP only, never paid requests."""
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import httpx
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QMessageBox
from graph_research.assistant.model import ConfiguredModel,ModelAPIError
from graph_research.assistant.model_config import ModelSettings,validate_settings,load_settings,save_configuration,ModelConfigurationError
from graph_research.assistant.model_profiles import save_profiles,load_profiles,profiles_path,credential_scope
from graph_research.assistant.model_capabilities import reasoning_choices
from graph_research.desktop.configuration import ModelDialog
from graph_research.desktop.chat import ChatWindow
from graph_research.desktop.model_service import ModelWorkspace


def response(mode):
    text='{"action":"final","answer":"模拟完成"}'
    return {'output':[{'content':[{'type':'output_text','text':text}]}]} if mode=='responses' else {'choices':[{'message':{'content':text}}]}


class ModelSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.config=self.root/'model.json'
        self.environment=patch.dict(os.environ,{k:v for k,v in os.environ.items() if not k.startswith('RESEARCH_')},clear=True)
        self.environment.start();self.addCleanup(self.environment.stop);self.addCleanup(self.temp.cleanup)
        self.widgets=[];self.addCleanup(self.cleanup)

    def cleanup(self):
        for widget in self.widgets:
            self.wait(widget);widget.close();widget.deleteLater()
        self.app.processEvents()

    def wait(self,widget):
        deadline=time.monotonic()+5
        while widget.thread is not None and time.monotonic()<deadline:self.app.processEvents();time.sleep(.005)
        self.assertIsNone(widget.thread);self.app.processEvents()

    def settings(self,**kw):
        return validate_settings({'base_url':'https://api.openai.com/v1','model':'gpt-6.1-sol','auth_required':False,**kw})

    def record(self,settings,models=None):return {'settings':settings.public(),'models':models or [settings.model]}

    def dialog(self,**kw):
        d=ModelDialog(config_path=self.config,**kw);self.widgets.append(d);return d

    def window(self):
        w=ChatWindow(ModelWorkspace(self.root/'workspace'),config_path=self.config);self.widgets.append(w);return w

    def transport(self,handler):
        original=httpx.Client
        return patch('httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(handler),**kw))

    def test_legacy_configuration_loads_without_reasoning_and_environment_still_wins(self):
        self.config.write_text(json.dumps({'base_url':'https://example.invalid/v1','model':'old','mode':'chat_completions'}))
        self.assertIsNone(load_settings(self.config).reasoning_effort)
        with patch.dict(os.environ,{'RESEARCH_MODEL':'override'}):self.assertEqual(load_settings(self.config).model,'override')

    def test_capabilities_are_conservative_and_manual_override_is_explicit(self):
        self.assertEqual(reasoning_choices('https://third.invalid/v1','gpt-6.1-sol'),(None,))
        self.assertEqual(reasoning_choices('https://api.openai.com/v1','new-alias'),(None,))
        self.assertNotIn('none',reasoning_choices('https://api.openai.com/v1','gpt-6.1-sol'))
        self.assertNotIn('minimal',reasoning_choices('https://api.openai.com/v1','gpt-6.1-sol'))
        self.assertIn('max',reasoning_choices('https://api.openai.com/v1','gpt-6.1-sol'))
        self.assertEqual(reasoning_choices('https://[','x'),(None,))
        self.assertEqual(reasoning_choices('https://api.openai.com/v1','gpt-6.1-sol','off'),(None,))
        self.assertIn('high',reasoning_choices('https://third.invalid','alias','openai'))
        with self.assertRaises(ModelConfigurationError):self.settings(reasoning_effort='none')
        with self.assertRaises(ModelConfigurationError):self.settings(reasoning_effort='high',base_url='https://third.invalid')
        with self.assertRaises(ModelConfigurationError):self.settings(reasoning_profile='invented')

    def test_both_protocols_send_exact_reasoning_fields_and_default_omits_them(self):
        for mode in ('responses','chat_completions'):
            for effort in (None,'high'):
                seen=[]
                def handler(request):seen.append(json.loads(request.content));return httpx.Response(200,json=response(mode))
                with self.transport(handler):ConfiguredModel(self.settings(mode=mode,reasoning_effort=effort)).complete([{'role':'user','content':'JSON'}])
                payload=seen[0]
                if effort is None:self.assertNotIn('reasoning',payload);self.assertNotIn('reasoning_effort',payload)
                elif mode=='responses':self.assertEqual(payload['reasoning'],{'effort':'high'});self.assertNotIn('reasoning_effort',payload)
                else:self.assertEqual(payload['reasoning_effort'],'high');self.assertNotIn('reasoning',payload)

    def test_profiles_roundtrip_and_active_legacy_config_remains_compatible(self):
        first=self.settings(reasoning_effort='high');second=self.settings(base_url='https://second.invalid/v1',model='custom',mode='chat_completions')
        with patch('httpx.Client',side_effect=AssertionError('No network')):
            save_profiles({'科研':self.record(first,['gpt-6.1-sol','gpt-5.4']),'本地':self.record(second)},self.config)
            save_configuration(first.public(),self.config)
            self.assertEqual(load_settings(self.config),first);self.assertEqual(len(load_profiles(self.config)),2)
            save_profiles({'科研':self.record(first)},self.config)
        self.assertTrue(profiles_path(self.config).with_name('model.profiles.json.previous').exists())
        self.assertNotIn('api_key',profiles_path(self.config).read_text())

    def test_invalid_or_credential_bearing_profile_file_is_never_copied_or_overwritten(self):
        target=profiles_path(self.config);target.write_text('{"api_key":"PRIVATE_ONLY"}');before=target.read_bytes()
        with self.assertRaises(ModelConfigurationError):save_profiles({'test':self.record(self.settings())},self.config)
        self.assertEqual(target.read_bytes(),before);self.assertFalse(target.with_name(target.name+'.previous').exists())
        for record in [dict(self.record(self.settings()),api_key='secret'),{'settings':{**self.settings().public(),'api_key':'secret'},'models':[]}]:
            with self.assertRaises(ModelConfigurationError):save_profiles({'test':record},self.root/'different.json')

    def test_model_discovery_is_one_get_preserves_auth_and_does_not_generate(self):
        settings=self.settings(auth_required=True);seen=[]
        def handler(request):
            seen.append(request);self.assertEqual(request.method,'GET');self.assertEqual(str(request.url),'https://api.openai.com/v1/models')
            self.assertEqual(request.headers['Authorization'],'Bearer PRIVATE_MODEL_LIST')
            return httpx.Response(200,json={'data':[{'id':'b'},{'id':'a'},{'id':'b'}]})
        with self.transport(handler):self.assertEqual(ConfiguredModel(settings,api_key='PRIVATE_MODEL_LIST').list_models(),['a','b'])
        self.assertEqual(len(seen),1);self.assertFalse(self.config.exists())

    def test_model_discovery_no_auth_never_sends_environment_key(self):
        def handler(request):self.assertNotIn('Authorization',request.headers);return httpx.Response(200,json={'data':[]})
        with patch.dict(os.environ,{'RESEARCH_API_KEY':'PRIVATE'}),self.transport(handler):self.assertEqual(ConfiguredModel(self.settings()).list_models(),[])

    def test_discovery_errors_are_bounded_redacted_and_not_retried(self):
        for status,body in [(307,None),(404,None),(200,{'data':'bad'}),(200,{'data':[{'id':'PRIVATE_MODEL_LIST'}]}),
                            (200,{'data':[{'id':'sk-1234567890123456789012'}]}),(200,{'data':[{'id':3}]}),(200,{'data':[{'id':'a'}]*1001})]:
            seen=[]
            def handler(request):seen.append(request);return httpx.Response(status,json=body,headers={'Location':'https://elsewhere.invalid'})
            with self.transport(handler),self.assertRaises(ModelAPIError) as caught:ConfiguredModel(self.settings(auth_required=True),api_key='PRIVATE_MODEL_LIST').list_models()
            self.assertNotIn('PRIVATE_MODEL_LIST',str(caught.exception));self.assertEqual(len(seen),1)
        def large(request):return httpx.Response(200,content=b'x'*(1024*1024+1))
        with self.transport(large),self.assertRaises(ModelAPIError):ConfiguredModel(self.settings()).list_models()

    def test_dialog_discovery_preserves_manual_model_and_fallback(self):
        d=self.dialog(settings=self.settings(model='manual-id'));seen=[]
        def handler(request):seen.append(request);return httpx.Response(200,json={'data':[{'id':'gpt-6.1-sol'},{'id':'gpt-5.4'}]})
        with self.transport(handler):
            d.discover_models();self.assertFalse(d.editor.isEnabled());d.reject();self.assertIsNotNone(d.thread);self.wait(d)
        self.assertEqual(d.model_id.text(),'manual-id');self.assertEqual(d.model_id.count(),2);self.assertEqual(len(seen),1)
        self.assertFalse(self.config.exists());self.assertTrue(d.editor.isEnabled())
        with self.transport(lambda request:httpx.Response(404)):
            d.discover_models();self.wait(d)
        self.assertEqual(d.model_id.text(),'manual-id');self.assertEqual(d.model_id.count(),2)

    def test_dialog_efforts_follow_model_and_service_with_no_explanatory_cost_text(self):
        d=self.dialog(settings=self.settings(reasoning_effort='max'))
        self.assertEqual(d.effort.currentData(),'max');self.assertEqual(d.effort.findData('none'),-1)
        d.model_id.setText('gpt-5.1');self.assertIsNone(d.effort.currentData());self.assertNotEqual(d.effort.findData('none'),-1)
        d.address.setText('https://third.invalid/v1');self.assertEqual(d.effort.count(),1)
        d.reasoning_profile.setCurrentIndex(d.reasoning_profile.findData('openai'));d.effort.setCurrentIndex(d.effort.findData('high'))
        self.assertEqual(d.read_settings().reasoning_effort,'high');self.assertFalse(self.config.exists())

    def test_keys_follow_exact_connection_scope_and_are_only_in_memory(self):
        first=self.settings(auth_required=True);second=self.settings(base_url='https://second.invalid/v1',auth_required=True)
        save_profiles({'一':self.record(first),'二':self.record(second)},self.config)
        d=self.dialog(settings=first,current_profile='一');d.password.setText('PRIVATE_ONE')
        d.profile_choice.setCurrentIndex(d.profile_choice.findData('二'));self.assertEqual(d.password.text(),'')
        d.password.setText('PRIVATE_TWO');d.profile_choice.setCurrentIndex(d.profile_choice.findData('一'));self.assertEqual(d.password.text(),'PRIVATE_ONE')
        with patch('httpx.Client',side_effect=AssertionError('No enable traffic')):d.enable()
        self.assertEqual(d.model.api_key,'PRIVATE_ONE');self.assertEqual(d.password.text(),'')
        for target in self.root.glob('*.json*'):
            self.assertNotIn('PRIVATE_ONE',target.read_text());self.assertNotIn('PRIVATE_TWO',target.read_text())
        self.assertEqual(d.credentials[credential_scope(second)],'PRIVATE_TWO')

    def test_known_key_cannot_be_saved_as_public_model_or_profile_name(self):
        d=self.dialog(settings=self.settings(auth_required=True));d.password.setText('PRIVATE_ONLY_SECRET');d.model_id.setText('PRIVATE_ONLY_SECRET')
        with patch.object(QMessageBox,'warning') as warning:d.save_public()
        self.assertTrue(warning.called);self.assertFalse(self.config.exists());self.assertFalse(profiles_path(self.config).exists())

    def test_dialog_save_as_delete_and_restart_preserve_all_other_profiles(self):
        d=self.dialog(settings=self.settings());d.persist(d.read_settings(),'科研')
        d.model_id.setText('gpt-5.4')
        with patch('graph_research.desktop.configuration.QInputDialog.getText',return_value=('日常',True)):d.save_as_profile()
        self.assertEqual(set(load_profiles(self.config)),{'科研','日常'})
        with patch.object(QMessageBox,'question',return_value=QMessageBox.StandardButton.Yes):d.delete_profile()
        self.assertEqual(set(load_profiles(self.config)),{'科研'})
        restored=self.dialog();self.assertEqual(restored.model_id.text(),'gpt-5.4')  # active model.json is independent of collection deletion
        restored.profile_choice.setCurrentIndex(restored.profile_choice.findData('科研'));self.assertEqual(restored.model_id.text(),'gpt-6.1-sol')

    def test_quick_controls_change_actual_payload_without_resetting_task_or_requests(self):
        settings=self.settings(reasoning_effort='high');save_profiles({'科研':self.record(settings,['gpt-6.1-sol','gpt-5.4'])},self.config)
        w=self.window()
        with patch('httpx.Client',side_effect=AssertionError('Switching must not connect')):w.activate_selection(settings,'科研')
        before=copy.deepcopy(w.workspace.session.workflow_usage())
        w.effort_choice.setCurrentIndex(w.effort_choice.findData('max'));w.switch_model();self.assertEqual(w.model.settings.reasoning_effort,'max')
        w.model_choice.setText('gpt-5.4');w.switch_model();self.assertEqual(w.model.settings.model,'gpt-5.4');self.assertIsNone(w.model.settings.reasoning_effort)
        w.effort_choice.setCurrentIndex(w.effort_choice.findData('low'));w.switch_model()
        self.assertEqual(w.workspace.session.workflow_usage(),before)
        seen=[]
        def handler(request):seen.append(json.loads(request.content));return httpx.Response(200,json=response('responses'))
        with self.transport(handler):w.composer.setPlainText('模拟分析');w.send_message();self.wait(w)
        self.assertEqual(seen[0]['model'],'gpt-5.4');self.assertEqual(seen[0]['reasoning'],{'effort':'low'})
        journal=json.loads((w.workspace.session.directory/'workflow-journal.json').read_text())
        rows=[row for task in journal['tasks'].values() for row in task['model_requests']]
        self.assertEqual(rows[0]['model_selection']['reasoning_effort'],'low');self.assertEqual(len(rows),1)
        self.assertEqual(load_settings(self.config).model,'gpt-5.4')

    def test_quick_profile_switch_never_reuses_key_for_different_address(self):
        a=self.settings(auth_required=True);b=self.settings(base_url='https://second.invalid/v1',model='custom',auth_required=True)
        save_profiles({'一':self.record(a),'二':self.record(b)},self.config);w=self.window();w.credentials[credential_scope(a)]='PRIVATE_ONE'
        w.activate_selection(a,'一');old=w.model
        w.profile_choice.setCurrentIndex(w.profile_choice.findData('二'))
        with patch.object(w,'configure_model') as configure:w.switch_profile();configure.assert_called_once_with('二')
        self.assertIs(w.model,old)
        w.credentials[credential_scope(b)]='PRIVATE_TWO';w.activate_selection(b,'二');self.assertEqual(old.api_key,'')
        seen=[]
        def handler(request):seen.append(request);return httpx.Response(200,json=response('responses'))
        with self.transport(handler):w.model.complete([{'role':'user','content':'JSON'}])
        self.assertEqual(seen[0].url.host,'second.invalid');self.assertEqual(seen[0].headers['Authorization'],'Bearer PRIVATE_TWO')
        w.disconnect_model();self.assertEqual(w.credentials,{});self.assertEqual(w.model,None)

    def test_busy_controls_refuse_changes_and_invalid_manual_id_keeps_current_model(self):
        settings=self.settings();save_profiles({'科研':self.record(settings)},self.config);w=self.window();w.activate_selection(settings,'科研')
        w.thread=object()
        try:
            w.refresh_controls();self.assertFalse(w.profile_choice.isEnabled());self.assertFalse(w.model_choice.isEnabled());self.assertFalse(w.effort_choice.isEnabled())
            w.model_choice.setText('another');w.switch_model();self.assertEqual(w.model.settings.model,settings.model)
        finally:w.thread=None
        w.sync_model_choices();w.model_choice.setText('')
        with patch.object(QMessageBox,'warning'):w.switch_model()
        self.assertEqual(w.model.settings.model,settings.model);self.assertEqual(w.model_choice.text(),settings.model)

    def test_open_save_and_switch_profiles_make_zero_network_requests(self):
        with patch('httpx.Client',side_effect=AssertionError('No automatic traffic')):
            d=self.dialog(settings=self.settings());d.persist(d.read_settings(),'科研');w=self.window();w.activate_selection(self.settings(),'科研')
            w.effort_choice.setCurrentIndex(w.effort_choice.findData('high'));w.switch_model();w.disconnect_model()

    def test_refreshing_list_preserves_existing_effort_and_does_not_infer_capabilities(self):
        d=self.dialog(settings=self.settings(reasoning_effort='max'))
        with self.transport(lambda request:httpx.Response(200,json={'data':[{'id':'gpt-5.4'},{'id':'gpt-6.1-sol'}]})):
            d.discover_models();self.wait(d)
        self.assertEqual(d.effort.currentData(),'max');self.assertEqual(d.model_id.text(),'gpt-6.1-sol')
        d.model_id.setText('unknown-model');self.assertEqual(d.effort.count(),1)

    def test_profile_size_limit_prevents_creating_a_file_that_cannot_be_reloaded(self):
        settings=self.settings();models=['model-'+str(i)+'x'*230 for i in range(1000)]
        profiles={str(i):self.record(settings,models) for i in range(5)}
        with self.assertRaises(ModelConfigurationError):save_profiles(profiles,self.config)
        self.assertFalse(profiles_path(self.config).exists())

    def test_missing_key_cancel_and_close_keep_no_foreign_key(self):
        settings=self.settings(auth_required=True);save_profiles({'科研':self.record(settings)},self.config)
        w=self.window();w.credentials[credential_scope(settings)]='PRIVATE_TO_CLEAR';w.activate_selection(settings,'科研');actual=w.model
        w.close();self.assertEqual(actual.api_key,'');self.assertEqual(w.credentials,{})

    def test_third_party_adapter_with_its_own_settings_retains_existing_contract(self):
        from types import SimpleNamespace
        from graph_research.assistant import ResearchSession
        class CustomAdapter:
            settings=SimpleNamespace(max_output_tokens=64)
            def complete(inner,messages,*,max_output_tokens=None):
                self.assertEqual(max_output_tokens,64)
                return {'action':'final','answer':'自定义适配器仍可使用。'}
        session=ResearchSession(self.root/'custom-adapter',auto_export=False)
        self.assertEqual(session.ask('只分析',CustomAdapter())['status'],'model_analysis_only')


if __name__=='__main__':unittest.main()
