"""Native dual-mode UX with fake models only: no credentials or paid traffic."""
import json
import os
from pathlib import Path
import tempfile
from threading import Event
import time
import unittest
from unittest.mock import patch
import zipfile

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    import httpx
    from PySide6.QtWidgets import QApplication,QMessageBox,QLabel
    from graph_research.desktop.shell import IntegratedWindow
    from graph_research.desktop.chat import ChatWindow
    from graph_research.desktop.configuration import ModelDialog
    from graph_research.desktop.model_service import ModelWorkspace,SafeModel
    from graph_research.desktop.service import DesktopWorkspace
    AVAILABLE=True
except ImportError:AVAILABLE=False

from graph_research.assistant import ResearchSession,verify_bundle
from graph_research.assistant.model_config import validate_settings
from graph_research.runtime.integrity import verify,CORE
from tests.test_feature_workflow import ScriptedModel
from tests.feature_helpers import proposal,request_for


@unittest.skipUnless(AVAILABLE,'Optional desktop and model dependencies unavailable')
class ChatDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.workspace=ModelWorkspace(self.root/'model');self.window=ChatWindow(self.workspace);self.addCleanup(self.cleanup)

    def wait(self,window=None,timeout=35):
        window=window or self.window;deadline=time.monotonic()+timeout
        while window.thread is not None and time.monotonic()<deadline:self.app.processEvents();time.sleep(.01)
        self.assertIsNone(window.thread);self.app.processEvents()

    def cleanup(self):
        if self.window.thread is not None:self.window.cancel_calculation();self.wait()
        self.window.close();self.window.deleteLater();self.app.processEvents();self.temp.cleanup()

    def send(self,text):
        self.window.composer.setPlainText(text);self.window.send_message();self.wait()
        self.assertIsNone(self.window.last_error)

    def test_dual_mode_switch_keeps_local_forms_and_separate_model_history_without_requests(self):
        shell=IntegratedWindow(DesktopWorkspace(self.root/'both'))
        with patch('httpx.Client',side_effect=AssertionError('No startup network')):
            shell.offline.fields['n'].set_value(7);shell.modes.setCurrentIndex(1)
            self.assertIsNotNone(shell.chat);self.assertFalse(shell.chat.workspace.session.state)
            shell.modes.setCurrentIndex(0);self.assertEqual(shell.offline.collect_arguments()['n'],7)
            self.assertNotEqual(shell.offline.workspace.session.directory,shell.chat.workspace.session.directory)
        shell.close();shell.deleteLater();self.app.processEvents()

    def test_graph_context_previews_numeric_results_and_exports_without_model_or_draft_changes(self):
        from graph_research.desktop.graph_actions import presentation_call
        from graph_research.graph_input.document import document
        graph=document(['a','b','isolate'],[{'vertices':['a','b']}],positions=[[0,0],[1,0],[0,1]])
        record={'ok':True,'tool':'graph_invariants','arguments':{'kind':'path','n':4},'result':{'order':4}}
        self.window.composer.setPlainText('保留我的问题草稿')
        with patch('httpx.Client',side_effect=AssertionError('Graph viewing must not request a model')):
            self.window.show_observation(record);self.window.refresh_controls();self.window.preview_result_graph()
            self.assertEqual(self.window.result_canvas.graph.order,4);self.assertTrue(self.window.result_graph_button.isEnabled())
            self.window._dispatch_graph_call(presentation_call(graph,self.workspace.registry.describe('graph_tikz')))
            self.wait()
        self.assertTrue(self.window.observation['ok'],self.window.observation);self.assertEqual(self.window.composer.toPlainText(),'保留我的问题草稿')
        self.assertEqual(self.workspace.history()[-1]['origin'],'manual_graph');self.assertEqual(self.workspace.session.workflow_usage()['model_calls'],0)
        self.assertIsNone(self.window.thread)

    def test_clarification_tool_composition_multiturn_results_export_and_restart(self):
        self.window.model=ScriptedModel([
            {'action':'clarify','questions':['路径图有多少个顶点？']},
            {'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':5}},
            {'action':'call','tool':'matrix_analysis','arguments':{'matrix':[[1,2],[2,1]]}},
            {'action':'final','answer':'路径图直径4，矩阵特征值为3与-1。'},
            {'action':'final','answer':'前一轮的直径计算已保留。'}])
        self.send('计算路径图与矩阵的性质');self.assertEqual(self.window.view_state['status'],'awaiting_clarification')
        self.send('5个顶点，矩阵为[[1,2],[2,1]]');self.assertEqual(len(self.workspace.history()),2)
        self.assertEqual(self.workspace.history()[0]['result']['diameter'],4);self.assertGreater(self.window.table.rowCount(),0)
        self.send('保留本轮结果');self.assertEqual(len(self.window.view_turns),3)
        self.assertFalse(self.workspace.session.store.directory.exists(),'Composition must not install an extension')
        output=self.workspace.export_bundle(self.root/'all.zip');self.assertTrue(verify_bundle(output)['ok'])
        restored=ModelWorkspace(self.workspace.directory);self.assertEqual(restored.session.directory,self.workspace.session.directory)
        self.assertEqual(len(restored.session.turns),3);self.assertEqual(len(restored.history()),2)
        self.assertIn('前一轮',restored.session.turns[-1]['answer'])
        self.assertTrue(any('路径图' in widget.text() for widget in self.window.messages.findChildren(QLabel)))

    def test_exact_scope_approval_is_explicit_and_installs_only_after_click(self):
        tool=proposal();before=verify()
        self.window.model=ScriptedModel([{'action':'assess','request':request_for(tool)},
            {'action':'extend','proposal':tool},{'action':'call','tool':tool['name'],'arguments':{'degrees':[3,2,2,1]}},
            {'action':'final','answer':'h指数为2；扩展仅通过登记样例。'}])
        self.send('新增h指数工具');pending=self.window.pending_approval
        self.assertIsNotNone(pending);self.assertTrue(self.window.approve_button.isEnabled())
        self.assertEqual(len(self.window.model.contexts),1);self.assertFalse(self.workspace.session.store.directory.exists())
        with patch.object(QMessageBox,'warning'):
            self.window.start_action('approve',pending=(pending[0],'stale-scope'));self.assertIsNone(self.window.thread)
        self.window.approve_button.click();self.wait()
        self.assertIsNone(self.window.last_error);self.assertIsNone(self.window.pending_approval)
        self.assertEqual(self.workspace.history()[-1]['result'],{'h_index':2})
        self.assertTrue((self.workspace.tool_directory/tool['name']/'approval.json').is_file())
        self.assertTrue(verify()['ok']);self.assertTrue(before['ok'])

    def test_restored_approval_can_be_rejected_without_model_and_revision_invalidates_old_scope(self):
        self.window.model=ScriptedModel([{'action':'assess','request':request_for(proposal())},{'action':'clarify','questions':['修改后的输入是什么？']}])
        self.send('新增算法');old=self.window.pending_approval
        self.send('先修改输入要求');self.assertIsNone(self.window.pending_approval)
        with patch.object(QMessageBox,'warning'):self.window.start_action('approve',pending=old)
        self.assertIsNone(self.window.thread)
        other=ModelWorkspace(self.root/'reject');session=other.session
        session.ask('新增算法',ScriptedModel([{'action':'assess','request':request_for(proposal())}]))
        self.window.open_directory(session.directory);self.window.disconnect_model()
        self.assertIsNotNone(self.window.pending_approval);self.assertFalse(self.window.approve_button.isEnabled())
        self.window.reject_button.click();self.wait()
        self.assertEqual(self.window.view_state['status'],'extension_rejected');self.assertFalse(session.store.directory.exists())

    def test_model_error_is_sanitized_and_manual_continue_preserves_completed_result(self):
        class Failure:
            api_key='sk-fake-private-only-for-test'
            def __init__(self):self.count=0
            def complete(inner,messages):
                inner.count+=1
                if inner.count==1:return {'action':'call','tool':'graph_invariants','arguments':{'n':3}}
                raise RuntimeError('Authorization: '+inner.api_key)
        failure=Failure();self.window.model=failure;self.send('计算路径图')
        self.assertEqual(self.window.view_state['status'],'execution_error');self.assertEqual(len(self.workspace.history()),1)
        snapshot=(self.workspace.session.directory/'session.json').read_text(encoding='utf-8');self.assertNotIn(failure.api_key,snapshot)
        self.window.model=ScriptedModel([{'action':'final','answer':'已保留直径2的计算。'}]);self.window.resume.click();self.wait()
        self.assertEqual(len(self.workspace.history()),1);self.assertEqual(self.window.view_state['status'],'tool_results_available')

    def test_early_stop_and_close_do_not_send_model_request_or_destroy_running_thread(self):
        class Forbidden:
            def complete(self,messages):raise AssertionError('Early stop must not call a model')
        self.window.model=Forbidden();self.window.composer.setPlainText('计算');self.window.send_message();self.window.cancel_calculation();self.wait()
        self.assertFalse(self.workspace.history());self.assertIn('模型请求0次',self.window.progress_text.text())
        self.window.show();self.window.composer.setPlainText('计算');self.window.send_message();self.window.close();self.wait()
        self.assertTrue(self.window.close_after);self.assertFalse(self.window.isVisible())

    def test_cancel_during_model_response_does_not_start_suggested_tool_and_can_resume(self):
        entered=Event();release=Event()
        class Slow:
            def complete(self,messages):
                entered.set();release.wait(5);return {'action':'call','tool':'graph_invariants','arguments':{'n':3}}
        self.window.model=Slow();self.window.composer.setPlainText('计算');self.window.send_message()
        deadline=time.monotonic()+5
        while not entered.is_set() and time.monotonic()<deadline:self.app.processEvents();time.sleep(.01)
        self.assertTrue(entered.is_set());self.window.cancel_calculation();release.set();self.wait()
        self.assertEqual(self.window.view_state['status'],'cancelled');self.assertFalse(self.workspace.history())

    def test_settings_keep_password_ephemeral_and_both_protocols_work_with_mock_http(self):
        secret='sk-fake-desktop-secret-123456';original=httpx.Client
        for protocol in ('responses','chat_completions'):
            with self.subTest(protocol=protocol):
                target=self.root/(protocol+'.json');dialog=ModelDialog(config_path=target)
                dialog.address.setText('https://research.invalid/v1');dialog.model_id.setText('test-model')
                dialog.protocol.setCurrentIndex(dialog.protocol.findData(protocol));dialog.password.setText(secret)
                with patch('httpx.Client',side_effect=AssertionError('Saving must not connect')):dialog.enable()
                self.assertIsNotNone(dialog.model);self.assertEqual(dialog.password.text(),'')
                self.assertNotIn(secret,target.read_text());self.assertNotIn('api_key',target.read_text())
                requests=[]
                def respond(request):
                    requests.append(request);self.assertEqual(request.headers['Authorization'],'Bearer '+secret)
                    payload={'action':'final','answer':'这是离线模拟响应。'}
                    if protocol=='responses':body={'output':[{'content':[{'type':'output_text','text':json.dumps(payload)}]}]}
                    else:body={'choices':[{'message':{'content':json.dumps(payload)}}]}
                    return httpx.Response(200,json=body)
                with patch('httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(respond),**kw)):
                    self.window.new_session();self.window.model=dialog.model;self.send('测试科研对话')
                self.assertEqual(len(requests),1);self.assertTrue(str(requests[0].url).endswith('/responses' if protocol=='responses' else '/chat/completions'))
                with zipfile.ZipFile(self.workspace.session.result_bundle['archive']) as archive:
                    for name in archive.namelist():self.assertNotIn(secret.encode(),archive.read(name))
                self.window.disconnect_model();self.assertEqual(dialog.model.api_key,'');dialog.close();dialog.deleteLater()

    def test_probe_is_one_explicit_fixed_request_and_dialog_waits_for_thread(self):
        dialog=ModelDialog(config_path=self.root/'probe.json');dialog.address.setText('https://research.invalid/v1');dialog.model_id.setText('test');dialog.password.setText('test-secret')
        original=httpx.Client;requests=[]
        def respond(request):
            requests.append(request);return httpx.Response(200,json={'output':[{'content':[{'type':'output_text','text':'{"action":"final","answer":"连接成功"}'}]}]})
        with patch('httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(respond),**kw)):
            self.assertEqual(len(requests),0);dialog.test_connection();dialog.reject();self.assertIsNotNone(dialog.thread)
            self.wait(dialog)
        self.assertEqual(len(requests),1);payload=json.loads(requests[0].content);self.assertEqual(payload['max_output_tokens'],128)
        self.assertNotIn('tools',payload);self.assertFalse((self.root/'probe.json').exists());dialog.close();dialog.deleteLater()

    def test_model_and_offline_sessions_cannot_be_cross_opened_or_bypass_parent_task(self):
        offline=DesktopWorkspace(self.root/'offline');offline.session.call_tool('graph_invariants',{'n':3})
        with self.assertRaises(ValueError):self.workspace.open_session(offline.session.directory)
        self.window.model=ScriptedModel([{'action':'final','answer':'完成'}]);self.send('开始')
        with self.assertRaises(ValueError):offline.open_session(self.workspace.session.directory)
        delegated=ResearchSession(self.root/'delegated',self.root/'packages',task_context={'request_id':'parent-request','objective':'bounded task'})
        delegated.ask('开始',ScriptedModel([{'action':'final','answer':'完成'}]))
        with self.assertRaises(ValueError):self.workspace.open_session(delegated.directory)
        self.assertTrue(verify()['ok'])


if __name__=='__main__':unittest.main()
