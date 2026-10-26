"""Native user clicks, signed delivery, stale/race protection and real MCP CEM."""
import asyncio
import copy
import importlib.util
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

from graph_research.assistant.task_approvals import TaskApprovals
from graph_research.assistant.task_contract import TaskProtocolError
from graph_research.mcp.runtime import HostConfiguration, MCPResearchRuntime
from graph_research.mcp.user_actions import dispatch_user_actions, enqueue, queued_action
from tests.test_experiment_execution import task
from tests.test_experiment_evaluation import execution
from tests.test_experiment_study import study, task as study_task

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from graph_research.desktop.task_approvals import TaskApprovalCenter
    from graph_research.desktop.i18n import set_language
    QT = True
except ImportError:
    QT = False
try:
    from mcp.client import Client
    from mcp.client.stdio import StdioServerParameters
    SDK = True
except ImportError:
    SDK = False


class ApprovalDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = MCPResearchRuntime(HostConfiguration(str(self.root), 'alice', max_tool_calls=4,
                                                          results_directory=str(self.root / 'results')))
        self.addCleanup(self.stop_children)
        self.ui = TaskApprovals(self.root, 'alice')

    def stop_children(self):
        for child in self.runtime.children.values():
            if child.poll() is None:
                child.terminate(); child.wait(5)

    def wait(self, value):
        deadline = time.monotonic() + 40
        while value.get('transport', {}).get('active'):
            self.assertLess(time.monotonic(), deadline)
            value = self.runtime.get(value['task_id'], wait_seconds=1, until='terminal', detail='full')
        return value

    def initial(self, spec=None):
        request = task(spec or execution())
        value = self.wait(self.runtime.submit(request))
        self.assertEqual(value['status'], 'waiting_for_user')
        return value

    def click(self, first, action='continue', payload=None):
        return self.ui.act(first['task_id'], first['interaction']['interaction_id'], first['revision'], action, payload)

    def test_refresh_and_enqueue_never_compute_then_original_host_delivers_once(self):
        first = self.initial()
        with patch.object(MCPResearchRuntime, '_launch', side_effect=AssertionError('UI must not launch workers')):
            self.assertEqual(self.ui.list_tasks()[0]['task_id'], first['task_id'])
            self.assertEqual(self.ui.get(first['task_id'])['task']['budget']['used']['tool_calls'], 0)
            event = self.click(first)
            with self.assertRaises(TaskProtocolError) as caught:
                self.click(first)
            self.assertEqual(caught.exception.code, 'user_action_pending')
        self.assertEqual(self.runtime.get(first['task_id'])['budget']['used']['tool_calls'], 0)
        self.assertEqual(queued_action(self.runtime, first['task_id'])['state'], 'queued')
        self.assertEqual(dispatch_user_actions(self.runtime), 1)
        final = self.wait(self.runtime.get(first['task_id'], detail='full'))
        self.assertEqual(final['status'], 'completed', final.get('error'))
        self.assertEqual(final['budget']['used'], {'model_calls': 0, 'tool_calls': 1})
        self.assertEqual(queued_action(self.runtime, first['task_id'])['event_id'], event['event_id'])
        with patch.object(self.runtime, '_launch', side_effect=AssertionError('No repeated delivery')):
            self.assertEqual(dispatch_user_actions(self.runtime), 0)

    def test_stale_click_and_stale_queued_event_do_not_resume_or_mint_more_events(self):
        first = self.initial(); self.click(first)
        self.runtime.cancel(first['task_id'])
        with self.assertRaises(TaskProtocolError) as caught:
            self.click(first)
        self.assertEqual(caught.exception.code, 'stale_interaction')
        with patch.object(self.runtime, '_launch', side_effect=AssertionError('Stale approval cannot launch')):
            self.assertEqual(dispatch_user_actions(self.runtime), 1)
        self.assertEqual(queued_action(self.runtime, first['task_id'])['error']['code'], 'stale_interaction')
        self.assertEqual(self.runtime.get(first['task_id'])['budget']['used']['tool_calls'], 0)

    def test_forged_outbox_is_not_authority_and_wrong_host_cannot_deliver(self):
        first = self.initial()
        enqueue(self.runtime, {'event_id': uuid.uuid4().hex, 'task_id': first['task_id']})
        with patch.object(self.runtime, '_launch', side_effect=AssertionError('No unsigned launch')):
            self.assertEqual(dispatch_user_actions(self.runtime), 1)
        self.assertEqual(queued_action(self.runtime, first['task_id'])['error']['code'], 'event_not_found')
        self.click(first)
        other = MCPResearchRuntime(HostConfiguration(str(self.root), 'alice', max_tool_calls=3))
        self.assertEqual(dispatch_user_actions(other), 0)
        self.assertEqual(queued_action(self.runtime, first['task_id'])['state'], 'queued')
        with self.assertRaises(TaskProtocolError):
            TaskApprovals(self.root, 'bob').get(first['task_id'])

    def test_delivery_crash_after_launch_reuses_same_job_without_recomputation(self):
        first = self.initial(); self.click(first)
        with patch('graph_research.mcp.user_actions._archive', side_effect=OSError('synthetic archive interruption')):
            self.assertEqual(dispatch_user_actions(self.runtime), 0)
        with patch.object(self.runtime, '_launch', side_effect=AssertionError('Already launched')):
            self.assertEqual(dispatch_user_actions(self.runtime), 1)
        final = self.wait(self.runtime.get(first['task_id'], detail='full'))
        self.assertEqual(final['status'], 'completed')
        self.assertEqual(final['budget']['used']['tool_calls'], 1)

    def test_invalid_feedback_cannot_mint_event_or_expand_the_budget(self):
        spec = study(); spec['segment_rounds'] = 1
        request = study_task(spec); request['constraints']['max_tool_calls'] = 4
        first = self.wait(self.runtime.submit(request)); self.click(first)
        dispatch_user_actions(self.runtime)
        paused = self.wait(self.runtime.get(first['task_id'], detail='full'))
        self.assertEqual(paused['status'], 'waiting_for_user')
        events = list(self.runtime.service.events.directory.glob('*.json'))
        for feedback in ({'knobs': {'exploration': .9}}, {'budget': {'max_evaluations': 999}}):
            with self.assertRaises(TaskProtocolError):
                self.click(paused, 'study_feedback', feedback)
        self.assertEqual(events, list(self.runtime.service.events.directory.glob('*.json')))
        self.assertEqual(self.runtime.get(first['task_id'])['budget']['used']['tool_calls'], 1)

    def test_foreign_configuration_in_job_record_is_rejected(self):
        first = self.initial()
        entry = self.ui.reader._current_job(first['task_id'])
        changed = copy.deepcopy(entry[1]); changed['configuration']['user_id'] = 'bob'
        with patch.object(self.ui.reader, '_current_job', return_value=(entry[0], changed)):
            with self.assertRaises(TaskProtocolError) as caught:
                self.click(first)
        self.assertEqual(caught.exception.code, 'host_scope_mismatch')

    def test_expired_event_is_rejected_and_busy_delivery_waits_without_reissuing(self):
        first = self.initial(); self.click(first)
        with patch.object(self.runtime, '_ensure_idle', side_effect=TaskProtocolError('mcp_busy', 'busy')):
            self.assertEqual(dispatch_user_actions(self.runtime), 0)
        self.assertEqual(queued_action(self.runtime, first['task_id'])['state'], 'queued')
        future = time.time() + 7200
        with patch('graph_research.assistant.host_events.time.time', return_value=future), patch.object(self.runtime, '_launch', side_effect=AssertionError('Expired event cannot execute')):
            self.assertEqual(dispatch_user_actions(self.runtime), 1)
        self.assertEqual(queued_action(self.runtime, first['task_id'])['error']['code'], 'event_expired')
        self.assertEqual(self.runtime.get(first['task_id'])['budget']['used']['tool_calls'], 0)

    def test_other_host_backlog_does_not_hide_this_hosts_confirmation(self):
        from graph_research.mcp.user_actions import action_path
        from graph_research.runtime.storage import write_json
        first = self.initial(); self.click(first)
        for index in range(17):
            event_id = f'{index:032x}'
            write_json(action_path(self.runtime, event_id), {
                'version': 1, 'event_id': event_id, 'task_id': first['task_id'],
                'configuration_sha256': 'another-host', 'state': 'queued'})
        with patch.object(self.runtime, '_launch', return_value={'operation': {'status': 'running'}}) as launch:
            self.assertEqual(dispatch_user_actions(self.runtime), 1)
        self.assertEqual(launch.call_count, 1)
        self.assertEqual(queued_action(self.runtime, first['task_id'])['state'], 'delivered')


@unittest.skipUnless(QT, 'Optional PySide6 unavailable')
class NativeApprovalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def test_language_buttons_and_feedback_preserve_values_and_no_automatic_approval(self):
        with tempfile.TemporaryDirectory() as folder:
            panel = TaskApprovalCenter(Path(folder) / 'preferences.json')
            # Construct a pure rendering fixture; no live root is connected.
            pending = {'kind': 'experiment_continue', 'interaction_id': 'a' * 32,
                       'host_actions': ['continue', 'study_feedback'], 'plan': {'runs': [{'id': 'run1', 'method': 'cem', 'seed': 11, 'parameters': {}}]}}
            panel.rows = [{'task_id': 'b' * 32, 'objective': 'n=4 fixed scope', 'status': 'waiting_for_user'}]
            panel.current = {'task': {'task_id': 'b' * 32, 'revision': 5, 'status': 'waiting_for_user',
                                      'interaction': pending, 'terminal': False, 'budget': {}, 'results': [], 'summary': {}}, 'user_action': None}
            try:
                panel.render(); panel.exploration.setValue(.3); panel.answer.setPlainText('preserve raw user note')
                set_language('en')
                self.assertEqual(panel.continue_button.text(), 'Apply feedback and continue')
                self.assertEqual(panel.feedback_button.text(), 'Apply feedback and continue')
                self.assertEqual(panel.exploration.value(), .3)
                self.assertEqual(panel.answer.toPlainText(), 'preserve raw user note')
                self.assertIsNone(panel.service)
                panel.current['user_action'] = {'state': 'queued'}; panel.render_buttons()
                self.assertFalse(panel.continue_button.isEnabled()); self.assertFalse(panel.feedback_button.isEnabled())
            finally:
                set_language('zh'); panel.close(); panel.deleteLater(); self.app.processEvents()


@unittest.skipUnless(QT and SDK and importlib.util.find_spec('torch'), 'Qt, MCP SDK and CPU torch required')
class NativeMCPWireTests(unittest.IsolatedAsyncioTestCase):
    async def test_user_click_and_feedback_automatically_resume_real_cem_over_stdio(self):
        import sys
        app = QApplication.instance() or QApplication([]); app.setQuitOnLastWindowClosed(False)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); state = root / 'state'; state.mkdir()
            parameters = StdioServerParameters(command=sys.executable, args=[
                '-I', '-X', 'utf8', '-m', 'graph_research', 'mcp', '--root', str(state),
                '--user', 'wire-native', '--max-tool-calls', '4', '--confirm-experiments', '--results-root', str(root / 'results')])
            panel = TaskApprovalCenter(root / 'ui.json', root=state, user_id='wire-native')
            async def pump(predicate, seconds=50):
                deadline = time.monotonic() + seconds
                while not predicate():
                    self.assertLess(time.monotonic(), deadline, 'native/MCP wait timed out: ' + str(panel.current)[:1500] + ' / ' + panel.message.text())
                    app.processEvents(); await asyncio.sleep(.015)
            try:
                async with Client(parameters, mode='legacy', cache=None, read_timeout_seconds=30) as client:
                    spec = study('cem'); spec['segment_rounds'] = 1
                    request = study_task(spec); request['request_id'] = 'wire-native-cem'; request['constraints']['max_tool_calls'] = 2
                    first = (await client.call_tool('research_submit', {'task': request})).structured_content
                    identifier = first['task_id']
                    panel.show(); panel.timer.setInterval(100)
                    await pump(lambda: panel.current is not None and panel.current['task']['status'] == 'waiting_for_user' and panel.continue_button.isEnabled())
                    self.assertEqual(panel.current['task']['budget']['used']['tool_calls'], 0)
                    panel.continue_button.click()
                    await pump(lambda: panel.current is not None and panel.current['task']['status'] == 'waiting_for_user'
                               and panel.current['task']['budget']['used']['tool_calls'] == 1 and panel.feedback_button.isEnabled())
                    first_result = (await client.call_tool('research_get', {'task_id': identifier, 'detail': 'full'})).structured_content
                    receipt = first_result['results'][0]['verification']['receipt_sha256']
                    panel.exploration.setValue(.3); panel.penalty.setValue(2.)
                    panel.answer.setPlainText('real native feedback fixture')
                    self.assertEqual(panel.continue_button.text(),'应用参数并继续')
                    panel.continue_button.click()
                    await pump(lambda: panel.current is not None and panel.current['task']['status'] == 'completed')
                    final = (await client.call_tool('research_get', {'task_id': identifier, 'detail': 'full'})).structured_content
                    self.assertEqual(final['budget']['used'], {'model_calls': 0, 'tool_calls': 2})
                    self.assertEqual(final['summary']['experiment']['evaluations_completed'], 8)
                    self.assertTrue(final['summary']['experiment']['training_performed'])
                    self.assertEqual(final['summary']['experiment']['feedback'][-1]['knobs']['exploration'], .3)
                    self.assertEqual(final['results'][0]['verification']['receipt_sha256'], receipt)
                    self.assertGreater(final['results'][1]['data']['checkpoint']['neural']['updates'], final['results'][0]['data']['checkpoint']['neural']['updates'])
                    self.assertEqual(final['results'][1]['arguments']['knobs']['penalty_weight'], 2.)
                    self.assertEqual((await client.list_tools()).tools.__len__(), 13)
            finally:
                panel.timer.stop(); await pump(lambda: panel.thread is None, seconds=10)
                panel.close(); panel.deleteLater(); app.processEvents()


if __name__ == '__main__':
    unittest.main()
