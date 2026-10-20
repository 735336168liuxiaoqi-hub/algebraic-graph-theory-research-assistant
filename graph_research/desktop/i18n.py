"""Presentation-only language selection; no tool inputs or model text are rewritten."""
import json
import os
from pathlib import Path
import re
import tempfile
import weakref

_language='zh'
_catalog=None
_pattern=None
_listeners=[]
class IdentityWeakMap:
    """Qt item wrappers can be weak-referenced but are intentionally unhashable."""
    def __init__(self):self.data={}
    def get(self,obj,default=None):
        entry=self.data.get(id(obj))
        return entry[1] if entry and entry[0]() is obj else default
    def setdefault(self,obj,default):
        existing=self.get(obj)
        if existing is not None:return existing
        key=id(obj)
        def cleanup(ref):
            entry=self.data.get(key)
            if entry and entry[0] is ref:self.data.pop(key,None)
        self.data[key]=(weakref.ref(obj,cleanup),default)
        return default
    def items(self):
        return [(ref(),value) for ref,value in list(self.data.values()) if ref() is not None]


_bindings=IdentityWeakMap()
_preference_path=None


class UiText(str):
    """Explicit context-dependent text, useful when one Chinese word is ambiguous."""
    def __new__(cls,chinese,english):
        value=super().__new__(cls,chinese);value.english=english;return value


def language():return _language


def preference_path():
    return _preference_path or Path.home()/'.graph_research'/'desktop-language.json'


def load_language(path=None):
    """Read only; invalid preferences fall back to Chinese, without overwriting."""
    try:
        data=json.loads(Path(path or preference_path()).read_text(encoding='utf-8'))
        if not isinstance(data,dict):return 'zh'
        return data['language'] if data.get('version')==1 and data.get('language') in ('zh','en') else 'zh'
    except (OSError,ValueError,TypeError,KeyError):return 'zh'


def save_language(value,path=None):
    if value not in ('zh','en'):raise ValueError('Unsupported desktop language')
    target=Path(path or preference_path());target.parent.mkdir(parents=True,exist_ok=True)
    descriptor,name=tempfile.mkstemp(prefix='desktop-language-',suffix='.tmp',dir=target.parent)
    try:
        with os.fdopen(descriptor,'w',encoding='utf-8',newline='\n') as stream:
            json.dump({'version':1,'language':value},stream);stream.write('\n')
        os.replace(name,target)
    finally:
        try:Path(name).unlink(missing_ok=True)
        except OSError:pass


def translations():
    global _catalog
    if _catalog is None:
        _catalog=json.loads((Path(__file__).resolve().parents[1]/'data/desktop_en.json').read_text(encoding='utf-8'))
    return _catalog


def register_translations(entries):
    global _pattern
    translations().update(entries);_pattern=None


def tr(value):
    """Translate registered UI phrases; leave unknown text and identifiers alone."""
    global _pattern
    if isinstance(value,UiText):return value.english if _language=='en' else str(value)
    if isinstance(value,(list,tuple)):return type(value)(tr(item) for item in value)
    if not isinstance(value,str) or _language=='zh':return value
    catalog=translations()
    if value in catalog:return catalog[value]
    if not re.search(r'[\u4e00-\u9fff]',value):return value
    if _pattern is None:
        keys=sorted((s for s in catalog if len(s)>1 and re.search(r'[\u4e00-\u9fff]',s)),key=len,reverse=True)
        _pattern=re.compile('|'.join(re.escape(s) for s in keys)) if keys else re.compile(r'(?!x)x')
    return _pattern.sub(lambda match:catalog[match.group()],value)


def bind(obj,key,setter,value,*prefix):
    """Retain the source phrase and unbound Qt setter, without retaining widgets."""
    _bindings.setdefault(obj,{})[key]=(setter,value,prefix)
    return setter(obj,*prefix,tr(value))


def unbind(obj,prefix):
    bindings=_bindings.get(obj,{})
    for key in list(bindings):
        if isinstance(key,tuple) and key[0]==prefix:bindings.pop(key,None)


def listen(callback):
    _listeners.append(weakref.WeakMethod(callback))


def set_language(value,*,persist=False,path=None):
    global _language
    if value not in ('zh','en'):raise ValueError('Unsupported desktop language')
    if persist:save_language(value,path)
    if value==_language:return
    _language=value
    for obj,entries in list(_bindings.items()):
        previous=None
        try:
            if hasattr(obj,'blockSignals'):previous=obj.blockSignals(True)
            for setter,source,prefix in list(entries.values()):setter(obj,*prefix,tr(source))
        except RuntimeError:pass  # Qt has already destroyed the C++ object.
        finally:
            if previous is not None:
                try:obj.blockSignals(previous)
                except RuntimeError:pass
    for ref in list(_listeners):
        callback=ref()
        if callback is None:_listeners.remove(ref)
        else:
            try:callback()
            except RuntimeError:
                from shiboken6 import isValid
                if not isValid(callback.__self__):_listeners.remove(ref)
                else:raise


def initialize(value=None,path=None):
    global _preference_path
    if path is not None:_preference_path=Path(path)
    set_language(value or load_language())


def forget(obj,key):
    _bindings.get(obj,{}).pop(key,None)
