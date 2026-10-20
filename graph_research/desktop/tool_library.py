"""Native persistent-extension manager; no model calls, installs or source edits."""
import json
import sqlite3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QHeaderView
from .widgets import QDialog,QLabel,QLineEdit,QPushButton,QTableWidget,QPlainTextEdit,QMessageBox,QTableWidgetItem
from graph_research.tools.library import ToolLibrary


STATES={'enabled':'已启用 · 实验工具','disabled':'已停用','inactive_version':'历史版本','quarantined':'已隔离','disabled_legacy':'旧扩展 · 未审阅停用'}


class ToolLibraryDialog(QDialog):
    def __init__(self,workspace,parent=None):
        super().__init__(parent);self.workspace=workspace;self.library=ToolLibrary(workspace.tool_directory);self.records=[];self.changed=False
        self.setWindowTitle('扩展工具库');self.resize(900,620)
        layout=QVBoxLayout(self)
        note=QLabel('新工具通过验收后保留在这里。实验工具仅通过所列样例，使用前请核对适用条件。');note.setWordWrap(True);layout.addWidget(note)
        path=QLineEdit(str(workspace.tool_directory));path.setReadOnly(True);path.setToolTip('当前工具库目录，可复制后用于其他入口的--tool-dir配置');path.setCursorPosition(0);layout.addWidget(path)
        row=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('搜索名称、用途或标签');self.search.textChanged.connect(self.filter_rows);row.addWidget(self.search)
        self.refresh_button=QPushButton('刷新');self.refresh_button.clicked.connect(self.refresh);row.addWidget(self.refresh_button);layout.addLayout(row)
        self.table=QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['工具','版本','状态','验收样例']);self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection);self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.show_selection);self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch);layout.addWidget(self.table,1)
        self.details=QPlainTextEdit();self.details.setReadOnly(True);layout.addWidget(self.details,1)
        row=QHBoxLayout();self.activate=QPushButton('启用此版本');self.activate.clicked.connect(lambda:self.select_version(True));row.addWidget(self.activate)
        self.disable=QPushButton('停用此工具');self.disable.clicked.connect(lambda:self.select_version(False));row.addWidget(self.disable)
        self.cases=QPushButton('查看已审阅案例');self.cases.clicked.connect(self.show_cases);row.addWidget(self.cases)
        row.addStretch();close=QPushButton('关闭');close.clicked.connect(self.accept);row.addWidget(close);layout.addLayout(row)
        self.refresh()

    def refresh(self):
        try:
            self.records=[];offset=0
            while True:
                page=self.library.catalog(limit=100,offset=offset);self.records.extend(page['records'])
                if page['next_offset'] is None:break
                offset=page['next_offset']
            self.filter_rows()
        except (OSError,ValueError,RuntimeError,KeyError,TypeError) as error:
            self.table.setRowCount(0);self.details.setPlainText('工具库暂不可读，原包保留：'+str(error));self.activate.setEnabled(False);self.disable.setEnabled(False);self.cases.setEnabled(False)

    def filter_rows(self):
        query=self.search.text().casefold();self.visible=[r for r in self.records if query in json.dumps(r,ensure_ascii=False).casefold()]
        self.table.setRowCount(len(self.visible))
        for index,record in enumerate(self.visible):
            title=record.get('metadata',{}).get('title',record['name']);values=[title+' · '+record['name'],(record.get('version') or '—')[:12],STATES.get(record['state'],record['state']),str(record.get('tests_passed',0))]
            for column,text in enumerate(values):self.table.setItem(index,column,QTableWidgetItem(text,ui=column==2))
        self.table.resizeColumnsToContents()
        if self.visible:self.table.selectRow(0)
        else:self.details.setPlainText('暂无已安装扩展工具。');self.show_selection()

    def selected(self):
        row=self.table.currentRow()
        return self.visible[row] if 0<=row<len(self.visible) else None

    def show_selection(self):
        record=self.selected();valid=bool(record and record['state'] not in ('quarantined','disabled_legacy'))
        self.activate.setEnabled(valid and record['state']!='enabled');self.disable.setEnabled(valid and record.get('active') and record.get('enabled'))
        self.cases.setEnabled(bool(record and self.workspace.session.user_id and self.workspace.session.memory_enabled))
        if record:
            info=record.get('metadata',{});parts=[info.get('title',record['name'])+' · '+record['name'],
                '状态：'+STATES.get(record['state'],record['state']),'',info.get('summary',record.get('description',''))]
            for key,title in (('preconditions','适用条件'),('limitations','限制')):
                if info.get(key):parts.extend(['',title,*('• '+text for text in info[key])])
            if info.get('returns'):parts.extend(['','输出：'+info['returns']])
            parts.extend(['',f"验收：{record.get('tests_passed',0)}个样例通过；不代表一般数学证明。"])
            if record.get('error'):parts.extend(['','隔离原因：'+record['error']])
            if record.get('parameters'):parts.extend(['','输入参数定义（JSON Schema）',json.dumps(record['parameters'],ensure_ascii=False,indent=2)])
            for number,example in enumerate(record.get('examples',[]),1):parts.extend(['',f'样例{number} · 输入',json.dumps(example['arguments'],ensure_ascii=False,indent=2),'预期输出',json.dumps(example.get('expected'),ensure_ascii=False,indent=2)])
            parts.extend(['','版本：'+str(record.get('version') or '未知'),'源码校验：'+str(record.get('source_sha256') or '未知')])
            self.details.setPlainText('\n'.join(parts))

    def select_version(self,enabled):
        record=self.selected()
        if not record:return
        if any(getattr(window,'thread',None) is not None for window in (self.parent(),getattr(self.parent(),'offline',None),getattr(self.parent(),'chat',None))):
            QMessageBox.information(self,'请等待任务结束','当前窗口任务仍在运行，结束后再切换工具版本。');return
        try:
            self.library.select(record['name'],record['version'],enabled=enabled);self.changed=True;self.workspace.refresh_tools();self.refresh()
        except (OSError,ValueError,RuntimeError) as error:QMessageBox.warning(self,'操作未完成',str(error))

    def show_cases(self):
        record=self.selected();session=self.workspace.session
        if not record or not session.user_id or not session.memory_enabled:return
        from graph_research.assistant.experience import search_experiences
        from graph_research.assistant.memory import read_memory_context
        try:
            if not read_memory_context(session.memory_directory,session.user_id)['enabled']:raise ValueError('当前用户已停用记忆。')
            cases=search_experiences(session.memory_directory,session.user_id,tool=record['name'],limit=20)
            self.details.setPlainText('已审阅历史案例；当前窗口未复核原始来源，请通过主agent检索接口核验来源和工具版本。\n'+json.dumps(cases,ensure_ascii=False,indent=2))
        except (OSError,ValueError,sqlite3.Error) as error:self.details.setPlainText(str(error))
