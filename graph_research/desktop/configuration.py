"""Native model profiles, explicit discovery, and process-only credentials."""
import copy
import json
import os
from PySide6.QtCore import QObject,QThread,Signal,Qt
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QWidget,QScrollArea
from .widgets import QDialog,QFormLayout,QLineEdit,QComboBox,QCheckBox,QSpinBox,QPushButton,QMessageBox,QInputDialog
from graph_research.assistant.model_config import load_settings,validate_settings,save_configuration,normalize_endpoint
from graph_research.assistant.model_profiles import load_profiles,save_profiles,credential_scope,public_name
from graph_research.assistant.model_capabilities import reasoning_choices,EFFORT_LABELS
from .app import label
from .i18n import UiText,bind


class ModelChoice(QComboBox):
    """Editable IDs, retaining old text-field accessors for integrations."""
    def __init__(self):
        super().__init__();self.setProperty('i18n_raw',True);self.setEditable(True);self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        bind(self.lineEdit(),'placeholder',type(self.lineEdit()).setPlaceholderText,'选择或填写服务商模型ID');self.lineEdit().setMaxLength(256)
        self.setMinimumContentsLength(18);self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    def text(self):return self.currentText()
    def setText(self,text):self.setEditText(text)


def fill_efforts(widget,base,model,profile,selected=None):
    widget.blockSignals(True);widget.clear()
    for value in reasoning_choices(base,model,profile):widget.addItem(UiText(EFFORT_LABELS[value],'Off') if value=='none' else EFFORT_LABELS[value],value)
    widget.setCurrentIndex(max(0,widget.findData(selected)));widget.blockSignals(False)


class ProbeWorker(QObject):
    done=Signal(object)
    def __init__(self,model,kind='probe'):super().__init__();self.model=model;self.kind=kind
    def run(self):
        try:
            result={'models':self.model.list_models()} if self.kind=='models' else self.model.test_connection()
            self.done.emit({'ok':True,**result})
        except Exception as exc:
            known=type(exc).__module__ in ('graph_research.assistant.model','graph_research.assistant.model_config')
            text=str(exc) if known else '请求未完成；请核对服务商配置。'
            secret=getattr(self.model,'api_key','')
            self.done.emit({'ok':False,'error':text.replace(secret,'[密钥已隐藏]') if secret else text})


class ModelDialog(QDialog):
    def __init__(self,parent=None,*,config_path=None,settings=None,credentials=None,current_profile=None):
        super().__init__(parent);self.config_path=config_path;self.model=None;self.settings=None;self.thread=None;self.worker=None
        self.credentials=dict(credentials or {});self.loading=True;self.scope=None;self.kind=None
        self.setWindowTitle('模型设置');self.resize(700,790)
        if settings is None:
            try:settings=load_settings(config_path)
            except ValueError:settings=None
        self.profiles_error=None
        try:self.profiles=load_profiles(config_path)
        except ValueError as error:self.profiles={};self.profiles_error=str(error)
        self.current_profile=current_profile or next((name for name,r in self.profiles.items() if settings and r['settings']==settings.public()),None)
        values=settings.public() if settings else {}
        outer=QVBoxLayout(self);outer.addWidget(label('模型设置','title'))
        row=QHBoxLayout();row.addWidget(label('配置'));self.profile_choice=QComboBox();self.profile_choice.addItem('当前设置',None)
        for name in self.profiles:self.profile_choice.addRawItem(name,name)
        self.profile_choice.setCurrentIndex(max(0,self.profile_choice.findData(self.current_profile)));row.addWidget(self.profile_choice,1)
        self.save_as=QPushButton('另存配置');self.save_as.clicked.connect(self.save_as_profile);row.addWidget(self.save_as)
        self.remove=QPushButton('删除配置');self.remove.clicked.connect(self.delete_profile);row.addWidget(self.remove);outer.addLayout(row)
        scroll=QScrollArea();scroll.setWidgetResizable(True);self.editor=QWidget();form=QFormLayout(self.editor);scroll.setWidget(self.editor);outer.addWidget(scroll,1)
        self.address=QLineEdit();self.address.setPlaceholderText('https://服务商地址/v1');form.addRow('API 基础地址',self.address)
        self.model_id=ModelChoice();self.fetch_models=QPushButton('获取模型列表');self.fetch_models.clicked.connect(self.discover_models)
        model_row=QHBoxLayout();model_row.addWidget(self.model_id,1);model_row.addWidget(self.fetch_models);form.addRow('模型',model_row)
        self.protocol=QComboBox();self.protocol.addItem('响应接口 · Responses','responses');self.protocol.addItem('对话补全接口 · Chat Completions','chat_completions');form.addRow('接口协议',self.protocol)
        self.protocol.setToolTip('选择服务商支持的接口协议。')
        self.reasoning_profile=QComboBox()
        for text,value in [('自动识别','auto'),('OpenAI 兼容 · 手动指定','openai'),('不发送思考参数','off')]:self.reasoning_profile.addItem(text,value)
        self.reasoning_profile.setToolTip('自动识别仅适用于已确认的官方模型；其他服务可按其文档选择兼容方式。')
        form.addRow('思考参数兼容',self.reasoning_profile)
        self.effort=QComboBox();form.addRow('思考强度',self.effort)
        self.endpoint=label('','muted');form.addRow('实际请求地址',self.endpoint)
        self.key_env=QLineEdit();form.addRow('密钥环境变量',self.key_env)
        self.password=QLineEdit();self.password.setEchoMode(QLineEdit.EchoMode.Password);self.password.setMaxLength(8192)
        self.password.setPlaceholderText('仅本次程序使用；留空则读取环境变量');form.addRow('API 密钥',self.password)
        self.auth=QCheckBox('接口需要密钥');form.addRow('',self.auth)
        self.json_mode=QCheckBox('请求 JSON 对象输出');form.addRow('',self.json_mode)
        self.streaming=QCheckBox('逐步显示回答');form.addRow('',self.streaming)
        self.streaming.setToolTip('完整JSON校验完成后才执行工具或保存正式回答。')
        self.timeout=QSpinBox();self.timeout.setRange(5,300);self.timeout.setSuffix(' 秒');form.addRow('请求超时',self.timeout)
        self.tokens=QSpinBox();self.tokens.setRange(0,32768);self.tokens.setSpecialValueText('不指定');form.addRow('输出 token 上限',self.tokens)
        self.token_field=QComboBox();self.token_field.addItem('输出上限 · max_tokens','max_tokens');self.token_field.addItem('补全上限 · max_completion_tokens','max_completion_tokens')
        self.token_field.setToolTip('按服务商要求选择；仅用于 Chat Completions。');form.addRow('对话补全上限字段',self.token_field)
        for combo in (self.protocol,self.token_field,self.reasoning_profile):
            for i in range(combo.count()):combo.setItemData(i,combo.itemText(i)+'；'+combo.toolTip(),Qt.ItemDataRole.ToolTipRole)
            combo.view().setMouseTracking(True)
        self.feedback=label(self.profiles_error or '保存和启用不发送请求；密钥不写入配置。','muted');outer.addWidget(self.feedback)
        row=QHBoxLayout();self.save=QPushButton('保存配置');self.save.clicked.connect(self.save_public);row.addWidget(self.save)
        self.probe=QPushButton('测试连接（1次请求）');self.probe.clicked.connect(self.test_connection);row.addWidget(self.probe);outer.addLayout(row)
        outer.addWidget(label('科研提问会发送问题、工具说明与本会话所需记录。连接测试仅发送固定短消息。','muted'))
        row=QHBoxLayout();row.addStretch();self.cancel_button=QPushButton('取消');self.cancel_button.clicked.connect(self.reject);row.addWidget(self.cancel_button)
        self.use=QPushButton('保存并启用');self.use.setObjectName('primary');self.use.clicked.connect(self.enable);row.addWidget(self.use);outer.addLayout(row)
        self.load_form(values,self.profiles.get(self.current_profile,{}).get('models',[]))
        self.profile_choice.currentIndexChanged.connect(self.choose_profile)
        self.address.textChanged.connect(self.connection_changed);self.key_env.textChanged.connect(self.connection_changed);self.auth.toggled.connect(self.connection_changed)
        self.protocol.currentIndexChanged.connect(self.update_endpoint)
        self.model_id.currentTextChanged.connect(self.update_efforts);self.reasoning_profile.currentIndexChanged.connect(self.update_efforts)

    def load_form(self,values,models):
        self.loading=True
        self.address.setText(values.get('base_url',''));self.key_env.setText(values.get('key_env','RESEARCH_API_KEY'))
        self.auth.setChecked(values.get('auth_required',True));self.protocol.setCurrentIndex(max(0,self.protocol.findData(values.get('mode','responses'))))
        self.model_id.clear();self.model_id.addItems(models);self.model_id.setText(values.get('model',''))
        self.reasoning_profile.setCurrentIndex(max(0,self.reasoning_profile.findData(values.get('reasoning_profile','auto'))))
        self.json_mode.setChecked(values.get('json_mode',True));self.streaming.setChecked(values.get('stream',False))
        self.timeout.setValue(int(values.get('timeout_seconds',90)));self.tokens.setValue(values.get('max_output_tokens') or 0)
        self.token_field.setCurrentIndex(max(0,self.token_field.findData(values.get('chat_token_field','max_tokens'))))
        self.scope=self.current_scope();self.password.setText(self.credentials.get(self.scope,''));self.loading=False
        self.update_endpoint();self.update_efforts(selected=values.get('reasoning_effort'))

    def current_scope(self):
        try:return (normalize_endpoint(self.address.text())[0],self.key_env.text(),self.auth.isChecked())
        except ValueError:return None

    def remember_key(self):
        if self.scope and self.password.text():self.credentials[self.scope]=self.password.text()

    def connection_changed(self,*args):
        if self.loading:return
        new=self.current_scope()
        if new!=self.scope:
            self.remember_key();self.scope=new;self.password.setText(self.credentials.get(new,''))
            text=self.model_id.text();self.model_id.blockSignals(True);self.model_id.clear();self.model_id.setText(text);self.model_id.blockSignals(False)
        self.update_endpoint();self.update_efforts()

    def update_endpoint(self,*args):
        try:self.endpoint.setText(normalize_endpoint(self.address.text(),self.protocol.currentData())[2])
        except ValueError:self.endpoint.setText('请填写与所选协议匹配的基础地址')

    def update_efforts(self,*args,selected=None):
        if self.loading:return
        if selected is None:selected=self.effort.currentData()
        fill_efforts(self.effort,self.address.text(),self.model_id.text().strip(),self.reasoning_profile.currentData(),selected)

    def choose_profile(self,index):
        if self.loading:return
        self.remember_key();self.current_profile=self.profile_choice.itemData(index)
        record=self.profiles.get(self.current_profile,{'settings':{},'models':[]});self.load_form(record['settings'],record['models'])

    def read_settings(self,*,discovery=False):
        return validate_settings({'base_url':self.address.text(),'model':'model-list' if discovery else self.model_id.text(),'mode':self.protocol.currentData(),
            'key_env':self.key_env.text(),'auth_required':self.auth.isChecked(),'json_mode':self.json_mode.isChecked(),
            'timeout_seconds':self.timeout.value(),'max_output_tokens':self.tokens.value() or None,'chat_token_field':self.token_field.currentData(),'stream':self.streaming.isChecked(),
            'reasoning_profile':self.reasoning_profile.currentData(),'reasoning_effort':None if discovery else self.effort.currentData()})

    def make_model(self,settings):
        from graph_research.assistant.model import ConfiguredModel
        return ConfiguredModel(settings,api_key=self.password.text() or None)

    def persist(self,settings,name=None):
        if self.profiles_error:raise ValueError(self.profiles_error)
        name=public_name(name or self.current_profile or settings.model[:80])
        models=list(dict.fromkeys([settings.model,*[self.model_id.itemText(i) for i in range(self.model_id.count())]]))[:1000]
        profiles=load_profiles(self.config_path);profiles[name]={'settings':settings.public(),'models':models}
        text=json.dumps(profiles,ensure_ascii=False)
        secrets=[self.password.text(),*self.credentials.values(),os.environ.get(settings.key_env,'') if settings.auth_required else '']
        if any(secret and secret in text for secret in secrets):raise ValueError('公开设置中出现了当前密钥，已拒绝保存。')
        from graph_research.assistant.model_config import load_public_config,configuration_path
        if configuration_path(self.config_path).exists():validate_settings(load_public_config(self.config_path))
        self.profiles=save_profiles(profiles,self.config_path);save_configuration(settings.public(),self.config_path)
        self.current_profile=name;self.profile_choice.blockSignals(True);self.profile_choice.clear();self.profile_choice.addItem('当前设置',None)
        for key in self.profiles:self.profile_choice.addItem(key,key)
        self.profile_choice.setCurrentIndex(self.profile_choice.findData(name));self.profile_choice.blockSignals(False);self.remember_key()

    def save_public(self):
        try:self.persist(self.read_settings());self.feedback.setText('配置已保存；没有发送请求或保存密钥。')
        except Exception as exc:QMessageBox.warning(self,'配置未保存',str(exc))

    def save_as_profile(self):
        name,ok=QInputDialog.getText(self,'另存配置','配置名称')
        if not ok:return
        try:
            if name.strip() in self.profiles:raise ValueError('此名称已存在；请选择其他名称，或选中原配置后保存。')
            self.persist(self.read_settings(),name);self.feedback.setText('新配置已保存。')
        except Exception as exc:QMessageBox.warning(self,'配置未保存',str(exc))

    def delete_profile(self):
        if self.current_profile not in self.profiles:return
        if QMessageBox.question(self,'删除配置','删除“'+self.current_profile+'”？')!=QMessageBox.StandardButton.Yes:return
        try:
            profiles=copy.deepcopy(self.profiles);del profiles[self.current_profile];self.profiles=save_profiles(profiles,self.config_path)
            index=self.profile_choice.currentIndex();self.profile_choice.removeItem(index);self.current_profile=self.profile_choice.currentData()
        except Exception as exc:QMessageBox.warning(self,'配置未删除',str(exc))

    def enable(self):
        try:
            settings=self.read_settings();model=self.make_model(settings);self.persist(settings)
            self.settings=settings;self.model=model;self.credentials[credential_scope(settings)]=model.api_key;self.password.clear();self.accept()
        except Exception as exc:QMessageBox.warning(self,'模型未启用',str(exc))

    def start_request(self,kind):
        if self.thread is not None:return
        try:model=self.make_model(self.read_settings(discovery=kind=='models'))
        except Exception as exc:QMessageBox.warning(self,'未发送请求',str(exc));return
        self.kind=kind;self.thread=QThread(self);self.worker=ProbeWorker(model,kind);self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run);self.worker.done.connect(self.probe_done);self.worker.done.connect(self.thread.quit)
        self.worker.done.connect(self.worker.deleteLater);self.thread.finished.connect(self.probe_finished)
        for widget in (self.editor,self.profile_choice,self.save_as,self.remove,self.save,self.use,self.probe,self.cancel_button):widget.setEnabled(False)
        self.feedback.setText('正在获取模型列表……' if kind=='models' else '正在发送1次连接测试……');self.thread.start()

    def discover_models(self):self.start_request('models')
    def test_connection(self):self.start_request('probe')

    def probe_done(self,result):
        if not result.get('ok'):self.feedback.setText(result['error']);return
        if self.kind=='models':
            text=self.model_id.text();effort=self.effort.currentData();self.model_id.blockSignals(True)
            self.model_id.clear();self.model_id.addItems(result['models']);self.model_id.setText(text);self.model_id.blockSignals(False);self.update_efforts(selected=effort)
            self.feedback.setText('已获取'+str(len(result['models']))+'个模型；请选择，也可手动填写。')
        else:self.feedback.setText('连接与最小 JSON 决策验证通过。用量：'+str(result.get('usage') or '服务商未返回'))

    def probe_finished(self):
        thread=self.thread;self.thread=None;self.worker=None;thread.deleteLater()
        for widget in (self.editor,self.profile_choice,self.save_as,self.remove,self.save,self.use,self.probe,self.cancel_button):widget.setEnabled(True)

    def reject(self):
        if self.thread is not None:return
        self.password.clear();self.credentials.clear();super().reject()

    def closeEvent(self,event):
        if self.thread is not None:event.ignore()
        else:self.password.clear();self.credentials.clear();event.accept()
