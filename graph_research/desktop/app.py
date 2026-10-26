"""Native desktop workbench. Qt widgets only; no browser engine or HTTP server."""
import argparse
import copy
import json
from pathlib import Path
from threading import Event
import time
from html import escape

import jsonschema
from shiboken6 import isValid
from PySide6.QtCore import Qt,QObject,QThread,Signal,QTimer,QUrl
from PySide6.QtGui import QColor,QIcon,QPainter,QPen,QPixmap,QDesktopServices,QPalette
from PySide6.QtWidgets import QApplication,QWidget,QFrame,QVBoxLayout,QHBoxLayout,QGridLayout,QSplitter,QScrollArea,QListWidget,QHeaderView,QProgressBar,QSizePolicy
from .widgets import QMainWindow,QLabel,QPushButton,QLineEdit,QPlainTextEdit,QComboBox,QCheckBox,QTabWidget,QTreeWidget,QTreeWidgetItem,QListWidgetItem,QTableWidget,QFileDialog,QMessageBox,QToolButton,QTableWidgetItem

from graph_research.assistant.offline import parse_parameter,read_arguments,validation_message
from graph_research.rendering.results import TITLES,LABELS,METRIC_KEYS,display_value,display_field,display_error,terminal_result
from graph_research.tools.input_guides import input_guide,compact
from graph_research.runtime.storage import staged_file,safe_path,read_json
from .service import DesktopWorkspace
from .localization import parameter_title,option_presentation
from .i18n import listen
from .graph_text import graph_summary,preview_title,mapping_text


STYLE='''
QMainWindow,QDialog{background:#f3f6f8;color:#20353f;font-family:"Microsoft YaHei";font-size:13px}
QWidget{font-family:"Microsoft YaHei";font-size:13px}QLabel{color:#263e47}QLabel#brand{color:#eef7f7;font-size:19px;font-weight:600}
QFrame#sidebar{background:#18323c;border-radius:0}QFrame#sidebar QLabel{color:#b5cbd2}QTreeWidget#tools{background:transparent;border:none;color:#e5eff1;font-size:13px;outline:0}
QTreeWidget#tools::item{padding:8px 4px;border-radius:5px}QTreeWidget#tools::item:selected{background:#30535d;color:white}QTreeWidget#tools::item:hover{background:#25464f}
QListWidget#recent{background:transparent;color:#d5e5e9;border:none;outline:0}QListWidget#recent::item{padding:7px 4px}QListWidget#recent::item:selected{background:#30535d;color:white}
QFrame#panel,QFrame#metric{background:white;border:1px solid #dfe8eb;border-radius:10px}QFrame#metric{background:#f5f9f9}
QLabel#title{font-size:22px;font-weight:600;color:#19363c}QLabel#sectionTitle{font-size:17px;font-weight:600}QLabel#muted{color:#647c85;font-size:12px}
QLabel#value{font-size:24px;color:#126c62;font-weight:600}
QToolButton{border:none;background:transparent;color:#617b84;padding:3px 0;text-align:left}QToolButton:hover{color:#176f65}
QPushButton{background:white;border:1px solid #ccdce1;border-radius:6px;padding:8px 13px;color:#27434d}QPushButton:hover{background:#eaf3f2}
QPushButton:disabled{color:#99aaaf;background:#f0f3f4;border-color:#e1e6e8}QPushButton#primary{background:#176f65;color:white;border-color:#176f65;font-weight:600}
QPushButton#primary:hover{background:#115e56}QPushButton#stop{color:#aa483e;border-color:#dcbfb9}QLineEdit,QComboBox,QPlainTextEdit{background:white;border:1px solid #cddce1;border-radius:5px;padding:7px;color:#243e49;selection-background-color:#c0e0d6}
QPushButton#primary:disabled{background:#b5cbc5;color:#f8fbfa;border-color:#b5cbc5}
QLineEdit:focus,QComboBox:focus,QPlainTextEdit:focus{border-color:#248d7e}QLineEdit:disabled,QComboBox:disabled,QPlainTextEdit:disabled{color:#8a9ca3;background:#f1f4f5}
QFrame#sidebar QLineEdit{background:#25464f;color:white;border:1px solid #3c5f68}QScrollArea{background:transparent;border:none}QTabWidget::pane{border:1px solid #dee7eb;background:white;border-radius:7px}
QTabBar::tab{padding:9px 14px;margin-right:3px;color:#5a737d;background:#e9f0f3;border-top-left-radius:5px;border-top-right-radius:5px}
QTabBar::tab:selected{background:white;color:#126e63;font-weight:600}QTableWidget{background:white;border:1px solid #e0e8ec;gridline-color:#e4ebee;selection-background-color:#ddf0e9;selection-color:#183d35}
QHeaderView::section{background:#f0f5f7;padding:7px;border:none;border-bottom:1px solid #dce6ea;color:#536d79}QProgressBar{border:none;background:#e4eeed;height:5px;border-radius:2px}QProgressBar::chunk{background:#3d9988;border-radius:2px}
QMenuBar{background:#f7fafb;padding:4px;color:#344f5a}QStatusBar{background:#eef3f5;color:#5b747f}QSplitter::handle{background:#e4ecef;width:4px}
'''


def app_icon():
    pixmap=QPixmap(64,64);pixmap.fill(QColor('#183c43'));painter=QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing);painter.setPen(QPen(QColor('#a7e3cc'),3))
    points=[(16,46),(17,18),(45,15),(47,45),(31,32)]
    for a,b in [(0,1),(1,2),(2,3),(3,0),(0,4),(2,4)]:painter.drawLine(*points[a],*points[b])
    painter.setBrush(QColor('#e8fff5'));painter.setPen(Qt.PenStyle.NoPen)
    for x,y in points:painter.drawEllipse(x-4,y-4,8,8)
    painter.end();return QIcon(pixmap)


def desktop_palette():
    palette=QPalette()
    for role,color in [(QPalette.ColorRole.Window,'#f3f6f8'),(QPalette.ColorRole.WindowText,'#20353f'),
        (QPalette.ColorRole.Base,'#ffffff'),(QPalette.ColorRole.AlternateBase,'#f2f7f8'),
        (QPalette.ColorRole.Text,'#243e49'),(QPalette.ColorRole.Button,'#f5f8fa'),(QPalette.ColorRole.ButtonText,'#27434d'),
        (QPalette.ColorRole.Highlight,'#b7ddcf'),(QPalette.ColorRole.HighlightedText,'#173f35'),
        (QPalette.ColorRole.ToolTipBase,'#ffffff'),(QPalette.ColorRole.ToolTipText,'#20353f')]:palette.setColor(role,QColor(color))
    return palette


def label(text,object_name=None,*,raw=False):
    result=QLabel();result.setProperty('i18n_raw',raw);result.setText(text);result.setWordWrap(True);result.setTextFormat(Qt.TextFormat.PlainText)
    if object_name:result.setObjectName(object_name)
    return result


def scroll_panel(widget):
    area=QScrollArea();area.setWidgetResizable(True);area.setWidget(widget);return area


class ParameterField(QWidget):
    def __init__(self,name,schema,guide,required,definition=None):
        super().__init__();self.name=name;self.schema=schema;self.required=required
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Minimum)
        definition=definition or {}
        layout=QVBoxLayout(self);layout.setContentsMargins(0,4,0,12);layout.setSpacing(6)
        row=QHBoxLayout();self.enabled=QCheckBox();self.enabled.setChecked(required or 'default' in schema)
        self.enabled.setEnabled(not required);row.addWidget(self.enabled)
        row.addWidget(label(parameter_title(definition,name)+' · '+name+('  必填' if required else '  可选')),1);layout.addLayout(row)
        if 'enum' in schema:
            self.editor=QComboBox()
            for value in schema['enum']:
                title,hint=option_presentation(definition,name,value)
                self.editor.addItem(title+' · '+str(value) if title!=str(value) else title,value)
                self.editor.setItemData(self.editor.count()-1,hint,Qt.ItemDataRole.ToolTipRole)
        elif schema.get('type')=='boolean':
            self.editor=QComboBox();self.editor.addItem('否',False);self.editor.addItem('是',True)
        elif schema.get('type') in ('array','object'):
            self.editor=QPlainTextEdit();self.editor.setMaximumHeight(95);self.editor.setMinimumHeight(65)
            self.editor.setPlaceholderText(guide.get('input_example') or '请填写JSON数据')
        else:
            self.editor=QLineEdit();self.editor.setPlaceholderText('例如：'+str(guide.get('input_example') or ''))
        if schema.get('type')=='boolean':
            for index,prefix in enumerate(('关闭：','启用：')):
                self.editor.setItemData(index,prefix+schema.get('description','此选项'),Qt.ItemDataRole.ToolTipRole)
        if isinstance(self.editor,QComboBox):
            self.editor.view().setMouseTracking(True)
            self.editor.currentIndexChanged.connect(lambda index:self.editor.setToolTip(self.editor.itemData(index,Qt.ItemDataRole.ToolTipRole) or ''))
            self.editor.setToolTip(self.editor.itemData(self.editor.currentIndex(),Qt.ItemDataRole.ToolTipRole) or '')
        else:self.editor.setToolTip(schema.get('description',''))
        layout.addWidget(self.editor)
        description=schema.get('description','')+'\n'+guide['format']+'\n'+guide['omission']
        example=guide.get('input_example')
        if example is not None:description+='\n输入例子：'+example
        brief=schema.get('description','').split('。')[0][:105]
        if not isinstance(self.editor,QComboBox) and example is not None:brief+='\n例如：'+example[:120]+(' …' if len(example)>120 else '')
        layout.addWidget(label(brief,'muted'))
        self.help=label(description,'muted');self.help.hide()
        self.help_toggle=QToolButton();self.help_toggle.setText('说明与示例');self.help_toggle.setCheckable(True)
        self.help_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon);self.help_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.help_toggle.toggled.connect(lambda checked:self.help_toggle.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow))
        self.help_toggle.toggled.connect(self.help.setVisible);layout.addWidget(self.help_toggle);layout.addWidget(self.help)
        self.enabled.toggled.connect(self.editor.setEnabled);self.editor.setEnabled(self.enabled.isChecked())
        if 'default' in schema:self.set_value(schema['default'])
        self.help_toggle.toggled.connect(self._reflow);listen(self._reflow)
        QTimer.singleShot(0,self._reflow)

    def _reflow(self,*_):
        """Let the scroll area grow fields when translated help wraps to more lines."""
        if not isValid(self):return
        layout=self.layout();layout.invalidate()
        needed=max(layout.minimumSize().height(),layout.heightForWidth(max(100,self.width())))
        if needed>=0 and needed!=self.minimumHeight():self.setMinimumHeight(needed)

    def resizeEvent(self,event):
        super().resizeEvent(event);self._reflow()

    def set_value(self,value):
        self.enabled.setChecked(True)
        if isinstance(self.editor,QComboBox):
            for i in range(self.editor.count()):
                if type(self.editor.itemData(i)) is type(value) and self.editor.itemData(i)==value:self.editor.setCurrentIndex(i);return
            raise ValueError('参数'+self.name+'不在选项中')
        text=value if isinstance(value,str) else compact(value)
        if isinstance(self.editor,QPlainTextEdit):self.editor.setPlainText(text)
        else:self.editor.setText(text)

    def read(self):
        if isinstance(self.editor,QComboBox):return copy.deepcopy(self.editor.currentData())
        text=self.editor.toPlainText() if isinstance(self.editor,QPlainTextEdit) else self.editor.text()
        if not text.strip():raise ValueError('请填写参数 '+self.name)
        return parse_parameter(text,self.schema)

    def snapshot(self):
        value=self.editor.currentData() if isinstance(self.editor,QComboBox) else self.editor.toPlainText() if isinstance(self.editor,QPlainTextEdit) else self.editor.text()
        return {'enabled':self.enabled.isChecked(),'value':value}

    def restore(self,state):
        if isinstance(self.editor,QComboBox):self.set_value(state['value'])
        elif isinstance(self.editor,QPlainTextEdit):self.editor.setPlainText(state['value'])
        else:self.editor.setText(state['value'])
        self.enabled.setChecked(state['enabled'])


class CalculationWorker(QObject):
    done=Signal(object)
    def __init__(self,session,name,arguments,graph_inputs=None):
        super().__init__();self.session=session;self.name=name;self.arguments=copy.deepcopy(arguments);self.cancel_event=Event()
        self.graph_inputs=graph_inputs
    def run(self):
        try:
            function=getattr(self.session,'call_tool',None) or self.session.present_graph
            result=function(self.name,self.arguments,cancel_event=self.cancel_event,**({'graph_inputs':self.graph_inputs} if self.graph_inputs else {}))
        except Exception as exc:result={'tool':self.name,'arguments':self.arguments,'ok':False,'error':str(exc),'not_recorded':True}
        self.done.emit(result)


class ImagePreview(QLabel):
    def __init__(self):
        super().__init__('选择图像文件后在这里预览');self.original=None
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter);self.setMinimumHeight(220)
        self.setStyleSheet('background:white;border:1px solid #e0e8ed;border-radius:7px;color:#6c8088;padding:12px')
    def show_image(self,path):
        pixmap=QPixmap(str(path))
        if pixmap.isNull():self.original=None;self.setText('此文件不是可预览图像，可通过“保存附件”导出。');return
        self.original=pixmap;self._fit()
    def _fit(self):
        if self.original is not None:self.setPixmap(self.original.scaled(max(40,self.width()-28),max(40,self.height()-28),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
    def resizeEvent(self,event):super().resizeEvent(event);self._fit()


class DesktopWindow(QMainWindow):
    # Chat results can request the same local workflow without altering model sessions.
    local_graph_call=Signal(object)
    def __init__(self,workspace):
        super().__init__();self.workspace=workspace;self.current_tool=None;self.fields={};self.drafts={};self.observation=None
        self.thread=None;self.worker=None;self.started=0;self.close_after=False;self._files=[];self._table_fields={}
        self.graph_bindings={};self.graph_drafts={};self.input_graph=None
        from .english import register_registry
        register_registry(workspace.registry)
        self.setWindowTitle('图论科研助手 · 桌面版');self.setWindowIcon(app_icon());self.setMinimumSize(1020,650)
        geometry=QApplication.primaryScreen().availableGeometry();self.resize(min(1480,geometry.width()-40),min(940,geometry.height()-60))
        self._build();self._menus();self._fill_tools();self.refresh_history()
        from .results_center import RESULT_EVENTS
        RESULT_EVENTS.changed.connect(self.results_updated)
        self.timer=QTimer(self);self.timer.timeout.connect(self._tick)
        first='graph_invariants' if 'graph_invariants' in self.workspace.registry.tools else next(iter(self.workspace.registry.tools));self.select_tool(first)
        self.clear_result()
        records=self.workspace.history()
        if records:self.show_observation(records[-1])
        if self.workspace.session.state.get('status') in ('running','execution_error'):self.statusBar().showMessage('上次计算未完成；已有结果已保留。未自动重新计算。')
        if self.workspace.recovery_warning:self.statusBar().showMessage(self.workspace.recovery_warning)

    def _build(self):
        shell=QWidget();outer=QHBoxLayout(shell);outer.setContentsMargins(0,0,0,0);outer.setSpacing(0);self.setCentralWidget(shell)
        side=QFrame();side.setObjectName('sidebar');side.setFixedWidth(248);left=QVBoxLayout(side);left.setContentsMargins(20,25,15,20)
        left.addWidget(label('工具库','brand'));left.addSpacing(20)
        self.search=QLineEdit();self.search.setPlaceholderText('搜索工具名称');self.search.textChanged.connect(self.filter_tools);left.addWidget(self.search)
        self.tool_tree=QTreeWidget();self.tool_tree.setObjectName('tools');self.tool_tree.setHeaderHidden(True)
        self.tool_tree.itemSelectionChanged.connect(self._tool_selected);left.addWidget(self.tool_tree,1)
        left.addWidget(label('最近计算'));self.recent=QListWidget();self.recent.setObjectName('recent');self.recent.setMaximumHeight(210)
        self.recent.itemClicked.connect(self._history_selected);left.addWidget(self.recent)
        outer.addWidget(side)
        body=QWidget();body_layout=QVBoxLayout(body);body_layout.setContentsMargins(24,20,24,15);body_layout.setSpacing(17)
        top=QHBoxLayout();top.addWidget(label('本地工具','title'));top.addStretch()
        self.graph_summary=label('','muted');self.graph_summary.setMaximumWidth(420);top.addWidget(self.graph_summary)
        self.graph_button=QPushButton('图输入');self.graph_button.clicked.connect(lambda:self.open_graph_input());top.addWidget(self.graph_button);body_layout.addLayout(top)
        self.paper_button=QPushButton('论文示意图');self.paper_button.clicked.connect(lambda:self.open_schematic());top.addWidget(self.paper_button)
        self.input_drawing_button=QPushButton('绘图与导出');self.input_drawing_button.clicked.connect(self.open_input_drawing);top.addWidget(self.input_drawing_button)
        self.splitter=QSplitter(Qt.Orientation.Horizontal)
        parameter_panel=QFrame();parameter_panel.setObjectName('panel');parameter_layout=QVBoxLayout(parameter_panel);parameter_layout.setContentsMargins(20,18,20,18)
        self.tool_title=label('选择工具','sectionTitle');parameter_layout.addWidget(self.tool_title)
        self.tool_description=label('','muted');parameter_layout.addWidget(self.tool_description)
        actions=QHBoxLayout();self.example=QPushButton('填入示例');self.example.clicked.connect(self.apply_example);actions.addWidget(self.example)
        self.import_button=QPushButton('导入参数');self.import_button.clicked.connect(self.import_parameters);actions.addWidget(self.import_button)
        self.reset_button=QPushButton('重置');self.reset_button.clicked.connect(self.reset_parameters);actions.addWidget(self.reset_button);parameter_layout.addLayout(actions)
        graph_actions=QHBoxLayout();self.graph_target=QComboBox();graph_actions.addWidget(self.graph_target)
        self.graph_target.currentIndexChanged.connect(lambda i:self.graph_target.setToolTip(self.graph_target.itemData(i,Qt.ItemDataRole.ToolTipRole) or ''));self.graph_target.view().setMouseTracking(True)
        self.apply_graph_button=QPushButton('应用当前图');self.apply_graph_button.clicked.connect(self.apply_current_graph);graph_actions.addWidget(self.apply_graph_button,1);parameter_layout.addLayout(graph_actions)
        self.mapping_note=label('','muted');self.mapping_note.hide();parameter_layout.addWidget(self.mapping_note)
        self.mapping_view=QPlainTextEdit();self.mapping_view.setReadOnly(True);self.mapping_view.setMaximumHeight(85);self.mapping_view.hide()
        self.mapping_toggle=QToolButton();self.mapping_toggle.setText('查看输入图与编号对照');self.mapping_toggle.setCheckable(True);self.mapping_toggle.toggled.connect(self.mapping_view.setVisible);self.mapping_toggle.hide();parameter_layout.addWidget(self.mapping_toggle);parameter_layout.addWidget(self.mapping_view)
        self.input_tabs=QTabWidget();self.form_container=QWidget();self.form_layout=QVBoxLayout(self.form_container);self.form_layout.setContentsMargins(3,10,10,8)
        self.input_tabs.addTab(scroll_panel(self.form_container),'参数填写')
        self.json_editor=QPlainTextEdit();self.json_editor.setPlaceholderText('完整参数JSON');self.input_tabs.addTab(self.json_editor,'完整JSON')
        self.input_tabs.currentChanged.connect(self._input_tab_changed);parameter_layout.addWidget(self.input_tabs,1)
        self.compute=QPushButton('开始计算');self.compute.setObjectName('primary');self.compute.clicked.connect(self.start_calculation)
        self.cancel=QPushButton('取消');self.cancel.setObjectName('stop');self.cancel.setEnabled(False);self.cancel.clicked.connect(self.cancel_calculation)
        row=QHBoxLayout();row.addWidget(self.compute,1);row.addWidget(self.cancel);parameter_layout.addLayout(row)
        self.progress=QProgressBar();self.progress.setRange(0,1);self.progress.setValue(0);self.progress.setTextVisible(False);self.progress.setMaximumHeight(5);parameter_layout.addWidget(self.progress)
        self.progress_text=label('就绪','muted');parameter_layout.addWidget(self.progress_text)
        self.progress_text.setToolTip('计算结果自动保存')
        self.splitter.addWidget(parameter_panel)
        result_panel=self._build_result_panel()
        self.splitter.addWidget(result_panel);self.splitter.setSizes([460,700]);body_layout.addWidget(self.splitter,1);outer.addWidget(body,1)
        self.statusBar().setSizeGripEnabled(False)

    def _build_result_panel(self):
        result_panel=QFrame();result_panel.setObjectName('panel');result_layout=QVBoxLayout(result_panel);result_layout.setContentsMargins(20,18,20,18)
        header=QHBoxLayout();self.result_title=label('计算结果','sectionTitle');header.addWidget(self.result_title);header.addStretch()
        self.result_graph_button=QPushButton('接着用此图');self.result_graph_button.clicked.connect(self.use_result_graph);self.result_graph_button.setEnabled(False);header.addWidget(self.result_graph_button)
        self.save_json=QPushButton('保存JSON');self.save_json.clicked.connect(self.save_json_record);header.addWidget(self.save_json)
        self.export=QPushButton('导出结果包');self.export.clicked.connect(self.export_bundle);header.addWidget(self.export);result_layout.addLayout(header)
        self.graph_result_actions=QWidget();graph_actions=QHBoxLayout(self.graph_result_actions);graph_actions.setContentsMargins(0,0,0,0)
        self.preview_graph_button=QPushButton('查看结构图');self.preview_graph_button.clicked.connect(self.preview_result_graph);graph_actions.addWidget(self.preview_graph_button)
        self.result_drawing_button=QPushButton('绘图 / 布局 / LaTeX');self.result_drawing_button.clicked.connect(self.open_result_drawing);graph_actions.addWidget(self.result_drawing_button)
        self.result_graph_note=label('','muted');graph_actions.addWidget(self.result_graph_note,1);result_layout.addWidget(self.graph_result_actions);self.graph_result_actions.hide()
        self.result_tabs=QTabWidget();self.overview=QWidget();self.overview_layout=QVBoxLayout(self.overview);self.overview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.result_tabs.addTab(scroll_panel(self.overview),'概览')
        data=QWidget();data_layout=QVBoxLayout(data);self.table_selector=QComboBox();self.table_selector.currentTextChanged.connect(self.show_table);data_layout.addWidget(self.table_selector)
        self.table_note=label('矩阵和向量可在这里查看，完整精度保留在原始数据中。','muted');data_layout.addWidget(self.table_note)
        self.table=QTableWidget();self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.table.setAlternatingRowColors(True);data_layout.addWidget(self.table,1)
        self.result_tabs.addTab(data,'数据表')
        figures=QWidget();fig_layout=QVBoxLayout(figures);self.file_selector=QComboBox();self.file_selector.currentIndexChanged.connect(self.show_file);fig_layout.addWidget(self.file_selector)
        from .graph_canvas import GraphCanvas
        self.result_canvas=GraphCanvas();self.result_canvas.set_editable(False);self.result_canvas.hide();fig_layout.addWidget(self.result_canvas,1)
        self.image=ImagePreview();fig_layout.addWidget(self.image,1)
        self.file_text=QPlainTextEdit();self.file_text.setReadOnly(True);self.file_text.setMaximumHeight(200);fig_layout.addWidget(self.file_text);self.file_text.hide()
        file_buttons=QHBoxLayout();self.save_attachment=QPushButton('保存附件');self.save_attachment.clicked.connect(self.save_file);file_buttons.addWidget(self.save_attachment)
        self.layout_button=QPushButton('调整布局');self.layout_button.clicked.connect(self.open_layout);file_buttons.addWidget(self.layout_button);fig_layout.addLayout(file_buttons)
        self.result_tabs.addTab(figures,'图形与文件')
        self.raw=QPlainTextEdit();self.raw.setReadOnly(True);self.result_tabs.addTab(self.raw,'原始数据');result_layout.addWidget(self.result_tabs,1)
        return result_panel

    def _menus(self):
        menu=self.menuBar().addMenu('文件')
        for title,action in [('新建会话',self.new_session),('打开已有会话',self.open_session),('打开会话文件夹',self.open_folder),('导出结果包',self.export_bundle)]:menu.addAction(title,action)
        menu.addAction('成果中心',self.open_results_center)
        self.menuBar().addMenu('工具').addAction('扩展工具库',self.open_tool_library)
        menu.addSeparator();menu.addAction('退出',self.close)
        self.menuBar().addMenu('帮助').addAction('使用说明',lambda:QMessageBox.information(self,'如何使用','选择左侧工具 → 填写参数或点击“填入示例” → 开始计算。\n右侧查看概览、数据表、图像和原始数据。\n计算自动保存，可导出整个会话的结果ZIP。\n此桌面版默认使用本地已有工具，不需要模型API或浏览器。'))

    def open_results_center(self):
        from .results_center import ResultsCenter
        dialog=ResultsCenter(self.workspace,self);dialog.exec();dialog.deleteLater()

    def open_tool_library(self):
        from .tool_library import ToolLibraryDialog
        dialog=ToolLibraryDialog(self.workspace,self);dialog.exec();dialog.deleteLater();self.refresh_tool_catalog()

    def refresh_tool_catalog(self):
        if self.thread is not None:return
        self.workspace.refresh_tools()
        if getattr(self,'_displayed_tool_groups',None)==self.workspace.groups:return
        current=self.current_tool;json_draft=self.json_editor.toPlainText();input_tab=self.input_tabs.currentIndex();self._fill_tools()
        self.select_tool(current if current in self.items else 'graph_invariants')
        if current==self.current_tool:
            self.input_tabs.setCurrentIndex(input_tab);self.json_editor.setPlainText(json_draft)

    def results_updated(self):
        if self.thread is not None:return
        try:
            path=self.workspace.session.directory
            if not (path/'session.json').is_file():return
            document,_=read_json(path/'session.json',max_bytes=16*1024*1024)
            if document.get('cleared'):self.workspace.new_session()
            else:self.workspace.open_session(path)
            if hasattr(self,'restore_view'):self.restore_view();self.refresh_sessions()
            else:
                self.refresh_history();self.clear_result()
                records=self.workspace.history()
                if records:self.show_observation(records[-1])
        except (OSError,ValueError,RuntimeError) as error:self.statusBar().showMessage(str(error))

    def _fill_tools(self):
        from .graph_actions import desktop_groups
        self._displayed_tool_groups=copy.deepcopy(self.workspace.groups)
        self.tool_tree.clear();self.items={}
        for number,group in enumerate(desktop_groups(self.workspace.groups)):
            category=QTreeWidgetItem([group['name']]);self.tool_tree.addTopLevelItem(category);category.setExpanded(number==0)
            for definition in group['tools']:
                if definition['name']=='hypergraph_editor':continue
                title=TITLES.get(definition['name'],definition.get('documentation',{}).get('title',definition['name']))
                item=QTreeWidgetItem([title],raw=definition.get('documentation',{}).get('coverage')!='reviewed_native');item.setData(0,Qt.ItemDataRole.UserRole,definition['name']);item.setToolTip(0,escape(definition['description']))
                category.addChild(item);self.items[definition['name']]=item

    def filter_tools(self,text):
        for i in range(self.tool_tree.topLevelItemCount()):
            group=self.tool_tree.topLevelItem(i);visible=False
            for j in range(group.childCount()):
                item=group.child(j);name=item.data(0,Qt.ItemDataRole.UserRole)
                matches=text.casefold() in (item.text(0)+' '+name).casefold()
                item.setHidden(not matches);visible|=matches
            group.setHidden(not visible)
            if text:group.setExpanded(True)

    def _tool_selected(self):
        items=self.tool_tree.selectedItems()
        if items:
            name=items[0].data(0,Qt.ItemDataRole.UserRole)
            if name and name!=self.current_tool:self.select_tool(name)

    def select_tool(self,name):
        if name=='hypergraph_editor':name='hypergraph_plot'
        if self.current_tool:self.drafts[self.current_tool]={key:field.snapshot() for key,field in self.fields.items()}
        if self.current_tool:self.graph_drafts[self.current_tool]=copy.deepcopy(self.graph_bindings)
        self.graph_bindings=copy.deepcopy(self.graph_drafts.get(name,{}))
        self.current_tool=name;self.definition=self.workspace.registry.describe(name)
        self.tool_title.setText(TITLES.get(name,self.definition.get('documentation',{}).get('title',name)));guide=input_guide(self.definition)
        self.tool_description.setText(guide['summary']+'\n'+'\n'.join(guide['notes']))
        self._build_form()
        for key,state in self.drafts.get(name,{}).items():
            if key in self.fields:self.fields[key].restore(state)
        self.json_editor.setPlainText('{}');self.input_tabs.setCurrentIndex(0)
        self.tool_tree.blockSignals(True);self.tool_tree.setCurrentItem(self.items.get(name))
        if name in self.items:self.items[name].parent().setExpanded(True)
        self.tool_tree.blockSignals(False)
        self.compute.setEnabled(self.thread is None and self.definition['availability']['available'])
        if not self.definition['availability']['available']:self.progress_text.setText('此工具缺少可选依赖，尚不能计算。')
        self.refresh_graph_input()

    def refresh_graph_input(self):
        from graph_research.graph_input.adapters import graph_targets
        targets=graph_targets(self.definition);current=self.graph_target.currentData();self.graph_target.clear()
        for target in targets:
            self.graph_target.addItem({'graph':'当前工具的图','left':'左侧图','right':'右侧图','case':'追加批量项目','base':'配方初始图'}[target],target)
            self.graph_target.setItemData(self.graph_target.count()-1,{'graph':'填入当前计算工具的图参数。','left':'作为左图；子图计数时为宿主图。','right':'作为右图；子图计数时为模式图。','case':'把当前图追加为新的批量项目。','base':'作为构图配方的初始结构，后续步骤继续填写。'}[target],Qt.ItemDataRole.ToolTipRole)
        self.graph_target.setToolTip(self.graph_target.currentData(Qt.ItemDataRole.ToolTipRole) or '')
        if self.graph_target.findData(current)>=0:self.graph_target.setCurrentIndex(self.graph_target.findData(current))
        self.graph_target.setVisible(len(targets)>1);self.apply_graph_button.setEnabled(bool(targets) and self.thread is None)
        try:self.input_graph=self.workspace.graph_library.current()
        except (ValueError,OSError) as error:self.statusBar().showMessage('当前图未读取：'+str(error));self.input_graph=None
        self.graph_summary.setText(graph_summary(self.input_graph) if self.input_graph else '');self._show_graph_mapping()

    def _show_graph_mapping(self):
        self.mapping_note.setVisible(bool(self.graph_bindings));self.mapping_toggle.setVisible(bool(self.graph_bindings))
        if not self.graph_bindings:self.mapping_view.hide();self.mapping_toggle.setChecked(False);return
        self.mapping_note.setText('已应用图输入；计算使用下方对照中的0起始编号。')
        sources=copy.deepcopy(list(self.graph_bindings.values()))
        self.mapping_view.setLocalizedRenderer(lambda:mapping_text(sources))

    def open_graph_input(self,graph=None):
        if self.thread is not None:return
        from .graph_input import GraphInputDialog
        try:
            dialog=GraphInputDialog(self.workspace.graph_library,graph or self.workspace.graph_library.current(),self)
            if dialog.exec()!=dialog.DialogCode.Accepted:return
            if dialog.schematic_result is not None:
                self._dispatch_graph_call(('hypergraph_schematic',{'diagram':dialog.schematic_result},[]));return
            self.workspace.graph_library.set_current(dialog.graph);self.input_graph=dialog.graph;self.graph_summary.setText(graph_summary(dialog.graph))
            if dialog.use_recipe:
                self.select_tool('graph_recipe');self.fill_arguments(dialog.graph.to_dict()['recipe']);self.graph_bindings={};self._show_graph_mapping()
                self.statusBar().showMessage('已准备保存的构图配方；可修改参数后开始计算。');return
            from graph_research.graph_input.adapters import graph_targets
            if graph_targets(self.definition):self.apply_graph(dialog.graph)
            else:self.statusBar().showMessage('图已准备；选择接收已有图的计算工具后点击“应用当前图”。')
        except jsonschema.ValidationError as error:QMessageBox.warning(self,'图尚未应用',validation_message(error))
        except (ValueError,OSError) as error:QMessageBox.warning(self,'图尚未应用',str(error))
        finally:
            if 'dialog' in locals():dialog.deleteLater()

    def apply_current_graph(self):
        try:
            graph=self.workspace.graph_library.current()
            if graph is None:self.open_graph_input();return
            self.apply_graph(graph)
        except jsonschema.ValidationError as error:QMessageBox.warning(self,'图尚未应用',validation_message(error))
        except (ValueError,OSError) as error:QMessageBox.warning(self,'图尚未应用',str(error))

    def open_schematic(self,scene=None):
        if self.thread is not None:return
        from .schematic import SchematicDialog
        from graph_research.schematics import SchematicDocument,template,from_graph
        try:
            if scene is None and getattr(self,'current_tool',None)=='hypergraph_schematic':
                try:scene=SchematicDocument(self.collect_arguments()['diagram'])
                except (ValueError,jsonschema.ValidationError):scene=template('blank')
            if scene is None and getattr(self,'input_graph',None) is not None:
                try:scene=from_graph(self.input_graph)
                except ValueError:scene=template('blank')
            dialog=SchematicDialog(scene or template('blank'),self)
            def prepared(value):
                self._dispatch_graph_call(('hypergraph_schematic',{'diagram':value.to_dict(),'vertex_labels':dialog.canvas.vertex_labels.isChecked()},[]))
            def expanded(graph):
                self.workspace.graph_library.set_current(graph);self.input_graph=graph;self.graph_summary.setText(graph_summary(graph))
            dialog.diagram_ready.connect(prepared);dialog.graph_ready.connect(expanded);dialog.exec();dialog.deleteLater()
        except (ValueError,OSError) as error:QMessageBox.warning(self,'示意图尚未应用',str(error))

    def apply_graph(self,graph,target=None):
        from graph_research.graph_input.adapters import graph_patch
        if self.thread is not None:return
        if self.input_tabs.currentIndex()==1:
            from graph_research.assistant.offline import _strict_json
            raw=_strict_json(self.json_editor.toPlainText())
            if not isinstance(raw,dict) or set(raw)-set(self.fields):raise ValueError('完整JSON不是本工具的参数对象。')
            for key,value in raw.items():jsonschema.validate(value,self.definition['parameters']['properties'][key])
            self._build_form()
            for key,value in raw.items():self.fields[key].set_value(value)
        initial={}
        if self.current_tool=='graph_batch_study' and self.fields['cases'].enabled.isChecked():initial['cases']=self.fields['cases'].read()
        prepared=graph_patch(graph,self.definition,target or self.graph_target.currentData(),initial)
        for key,value in prepared['patch'].items():self.fields[key].set_value(value)
        for key in prepared['remove']:
            if key in self.fields:self.fields[key].enabled.setChecked(False)
        binding={key:prepared[key] for key in ('target','patch','vertex_mapping')}
        if 'case_index' in prepared:binding['case_index']=prepared['case_index']
        binding['document']=graph.to_dict();key='case'+str(prepared['case_index']) if prepared['target']=='case' else prepared['target']
        self.graph_bindings[key]=binding;self.input_graph=graph;self.graph_summary.setText(graph_summary(graph));self._show_graph_mapping()
        self.input_tabs.setCurrentIndex(0);self.statusBar().showMessage(prepared['notice'])

    def use_result_graph(self):
        try:
            graphs=self._result_graphs()
            if len(graphs)==1:self.open_graph_input(graphs[0][1])
            elif graphs:
                from .widgets import QInputDialog
                from .i18n import UiText
                captions=[graph_summary(graph,role=title) for title,graph in graphs]
                titles=[UiText(str(i+1)+' · '+caption,str(i+1)+' · '+caption.english) for i,caption in enumerate(captions)]
                selected,accepted=QInputDialog.getItem(self,'继续使用图','选择图对象',titles,0,False)
                if accepted:self.open_graph_input(graphs[titles.index(selected)][1])
        except ValueError as error:QMessageBox.warning(self,'此结果不能继续构图',str(error))

    def _result_graphs(self):
        from .graph_actions import observation_graphs
        try:return observation_graphs(self.observation or {},self.workspace.registry)
        except (ValueError,KeyError,TypeError,jsonschema.ValidationError):return []

    def open_input_drawing(self):
        if self.thread is not None:return
        try:
            from graph_research.graph_input.adapters import bound_inputs,validate_bindings
            from .graph_actions import input_graphs
            from graph_research.graph_input.adapters import graph_targets
            if graph_targets(self.definition):
                arguments=self.collect_arguments();bindings=bound_inputs(self.graph_bindings,arguments)
                sources=validate_bindings(self.definition,arguments,bindings) if bindings else []
                graphs=input_graphs(self.definition,arguments,sources)
            else:graphs=[]
            graph=self.workspace.graph_library.current()
            if graph is not None and all(g.sha256!=graph.sha256 for _,g in graphs):graphs.append(('图输入中的当前图',graph))
            if not graphs:raise ValueError('请先通过“图输入”准备图，或填写当前工具的图参数。')
            self.open_graph_actions(graphs)
        except (ValueError,KeyError,TypeError,jsonschema.ValidationError) as error:QMessageBox.warning(self,'图尚未准备',str(error))

    def open_result_drawing(self):
        if self.thread is not None:return
        graphs=self._result_graphs()
        if graphs:self.open_graph_actions(graphs)

    def preview_result_graph(self):
        graphs=self._result_graphs()
        if graphs:
            index=self.file_selector.currentIndex();index=index if 0<=index<len(graphs) else 0
            self.result_tabs.setCurrentIndex(2);self.file_selector.setCurrentIndex(index);self.show_file(index)

    def open_graph_actions(self,graphs):
        if self.thread is not None:return
        from .graph_actions import GraphActionsDialog
        try:
            dialog=GraphActionsDialog(graphs,self.workspace.registry,self)
            if dialog.exec()==dialog.DialogCode.Accepted and dialog.request:self._dispatch_graph_call(dialog.request)
        except (ValueError,KeyError,TypeError) as error:QMessageBox.warning(self,'图形面板未打开',str(error))
        finally:
            if 'dialog' in locals():dialog.deleteLater()

    def _dispatch_graph_call(self,request):
        if self.thread is not None:return
        if not callable(getattr(self.workspace.session,'call_tool',None)):
            self.local_graph_call.emit(request);return
        name,arguments,inputs=request;self._start_tool_call(name,arguments,inputs)

    def _build_form(self):
        while self.form_layout.count():
            item=self.form_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.fields={};guide=input_guide(self.definition);guides={field['name']:field for field in guide['fields']}
        for name,schema in self.definition['parameters']['properties'].items():
            field=ParameterField(name,schema,guides[name],name in self.definition['parameters'].get('required',[]),self.definition);self.fields[name]=field;self.form_layout.addWidget(field)
        self.form_layout.addStretch()

    def collect_arguments(self):
        if self.input_tabs.currentIndex()==1:
            from graph_research.assistant.offline import _strict_json
            text=self.json_editor.toPlainText()
            if len(text)>100000:raise ValueError('输入参数超过100000字符')
            arguments=_strict_json(text)
        else:arguments={name:field.read() for name,field in self.fields.items() if field.enabled.isChecked()}
        jsonschema.validate(arguments,self.definition['parameters'])
        if len(json.dumps(arguments,allow_nan=False))>100000:raise ValueError('输入参数过长')
        return arguments

    def fill_arguments(self,arguments):
        jsonschema.validate(arguments,self.definition['parameters']);self._build_form()
        for name,value in arguments.items():self.fields[name].set_value(value)
        self.json_editor.setPlainText(json.dumps(arguments,ensure_ascii=False,indent=2));self.input_tabs.setCurrentIndex(0)

    def _input_tab_changed(self,index):
        if index==1:
            try:
                args={name:field.read() for name,field in self.fields.items() if field.enabled.isChecked()}
                self.json_editor.setPlainText(json.dumps(args,ensure_ascii=False,indent=2))
            except (ValueError,jsonschema.ValidationError):pass

    def apply_example(self):
        examples=self.definition['documentation'].get('examples',[])
        if examples:self.fill_arguments(examples[0]['arguments']);self.graph_bindings={};self._show_graph_mapping();self.statusBar().showMessage('已填入示例；点击“开始计算”才会运行。')

    def reset_parameters(self):self.drafts.pop(self.current_tool,None);self.graph_bindings={};self._show_graph_mapping();self._build_form();self.json_editor.setPlainText('{}')

    def import_parameters(self):
        path,_=QFileDialog.getOpenFileName(self,'导入当前工具的参数','','JSON (*.json)')
        if not path:return
        try:self.fill_arguments(read_arguments(path))
        except jsonschema.ValidationError as exc:QMessageBox.warning(self,'参数未导入',validation_message(exc))
        except Exception as exc:QMessageBox.warning(self,'参数未导入',str(exc))

    def start_calculation(self):
        if self.thread is not None:return
        try:arguments=self.collect_arguments()
        except jsonschema.ValidationError as exc:QMessageBox.warning(self,'请核对参数',validation_message(exc));return
        except Exception as exc:QMessageBox.warning(self,'请核对参数',str(exc));return
        from graph_research.graph_input.adapters import bound_inputs
        inputs=bound_inputs(self.graph_bindings,arguments)
        self._start_tool_call(self.current_tool,arguments,inputs)

    def _start_tool_call(self,name,arguments,inputs=None):
        if self.thread is not None:return
        self.thread=QThread(self);self.worker=CalculationWorker(self.workspace.session,name,arguments,inputs);self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run);self.worker.done.connect(self._calculation_done);self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater);self.thread.finished.connect(self._thread_finished)
        self.started=time.monotonic();self.progress.setRange(0,0);self.compute.setEnabled(False);self.cancel.setEnabled(True)
        self.input_tabs.setEnabled(False);self.tool_tree.setEnabled(False);self.example.setEnabled(False);self.import_button.setEnabled(False);self.reset_button.setEnabled(False)
        self.export.setEnabled(False);self.timer.start(250);self._tick();self.thread.start()
        self.graph_button.setEnabled(False);self.apply_graph_button.setEnabled(False);self.result_graph_button.setEnabled(False)
        self.result_drawing_button.setEnabled(False);self.input_drawing_button.setEnabled(False);self.paper_button.setEnabled(False);self.layout_button.setEnabled(False)

    def _tick(self):
        action='正在停止计算' if self.worker and self.worker.cancel_event.is_set() else '正在计算'
        self.progress_text.setText(f'{action} · {int(time.monotonic()-self.started)} 秒')

    def cancel_calculation(self):
        if self.worker:self.worker.cancel_event.set();self.progress_text.setText('正在停止计算并保存记录……');self.cancel.setEnabled(False)

    def _calculation_done(self,observation):
        self.timer.stop();self.show_observation(observation);self.refresh_history()
        self.progress_text.setText(('计算完成' if observation.get('ok') else '计算未完成')+f' · {time.monotonic()-self.started:.1f} 秒')
        if self.workspace.session.export_error:self.statusBar().showMessage('计算记录已保留，结果打包未完成：'+self.workspace.session.export_error)

    def _thread_finished(self):
        thread=self.thread;self.thread=None;self.worker=None;thread.deleteLater()
        self.progress.setRange(0,1);self.progress.setValue(1);self.cancel.setEnabled(False)
        self.compute.setEnabled(self.definition['availability']['available']);self.input_tabs.setEnabled(True);self.tool_tree.setEnabled(True)
        for button in (self.example,self.import_button,self.reset_button,self.export):button.setEnabled(True)
        self.graph_button.setEnabled(True);self.refresh_graph_input()
        self.input_drawing_button.setEnabled(True);self.paper_button.setEnabled(True);self._refresh_result_actions()
        if self.close_after:self.close()

    def refresh_history(self):
        from .graph_actions import presentation_title
        self.recent.clear();records=self.workspace.history()
        for index in range(len(records)-1,max(-1,len(records)-13),-1):
            record=records[index];item=QListWidgetItem(('✓ ' if record.get('ok') else '• ')+(presentation_title(record,self.workspace.registry) or TITLES.get(record.get('tool'),str(record.get('tool')))))
            item.setData(Qt.ItemDataRole.UserRole,index);self.recent.addItem(item)

    def _history_selected(self,item):
        if self.thread is not None:return
        index=item.data(Qt.ItemDataRole.UserRole);self.show_observation(self.workspace.history()[index])

    def show_observation(self,observation):
        from .graph_actions import presentation_title
        self.observation=copy.deepcopy(observation);self.result_title.setText(presentation_title(observation,self.workspace.registry) or TITLES.get(observation.get('tool'),'计算结果'))
        self.result_canvas.hide();self.image.show()
        self.raw.setPlainText(json.dumps(observation,ensure_ascii=False,indent=2,allow_nan=False));self._table_fields={}
        while self.overview_layout.count():
            item=self.overview_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
            elif item.layout():
                child=item.layout()
                while child.count():
                    cell=child.takeAt(0)
                    if cell.widget():cell.widget().deleteLater()
        if not observation.get('ok'):
            self.overview_layout.addWidget(label('此次计算未完成','sectionTitle'));self.overview_layout.addWidget(label(display_error(observation.get('error','没有有效结果'))))
        else:
            data=observation.get('result');data=data if isinstance(data,dict) else {'result':data}
            grid=QGridLayout();row=0
            for key in METRIC_KEYS:
                value=data.get(key)
                if key not in data or not (value is None or isinstance(value,(str,bool,int,float))):continue
                card=QFrame();card.setObjectName('metric');card_layout=QVBoxLayout(card);card_layout.addWidget(label(LABELS.get(key,key),'muted'));card_layout.addWidget(label(display_field(key,value),'value'))
                grid.addWidget(card,row//2,row%2);row+=1
            self.overview_layout.addLayout(grid)
            if observation.get('graph_inputs'):
                source=QPlainTextEdit();source.setReadOnly(True);source.setMaximumHeight(120)
                from .i18n import tr
                source.setLocalizedRenderer(lambda:tr('输入图与顶点编号对照\n')+mapping_text(observation['graph_inputs']));self.overview_layout.addWidget(source)
            for key,value in data.items():
                if isinstance(value,list):self._table_fields[key]=value
            from .result_text import result_text
            details=QPlainTextEdit();details.setReadOnly(True);details.setLocalizedRenderer(lambda:result_text(observation));details.setMinimumHeight(230);self.overview_layout.addWidget(details,1)
            if observation.get('tool_status')=='fixture_tested_experimental':self.overview_layout.addWidget(label('实验工具：只通过登记的样例，需要独立复核。','muted'))
        self.table_selector.clear();self.table_selector.addItems([LABELS.get(key,key)+'  ['+key+']' for key in self._table_fields])
        if not self._table_fields:self.table.clear();self.table.setRowCount(0);self.table.setColumnCount(0)
        try:self._files=self.workspace.artifacts(observation)
        except Exception as exc:self._files=[];self.statusBar().showMessage('附件验证未通过：'+str(exc))
        self.file_selector.blockSignals(True);self.file_selector.clear();self.file_selector.addItems([path.name for path in self._files])
        if not self._files:self.image.original=None;self.image.setText('本次没有图形附件');self.file_text.hide()
        graphs=self._result_graphs()
        if graphs:
            for i,(title,_) in enumerate(graphs):self.file_selector.insertItem(i,preview_title(title))
            self.file_selector.setCurrentIndex(0)
        self.file_selector.blockSignals(False)
        image_index=next((i+len(graphs) for i,path in enumerate(self._files) if path.suffix.lower() in ('.png','.svg','.jpg','.jpeg')),None)
        if image_index is not None:self.file_selector.setCurrentIndex(image_index)
        if self.file_selector.count():self.show_file(self.file_selector.currentIndex())
        self._refresh_result_actions()
        self.result_tabs.setCurrentIndex(2 if observation.get('tool') in ('hypergraph_plot','hypergraph_editor','combinatorial_plot','graph_layout') else 0)

    def _refresh_result_actions(self):
        graphs=self._result_graphs();ready=self.thread is None
        self.graph_result_actions.setVisible(bool(graphs));self.preview_graph_button.setEnabled(bool(graphs) and ready)
        self.result_graph_button.setEnabled(bool(graphs) and ready);self.result_drawing_button.setEnabled(bool(graphs) and ready)
        if graphs:self.result_graph_note.setText(graphs[0][0]+' · '+('普通图' if graphs[0][1].graph_type=='graph' else '超图')+(' · 共'+str(len(graphs))+'幅' if len(graphs)>1 else ''))
        schematic=bool(self.observation and self.observation.get('ok') and self.observation.get('tool')=='hypergraph_schematic')
        self.layout_button.setVisible(schematic);self.layout_button.setText('编辑论文示意图');self.layout_button.setEnabled(schematic and ready)
        if self.file_selector.count():self.save_attachment.setEnabled(self.file_selector.currentIndex()>=len(graphs))
        else:self.save_attachment.setEnabled(False)

    def show_table(self,text):
        index=self.table_selector.currentIndex()
        if index<0:return
        key=list(self._table_fields)[index];value=self._table_fields[key]
        rows=value if value and all(isinstance(row,list) for row in value) else [[i,v] for i,v in enumerate(value)]
        max_cols=max((len(row) for row in rows),default=0);nrows=min(len(rows),128);ncols=min(max_cols,32)
        self.table.setRowCount(nrows);self.table.setColumnCount(ncols)
        self.table.setHorizontalHeaderLabels([str(i) for i in range(ncols)])
        for i,row in enumerate(rows[:nrows]):
            for j,cell in enumerate(row[:ncols]):
                item=QTableWidgetItem(display_value(cell),ui=isinstance(cell,bool));item.setToolTip(escape(json.dumps(cell,ensure_ascii=False)));self.table.setItem(i,j,item)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_note.setText(f'{len(rows)}行 × {max_cols}列'+(' · 仅预览前128行、32列，完整数据见JSON。' if len(rows)>128 or max_cols>32 else ' · 悬停查看原始值。'))

    def show_file(self,index):
        graphs=self._result_graphs()
        if 0<=index<len(graphs):
            try:
                self.result_canvas.set_graph(graphs[index][1])
                for vertex in self.result_canvas.vertices:vertex.setFlag(vertex.GraphicsItemFlag.ItemIsMovable,False)
                self.result_canvas.show();self.image.hide();self.file_text.hide();self.save_attachment.setEnabled(False)
            except (ValueError,TypeError) as error:
                self.result_canvas.hide();self.image.show();self.image.original=None;self.image.setText('结构预览未生成：'+str(error))
            return
        index-=len(graphs);self.result_canvas.hide();self.image.show()
        self.save_attachment.setEnabled(0<=index<len(self._files))
        if not 0<=index<len(self._files):return
        path=self._files[index]
        try:
            if path not in self.workspace.artifacts(self.observation):raise ValueError('附件不属于当前计算')
        except Exception as exc:
            self.image.original=None;self.image.setText('附件验证未通过：'+str(exc));self.file_text.hide();return
        self.file_text.hide()
        if path.suffix.lower() in ('.png','.svg','.jpg','.jpeg'):self.image.show_image(path)
        elif path.suffix.lower() in ('.tex','.json','.txt'):
            self.image.original=None;self.image.setRawText(path.name)
            with path.open('r',encoding='utf-8') as stream:text=stream.read(100000)
            self.file_text.setPlainText(text);self.file_text.show()
        elif path.suffix.lower()=='.html':
            self.image.original=None;self.image.setText('可点击下方“桌面布局编辑器”直接拖动顶点。\n已有HTML文件也可保存；桌面版不会自动打开浏览器。')
        else:self.image.original=None;self.image.setText('可保存此附件后使用相应程序查看。')

    def save_file(self):
        index=self.file_selector.currentIndex()-len(self._result_graphs())
        if not 0<=index<len(self._files):return
        source=self._files[index];path,_=QFileDialog.getSaveFileName(self,'保存附件',source.name)
        if not path:return
        try:
            if source not in self.workspace.artifacts(self.observation):raise ValueError('附件验证未通过')
            target=safe_path(path)
            if target==source.resolve():return
            with staged_file(target,overwrite=True) as temporary:temporary.write_bytes(source.read_bytes())
            self.statusBar().showMessage('已保存：'+str(target))
        except Exception as exc:QMessageBox.warning(self,'保存未完成',str(exc))

    def open_layout(self):
        if not self.observation:return
        try:
            if self.observation.get('tool')=='hypergraph_schematic':
                from graph_research.schematics import SchematicDocument
                self.open_schematic(SchematicDocument(self.observation['arguments']['diagram']));return
            from .layout import LayoutDialog
            arguments=copy.deepcopy(self.observation['arguments'])
            result=self.observation.get('result')
            if self.observation.get('tool')=='graph_layout':
                arguments={'edges':copy.deepcopy(result['edges']),'vertices':copy.deepcopy(result['vertices']),
                           'positions':copy.deepcopy(result['positions']),'seed':arguments.get('seed',42)}
            if 'positions' not in arguments and isinstance(result,dict) and 'positions' in result:arguments['positions']=copy.deepcopy(result['positions'])
            dialog=LayoutDialog(arguments,self);dialog.positions_ready.connect(self.use_layout);dialog.exec()
        except Exception as exc:QMessageBox.warning(self,'布局编辑器未打开',str(exc))

    def use_layout(self,arguments):
        target='graph_tikz' if all(len(edge)==2 for edge in arguments['edges']) else 'hypergraph_tikz'
        self._dispatch_graph_call((target,arguments,[]))

    def save_json_record(self):
        if self.observation is None:return
        path,_=QFileDialog.getSaveFileName(self,'保存完整结果','计算结果.json','JSON (*.json)')
        if path:
            try:self.workspace.save_record(self.observation,path);self.statusBar().showMessage('结果已保存：'+path)
            except Exception as exc:QMessageBox.warning(self,'保存未完成',str(exc))

    def export_bundle(self):
        if self.thread is not None:return
        if not self.workspace.history():QMessageBox.information(self,'暂无结果','请先选择工具并完成一次计算。');return
        path,_=QFileDialog.getSaveFileName(self,'导出整个会话的结果包','科研计算结果.zip','ZIP (*.zip)')
        if path:
            try:self.workspace.export_bundle(path);self.statusBar().showMessage('结果包已导出：'+path)
            except Exception as exc:QMessageBox.warning(self,'导出未完成',str(exc))

    def new_session(self):
        if self.thread is not None:return
        self.workspace.new_session();self.current_tool=None;self.drafts={};self.graph_bindings={};self.graph_drafts={};self._fill_tools();self.select_tool('graph_invariants');self.refresh_history();self.clear_result()
        self.statusBar().showMessage('已新建会话；此前结果保留在原目录。')

    def open_session(self):
        if self.thread is not None:return
        file,_=QFileDialog.getOpenFileName(self,'选择已有无API会话的session.json',str(self.workspace.directory),'会话文件 (session.json)')
        if not file:return
        try:
            self.workspace.open_session(Path(file).parent);self.refresh_history()
            self.current_tool=None;self.drafts={};self.graph_bindings={};self.graph_drafts={};self._fill_tools();self.select_tool('graph_invariants');self.clear_result()
            records=self.workspace.history()
            if records:self.show_observation(records[-1])
        except Exception as exc:QMessageBox.warning(self,'会话未打开',str(exc))

    def clear_result(self):
        self.observation=None;self.raw.clear();self.result_title.setText('计算结果')
        self.result_graph_button.setEnabled(False)
        self.result_canvas.hide();self.image.show();self.result_drawing_button.setEnabled(False);self.graph_result_actions.hide()
        while self.overview_layout.count():
            item=self.overview_layout.takeAt(0)
            if item.widget():item.widget().deleteLater()
            elif item.layout():
                child=item.layout()
                while child.count():
                    cell=child.takeAt(0)
                    if cell.widget():cell.widget().deleteLater()
                child.deleteLater()
        self.overview_layout.addWidget(label('开始你的第一次计算','sectionTitle'))
        self.overview_layout.addWidget(label('从左侧选择工具，填写参数或填入示例，点击“开始计算”。\n完成后可在这里查看指标、数据表、图像与原始记录。','muted'))
        self.table_selector.clear();self.table.setRowCount(0);self.table.setColumnCount(0);self._files=[];self.file_selector.clear()
        self.image.original=None;self.image.setText('计算图形会在这里显示');self.file_text.hide();self.layout_button.setEnabled(False)

    def open_folder(self):
        self.workspace.session.directory.mkdir(parents=True,exist_ok=True);QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.workspace.session.directory)))

    def closeEvent(self,event):
        if self.thread is not None:
            self.close_after=True;self.cancel_calculation();event.ignore()
        else:event.accept()


def desktop_command(arguments):
    from .native_diagnostics import install
    install()
    parser=argparse.ArgumentParser(description='独立桌面科研助手：本地工具、参数表单、计算及结果，无需浏览器')
    parser.add_argument('--workspace',default='outputs/desktop');parser.add_argument('--session');parser.add_argument('--tool-dir')
    parser.add_argument('--language',choices=('zh','en'),help='Desktop language; defaults to the saved selection')
    options=parser.parse_args(arguments)
    from .i18n import initialize
    initialize(options.language)
    application=QApplication.instance() or QApplication([]);application.setApplicationName('GraphResearchAssistant');application.setStyle('Fusion');application.setPalette(desktop_palette());application.setStyleSheet(STYLE)
    from .widgets import QtLanguageController
    application._language_controller=QtLanguageController(application)
    application.setWindowIcon(app_icon())
    from graph_research.assistant.result_catalog import ResultPreferences
    workspace=DesktopWorkspace(options.workspace,session_directory=options.session,tool_directory=options.tool_dir,results_preferences=ResultPreferences())
    from .shell import IntegratedWindow
    window=IntegratedWindow(workspace);window.show()
    return application.exec()
