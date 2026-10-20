"""Public model settings and local checks; credentials are never persisted.

This module uses only the standard library. Environment variables retain
priority over the optional user configuration file. Status checks never connect.
"""
from dataclasses import dataclass,asdict
from importlib.util import find_spec
import ipaddress
import json
import math
import os
from pathlib import Path
import re
from urllib.parse import urlsplit,urlunsplit

from graph_research.runtime.storage import safe_path,write_json


class ModelConfigurationError(ValueError):
    pass


def configuration_path(path=None):
    supplied=path or os.environ.get('RESEARCH_MODEL_CONFIG')
    try:return Path(supplied or Path.home()/'.graph_research'/'model.json').expanduser()
    except RuntimeError:raise ModelConfigurationError('无法定位用户配置目录，请通过--config或RESEARCH_MODEL_CONFIG指定公开配置文件。') from None


def _loopback(host):
    if host and host.lower()=='localhost':return True
    try:return ipaddress.ip_address(host).is_loopback
    except ValueError:return False


def normalize_endpoint(base_url,mode=None):
    if not isinstance(base_url,str) or not base_url.strip() or len(base_url)>2048 or any(ord(ch)<32 for ch in base_url):
        raise ModelConfigurationError('请填写服务商提供的API基础地址。运行：python -m graph_research model setup')
    base_url=base_url.strip().rstrip('/')
    try:
        parsed=urlsplit(base_url);host=parsed.hostname;port=parsed.port
    except ValueError:raise ModelConfigurationError('API地址格式无效，请检查协议、主机名及端口。') from None
    if not host or any(ch.isspace() for ch in host) or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
        raise ModelConfigurationError('API地址不能包含用户名、密码、查询参数或片段；密钥请在本机隐藏输入或通过环境变量提供。')
    if parsed.scheme not in ('https','http'):raise ModelConfigurationError('API地址需要以https://开头；本机模型允许http://。')
    local=_loopback(host)
    if parsed.scheme=='http' and not local:raise ModelConfigurationError('远程API需要HTTPS；HTTP只允许localhost或回环IP。')
    path=parsed.path.rstrip('/');inferred=None
    for suffix,protocol in (('/chat/completions','chat_completions'),('/responses','responses')):
        if path.endswith(suffix):path=path[:-len(suffix)];inferred=protocol;break
    if mode is not None and mode not in ('responses','chat_completions'):raise ModelConfigurationError('协议应选择responses或chat_completions。')
    if inferred and mode and inferred!=mode:raise ModelConfigurationError('完整请求地址的结尾与所选协议不一致，请重新选择协议或填写基础地址。')
    mode=mode or inferred or 'responses'
    base=urlunsplit((parsed.scheme,parsed.netloc,path,'','')).rstrip('/')
    return base,mode,base+('/responses' if mode=='responses' else '/chat/completions')


@dataclass(frozen=True)
class ModelSettings:
    base_url:str
    model:str
    mode:str='responses'
    key_env:str='RESEARCH_API_KEY'
    auth_required:bool=True
    timeout_seconds:float=90
    json_mode:bool=True
    max_output_tokens:int|None=None
    chat_token_field:str='max_tokens'
    stream:bool=False
    reasoning_effort:str|None=None
    reasoning_profile:str='auto'

    @property
    def endpoint(self):
        return self.base_url+('/responses' if self.mode=='responses' else '/chat/completions')

    def public(self):
        return asdict(self)

    @property
    def is_local(self):
        return _loopback(urlsplit(self.base_url).hostname)


FIELDS=set(ModelSettings.__dataclass_fields__)


def validate_settings(values):
    if not isinstance(values,dict) or set(values)-FIELDS-{'version'}:raise ModelConfigurationError('配置含有不支持的字段。配置文件不能保存API密钥。')
    if 'version' in values and (type(values['version']) is not int or values['version']!=1):raise ModelConfigurationError('模型配置版本不受支持。')
    model=values.get('model')
    if not isinstance(model,str) or not model.strip() or len(model)>256 or any(ord(ch)<32 for ch in model):
        raise ModelConfigurationError('请填写服务商提供的模型ID，而非页面上的展示名称。运行：python -m graph_research model setup')
    if re.match(r'^(?:Bearer\s|sk[-_])[A-Za-z0-9_-]{16,}',model):raise ModelConfigurationError('模型ID看起来像密钥，已拒绝保存；请在隐藏密钥输入处填写密钥。')
    base,mode,_=normalize_endpoint(values.get('base_url'),values.get('mode'))
    key_env=values.get('key_env','RESEARCH_API_KEY')
    if not isinstance(key_env,str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,127}',key_env):raise ModelConfigurationError('密钥环境变量名称格式无效，通常使用RESEARCH_API_KEY。')
    auth=values.get('auth_required',True);json_mode=values.get('json_mode',True);stream=values.get('stream',False)
    if any(type(v) is not bool for v in (auth,json_mode,stream)):raise ModelConfigurationError('认证、JSON和流式模式开关必须是布尔值。')
    timeout=values.get('timeout_seconds',90)
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 5<=timeout<=300:raise ModelConfigurationError('请求超时应在5至300秒之间。')
    tokens=values.get('max_output_tokens')
    if tokens is not None and (type(tokens) is not int or not 16<=tokens<=32768):raise ModelConfigurationError('输出token上限应为16至32768之间的整数，或不指定。')
    token_field=values.get('chat_token_field','max_tokens')
    if token_field not in ('max_tokens','max_completion_tokens'):raise ModelConfigurationError('Chat输出上限字段应为max_tokens或max_completion_tokens。')
    effort=values.get('reasoning_effort');profile=values.get('reasoning_profile','auto')
    if profile not in ('auto','off','openai'):raise ModelConfigurationError('思考强度兼容方式无效。')
    from .model_capabilities import reasoning_choices
    if effort not in reasoning_choices(base,model.strip(),profile):
        raise ModelConfigurationError('当前模型未确认支持此思考档位；请选择服务默认，或按服务商文档手动指定OpenAI兼容方式。')
    return ModelSettings(base,model.strip(),mode,key_env,auth,float(timeout),json_mode,tokens,token_field,stream,effort,profile)


def load_public_config(path=None):
    try:path=configuration_path(path)
    except ModelConfigurationError:
        if os.environ.get('RESEARCH_BASE_URL') and os.environ.get('RESEARCH_MODEL'):return {}
        raise
    if not path.exists():return {}
    if path.stat().st_size>32768:raise ModelConfigurationError('模型配置文件过大，请通过配置向导重新创建。')
    try:document=json.loads(path.read_text(encoding='utf-8-sig'))
    except (ValueError,OSError):raise ModelConfigurationError('模型配置文件无法读取，请检查文件或通过配置向导重新创建。') from None
    if not isinstance(document,dict) or set(document)-FIELDS-{'version'}:raise ModelConfigurationError('模型配置只允许公开设置，不能包含密钥或其他字段。')
    return document


def load_settings(path=None):
    values=load_public_config(path)
    for key,variable in [('base_url','RESEARCH_BASE_URL'),('model','RESEARCH_MODEL'),('mode','RESEARCH_API_MODE')]:
        if os.environ.get(variable):values[key]=os.environ[variable]
    return validate_settings(values)


def save_configuration(values,path=None):
    settings=validate_settings(values)
    target=safe_path(configuration_path(path))
    # Only update a known public-only configuration. Preserve an unknown or
    # manually credential-bearing file in place rather than copy OR erase it.
    previous_safe=False
    if target.exists():
        try:validate_settings(load_public_config(target));previous_safe=True
        except ModelConfigurationError:raise ModelConfigurationError('现有配置损坏或含未支持字段，未覆盖也未复制。请先整理该文件，或使用--config指定一个新文件。') from None
    write_json(target,{'version':1,**settings.public()},backup=previous_safe)
    return settings,target


def configuration_status(path=None):
    """Read-only diagnostics. A configured key is not a connection test."""
    try:location=str(configuration_path(path).resolve())
    except ModelConfigurationError:location=None
    report={'configuration_file':location,'connection_tested':False,
            'dependencies':{name:find_spec(name) is not None for name in ('httpx','langgraph')},
            'environment_overrides':[name for name in ('RESEARCH_MODEL','RESEARCH_BASE_URL','RESEARCH_API_MODE') if os.environ.get(name)]}
    try:
        settings=load_settings(path)
        key_present=bool(os.environ.get(settings.key_env,'').strip())
        report.update(valid=True,settings=settings.public(),request_url=settings.endpoint,key_configured=key_present,
                      ready_without_prompt=not settings.auth_required or key_present,
                      next_step='可执行model test进行一次最小连接测试，或运行chat开始对话。' if not settings.auth_required or key_present else '地址与模型已配置。运行model test或chat时，可在本机终端隐藏输入密钥。')
    except ModelConfigurationError as exc:
        report.update(valid=False,key_configured=False,ready_without_prompt=False,error=str(exc),
                      next_step='运行：python -m graph_research model setup')
    return report


def setup_wizard(path=None,*,input_fn=input,print_fn=print):
    """Ask only public settings. Never asks for, stores or tests a key here."""
    print_fn('模型接入向导：仅保存公开配置，不保存密钥，也不会发出网络请求。')
    print_fn('请准备：API地址、模型ID、协议类型。它们来自你的模型服务商。')
    try:previous=load_public_config(path)
    except ModelConfigurationError:previous={}
    def ask(label,default=''):
        prompt=label+(f' [{default}]' if default else '')+'：'
        return input_fn(prompt).strip() or default
    print_fn('1. 协议：输入1选择Chat Completions兼容接口；输入2选择Responses接口。')
    protocol=ask('协议编号','2' if previous.get('mode')=='responses' else '1')
    if protocol not in ('1','2'):raise ModelConfigurationError('协议编号应为1或2，请重新运行向导。')
    mode='chat_completions' if protocol=='1' else 'responses'
    base=ask('2. API基础地址（可含/v1，不要填写密钥）',previous.get('base_url',''))
    model=ask('3. 模型ID',previous.get('model',''))
    auth=ask('4. 服务是否需要API密钥？y=需要，n=不需要','n' if previous.get('auth_required') is False else 'y').lower()
    if auth not in ('y','n'):raise ModelConfigurationError('请输入y或n。')
    settings,target=save_configuration({**previous,'base_url':base,'model':model,'mode':mode,'auth_required':auth=='y'},path)
    print_fn('已保存公开配置：'+str(target))
    print_fn('实际请求地址：'+settings.endpoint)
    print_fn('认证来源：'+settings.key_env+'环境变量或本机隐藏输入；没有读取或保存密钥。' if settings.auth_required else '此服务选择无需认证，不会发送环境中的已有密钥。')
    if os.environ.get('RESEARCH_BASE_URL') or os.environ.get('RESEARCH_MODEL') or os.environ.get('RESEARCH_API_MODE'):
        print_fn('当前终端的RESEARCH_*环境变量优先于配置文件；请用model status核对实际生效设置。')
    print_fn('下一步：python -m graph_research model status（只检查本地配置）')
    print_fn('可选：python -m graph_research model test（发出一次短请求，可能产生少量API用量）')
    print_fn('开始使用：python -m graph_research chat --user 你的用户标识（密钥仅在本机隐藏输入）')
    return settings
