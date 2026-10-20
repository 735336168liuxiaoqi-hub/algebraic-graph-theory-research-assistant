"""Public named connection profiles. Credentials are deliberately not a field."""
import json
import re
from .model_config import configuration_path,validate_settings,ModelConfigurationError
from graph_research.runtime.storage import safe_path,write_json


def profiles_path(path=None):
    target=configuration_path(path)
    return target.with_name(target.stem+'.profiles.json')


def public_name(value,*,maximum=80):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum or any(ord(c)<32 for c in value):
        raise ModelConfigurationError('配置名称或模型ID为空、过长或含控制字符。')
    value=value.strip()
    if re.match(r'^(?:Bearer\s|sk[-_])[A-Za-z0-9_-]{16,}',value):
        raise ModelConfigurationError('名称看起来像密钥，已拒绝保存。')
    return value


def validate_profiles(document):
    if not isinstance(document,dict) or set(document)!={'version','profiles'} or type(document['version']) is not int or document['version']!=1:
        raise ModelConfigurationError('模型配置集合格式无效，原文件已保留。')
    profiles=document['profiles']
    if not isinstance(profiles,dict) or len(profiles)>50:raise ModelConfigurationError('最多保存50套模型配置。')
    result={}
    for name,record in profiles.items():
        if public_name(name)!=name or not isinstance(record,dict) or set(record)!={'settings','models'}:
            raise ModelConfigurationError('模型配置集合含未支持字段，不能保存密钥。')
        settings=validate_settings(record['settings']);models=record['models']
        if not isinstance(models,list) or len(models)>1000:raise ModelConfigurationError('模型列表无效或超过1000项。')
        models=list(dict.fromkeys(public_name(m,maximum=256) for m in models))
        if settings.model not in models:models.insert(0,settings.model)
        result[name]={'settings':settings.public(),'models':models[:1000]}
    return result


def load_profiles(path=None):
    target=profiles_path(path)
    if not target.exists():return {}
    try:
        if target.stat().st_size>1024*1024:raise ValueError()
        document=json.loads(target.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):raise ModelConfigurationError('无法读取模型配置集合，原文件已保留。') from None
    return validate_profiles(document)


def save_profiles(profiles,path=None):
    checked=validate_profiles({'version':1,'profiles':profiles});target=safe_path(profiles_path(path))
    if len(json.dumps({'version':1,'profiles':checked},ensure_ascii=False,indent=2).encode('utf-8'))>1024*1024:
        raise ModelConfigurationError('模型配置集合超过1MiB，请减少配置或模型列表。')
    if target.exists():load_profiles(path)  # Never overwrite or back up unknown credential-bearing files.
    write_json(target,{'version':1,'profiles':checked},backup=target.exists())
    return checked


def credential_scope(settings):
    """Keys may only be reused for the same address, variable and auth mode."""
    return (settings.base_url,settings.key_env,settings.auth_required)
