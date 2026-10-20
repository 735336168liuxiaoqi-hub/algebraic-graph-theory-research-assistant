"""Native acceptance runner; live traffic starts only from the explicit user button."""
import json
from pathlib import Path
from threading import Event
from PySide6.QtCore import QObject,QThread,Signal,Qt,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QListWidget,QListWidgetItem,QCheckBox,QSpinBox,QLineEdit,QPushButton,QTextBrowser,QMessageBox
from .app import label
from graph_research.assistant.evaluation import evaluation_cases,run_evaluation
from graph_research.assistant.governance import validate_policy


class EvaluationWorker(QObject):
    progress=Signal(object);done=Signal(object)
    def __init__(self,directory,case_ids,live,model,limits):
        super().__init__();self.directory=directory;self.case_ids=case_ids;self.live=live;self.model=model;self.limits=limits;self.cancel=Event()
    def run(self):
        try:self.done.emit({'ok':True,**run_evaluation(self.directory,case_ids=self.case_ids,live=self.live,model=self.model,limits=self.limits,cancel=self.cancel,on_progress=self.progress.emit)})
        except Exception as error:
            text=str(error);secret=getattr(self.model,'api_key','')
            self.done.emit({'ok':False,'error':text.replace(secret,'[密钥已隐藏]') if secret else text})


class EvaluationDialog(QDialog):
    def __init__(self,directory,model=None,parent=None):
        super().__init__(parent);self.directory=Path(directory);self.model=model;self.thread=None;self.worker=None;self.close_after=False;self.report_result=None
        self.setWindowTitle('API流程验收');self.resize(820,800);layout=QVBoxLayout(self)
        layout.addWidget(label('固定流程验收','title'))
        layout.addWidget(label('默认使用离线模拟响应和真实本地工具。真实验收只发送所选合成样例及工具说明，不发送当前科研历史或记忆；不自动重试、批准或安装扩展。','muted'))
        self.cases=QListWidget()
        for case in evaluation_cases():
            item=QListWidgetItem(case['title']+(' · 控制回归' if case.get('host_only') else ''))
            item.setData(Qt.ItemDataRole.UserRole,case['id']);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked);self.cases.addItem(item)
        layout.addWidget(self.cases,1)
        self.live=QCheckBox('使用当前模型进行真实API验收（可能计费）');self.live.toggled.connect(self.mode_changed);layout.addWidget(self.live)
        self.options_widget=QWidget();self.options=QFormLayout(self.options_widget);self.fields={}
        for name,title,value,maximum in [('max_model_calls','总模型请求上限',30,100),('max_tool_calls','总工具尝试上限',40,200),('max_input_tokens','总输入token上限',1000000,10000000),('max_output_tokens','总输出token上限',80000,10000000),('request_output_tokens','单次输出token上限',2048,32768)]:
            field=QSpinBox();field.setRange(16 if name=='request_output_tokens' else 1,maximum);field.setValue(value);self.fields[name]=field;self.options.addRow(title,field)
        self.prices={}
        for name,title in [('input_per_million','每百万输入token单价'),('output_per_million','每百万输出token单价'),('currency','币种'),('max_cost','总金额上限')]:
            field=QLineEdit('未指定' if name=='currency' else '');field.setPlaceholderText('留空为未知/不限制');self.prices[name]=field;self.options.addRow(title,field)
        layout.addWidget(self.options_widget);self.feedback=QTextBrowser();self.feedback.setMinimumHeight(100);self.feedback.setMaximumHeight(180);layout.addWidget(self.feedback)
        row=QHBoxLayout();self.open=QPushButton('打开报告文件夹');self.open.setEnabled(False);self.open.clicked.connect(self.open_report);row.addWidget(self.open)
        self.run_button=QPushButton();self.run_button.clicked.connect(self.start);row.addWidget(self.run_button)
        self.stop=QPushButton('停止');self.stop.setEnabled(False);self.stop.clicked.connect(self.cancel_run);row.addWidget(self.stop)
        self.back=QPushButton('返回');self.back.clicked.connect(self.reject);row.addWidget(self.back);layout.addLayout(row);self.mode_changed()

    def mode_changed(self):
        live=self.live.isChecked();self.run_button.setText('开始真实验收（可能计费）' if live else '运行离线验收')
        self.options_widget.setVisible(live)
        for field in [*self.fields.values(),*self.prices.values()]:field.setEnabled(live and self.thread is None)
        if self.thread is None:self.feedback.setPlainText('真实模式遇到预算耗尽会停止后续真实样例。标记为控制回归的样例始终在离线模拟下验证。' if live else '离线验收不会发送真实模型请求，结果用于验证程序流程。')

    def start(self):
        if self.thread is not None:return
        selected=[self.cases.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.cases.count()) if self.cases.item(i).checkState()==Qt.CheckState.Checked]
        if not selected:QMessageBox.warning(self,'尚未开始','请选择至少一个样例。');return
        live=self.live.isChecked();limits=None
        if live:
            if self.model is None:QMessageBox.warning(self,'尚未配置模型','请先返回模型设置，配置本次使用的服务。');return
            try:
                limits={k:f.value() for k,f in self.fields.items()};limits.update({k:(f.text().strip() if k=='currency' else float(f.text()) if f.text().strip() else None) for k,f in self.prices.items()});validate_policy(limits)
            except ValueError as error:QMessageBox.warning(self,'预算无效',str(error));return
        self.thread=QThread(self);self.worker=EvaluationWorker(self.directory,selected,live,self.model,limits);self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run);self.worker.progress.connect(self.progress);self.worker.done.connect(self.completed);self.worker.done.connect(self.thread.quit);self.worker.done.connect(self.worker.deleteLater);self.thread.finished.connect(self.finished_run)
        self.run_button.setEnabled(False);self.cases.setEnabled(False);self.live.setEnabled(False);self.stop.setEnabled(True);self.open.setEnabled(False)
        for field in [*self.fields.values(),*self.prices.values()]:field.setEnabled(False)
        self.feedback.setPlainText('正在准备合成验收样例。');self.thread.start()

    def append_message(self,text):
        from PySide6.QtGui import QTextCursor
        self.feedback.moveCursor(QTextCursor.MoveOperation.End);self.feedback.insertPlainText('\n'+text)
    def progress(self,value):self.append_message(str(value['index'])+'/'+str(value['total'])+' '+value['title']+' · '+{'running':'运行中','passed':'通过','failed':'未通过'}.get(value['stage'],value['stage']))
    def completed(self,result):
        self.report_result=result;self.stop.setEnabled(False)
        if result['ok']:
            self.append_message('完成：通过 '+str(result['passed'])+'，未通过 '+str(result['failed'])+'，未运行 '+str(result['not_run'])+'；真实模型请求 '+str(result['real_model_requests'])+' 次。')
            self.open.setEnabled(True)
        else:self.append_message('验收未完成：'+result['error'])
    def finished_run(self):
        thread=self.thread;self.thread=None;self.worker=None;thread.deleteLater();self.run_button.setEnabled(True);self.cases.setEnabled(True);self.live.setEnabled(True)
        for field in [*self.fields.values(),*self.prices.values()]:field.setEnabled(self.live.isChecked())
        if self.close_after:super().reject()
    def cancel_run(self):
        if self.worker is not None:self.worker.cancel.set();self.stop.setEnabled(False);self.append_message('已请求停止；远程响应可能仍需等待返回或超时。')
    def open_report(self):
        if self.report_result and self.report_result.get('directory'):QDesktopServices.openUrl(QUrl.fromLocalFile(self.report_result['directory']))
    def reject(self):
        if self.thread is not None:self.close_after=True;self.cancel_run();return
        super().reject()
    def closeEvent(self,event):
        if self.thread is not None:self.close_after=True;self.cancel_run();event.ignore();return
        super().closeEvent(event)
