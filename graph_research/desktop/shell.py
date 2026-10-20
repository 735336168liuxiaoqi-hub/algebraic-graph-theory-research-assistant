"""One native application with lazy, independent offline and API workspaces."""
from PySide6.QtWidgets import QWidget,QVBoxLayout
from .widgets import QMainWindow,QTabWidget,QLabel,QMessageBox
from .app import DesktopWindow,app_icon


class IntegratedWindow(QMainWindow):
    def __init__(self,workspace):
        super().__init__();self.workspace=workspace;self.chat=None;self.closing=False
        self.setWindowTitle('图论科研助手 · 桌面版');self.setWindowIcon(app_icon())
        self.offline=DesktopWindow(workspace);self.resize(self.offline.size());self.setMinimumSize(1020,650)
        self.modes=QTabWidget();self.modes.addTab(self.offline,'本地工具');self.modes.setTabToolTip(0,'选择工具并填写参数')
        self.placeholder=QWidget();layout=QVBoxLayout(self.placeholder)
        layout.addWidget(QLabel('科研对话'));self.modes.addTab(self.placeholder,'科研对话');self.modes.setTabToolTip(1,'连接模型，通过对话开展计算')
        self.setCentralWidget(self.modes);self.modes.currentChanged.connect(self.switch_mode)
        from graph_research import __version__
        self.version_label=QLabel('v'+__version__)
        self.version_label.setToolTip('当前运行的程序版本')
        self.statusBar().setSizeGripEnabled(False);self.statusBar().addPermanentWidget(self.version_label)
        self.menuBar().addMenu('成果').addAction('成果中心',lambda:self.offline.open_results_center())
        self.menuBar().addMenu('工具').addAction('扩展工具库',self.open_tool_library)
        from .widgets import language_menu
        from .i18n import listen
        language_menu(self);listen(self._language_changed)

    def _language_changed(self):
        from .i18n import language
        for code,action in self._language_actions.items():action.setChecked(code==language())

    def open_tool_library(self):
        from .tool_library import ToolLibraryDialog
        dialog=ToolLibraryDialog(self.workspace,self);dialog.exec();dialog.deleteLater()
        self.offline.refresh_tool_catalog()
        if self.chat is not None and self.chat.thread is None:self.chat.workspace.refresh_tools()

    def switch_mode(self,index):
        if index==0:self.offline.refresh_tool_catalog()
        if index!=1 or self.chat is not None:return
        try:
            from .chat import ChatWindow
            from .model_service import ModelWorkspace
            self.chat=ChatWindow(ModelWorkspace(self.workspace.directory/'model',tool_directory=self.workspace.tool_directory,graph_directory=self.workspace.graph_library.directory,results_preferences=self.workspace.results_preferences))
            self.modes.blockSignals(True);self.modes.removeTab(1);self.modes.insertTab(1,self.chat,'科研对话');self.modes.setTabToolTip(1,'连接模型，通过对话开展计算');self.modes.setCurrentIndex(1);self.modes.blockSignals(False)
            self.placeholder.deleteLater()
        except Exception as exc:
            self.chat=None
            self.modes.blockSignals(False)
            self.modes.setCurrentIndex(0)
            QMessageBox.warning(self,'科研对话未打开','请安装 assistant 可选依赖后重试。\n'+str(exc))

    def closeEvent(self,event):
        running=[w for w in (self.offline,self.chat) if w is not None and w.thread is not None]
        if running:
            self.closing=True
            for window in running:window.cancel_calculation()
            self.statusBar().showMessage('正在停止并保存；模型请求可能需要等待返回或超时。')
            from PySide6.QtCore import QTimer
            QTimer.singleShot(200,self._close_when_idle);event.ignore()
        else:
            if self.chat is not None:self.chat.disconnect_model()
            event.accept()

    def _close_when_idle(self):
        if any(w is not None and w.thread is not None for w in (self.offline,self.chat)):
            from PySide6.QtCore import QTimer
            QTimer.singleShot(200,self._close_when_idle)
        else:self.close()
