"""Bounded HTTP model adapter with public configuration and redacted errors."""
import getpass
import json
import os
import sys
import httpx

from .model_config import ModelConfigurationError,load_settings,load_public_config,validate_settings


class ModelAPIError(RuntimeError):
    def __init__(self,code,message):
        self.code=code
        super().__init__(message)


def _http_error(status):
    messages={
        400:('request_rejected','接口拒绝请求格式：检查协议、模型ID、JSON模式及输出上限字段；程序不会自动换协议重试。'),
        401:('authentication_failed','密钥验证失败：检查密钥所属服务商、是否过期，以及当前使用的密钥环境变量。'),
        402:('account_payment_required','服务返回付款或余额问题：请到所选服务商控制台查看账户状态。'),
        403:('access_denied','服务拒绝访问：检查模型权限、账户或访问策略。'),
        404:('endpoint_or_model_not_found','地址或模型未找到：检查实际请求地址、/v1路径、协议以及模型ID。'),
        413:('request_too_large','请求过大：请缩小上下文或任务输入。'),
        429:('rate_or_quota_limit','服务触发频率或配额限制：请查看账户用量并稍后手工继续；本程序不自动重试扣费请求。'),
    }
    if 300<=status<400:return ModelAPIError('redirect_refused','API返回重定向，程序未跟随，以免将密钥发往其他地址；请核对正确的基础地址。')
    code,message=messages.get(status,('provider_unavailable','模型服务暂时不可用，请检查服务商状态，稍后手工继续。') if status>=500 else ('http_error','API请求失败，请核对服务商的接口配置。'))
    return ModelAPIError(code,f'{message}（HTTP {status}）')


def _reject_constant(value):
    raise ValueError('Nonfinite JSON')


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate JSON key')
        result[key]=value
    return result


class ConfiguredModel:
    """Read credentials on construction; never serialize them into sessions.

    Library callers remain noninteractive. CLI callers can explicitly enable a
    hidden terminal prompt; getpass's echoing fallback is refused.
    """
    def __init__(self,settings=None,*,config_path=None,prompt_for_key=False,api_key=None):
        self.settings=validate_settings(settings.public()) if settings is not None else load_settings(config_path)
        self.model=self.settings.model;self.base_url=self.settings.base_url;self.mode=self.settings.mode
        if api_key is not None and not isinstance(api_key,str):raise ModelConfigurationError('API密钥应为文本。')
        self.api_key=(os.environ.get(self.settings.key_env,'') if api_key is None else api_key).strip() if self.settings.auth_required else ''
        if self.settings.auth_required and not self.api_key:
            if prompt_for_key and sys.stdin.isatty() and sys.stderr.isatty():
                import warnings
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter('error',getpass.GetPassWarning)
                        self.api_key=getpass.getpass('API密钥（隐藏输入，仅保留在本次进程内，不写入配置）：').strip()
                except (getpass.GetPassWarning,EOFError):raise ModelConfigurationError('当前终端无法安全隐藏输入，请在本机交互终端运行，或通过指定环境变量提供密钥。') from None
            else:raise ModelConfigurationError('尚未提供API密钥。请在本机终端运行model test或chat隐藏输入，或设置'+self.settings.key_env+'；不要将密钥发送到聊天或写入配置文件。')
        if self.settings.auth_required and (not self.api_key or len(self.api_key)>8192 or any(not 33<=ord(ch)<=126 for ch in self.api_key)):
            raise ModelConfigurationError('API密钥为空或含无效字符。请仅输入密钥本身，不含Bearer前缀、空白或智能引号。')
        self.last_usage=None

    def complete(self,messages,*,max_output_tokens=None,on_text=None,cancel=None):
        if not isinstance(messages,list) or not messages:raise ValueError('Model messages must be a nonempty list')
        limit=max_output_tokens if max_output_tokens is not None else self.settings.max_output_tokens
        if limit is not None and (type(limit) is not int or not 16<=limit<=32768):raise ModelConfigurationError('输出token上限无效。')
        if self.mode=='responses':
            payload={'model':self.model,'input':messages}
            if self.settings.json_mode:payload['text']={'format':{'type':'json_object'}}
            if limit is not None:payload['max_output_tokens']=limit
        else:
            payload={'model':self.model,'messages':messages}
            if self.settings.json_mode:payload['response_format']={'type':'json_object'}
            if limit is not None:payload[self.settings.chat_token_field]=limit
        headers={'Authorization':'Bearer '+self.api_key} if self.api_key else {}
        if self.settings.reasoning_effort is not None:
            if self.mode=='responses':payload['reasoning']={'effort':self.settings.reasoning_effort}
            else:payload['reasoning_effort']=self.settings.reasoning_effort
        if self.settings.stream:
            payload['stream']=True
            if self.mode!='responses':payload['stream_options']={'include_usage':True}
        self.last_usage=None
        streamed_text=None
        def record_usage(usage):
            self.last_usage={key:value for key,value in usage.items() if key in ('input_tokens','output_tokens','total_tokens','prompt_tokens','completion_tokens') and type(value) is int and value>=0}
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds,follow_redirects=False,trust_env=not self.settings.is_local) as client:
                with client.stream('POST',self.settings.endpoint,json=payload,headers=headers) as response:
                    if response.status_code!=200:raise _http_error(response.status_code)
                    if self.settings.stream and 'text/event-stream' in response.headers.get('content-type',''):
                        from .streaming import consume_stream,StreamFormatError
                        try:streamed_text,_=consume_stream(response,self.mode,on_text=on_text,on_usage=record_usage,cancel=cancel,timeout=self.settings.timeout_seconds)
                        except StreamFormatError as error:raise ModelAPIError('incomplete_stream',str(error)) from None
                    else:
                        raw=bytearray()
                        for chunk in response.iter_bytes(chunk_size=16384):
                            if cancel is not None and cancel.is_set():raise InterruptedError('用户停止了模型响应；用量可能未知。')
                            if len(raw)+len(chunk)>1024*1024:raise ModelAPIError('response_too_large','模型响应超过1MiB，已停止读取；请缩小任务或设置输出上限。')
                            raw.extend(chunk)
        except httpx.TimeoutException:raise ModelAPIError('timeout','模型请求超时。请检查网络、模型响应速度或配置的超时；已完成计算可从会话记录继续，不会自动重试。') from None
        except httpx.RequestError:raise ModelAPIError('connection_failed','无法连接模型接口。请检查基础地址、网络、代理与证书设置；程序不会关闭证书验证。') from None
        except httpx.InvalidURL:raise ModelAPIError('invalid_url','HTTP客户端无法识别该API地址，请重新运行model setup。') from None
        try:
            body=json.loads(raw) if streamed_text is None else {}
            if not isinstance(body,dict):raise ValueError()
            if isinstance(body.get('usage'),dict):record_usage(body['usage'])
            if streamed_text is not None:text=streamed_text
            elif self.mode=='responses':
                if body.get('status') in ('failed','incomplete','cancelled'):raise ModelAPIError('incomplete_response','模型未完成输出，请检查输出上限或服务状态；未执行不完整的工具决策。')
                text=''.join(content.get('text','') for item in body.get('output',[]) if isinstance(item,dict)
                             for content in item.get('content',[]) if isinstance(content,dict) and content.get('type')=='output_text')
            else:
                choice=body['choices'][0]
                if choice.get('finish_reason')=='length':raise ModelAPIError('incomplete_response','模型达到输出上限，返回内容不完整；请调整上限，未执行该决策。')
                text=choice['message']['content']
            if not isinstance(text,str):raise ValueError()
            result=json.loads(text,parse_constant=_reject_constant,object_pairs_hook=_unique_object)
            if not isinstance(result,dict):raise ValueError()
        except (ValueError,TypeError,KeyError,IndexError,AttributeError):raise ModelAPIError('invalid_json_response','服务已响应，但没有返回所需的完整JSON对象。请核对协议、JSON模式及模型的结构化输出能力；未执行工具。') from None
        return result

    def list_models(self):
        """One explicit bounded GET; no completions, redirects, retries or paging."""
        from .model_profiles import public_name
        headers={'Authorization':'Bearer '+self.api_key} if self.api_key else {}
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds,follow_redirects=False,trust_env=not self.settings.is_local) as client:
                with client.stream('GET',self.base_url+'/models',headers=headers) as response:
                    if response.status_code!=200:raise _http_error(response.status_code)
                    raw=bytearray()
                    for chunk in response.iter_bytes(chunk_size=16384):
                        if len(raw)+len(chunk)>1024*1024:raise ModelAPIError('response_too_large','模型列表超过1MiB；可手动填写模型ID。')
                        raw.extend(chunk)
        except httpx.TimeoutException:raise ModelAPIError('timeout','获取模型列表超时；可手动填写模型ID。') from None
        except (httpx.RequestError,httpx.InvalidURL):raise ModelAPIError('connection_failed','无法获取模型列表；请检查地址，或手动填写模型ID。') from None
        try:
            body=json.loads(raw,parse_constant=_reject_constant,object_pairs_hook=_unique_object)
            rows=body['data']
            if not isinstance(rows,list) or len(rows)>1000:raise ValueError()
            models=sorted(set(public_name(row['id'],maximum=256) for row in rows))
            if any(self.api_key and self.api_key in value for value in models):raise ValueError()
        except (ValueError,TypeError,KeyError,AttributeError):
            raise ModelAPIError('invalid_model_list','服务未返回有效的兼容模型列表；可手动填写模型ID。') from None
        return models

    def test_connection(self,*,max_output_tokens=128):
        """One explicitly requested short JSON probe; no research data or tools."""
        if type(max_output_tokens) is not int or not 16<=max_output_tokens<=4096:raise ModelConfigurationError('连接测试的输出上限应在16至4096之间。')
        result=self.complete([{'role':'system','content':'Return a JSON object only. Do not call tools.'},
                              {'role':'user','content':'Return exactly this JSON: {"action":"final","answer":"连接成功"}'}],max_output_tokens=max_output_tokens)
        if result.get('action')!='final' or not isinstance(result.get('answer'),str) or not result['answer'].strip():
            raise ModelAPIError('decision_protocol_failed','连接成功，但模型未遵循最小JSON决策协议。暂不应投入自动工具调用。')
        return {'ok':True,'model':self.model,'request_url':self.settings.endpoint,'protocol':self.mode,
                'structured_json_verified':True,'requests_sent':1,'max_output_tokens':max_output_tokens,'usage':self.last_usage,
                'scope':'仅验证一次短请求与最小JSON决策，不表示所有科研任务或工具选择已验证。'}
