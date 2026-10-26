"""Report regressions: feedback routing, pending filtering and native lifetime."""
import copy
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from graph_research.assistant.task_approvals import TaskApprovals
from graph_research.assistant.task_contract import TaskProtocolError
from graph_research.mcp.approval_ui import ApprovalNotifier,read_optional
from graph_research.runtime.storage import write_json

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtCore import QThread,Qt
    from PySide6.QtWidgets import QApplication
    from graph_research.desktop.task_approvals import TaskApprovalCenter,filter_rows
    QT=True
except ImportError:QT=False


class AutoWindowTests(unittest.TestCase):
    def test_shared_window_state_rejects_stale_future_or_malformed_heartbeats(self):
        from graph_research.assistant.approval_state import heartbeat_fresh
        self.assertTrue(heartbeat_fresh({'heartbeat':99,'closed':False},now=100))
        for marker in ({},{'heartbeat':88},{'heartbeat':101},{'heartbeat':'99'},
                       {'heartbeat':True},{'heartbeat':float('nan')},
                       {'heartbeat':99,'closed':True}):
            with self.subTest(marker=marker):self.assertFalse(heartbeat_fresh(marker,now=100))

    def test_shared_markers_are_bounded_advisory_state_and_keep_original_aliases(self):
        from graph_research.assistant import approval_state as state
        from graph_research.mcp import approval_ui
        self.assertIs(approval_ui.read_optional,state.read_optional)
        self.assertIs(approval_ui.request_window,state.request_window)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            self.assertEqual(state.read_optional(root/'missing.json'),{})
            for raw in ('[1,2]','{broken','{"text":"'+'x'*state.MARKER_BYTES+'"}'):
                path=root/'marker.json';path.write_text(raw,encoding='utf-8')
                self.assertEqual(state.read_optional(path),{})
            state.write_heartbeat(root)
            self.assertTrue(state.heartbeat_fresh(state.read_optional(root/state.WINDOW_FILE)))
            state.write_heartbeat(root,closed=True)
            self.assertFalse(state.heartbeat_fresh(state.read_optional(root/state.WINDOW_FILE)))
            with self.assertRaises(ValueError):state.write_heartbeat(root,'../unexpected.json')
            self.assertFalse((root/'user-actions').exists())

    def test_review_and_notification_use_the_same_core_compatibility_rule(self):
        from graph_research.assistant.approval_state import compatible_core
        pin='c'*64
        self.assertTrue(compatible_core({},pin))
        for kind in ('study_ledger','experiment_ledger'):
            with self.subTest(kind=kind):
                self.assertTrue(compatible_core({kind:{'core_sha256':pin}},pin))
                self.assertFalse(compatible_core({kind:{'core_sha256':'d'*64}},pin))

    def make(self,root):
        record={'pending':{'interaction_id':'a'*32},'study_ledger':{}}
        row={'task_id':'b'*32,'status':'waiting_for_user','updated_at':'2026-10-25T00:00:00Z'}
        runtime=SimpleNamespace(directory=root,configuration=SimpleNamespace(approval_ui='auto',root=str(root),user_id='test'),
            list_tasks=lambda limit:{'tasks':[row]},service=SimpleNamespace(read=lambda identifier:record))
        return ApprovalNotifier(runtime,desktop_bridge=root/'desktop'),record,row

    def test_waiting_task_opens_once_and_never_approves_or_reopens_user_closed_window(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);notifier,record,row=self.make(root)
            child=Mock(pid=12345);child.poll.return_value=None
            with patch('graph_research.mcp.approval_ui.interactive_available',return_value=True),patch('graph_research.mcp.approval_ui.subprocess.Popen',return_value=child) as launch:
                marker=notifier.notify();self.assertEqual(marker['state'],'launched')
                self.assertIsNone(notifier.notify());self.assertEqual(launch.call_count,1)
                args=launch.call_args.args[0]
                self.assertIn('--task',args);self.assertIn(row['task_id'],args)
                self.assertNotIn('CREATE_BREAKAWAY_FROM_JOB',str(launch.call_args))
                write_json(root/'approval-ui-active.json',{'heartbeat':time.time(),'closed':True})
                child.poll.return_value=0
                self.assertIsNone(notifier.notify());self.assertEqual(launch.call_count,1)
            self.assertFalse((root/'user-actions').exists())

    def test_existing_window_is_reused_and_headless_or_disabled_mode_never_spawns(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);notifier,record,row=self.make(root)
            write_json(root/'approval-ui-active.json',{'heartbeat':time.time(),'closed':False})
            with patch('graph_research.mcp.approval_ui.interactive_available',return_value=True),patch('graph_research.mcp.approval_ui.subprocess.Popen',side_effect=AssertionError('No extra process')):
                self.assertEqual(notifier.notify()['state'],'reused')
                self.assertEqual(read_optional(root/'approval-ui-request.json')['task_id'],row['task_id'])
                record['pending']['interaction_id']='c'*32
                self.assertEqual(notifier.notify()['state'],'reused')
                notifier.runtime.configuration.approval_ui='off'
                self.assertIsNone(notifier.notify())

    def test_unexpected_ui_exit_gets_one_bounded_reopen_without_computation_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            notifier,record,row=self.make(Path(folder));child=Mock(pid=123);child.poll.return_value=1
            with patch('graph_research.mcp.approval_ui.interactive_available',return_value=True),patch('graph_research.mcp.approval_ui.subprocess.Popen',return_value=child) as launch:
                notifier.notify();self.assertEqual(notifier.notify()['launch_attempts'],2)
                self.assertIsNone(notifier.notify());self.assertEqual(launch.call_count,2)

    def test_wrong_user_does_not_create_a_namespace_or_host_event_key(self):
        with tempfile.TemporaryDirectory() as folder:
            before=set(Path(folder).rglob('*'))
            with self.assertRaises(TaskProtocolError) as caught:TaskApprovals(folder,'db46b93cf69e7be547c7356edcf151f2')
            self.assertEqual(caught.exception.code,'approval_user_not_found')
            self.assertEqual(set(Path(folder).rglob('*')),before)

    def test_user_session_desktop_is_preferred_over_spawning_an_agent_child(self):
        with tempfile.TemporaryDirectory() as folder:
            notifier,record,row=self.make(Path(folder))
            write_json(notifier.desktop/'desktop-active.json',{'pid':777,'heartbeat':time.time(),'closed':False})
            with patch('graph_research.mcp.approval_ui.interactive_available',return_value=True),patch('graph_research.mcp.approval_ui.subprocess.Popen',side_effect=AssertionError('Use the user desktop')):
                marker=notifier.notify();self.assertEqual(marker['state'],'reused_desktop')
                request=read_optional(notifier.desktop/'approval-ui-request.json')
                self.assertEqual(request['connection'],{'root':folder,'user_id':'test'})
                self.assertEqual(request['task_id'],row['task_id'])
                self.assertIsNone(notifier.notify())


@unittest.skipUnless(QT,'Optional PySide6 missing')
class NativeLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def wait(self,panel,timeout=10):
        deadline=time.monotonic()+timeout
        while panel.thread is not None:
            self.assertLess(time.monotonic(),deadline)
            self.app.processEvents();time.sleep(.002)

    def view(self,identifier='b'*32,revision=17):
        return {'task':{'task_id':identifier,'request_id':'feedback-test','revision':revision,'status':'waiting_for_user','terminal':False,
            'interaction':{'kind':'experiment_continue','interaction_id':'a'*32,'host_actions':['continue','study_feedback'],
                'plan':{'runs':[{'id':'run1','method':'cem','seed':11,'parameters':{}}]}},
            'ui_knobs':{'exploration':.1,'elite_fraction':.25,'penalty_weight':1},'budget':{},'results':[],'summary':{}},'user_action':None}

    def test_primary_click_applies_dirty_feedback_and_reset_does_not_execute(self):
        with tempfile.TemporaryDirectory() as folder:
            panel=TaskApprovalCenter(Path(folder)/'ui.json',root=Path(folder)/'no-live-service')
            service=Mock();service.reader=SimpleNamespace(directory=Path(folder));service.act.return_value={'state':'queued'};panel.service=service
            panel.rows=[{'task_id':'b'*32,'request_id':'feedback-test','objective':'CEM feedback','status':'waiting_for_user'}]
            panel.current=self.view();panel.render()
            try:
                panel.exploration.setValue(.3);panel.penalty.setValue(2)
                self.assertTrue(panel.feedback_dirty());self.assertEqual(panel.continue_button.text(),'应用参数并继续')
                self.assertFalse(panel.feedback_button.isVisible())
                with patch.object(panel,'action_queued'):
                    panel.continue_button.click();self.wait(panel)
                self.assertEqual(service.act.call_args.args[3],'study_feedback')
                self.assertEqual(service.act.call_args.args[4]['knobs'],{'exploration':.3,'penalty_weight':2.})
                before=service.act.call_count;panel.reset_feedback_edits()
                self.assertFalse(panel.feedback_dirty());self.assertEqual(service.act.call_count,before)
                self.assertEqual(panel.continue_button.text(),'继续执行')
            finally:
                panel.shutdown();self.wait(panel);panel.close();panel.deleteLater();self.app.processEvents()

    def test_default_filter_hides_history_and_search_finds_request_id(self):
        rows=[{'task_id':f'{i:032x}','request_id':'request-'+str(i),'objective':'graph '+str(i),
               'status':'waiting_for_user' if i==180 else 'completed'} for i in range(181)]
        self.assertEqual(len(filter_rows(rows)),1)
        self.assertEqual(len(filter_rows(rows,'request-17',False)),11)
        self.assertEqual(len(filter_rows(rows,'request-180')),1)
        rows[-1]['compatible_core']=False
        self.assertEqual(filter_rows(rows),[])

    def test_repeated_refresh_and_task_switch_stays_visible_and_callbacks_run_on_gui_thread(self):
        with tempfile.TemporaryDirectory() as folder:
            panel=TaskApprovalCenter(Path(folder)/'ui.json',root=Path(folder)/'no-live-service')
            rows=[{'task_id':f'{i:032x}','request_id':f'task-{i}','objective':f'graph-{i}','status':'waiting_for_user'} for i in range(3)]
            class Service:
                reader=SimpleNamespace(directory=Path(folder))
                def list_tasks(inner):time.sleep(.001);return rows
                def get(inner,identifier):time.sleep(.001);return self.view(identifier)
            panel.service=Service();panel.timer.setInterval(12)
            original=panel.controls;observed=[]
            def controls(enabled):
                observed.append(QThread.currentThread()==self.app.thread());return original(enabled)
            panel.controls=controls
            try:
                panel.show();self.wait(panel)
                for i in range(160):
                    self.app.processEvents()
                    if panel.thread is None and panel.tasks.topLevelItemCount():
                        panel.tasks.setCurrentItem(panel.tasks.topLevelItem(i%3));panel.refresh()
                    time.sleep(.003)
                    self.assertTrue(panel.isVisible())
                panel.timer.stop();self.wait(panel)
                self.assertTrue(observed);self.assertTrue(all(observed))
                self.assertGreater(len(observed),40)
            finally:
                panel.shutdown();self.wait(panel);panel.close();panel.deleteLater();self.app.processEvents()

    def test_user_desktop_bridge_forwards_a_new_task_once_without_signing(self):
        from PySide6.QtWidgets import QWidget
        from graph_research.desktop.approval_bridge import DesktopApprovalBridge
        from graph_research.mcp.approval_ui import request_window
        with tempfile.TemporaryDirectory() as folder:
            class Window(QWidget):
                def __init__(inner):super().__init__();inner.received=[]
                def open_approval_request(inner,*args):inner.received.append(args);return True
            window=Window();window.show()
            with patch('graph_research.desktop.approval_bridge.interactive_available',return_value=True):
                bridge=DesktopApprovalBridge(window,directory=Path(folder))
                try:
                    request_window(Path(folder),'a'*32,{'root':'D:/Research/state','user_id':'researcher'})
                    bridge.poll();bridge.poll()
                    self.assertEqual(window.received,[('D:/Research/state','researcher','a'*32)])
                    self.assertFalse((Path(folder)/'user-actions').exists())
                finally:
                    bridge.shutdown();window.close();window.deleteLater();self.app.processEvents()


if __name__=='__main__':unittest.main()
