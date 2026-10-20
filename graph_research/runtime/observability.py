"""Bounded timing and exception metadata; no task inputs or credentials."""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import math
import re
import time
import uuid

_CURRENT=ContextVar('research_execution_timings',default=None)
_NAME=re.compile(r'^[A-Za-z][A-Za-z0-9_.-]{0,79}$')


def _name(value,fallback):
    return value if isinstance(value,str) and _NAME.fullmatch(value) else fallback


class Timings:
    """Nested spans: inclusive durations overlap; exclusive durations do not."""
    def __init__(self,clock=None):
        self.clock=clock or time.perf_counter;self.started=self.clock()
        self.stages={};self.stack=[];self.failed_stage=None

    @contextmanager
    def span(self,name):
        name=_name(name,'other');frame=[self.clock(),0.0];self.stack.append(frame)
        try:yield
        except BaseException as error:
            if self.failed_stage is None:self.failed_stage=name
            if not getattr(error,'failure_stage',None):error.failure_stage=name
            raise
        finally:
            elapsed=max(0.0,self.clock()-frame[0]);self.stack.pop()
            if self.stack:self.stack[-1][1]+=elapsed
            if name in self.stages or len(self.stages)<64:
                item=self.stages.setdefault(name,{'seconds':0.0,'exclusive_seconds':0.0,'calls':0})
                item['seconds']+=elapsed;item['exclusive_seconds']+=max(0.0,elapsed-frame[1]);item['calls']+=1

    def snapshot(self):
        elapsed=max(0.0,self.clock()-self.started)
        return {'format':'graph-research-stage-timings/1','clock':'perf_counter','elapsed_seconds':elapsed,
                'stages':{key:dict(value) for key,value in self.stages.items()},'failed_stage':self.failed_stage,
                'unattributed_seconds':max(0.0,elapsed-sum(v['exclusive_seconds'] for v in self.stages.values())),
                'meaning':'seconds includes child spans; sum exclusive_seconds only within this process. Absent stages were not observed, not zero. failed_stage is the first observed exception and may have been handled.'}


@contextmanager
def recording(timings,identifier=None):
    timings.diagnostic_id=identifier
    token=_CURRENT.set(timings)
    try:yield timings
    finally:_CURRENT.reset(token)


@contextmanager
def measure(name):
    current=_CURRENT.get()
    if current is not None:
        with current.span(name):yield
    else:
        try:yield
        except BaseException as error:
            if not getattr(error,'failure_stage',None):error.failure_stage=_name(name,'other')
            raise


def timed(name):
    def decorate(function):
        @wraps(function)
        def wrapped(*args,**kwargs):
            with measure(name):return function(*args,**kwargs)
        return wrapped
    return decorate


def diagnostic_id(value=None):
    return value if isinstance(value,str) and re.fullmatch('[0-9a-f]{32}',value) else uuid.uuid4().hex


def error_details(error,*,phase=None,identifier=None):
    """Preserve original codes across wrappers; never serialize str(error)."""
    previous=getattr(error,'error_details',{})
    previous=previous if isinstance(previous,dict) else {}
    current=_CURRENT.get()
    detail={'diagnostic_id':diagnostic_id(identifier or getattr(error,'diagnostic_id',None) or previous.get('diagnostic_id') or getattr(current,'diagnostic_id',None)),
            'phase':_name(previous.get('phase') or getattr(error,'failure_stage',None) or getattr(error,'protected_startup_phase',None) or phase or getattr(error,'phase',None),'host_dispatch'),
            'exception_type':_name(previous.get('exception_type') or getattr(error,'error_type',None) or type(error).__name__,'Exception')}
    for field in ('errno','winerror'):
        value=previous.get(field,getattr(error,field,None))
        if type(value) is int:detail[field]=value
    for field,name in (('path_length_utf16','filename'),('second_path_length_utf16','filename2')):
        value=previous.get(field);path=getattr(error,name,None)
        if type(value) is int:detail[field]=value
        elif isinstance(path,str):detail[field]=len(path.encode('utf-16-le',errors='surrogatepass'))//2
    code=previous.get('cause_code') or getattr(error,'error_code',None) or getattr(error,'code',None)
    if isinstance(code,str) and _NAME.fullmatch(code):detail['cause_code']=code
    path=previous.get('field_path',getattr(error,'field_path',None))
    validation=previous.get('validation',getattr(error,'validation',None))
    # jsonschema paths describe the failed field, never serialize its instance
    # or full error message (which may contain credentials or large inputs).
    if path is None and type(error).__module__.startswith('jsonschema'):
        path=list(error.absolute_path)
        validation={error.validator:error.validator_value} if isinstance(error.validator,str) else {}
    if isinstance(path,list) and len(path)<=32 and all(type(v) is int or isinstance(v,str) and len(v)<=128 for v in path):detail['field_path']=path
    if isinstance(validation,dict):
        import json
        allowed={'type','enum','minimum','maximum','pattern','minItems','maxItems','maxLength','required','additionalProperties'}
        clean={key:value for key,value in validation.items() if key in allowed}
        try:
            if len(json.dumps(clean,ensure_ascii=False,allow_nan=False))<=2048:detail['validation']=clean
        except (TypeError,ValueError):pass
    secondary=getattr(error,'failure_receipt_error',None) or previous.get('failure_receipt_error')
    if isinstance(secondary,dict):detail['failure_receipt_error']={key:secondary[key] for key in ('diagnostic_id','phase','exception_type','errno','winerror') if key in secondary}
    return detail


def annotate(error,*,phase=None,identifier=None):
    detail=error_details(error,phase=phase,identifier=identifier)
    error.diagnostic_id=detail['diagnostic_id'];error.error_details=detail
    return detail


def bounded_timings(value):
    """Keep only finite measurements from the fixed child timing envelope."""
    if not isinstance(value,dict) or value.get('format')!='graph-research-stage-timings/1':return None
    stages=value.get('stages')
    if not isinstance(stages,dict) or len(stages)>64:return None
    clean={}
    for name,item in stages.items():
        if not isinstance(name,str) or not _NAME.fullmatch(name) or not isinstance(item,dict):return None
        if any(type(item.get(key)) not in (int,float) or not math.isfinite(item[key]) or item[key]<0 for key in ('seconds','exclusive_seconds')):return None
        if type(item.get('calls')) is not int or item['calls']<1:return None
        clean[name]={key:item[key] for key in ('seconds','exclusive_seconds','calls')}
    elapsed=value.get('elapsed_seconds')
    if type(elapsed) not in (int,float) or not math.isfinite(elapsed) or elapsed<0:return None
    return {'format':value['format'],'clock':'perf_counter','elapsed_seconds':elapsed,'stages':clean,
            'failed_stage':_name(value.get('failed_stage'),'unknown') if value.get('failed_stage') else None}
