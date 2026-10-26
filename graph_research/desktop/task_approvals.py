"""Native task review: human clicks issue events; refresh only reads state."""
import json
from pathlib import Path

from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot, Qt
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
                              QDoubleSpinBox, QFormLayout, QHeaderView)
from .widgets import (QLabel, QPushButton, QLineEdit, QPlainTextEdit, QComboBox,
                      QTreeWidget, QTreeWidgetItem, QCheckBox, QFileDialog, QMessageBox)
from .i18n import UiText, tr, listen
from graph_research.runtime.storage import read_json, write_json
from graph_research.assistant.task_approvals import TaskApprovals
from graph_research.assistant.approval_state import REQUEST_FILE, read_optional, write_heartbeat


def ui(zh, en):
    return UiText(zh, en)


STATES = {
    'waiting_for_user': ui('等待确认', 'Awaiting user'),
    'waiting_for_approval': ui('等待审批', 'Awaiting approval'),
    'queued': ui('排队中', 'Queued'), 'running': ui('执行中', 'Running'),
    'completed': ui('已完成', 'Completed'), 'partial': ui('部分完成', 'Partial'),
    'interrupted': ui('执行中断', 'Interrupted'), 'cancelled': ui('已结束', 'Cancelled'),
    'rejected': ui('已拒绝', 'Rejected'), 'failed': ui('失败', 'Failed'),
    'budget_exhausted': ui('预算已用尽', 'Budget exhausted')}

OBJECTS = {'simple_graph': ui('普通简单图', 'Simple graph'), 'hypergraph': ui('一般超图', 'Hypergraph'),
           'uniform_hypergraph': ui('一致超图', 'Uniform hypergraph'), 'uniform_hypertree': ui('一致超树', 'Uniform hypertree')}
METRICS = {'edge_count': ui('边数', 'Edge count'), 'alpha_spectral_radius': ui('α谱半径', 'Alpha spectral radius'),
           'adjacency_spectral_radius': ui('邻接谱半径', 'Adjacency spectral radius'),
           'distance_spectral_radius': ui('距离谱半径', 'Distance spectral radius'), 'energy': ui('图能量', 'Graph energy')}
METHODS = {'cem': ui('CEM神经搜索', 'Neural CEM'), 'random': ui('随机搜索', 'Random search'),
           'local': ui('局部搜索', 'Local search'), 'enumerate': ui('精确枚举', 'Exact enumeration')}


PENDING_STATES={'waiting_for_user','waiting_for_approval','interrupted','queued','running'}


def filter_rows(rows,needle='',pending_only=True):
    needle=needle.strip().casefold()
    return [r for r in rows if (not pending_only or r['status'] in PENDING_STATES and r.get('compatible_core',True)) and
        (not needle or needle in (r['objective']+' '+r.get('request_id','')+' '+r['task_id']).casefold())]


def plan_text(task):
    """A readable view plus a separate exact JSON view; no input rewriting."""
    pending = task.get('interaction') or {}
    plan = pending.get('plan') or {}
    exp = task.get('summary', {}).get('experiment', {})
    limits = task.get('budget', {}).get('limits', {})
    used = task.get('budget', {}).get('used', {})
    lines = [tr(ui('说明：', 'Description: ')) + task.get('answer', ''),
             tr(ui('状态：', 'Status: ')) + tr(STATES.get(task['status'], task['status'])),
             '', pending.get('message', ''), '',
             tr(ui('工具调用：', 'Tool calls: ')) + f'{used.get("tool_calls", 0)} / {limits.get("max_tool_calls", "—")}',
             tr(ui('模型调用：', 'Model calls: ')) + f'{used.get("model_calls", 0)} / {limits.get("max_model_calls", "—")}']
    p = plan.get('problem') or {}
    if p:
        obj = p.get('object', {}); objective = p.get('objective', {})
        object_name = tr(OBJECTS.get(obj.get('type'), obj.get('type', '')))
        if 'order' in obj:
            object_name += tr(ui('，顶点数 ', ', order ')) + str(obj['order'])
        if 'uniformity' in obj:
            object_name += tr(ui('，一致度 ', ', uniformity ')) + str(obj['uniformity'])
        metric = tr(METRICS.get(objective.get('metric'), objective.get('metric', '')))
        direction = tr(ui('最大化 ', 'Maximize ')) if objective.get('direction') == 'maximize' else tr(ui('最小化 ', 'Minimize '))
        lines.extend(['', p.get('question', ''),
                      tr(ui('研究对象：', 'Object: ')) + object_name,
                      tr(ui('目标：', 'Objective: ')) + direction + metric,
                      tr(ui('约束：', 'Constraints: ')) + (json.dumps(p['constraints'], ensure_ascii=False) if p.get('constraints') else tr(ui('无额外约束', 'No additional constraints')))])
        if objective.get('arguments'):
            lines.append(tr(ui('目标参数：', 'Objective parameters: ')) + json.dumps(objective['arguments'], ensure_ascii=False))
    b = plan.get('budget') or exp.get('budget', {}).get('limits', {})
    if b:
        lines.extend(['', tr(ui('候选评价上限：', 'Candidate evaluation ceiling: ')) + str(b.get('max_evaluations', '—')),
                      tr(ui('工作进程累计墙钟 / CPU：', 'Cumulative worker wall / CPU: ')) + f'{b.get("wall_seconds", "—")} / {b.get("cpu_seconds", "—")} s',
                      tr(ui('内存上限：', 'Memory ceiling: ')) + str(b.get('memory_mb', '—')) + ' MiB'])
    if 'planned_rounds' in plan:
        lines.append(tr(ui('计划轮数：', 'Planned rounds: ')) + str(plan['planned_rounds']))
    if 'worker_rounds' in plan:
        lines.extend([tr(ui('每代候选数：','Candidates per generation: '))+str(plan['batch_size']),
                      tr(ui('每个计算分段的代数：','Generations per worker: '))+str(plan['worker_rounds']),
                      tr(ui('计划计算调用数：','Planned worker calls: '))+str(plan['planned_calls']),
                      tr(ui('CPU线程数：','CPU threads: '))+str(plan['cpu_threads'])])
    if 'evaluations_completed' in exp:
        lines.append(tr(ui('已完成评价：', 'Completed evaluations: ')) + str(exp['evaluations_completed']))
    for run in plan.get('runs', []):
        lines.append(f'{run["id"]} · {tr(METHODS.get(run["method"], run["method"]))} · seed={run["seed"]} · ' + json.dumps(run['parameters'], ensure_ascii=False))
    for case in plan.get('candidate_collection', []):
        lines.append(f'{case["id"]} · ' + json.dumps(case.get('parameters', {}), ensure_ascii=False)
                     + tr(ui(' · 候选数 ', ' · candidates ')) + str(len(case.get('candidates', []))))
    for q in pending.get('questions', []):
        lines.extend(['', q['text']])
    if pending.get('assessment'):
        lines.extend(['', tr(ui('开发范围与评估：', 'Development scope and assessment: ')),
                      json.dumps(pending['assessment'], ensure_ascii=False, indent=2)])
    if task.get('warnings'):
        lines.extend(['', tr(ui('提示：', 'Notes: ')), *task['warnings']])
    if task.get('error'):
        lines.extend(['', task['error'].get('message', '')])
    if task.get('unverified_progress'):
        progress=task['unverified_progress']
        lines.extend(['',tr(ui('当前分段进度（结束后核验）：','Current segment progress (not verified until completion): '))+
            str(progress.get('evaluations_in_segment',0))+tr(ui(' 次评价',' evaluations'))])
    return '\n'.join(lines)


class ApprovalWorker(QObject):
    done = Signal(object)

    def __init__(self, function):
        super().__init__(); self.function = function

    @Slot()
    def run(self):
        try:
            self.done.emit({'ok': True, 'value': self.function()})
        except Exception as error:
            self.done.emit({'ok': False, 'error': str(error), 'code': getattr(error, 'code', None)})


class TaskApprovalCenter(QWidget):
    activation_requested = Signal()

    def __init__(self, preferences, parent=None, *, root=None, user_id=None):
        super().__init__(parent)
        self.preferences = Path(preferences)
        self.service = None; self.thread = None; self.worker = None
        self.rows = []; self.current = None; self.response = None; self.after = None
        self._rendered = None
        self._requested_task = None; self._request_seen = None
        self._closing = False
        self._feedback_base=None
        saved = {}
        if self.preferences.is_file():
            try:
                saved = read_json(self.preferences, max_bytes=8192)[0]
            except (OSError, ValueError):
                pass
        layout = QVBoxLayout(self); layout.setContentsMargins(18, 18, 18, 18); layout.setSpacing(12)
        title = QLabel(ui('任务审批', 'Task approvals')); title.setObjectName('title')
        layout.addWidget(title)
        connection = QHBoxLayout()
        self.root = QLineEdit(str(root or saved.get('root') or Path.home() / '.graph_research' / 'mcp-state'))
        self.root.setToolTip(ui('MCP配置中的root；这里只连接已有任务，不创建计算。', 'The root from your MCP configuration; connects to existing tasks only.'))
        self.user = QLineEdit(user_id or saved.get('user_id') or 'local-researcher'); self.user.setMaximumWidth(170)
        self.user.setToolTip(ui('与MCP配置中的user保持一致', 'Use the user from your MCP configuration'))
        self.browse = QPushButton(ui('选择目录', 'Browse')); self.browse.clicked.connect(self.browse_root)
        self.connect_button = QPushButton(ui('连接', 'Connect')); self.connect_button.clicked.connect(self.connect_service)
        connection.addWidget(self.root, 1); connection.addWidget(self.browse)
        connection.addWidget(self.user); connection.addWidget(self.connect_button)
        layout.addLayout(connection)
        row = QHBoxLayout()
        self.refresh_button = QPushButton(ui('刷新', 'Refresh')); self.refresh_button.clicked.connect(self.refresh)
        self.status = QLabel(ui('连接后查看待确认任务。', 'Connect to view pending tasks.')); self.status.setWordWrap(True)
        row.addWidget(self.status, 1); row.addWidget(self.refresh_button); layout.addLayout(row)
        filters=QHBoxLayout()
        self.pending_only=QCheckBox(ui('仅待处理任务','Pending tasks only'));self.pending_only.setChecked(True)
        self.search=QLineEdit();self.search.setPlaceholderText(ui('按任务名、请求编号或任务编号搜索','Search title, request ID or task ID'))
        filters.addWidget(self.pending_only);filters.addWidget(self.search,1);layout.addLayout(filters)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tasks = QTreeWidget(); self.tasks.setHeaderLabels([ui('任务', 'Task'), ui('状态', 'Status')])
        self.tasks.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tasks.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tasks.setRootIsDecorated(False); self.tasks.setMinimumWidth(250)
        self.tasks.currentItemChanged.connect(self.selection_changed); splitter.addWidget(self.tasks)
        body = QWidget(); content = QVBoxLayout(body); content.setContentsMargins(10, 0, 0, 0)
        self.title = QLabel(''); self.title.setWordWrap(True); self.title.setObjectName('sectionTitle'); content.addWidget(self.title)
        self.task_identity=QLabel('');self.task_identity.setWordWrap(True);content.addWidget(self.task_identity)
        self.plan = QPlainTextEdit(); self.plan.setReadOnly(True); content.addWidget(self.plan, 1)
        self.show_details = QCheckBox(ui('查看完整计划与当前记录', 'Show full plan and current record'))
        self.show_details.toggled.connect(self.render_text); content.addWidget(self.show_details)
        self.feedback = QWidget(); form = QFormLayout(self.feedback); form.setContentsMargins(0, 0, 0, 0)
        self.exploration = QDoubleSpinBox(); self.exploration.setRange(.01, .5); self.exploration.setSingleStep(.05)
        self.elite = QDoubleSpinBox(); self.elite.setRange(.1, .75); self.elite.setSingleStep(.05)
        self.penalty = QDoubleSpinBox(); self.penalty.setRange(.1, 10); self.penalty.setSingleStep(.1)
        self.focus = QComboBox()
        form.addRow(QLabel(ui('探索比例', 'Exploration')), self.exploration)
        form.addRow(QLabel(ui('精英比例', 'Elite fraction')), self.elite)
        form.addRow(QLabel(ui('约束惩罚权重', 'Constraint penalty weight')), self.penalty)
        form.addRow(QLabel(ui('优先实例', 'Priority run')), self.focus); content.addWidget(self.feedback)
        self.answer = QPlainTextEdit(); self.answer.setMaximumHeight(75)
        self.answer.setPlaceholderText(ui('补充需求或填写反馈说明', 'Answer the question or add a feedback note'))
        content.addWidget(self.answer)
        buttons = QHBoxLayout()
        self.continue_button = QPushButton(ui('确认并开始', 'Confirm and start')); self.continue_button.setObjectName('primary')
        self.feedback_button = QPushButton(ui('应用参数并继续', 'Apply feedback and continue'),self)
        self.answer_button = QPushButton(ui('提交补充', 'Send answer'))
        self.approve_button = QPushButton(ui('批准并继续', 'Approve and continue'))
        self.reject_button = QPushButton(ui('拒绝', 'Reject'))
        self.cancel_button = QPushButton(ui('结束任务', 'End task')); self.cancel_button.setObjectName('stop')
        self.continue_button.clicked.connect(lambda: self.act('continue'))
        self.feedback_button.clicked.connect(lambda: self.act('study_feedback'))
        self.answer_button.clicked.connect(lambda: self.act('answer'))
        self.approve_button.clicked.connect(lambda: self.act('approve'))
        self.reject_button.clicked.connect(lambda: self.act('reject'))
        self.cancel_button.clicked.connect(self.cancel_task)
        self.action_buttons = (self.continue_button, self.feedback_button, self.answer_button,
                               self.approve_button, self.reject_button, self.cancel_button)
        for button in self.action_buttons:
            if button is not self.feedback_button:buttons.addWidget(button)
        self.reset_feedback=QPushButton(ui('撤销本次修改','Reset feedback edits'));self.reset_feedback.clicked.connect(self.reset_feedback_edits)
        buttons.addWidget(self.reset_feedback)
        buttons.addStretch(); content.addLayout(buttons); splitter.addWidget(body)
        splitter.setSizes([300, 720]); layout.addWidget(splitter, 1)
        self.message = QLabel(''); self.message.setWordWrap(True); layout.addWidget(self.message)
        self.timer = QTimer(self); self.timer.setInterval(2000); self.timer.timeout.connect(self.refresh)
        self.heartbeat = QTimer(self); self.heartbeat.setInterval(2000); self.heartbeat.timeout.connect(self.check_activation)
        self.root.textChanged.connect(self.connection_edited); self.user.textChanged.connect(self.connection_edited)
        self.pending_only.toggled.connect(self.refresh);self.search.textChanged.connect(self.refresh)
        for field in (self.exploration,self.elite,self.penalty):field.valueChanged.connect(self.render_buttons)
        self.focus.currentIndexChanged.connect(self.render_buttons);self.answer.textChanged.connect(self.render_buttons)
        listen(self.language_changed); self.render()

    def connection_edited(self):
        self.service = None; self.rows = []; self.current = None; self._rendered = None
        self.status.setText(ui('连接信息已更改，请点击连接。', 'Connection details changed; click Connect.'))
        self.render(); self.controls(self.thread is None)

    def browse_root(self):
        value = QFileDialog.getExistingDirectory(self, tr(ui('选择MCP任务目录', 'Choose MCP task directory')), self.root.text())
        if value:
            self.root.setText(value)

    def start(self, function, after):
        if self.thread is not None or self._closing:
            return
        self.after = after; self.response = None
        self.thread = QThread(self); self.worker = ApprovalWorker(function); self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run); self.worker.done.connect(self.received, Qt.ConnectionType.QueuedConnection)
        self.worker.done.connect(self.thread.quit, Qt.ConnectionType.DirectConnection); self.worker.done.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.finished, Qt.ConnectionType.QueuedConnection); self.controls(False); self.thread.start()

    @Slot(object)
    def received(self, result):
        self.response = result

    @Slot()
    def finished(self):
        if self.thread is None:return
        if not self.thread.wait(50):
            QTimer.singleShot(50,self.finished);return
        thread = self.thread; self.thread = None; self.worker = None; thread.deleteLater()
        response = self.response; after = self.after; self.after = None; self.controls(True)
        if not response or not response['ok']:
            self.message.setText((response or {}).get('error', tr(ui('操作未完成，请刷新查看状态。', 'Action incomplete; refresh to inspect state.'))))
            return
        if self._closing:return
        try:after(response['value'])
        except Exception as error:
            from .native_diagnostics import note
            note('approval callback failed: '+type(error).__name__)
            self.message.setText(str(error))

    def controls(self, enabled):
        for widget in (self.root, self.user, self.browse, self.connect_button, self.tasks,self.search,self.pending_only):
            widget.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled and self.service is not None)
        self.render_buttons()

    def connect_service(self):
        root = self.root.text().strip(); user = self.user.text().strip()
        if not root or not user:
            return
        def connect():
            service = TaskApprovals(root, user)
            rows = service.list_tasks()
            write_json(self.preferences, {'version': 1, 'root': str(service.root), 'user_id': user})
            return service, rows
        def connected(result):
            self.service, _ = result; self.current = None; self._rendered = None
            self.heartbeat.start();self.check_activation()
            self.message.setText('' if result[1] else ui('这个用户下尚未找到MCP任务；请核对root和user，user不是目录哈希名。提交新任务后会自动显示。','No MCP tasks found for this user. Check root and user; user is not the directory hash. New submitted tasks will appear automatically.')); self.refresh()
        self.start(connect, connected)

    def selected_id(self):
        item = self.tasks.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def refresh(self,*unused):
        if self.thread is not None or self.service is None:
            return
        selected = self._requested_task or self.selected_id() or (self.current['task']['task_id'] if self.current else None); service = self.service
        needle=self.search.text();pending_only=self.pending_only.isChecked()
        def read():
            rows = service.list_tasks()
            visible=filter_rows(rows,needle,pending_only)
            target = selected if any(r['task_id'] == selected for r in visible) else (visible[0]['task_id'] if visible else None)
            if target is None and selected and not needle and any(r['task_id']==selected for r in rows):target=selected
            return rows, service.get(target) if target else None
        self.start(read, self.loaded)

    def loaded(self, result):
        self.rows, self.current = result
        if self.current and self.current['task']['task_id']==self._requested_task:self._requested_task=None
        self.render()

    @Slot()
    def check_activation(self):
        if self.service is None or self._closing:return
        directory=self.service.reader.directory
        try:
            write_heartbeat(directory)
            request=read_optional(directory/REQUEST_FILE)
            if request.get('request_id') and request['request_id']!=self._request_seen:
                self._request_seen=request['request_id'];self._requested_task=request.get('task_id')
                self.search.blockSignals(True);self.search.clear();self.search.blockSignals(False)
                self.pending_only.blockSignals(True);self.pending_only.setChecked(True);self.pending_only.blockSignals(False)
                self.activation_requested.emit();self.refresh()
        except (OSError,RuntimeError,ValueError):pass

    def shutdown(self):
        self._closing=True;self.timer.stop();self.heartbeat.stop()
        if self.service is not None:
            try:
                write_heartbeat(self.service.reader.directory, closed=True)
            except (OSError,RuntimeError,ValueError):pass

    def render(self):
        selected = self.current['task']['task_id'] if self.current else self.selected_id()
        self.tasks.blockSignals(True); self.tasks.clear()
        for row in filter_rows(self.rows,self.search.text(),self.pending_only.isChecked()):
            item = QTreeWidgetItem([row['objective'], tr(STATES.get(row['status'], row['status']))])
            item.setToolTip(0,row.get('request_id','')+'\n'+row['task_id'])
            item.setData(0, Qt.ItemDataRole.UserRole, row['task_id']); self.tasks.addTopLevelItem(item)
            if row['task_id'] == selected:
                self.tasks.setCurrentItem(item)
        self.tasks.blockSignals(False)
        if not self.current:
            self.title.setText(ui('暂无匹配的待处理任务', 'No matching pending task'));self.task_identity.setText('');self.plan.clear()
        else:
            task = self.current['task']; pending = task.get('interaction') or {}
            identity = (task['task_id'], task['revision'])
            if identity != self._rendered:
                if self._rendered is None or self._rendered[0] != task['task_id']:
                    self.answer.clear()
                self._rendered = identity
                knobs = {'exploration': .1, 'elite_fraction': .25, 'penalty_weight': 1.}
                knobs.update(task.get('ui_knobs',{}))
                for result in task.get('results', []):
                    knobs.update(result.get('arguments', {}).get('knobs', {}))
                self.exploration.setValue(knobs['exploration']); self.elite.setValue(knobs['elite_fraction']); self.penalty.setValue(knobs['penalty_weight'])
                self.focus.clear(); self.focus.addItem(ui('保持当前优先级', 'Keep current priority'), None)
                for run in pending.get('plan', {}).get('runs', []):
                    self.focus.addItem(run['id'], run['id'])
                self._feedback_base={'exploration':self.exploration.value(),'elite_fraction':self.elite.value(),'penalty_weight':self.penalty.value()}
            row = next((r for r in self.rows if r['task_id'] == task['task_id']), {})
            self.title.setText(row.get('objective') or task.get('request_id', ''))
            self.task_identity.setText(task.get('request_id','')+' · '+task['task_id'][:8])
            self.render_text()
        self.render_buttons()

    def render_text(self, *unused):
        if not self.current:
            return
        task = self.current['task']
        self.plan.setPlainText(json.dumps(task, ensure_ascii=False, indent=2) if self.show_details.isChecked() else plan_text(task))

    def render_buttons(self):
        task = self.current['task'] if self.current else {}
        pending = task.get('interaction') or {}; actions = pending.get('host_actions', [])
        delivery = (self.current or {}).get('user_action') or {}
        busy = self.thread is not None or task.get('transport', {}).get('active') or delivery.get('state') == 'queued' or task.get('compatible_core') is False
        for button, action in [(self.continue_button, 'continue'), (self.feedback_button, 'study_feedback'),
                               (self.answer_button, 'answer'), (self.approve_button, 'approve'), (self.reject_button, 'reject')]:
            visible = action in actions or action == 'answer' and 'revise' in actions
            button.setVisible(visible and button is not self.feedback_button); button.setEnabled(visible and not busy)
        self.feedback.setVisible('study_feedback' in actions)
        self.feedback.setEnabled(not busy)
        self.answer.setVisible(any(a in actions for a in ('answer', 'revise', 'study_feedback')))
        self.answer.setEnabled(not busy)
        self.cancel_button.setVisible(bool(task) and not task.get('terminal', True) and task.get('status') != 'cancelled')
        self.cancel_button.setEnabled(self.thread is None and bool(task))
        dirty='study_feedback' in actions and self.feedback_dirty()
        self.continue_button.setText(ui('应用参数并继续','Apply feedback and continue') if dirty else
            ui('确认并开始', 'Confirm and start') if pending.get('kind') == 'experiment_review' else ui('继续执行', 'Continue'))
        self.reset_feedback.setVisible(dirty);self.reset_feedback.setEnabled(not busy)
        self.cancel_button.setText(ui('取消此任务（不执行）','Cancel without running') if pending.get('kind')=='experiment_review' else ui('结束任务','End task'))
        if delivery.get('state') == 'queued':
            self.status.setText(ui('确认已保存，等待对应MCP服务接收；若一直等待，请重启已更新的MCP连接。', 'Confirmation saved; waiting for the matching MCP service. Restart the updated MCP connection if it stays queued.'))
        elif delivery.get('state') == 'rejected':
            self.status.setText(ui('本次用户操作未送达，请查看原因并刷新。', 'The user action was rejected; inspect the reason and refresh.'))
            self.message.setText(delivery.get('error', {}).get('message', ''))
        elif task.get('transport', {}).get('active'):
            self.status.setText(ui('后台正在执行或保存记录，请稍候。', 'The background task is executing or saving records.'))
        elif task:
            self.status.setText(ui('状态自动刷新；点击确认后原任务继续执行。', 'Status refreshes automatically. Confirm to continue the original task.'))
        elif self.service is not None:
            self.status.setText(ui('暂无待处理任务；可关闭“仅待处理任务”查看历史。','No pending tasks. Clear Pending tasks only to view history.'))

    def selection_changed(self, item, previous):
        if item and self.thread is None and self.service is not None:
            task_id = item.data(0, Qt.ItemDataRole.UserRole)
            self.start(lambda: self.service.get(task_id), lambda value: self.loaded((self.rows, value)))

    def feedback_dirty(self):
        values={'exploration':self.exploration.value(),'elite_fraction':self.elite.value(),'penalty_weight':self.penalty.value()}
        return bool(self._feedback_base and (values!=self._feedback_base or self.focus.currentData() is not None or self.answer.toPlainText().strip()))

    def reset_feedback_edits(self):
        if self._feedback_base is None:return
        self.exploration.setValue(self._feedback_base['exploration']);self.elite.setValue(self._feedback_base['elite_fraction']);self.penalty.setValue(self._feedback_base['penalty_weight'])
        self.focus.setCurrentIndex(0);self.answer.clear();self.render_buttons()

    def act(self, action):
        if self.current is None or self.thread is not None:
            return
        task = self.current['task']; pending = task.get('interaction') or {}
        if action=='continue' and 'study_feedback' in pending.get('host_actions',[]) and self.feedback_dirty():action='study_feedback'
        if pending.get('kind') == 'resume' and QMessageBox.question(self,
                ui('继续未完成任务', 'Resume incomplete task'),
                ui('已核验结果将复用。未核验或失败的步骤可能重试，先前预算保留，重试另计尝试。是否继续？',
                   'Verified results will be reused. Unverified or failed steps may be retried; previous charges remain and retries consume additional attempts. Continue?')) != QMessageBox.StandardButton.Yes:
            return
        payload = None
        if action == 'study_feedback':
            knobs={'exploration': self.exploration.value(), 'elite_fraction': self.elite.value(), 'penalty_weight': self.penalty.value()}
            payload = {'knobs': {k:v for k,v in knobs.items() if self._feedback_base is None or self._feedback_base.get(k)!=v}, 'note': self.answer.toPlainText()}
            if self.focus.currentData():
                payload['focus_runs'] = [self.focus.currentData()]
        elif action == 'answer':
            payload = self.answer.toPlainText()
        self.message.setText('')
        self.start(lambda: self.service.act(task['task_id'], pending.get('interaction_id'), task['revision'], action, payload), self.action_queued)

    def action_queued(self, item):
        self.message.setText(ui('操作已保存，无需复制事件编号。', 'Action saved; no event ID needs to be copied.'))
        self.refresh()

    def cancel_task(self):
        if not self.current or self.thread is not None:
            return
        if QMessageBox.question(self, ui('结束任务', 'End task'),
                ui('结束当前任务并保留已完成结果？', 'End this task and keep completed results?')) != QMessageBox.StandardButton.Yes:
            return
        task = self.current['task']
        self.start(lambda: self.service.cancel(task['task_id'], task['revision']), lambda value: self.refresh())

    def language_changed(self):
        self.render()

    def showEvent(self, event):
        super().showEvent(event); self.timer.start()
        if self.service is None and Path(self.root.text()).is_dir():
            self.connect_service()
        else:
            self.refresh()

    def hideEvent(self, event):
        self.timer.stop(); super().hideEvent(event)

    def closeEvent(self, event):
        if self.thread is not None:
            event.ignore()
        else:
            self.shutdown(); event.accept()


def approvals_command(arguments):
    import argparse
    from PySide6.QtWidgets import QApplication
    from .widgets import QMainWindow, language_menu, QtLanguageController
    from .app import STYLE, app_icon, desktop_palette
    from .i18n import initialize
    parser = argparse.ArgumentParser(description='Native trusted task approvals; no manual event IDs')
    parser.add_argument('--root'); parser.add_argument('--user'); parser.add_argument('--task'); parser.add_argument('--language', choices=('zh', 'en'))
    options = parser.parse_args(arguments); initialize(options.language)
    from .native_diagnostics import install,note
    install()
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    app.setStyle('Fusion'); app.setPalette(desktop_palette()); app.setStyleSheet(STYLE)
    app._language_controller = QtLanguageController(app)
    class Window(QMainWindow):
        def closeEvent(self, event):
            if self.centralWidget().thread is not None:
                event.ignore()
            else:
                self.centralWidget().shutdown();note('approval window closed by user');event.accept();QTimer.singleShot(0,app.quit)
    window = Window(); window.setWindowTitle(ui('图论科研助手 · 任务审批', 'Graph Research Assistant · Task approvals'))
    window.setWindowIcon(app_icon()); window.resize(1100, 760); window.setMinimumSize(860, 600)
    center=TaskApprovalCenter(Path.home() / '.graph_research' / 'task-approvals.json', root=options.root, user_id=options.user)
    center._requested_task=options.task
    window.setCentralWidget(center)
    def activate():
        window.showNormal();window.raise_();window.activateWindow()
    center.activation_requested.connect(activate)
    app._approval_window=window
    language_menu(window); window.show()
    return app.exec()
