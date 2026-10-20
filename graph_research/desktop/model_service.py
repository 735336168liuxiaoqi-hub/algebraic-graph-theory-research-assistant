"""Durable standalone model sessions, isolated from offline and delegated tasks."""
import copy
import uuid

from graph_research.assistant.session import ResearchSession
from graph_research.runtime.storage import read_json
from graph_research.tools.registry import ToolRegistry
from graph_research.assistant.offline import grouped_tools
from .service import DesktopWorkspace


class ModelWorkspace(DesktopWorkspace):
    RESULT_MODE='api'
    def _bind(self,session):
        if session.results_directory is None:session.results_directory=self.results_preferences.active;session.results_mode='api'
        self.results_preferences.remember(session.results_directory)
        self.session=session
        self.registry=ToolRegistry();session.store.load_into(self.registry)
        self.groups=grouped_tools(self.registry)
        from graph_research.runtime.storage import write_json
        if session.directory.parent==self.directory:
            write_json(self.directory/'desktop.json',{'version':1,'last_session':session.directory.name})
        return session

    def new_session(self):
        return self._bind(ResearchSession(self.directory/('session_'+uuid.uuid4().hex[:12]),self.tool_directory,results_directory=self.results_preferences.active,results_mode='api'))

    def open_session(self,directory):
        from pathlib import Path
        saved,_=read_json(Path(directory)/'session.json',recover=True)
        context=saved.get('task_context',{})
        if context and context.get('interaction_mode')!='standalone_chat':
            raise ValueError('请选择独立模型对话会话；本地工具与主agent任务由各自入口继续。')
        session=ResearchSession(directory,results_directory=self.results_preferences.active,results_mode='api')
        # A process that ended abruptly must never silently replay an API call.
        if session.state.get('status')=='running':
            session.state.update(status='execution_error',answer='上次运行中断。已有结果已保留，点击“继续未完成任务”才会再次请求模型。')
        return self._bind(session)

    def history(self):
        return copy.deepcopy([o for o in self.session.state.get('observations',[]) if 'tool' in o])


class SafeModel:
    """Keep adapter errors and known credentials out of durable research data."""
    def __init__(self,actual,progress=None,on_text=None,cancel=None):
        self.actual=actual;self.progress=progress;self.calls=0;self.usage={};self.on_text=on_text;self.cancel=cancel

    def redact(self,text):
        secret=getattr(self.actual,'api_key','')
        return text.replace(secret,'[密钥已隐藏]') if secret else text

    def _clean(self,value):
        if isinstance(value,str):return self.redact(value)
        if isinstance(value,list):return [self._clean(v) for v in value]
        if isinstance(value,dict):return {self.redact(str(k)):self._clean(v) for k,v in value.items()}
        return value

    def complete(self,messages,*,max_output_tokens=None):
        self.calls+=1
        if self.progress:self.progress('正在请求模型 · 本次操作第'+str(self.calls)+'次请求')
        try:
            import inspect
            parameters=inspect.signature(self.actual.complete).parameters
            options={'max_output_tokens':max_output_tokens} if max_output_tokens is not None and 'max_output_tokens' in parameters else {}
            if 'cancel' in parameters:options['cancel']=self.cancel
            if 'on_text' in parameters and self.on_text is not None:options['on_text']=self.preview
            result=self.actual.complete(messages,**options)
        except InterruptedError:raise
        except Exception as exc:
            if type(exc).__module__ in ('graph_research.assistant.model','graph_research.assistant.model_config'):
                raise RuntimeError(self.redact(str(exc))) from None
            raise RuntimeError('模型适配器调用失败；原始异常未写入会话，以免泄露凭据。') from None
        self.usage=dict(getattr(self.actual,'last_usage',None) or {})
        return self._clean(result)

    def preview(self,text):
        text=self.redact(text);secret=getattr(self.actual,'api_key','')
        for length in range(min(len(text),len(secret)-1),0,-1):
            if text.endswith(secret[:length]):text=text[:-length]+'…';break
        self.on_text(text[:16000])
