"""Native trusted-user adapter. Never register this adapter as model tools."""
import copy

from graph_research.runtime.integrity import assert_integrity
from graph_research.runtime.storage import safe_path, exclusive_lock
from .task_contract import TaskProtocolError, check_id
from .subagent import SubagentUserPortal
from .approval_state import compatible_core, read_optional


class TaskApprovals:
    def __init__(self, root, user_id):
        from graph_research.mcp.runtime import HostConfiguration, MCPResearchRuntime
        self.root = safe_path(root)
        if not self.root.is_dir():
            raise ValueError('任务目录不存在，请选择MCP配置中的root。')
        from .memory import _user_key
        if not isinstance(user_id,str) or not user_id.strip():raise ValueError('MCP用户标识不能为空。')
        if not (self.root/'users'/_user_key(user_id)[:32]).is_dir():
            raise TaskProtocolError('approval_user_not_found','未找到这个MCP用户。请填写MCP启动参数中的user，不是users目录下的哈希名；没有创建新用户或任务。')
        self.user_id = user_id
        from graph_research.runtime.integrity import CORE,sha256
        self.core_pin=sha256(CORE/'_integrity.json')
        self.reader = MCPResearchRuntime(HostConfiguration(str(self.root), user_id))

    def compatible(self,record):
        return compatible_core(record,self.core_pin)

    def _runtime(self, task_id):
        from graph_research.mcp.runtime import HostConfiguration, MCPResearchRuntime
        task_id = check_id(task_id)
        entry = self.reader._current_job(task_id)
        if not entry:
            raise TaskProtocolError('not_mcp_task', '此任务没有MCP宿主记录，请使用其原有用户入口。')
        configuration = HostConfiguration.from_public(entry[1]['configuration'])
        if safe_path(configuration.root) != self.root or configuration.user_id != self.user_id:
            raise TaskProtocolError('host_scope_mismatch', '任务的宿主目录或用户不匹配。')
        return MCPResearchRuntime(configuration)

    def list_tasks(self):
        rows = self.reader.list_tasks(limit=1000)['tasks']
        return [{**row,'compatible_core':self.compatible(self.reader.service.read(row['task_id']))} for row in rows if self.reader._current_job(row['task_id'])]

    def get(self, task_id):
        from graph_research.mcp.user_actions import queued_action
        runtime = self._runtime(task_id)
        value = self._review(runtime,task_id)
        if not value['compatible_core']:value['warnings'].append('此任务绑定旧版核心，只供查看；请为新版提交新任务，不改写旧检查点。')
        return {'task': value, 'user_action': queued_action(runtime, task_id)}

    def _review(self,runtime,task_id):
        """Review metadata only; polling must not load all candidate histories."""
        from .subagent import TERMINAL
        record=runtime.service.read(task_id);entry=runtime._current_job(task_id)
        pending=copy.deepcopy(record.get('pending'));progress=record.get('study_display',{})
        active=runtime._live(entry);inflight=None
        if active and record.get('study_ledger',{}).get('attempts'):
            attempt=record['study_ledger']['attempts'][-1]
            progress_path=safe_path(runtime.service.task_dir(task_id)/'session/tasks'/('task_'+attempt['id'])/'outputs/search-progress.json',root=runtime.service.task_dir(task_id)/'session/tasks')
            inflight=read_optional(progress_path)
        return {'task_id':task_id,'request_id':record['request']['request_id'],'revision':record['revision'],
            'status':record['status'],'terminal':record['status'] in TERMINAL,
            'answer':(pending or {}).get('message',record['request']['objective']),'interaction':pending,
            'results':[],'ui_knobs':copy.deepcopy(progress.get('knobs',{})),
            'budget':{'limits':record['policy'],'used':dict(record['usage'])},
            'summary':{'experiment':copy.deepcopy(progress)},
            'transport':{'active':active},'unverified_progress':inflight,
            'compatible_core':self.compatible(record),
            'warnings':[], 'error':entry[1].get('error') if entry else None}

    def act(self, task_id, interaction_id, revision, action, payload=None):
        """One actual UI action, pinned to the exact task the user reviewed."""
        from graph_research.mcp.user_actions import enqueue, queued_action
        assert_integrity()
        runtime = self._runtime(task_id)
        with exclusive_lock(runtime.directory / '.dispatch.lock'):
            if not self.compatible(runtime.service.read(task_id)):raise TaskProtocolError('study_core_changed','旧版核心任务只供查看，请为新版提交新任务。')
            value = self._review(runtime,task_id)
            pending = value.get('interaction') or {}
            if (value['revision'] != revision or pending.get('interaction_id') != interaction_id
                    or value.get('transport', {}).get('active')):
                raise TaskProtocolError('stale_interaction', '任务已变化或仍在执行，请刷新后操作。')
            previous = queued_action(runtime, task_id)
            if previous and previous['state'] == 'queued':
                raise TaskProtocolError('user_action_pending', '已有用户操作等待宿主接收，请勿重复点击。')
            portal = SubagentUserPortal(runtime.service)
            common = (task_id, interaction_id, revision)
            if action == 'continue':
                event = portal.continue_task(*common)
            elif action == 'study_feedback':
                event = portal.study_feedback(*common, payload)
            elif action in ('answer', 'revise'):
                event = portal.answer(*common, payload)
            elif action in ('approve', 'reject'):
                args = (*common, pending['assessment_id'], pending['scope_sha256'])
                event = portal.approve(*args) if action == 'approve' else portal.reject(*args)
            else:
                raise TaskProtocolError('event_not_allowed', '不支持此用户操作。')
            # The native app only signs/enqueues. The original MCP process
            # resumes using its own environment, API credentials and limits.
            return enqueue(runtime, event)

    def cancel(self, task_id, revision):
        runtime = self._runtime(task_id)
        if runtime.get(task_id)['revision'] != revision:
            raise TaskProtocolError('stale_interaction', '任务已变化，请刷新后再结束。')
        return runtime.cancel(task_id)
