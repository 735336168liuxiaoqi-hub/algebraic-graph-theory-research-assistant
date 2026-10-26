"""Durable, single-flight local scheduling. This module does not import MCP.

The trusted host fixes identity, paths, and ceilings. Jobs contain public
configuration only. User-event minting is deliberately absent from this facade.
"""
import base64
import copy
from dataclasses import asdict,dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import uuid

import jsonschema
from graph_research.assistant.subagent import create_subagent
from graph_research.assistant.task_contract import TaskProtocolError,validate_task,check_id,canonical
from graph_research.assistant.task_control import SubagentLimits
from graph_research.runtime.runner import TaskLimits
from graph_research.runtime.storage import safe_path,write_json,read_json,exclusive_lock,io_path,storage_error
from graph_research.runtime.integrity import IntegrityError
from graph_research.errors import PathBoundaryError,SessionBusyError,schema_protocol_error
from graph_research.runtime.evidence import file_hash
from .contracts import tool_definitions
from graph_research.runtime.observability import error_details


def _read_metadata(path,**options):
    for attempt in range(5):
        try:return read_json(path,**options)
        except OSError:
            if attempt==4:raise
            time.sleep(.01)


@dataclass(frozen=True)
class HostConfiguration:
    root:str
    user_id:str
    max_tool_calls:int=10
    max_model_calls:int=0
    allow_extensions:bool=False
    allowed_tools:tuple|None=None
    tool_seconds:float=30
    tool_cpu_seconds:int=30
    tool_memory_mb:int=1024
    tool_threads:int=1
    approval_ui:str='auto'
    model_settings:dict|None=None
    results_directory:str|None=None
    tool_directory:str|None=None
    allow_development:bool=False
    confirm_experiments:bool=False

    def __post_init__(self):
        if self.approval_ui not in ('auto','off'):raise ValueError('Invalid native approval mode')
        object.__setattr__(self,'root',str(safe_path(self.root)))
        if self.results_directory is not None:object.__setattr__(self,'results_directory',str(safe_path(self.results_directory)))
        if self.tool_directory is not None:object.__setattr__(self,'tool_directory',str(safe_path(self.tool_directory)))
        if type(self.allow_development) is not bool:raise ValueError('allow_development must be boolean')
        if not isinstance(self.user_id,str) or not self.user_id.strip() or len(self.user_id)>256:raise ValueError('用户标识需为1至256字符的非空文本。')
        if self.model_settings is not None:
            from graph_research.assistant.model_config import validate_settings
            object.__setattr__(self,'model_settings',validate_settings(self.model_settings).public())
        elif self.max_model_calls!=0 or self.allow_extensions:raise ValueError('启用模型调用或扩展需要显式提供公开模型设置。')
        self.limits()

    def limits(self):
        return SubagentLimits(max_model_calls=self.max_model_calls,max_tool_calls=self.max_tool_calls,allow_extensions=self.allow_extensions,
            allowed_tools=self.allowed_tools,confirm_experiments=self.confirm_experiments,tool_limits=TaskLimits(wall_seconds=self.tool_seconds,cpu_seconds=self.tool_cpu_seconds,memory_mb=self.tool_memory_mb,cpu_threads=self.tool_threads))

    def public(self):return asdict(self)

    @classmethod
    def from_public(cls,document):
        if isinstance(document,dict):
            document=dict(document);legacy=document.pop('review_policy',None)
            if legacy not in (None,'always','bounded'):raise ValueError('未支持的旧审阅配置。')
            document.setdefault('confirm_experiments',legacy=='always')
        fields=set(cls.__dataclass_fields__)
        if not isinstance(document,dict) or set(document)-fields or fields-{'results_directory','tool_directory','allow_development','tool_threads','approval_ui','confirm_experiments'}-set(document):raise ValueError('MCP宿主配置含未支持字段。')
        document=dict(document)
        if document['allowed_tools'] is not None:document['allowed_tools']=tuple(document['allowed_tools'])
        return cls(**document)

    def parent(self):
        factory=None
        if self.model_settings is not None:
            from graph_research.assistant.model import ConfiguredModel
            from graph_research.assistant.model_config import validate_settings
            factory=lambda:ConfiguredModel(validate_settings(self.model_settings))
        parent,_=create_subagent(self.root,user_id=self.user_id,limits=self.limits(),model_factory=factory,results_directory=self.results_directory,tool_directory=self.tool_directory)
        return parent


class MCPResearchRuntime:
    """Bounded trusted service facade; one live job per user and storage root."""
    def __init__(self,configuration):
        self.configuration=configuration;self.parent=configuration.parent();self.service=self.parent._service
        self.directory=safe_path(self.service.directory/'mcp');self.directory.mkdir(parents=True,exist_ok=True)
        self.children={}
        self.schemas={d['name']:d['input_schema'] for d in tool_definitions()}

    def _snapshot(self,task_id):
        # Windows can briefly deny an open while another process atomically
        # replaces a JSON file. Retry reads only, never execution or model calls.
        for attempt in range(5):
            try:return self.parent.get(task_id)
            except TaskProtocolError as error:
                if error.code!='task_not_found' or attempt==4:raise
            except OSError:
                if attempt==4:raise
            time.sleep(.01)

    def _current_job(self,task_id=None):
        path=self.directory/'active.json' if task_id is None else self.service.task_dir(check_id(task_id))/'mcp-current.json'
        path=safe_path(path,root=self.service.directory)
        if not path.exists():return None
        pointer,_=_read_metadata(path,max_bytes=4096);job_id=check_id(pointer['job_id'])
        job_path=safe_path(self.directory/'jobs'/(job_id+'.json'),root=self.directory)
        job,_=_read_metadata(job_path,max_bytes=32768)
        if job.get('job_id')!=job_id or (task_id and job.get('task_id')!=task_id):raise ValueError('MCP任务记录不一致。')
        return job_path,job

    def _live(self,entry):
        if entry is None:return False
        path,job=entry
        child=self.children.get(job['job_id'])
        if child is not None:
            if child.poll() is not None:
                if job['state'] not in ('queued','running'):self.children.pop(job['job_id'],None)
                return False
            return True
        if job['state'] not in ('queued','running'):return False
        try:
            with exclusive_lock(path.with_suffix('.lock')):pass
        except RuntimeError:return True
        # Another server can observe a newly spawned process before its first
        # instruction acquires the lock. Do not recover that launch as a crash.
        return job['state']=='queued' and time.time()-job['created_at']<15

    def _decorate(self,result,detail="summary"):
        result=copy.deepcopy(result);task_id=result.get('task_id')
        if task_id:
            entry=self._current_job(task_id)
            if entry:
                _,job=entry;live=self._live(entry)
                expected_revision=job.get('result_revision') or 0
                if job['state']=='finished' and (result['status'] in ('queued','running') or result['revision']<expected_revision):
                    # The worker may commit/exit between the first task read
                    # and the job read. Re-read only; never replay execution.
                    result=copy.deepcopy(self._snapshot(task_id))
                state=job['state'] if job['state'] not in ('queued','running') or live else 'interrupted'
                result['transport']={'worker_state':state,'operation':job['operation'],'job_id':job['job_id'],'active':live,'poll_after_seconds':2,'phase':('finalizing' if live and result.get('terminal') else result.get('summary',{}).get('phase',state))}
                if job.get('error'):result['transport']['error']=job['error']
                # A rejected resume retains the paused task state. Report the
                # operation outcome separately so hosts cannot mistake it for
                # a successful continuation.
                result['operation']={'name':job['operation'],'job_id':job['job_id'],'scope':'latest_background_job',
                    'status':'failed' if job.get('error') or state=='interrupted' else 'running' if live else 'succeeded',
                    'error':job.get('error') or ({'code':'worker_interrupted','message':'后台已停止，未自动重算；请查询或恢复原任务。','retryable':False} if state=='interrupted' else None)}
                baseline=job.get('usage_before')
                if baseline is not None:
                    used=result.get('budget',{}).get('used',{})
                    result['operation']['usage']={'scope':'background_job_since_launch',
                        **{key:max(0,used.get(key,0)-baseline.get(key,0)) for key in ('tool_calls','model_calls')}}
                if job.get('started_at'):result['transport']['queue_and_startup_seconds']=max(0,job['started_at']-job['created_at'])
                if state=='interrupted' and result['status'] in ('queued','running'):
                    if (job.get('error') or {}).get('code')=='core_integrity_failed':
                        result['warnings'].append('核心完整性校验失败；先恢复已验证运行版本，查询或重试不能修复源码清单。')
                        result['next_actions']=['get','restore_verified_runtime']
                    else:
                        result['warnings'].append('后台进程已中断；请调用research_recover恢复记录，未自动重算。')
                        result['next_actions']=['get','recover']
            for index,artifact in enumerate(result.get('artifacts',[])):
                artifact['uri']=f'graph-research://tasks/{task_id}/artifacts/{index}'
        from .presentation import result_view
        return result_view(result,detail)

    @staticmethod
    def _effect(result,operation,disposition,*,launched=False):
        result['request_effect']={'operation':operation,'disposition':disposition,'new_worker_started':launched,
            'new_tool_calls':None if launched else 0,'new_model_calls':None if launched else 0,
            'accounting_scope':'this_request; background job usage is in operation.usage; task totals are in budget.used'}
        return result

    def _ensure_idle(self):
        entry=self._current_job()
        if self._live(entry):raise TaskProtocolError('mcp_busy','当前用户已有后台任务；请查询或取消原任务，完成后再提交。')

    def _launch(self,task_id,operation,event_id=None):
        # Clear the previous cancellation before publishing a resume job.
        # Any cancellation arriving after launch must survive worker startup.
        if operation=='resume':(self.service.task_dir(task_id)/'session/.cancel').unlink(missing_ok=True)
        for known,process in list(self.children.items()):
            if process.poll() is not None:
                previous_path=self.directory/'jobs'/(known+'.json')
                previous,_=_read_metadata(previous_path,max_bytes=32768)
                if previous['state'] in ('queued','running'):
                    previous.update(state='interrupted',error={'code':'worker_exited','message':'后台进程已退出，未自动重算；请恢复原任务记录。'})
                    write_json(previous_path,previous)
                self.children.pop(known,None)
        job_id=uuid.uuid4().hex;path=safe_path(self.directory/'jobs'/(job_id+'.json'),root=self.directory)
        job={'version':1,'job_id':job_id,'task_id':task_id,'operation':operation,'event_id':event_id,
             'configuration':self.configuration.public(),'state':'queued','created_at':time.time(),'error':None,
             'usage_before':dict(self._snapshot(task_id)['budget']['used'])}
        write_json(path,job);write_json(self.directory/'active.json',{'job_id':job_id})
        write_json(self.service.task_dir(task_id)/'mcp-current.json',{'job_id':job_id})
        # Spawn a fixed module, never a model-supplied executable or expression.
        source=Path(__file__).resolve().parents[2]
        bootstrap='import sys;sys.path.insert(0,'+repr(str(source))+');from graph_research.mcp.worker import main;main()'
        environment={k:v for k,v in os.environ.items() if not re.search(r'KEY|PASSWORD|SECRET|TOKEN',k,re.I) and not k.startswith(('DSH_','RESEARCH_'))}
        environment.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
        settings=self.configuration.model_settings
        if settings and settings['auth_required']:
            key=settings['key_env']
            if key in os.environ:environment[key]=os.environ[key]
        try:
            child=subprocess.Popen([sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(path)],stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=environment,cwd=str(self.directory),
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),close_fds=True)
            self.children[job_id]=child
        except OSError:
            job.update(state='interrupted',error={'code':'worker_start_failed','message':'后台进程未能启动；任务记录已保留，请恢复记录，不要更换request_id重复提交。'})
            write_json(path,job)
        return self._decorate(self._snapshot(task_id))

    def submit(self,task,wait_seconds=0,detail="summary"):
        try:request=validate_task(task)
        except TaskProtocolError as error:
            if hasattr(error,'field_path'):error.field_path=['task',*error.field_path]
            raise
        model_mode=request['execution']['mode'] in ('agent','research') or (request['execution']['mode']=='counterexample' and request['execution']['counterexample'].get('planner','rules')=='model')
        model_mode=model_mode or request['execution']['mode']=='experiment' and request['execution']['experiment'].get('planner')=='model'
        if model_mode and self.configuration.model_settings is None:
            raise TaskProtocolError('agent_mode_disabled','此MCP服务只启用已有工具计算；自主模型规划需由宿主显式启用。')
        self.configuration.limits().resolve(request)
        with exclusive_lock(self.directory/'.dispatch.lock'):
            index=self.service.directory/'requests'/(hashlib.sha256(request['request_id'].encode()).hexdigest()+'.json')
            if index.exists():
                # Idempotent replay: no worker is launched; the parent's fresh
                # response carries the replay count, so answer it directly.
                return self._effect(self._decorate(self.parent.submit(request,defer=True),detail),'submit','reused')
            else:
                self._ensure_idle();registered=self.parent.submit(request,defer=True)
                self._launch(registered['task_id'],'start')
        return self._effect(self.get(registered['task_id'],wait_seconds=wait_seconds,until='terminal',detail=detail),'submit','launched',launched=True)

    def get(self,task_id,wait_seconds=0,until='change',detail='summary'):
        if until not in ('change','terminal') or not 0<=wait_seconds<=10:raise ValueError('Invalid wait controls')
        result=self._decorate(self._snapshot(task_id),detail);initial=(result['revision'],canonical(result.get('transport')))
        deadline=time.monotonic()+wait_seconds
        while result.get('transport',{}).get('active') and time.monotonic()<deadline:
            time.sleep(min(.15,max(0,deadline-time.monotonic())))
            result=self._decorate(self._snapshot(task_id),detail)
            if until=='change' and (result['revision'],canonical(result.get('transport')))!=initial:break
        return self._effect(result,'get','read_only')

    def resume(self,task_id,event_id):
        check_id(task_id);check_id(event_id)
        with exclusive_lock(self.directory/'.dispatch.lock'):
            result=self._snapshot(task_id);entry=self._current_job(task_id)
            if entry and entry[1]['operation']=='resume' and entry[1].get('event_id')==event_id:return self._effect(self._decorate(result),'resume','reused')
            self._ensure_idle()
            if result['status'] in ('queued','running'):raise TaskProtocolError('task_not_paused','任务尚未暂停；请查询或先恢复中断记录。')
            self.parent.check_resume(task_id,event_id)
            return self._effect(self._launch(task_id,'resume',event_id),'resume','launched',launched=True)

    def cancel(self,task_id):
        with exclusive_lock(self.directory/'.dispatch.lock'):
            before=self._snapshot(task_id);live=self._live(self._current_job(task_id))
            if live:
                from graph_research.runtime.storage import atomic_text
                atomic_text(self.service.task_dir(task_id)/'session/.cancel','cancel',overwrite=True)
            result=self._decorate(self.parent.cancel(task_id))
            return self._effect(result,'cancel','unchanged' if not live and before['status']==result['status'] and result['status'] not in ('queued','running') else 'cancel_requested')

    def recover(self,task_id):
        with exclusive_lock(self.directory/'.dispatch.lock'):
            entry=self._current_job(task_id)
            if self._live(entry):raise TaskProtocolError('worker_still_active','后台仍在执行或启动，请先查询或取消，不能标记为中断。')
            if entry:
                path,job=entry
                with exclusive_lock(path.with_suffix('.lock')):
                    result=self.parent.recover(task_id)
                    if job['state'] in ('queued','running'):job['state']='interrupted';write_json(path,job)
            else:result=self.parent.recover(task_id)
            return self._effect(self._decorate(result),'recover','metadata_only')

    def catalog(self,name=None,known_hash=None):
        from .approval_ui import interactive_available
        from graph_research.tools.registry import ToolRegistry
        from graph_research.tools.extensions import ToolStore
        registry=ToolRegistry();ToolStore(self.service.tool_directory).load_into(registry)
        from graph_research import __version__
        from graph_research.runtime.integrity import assert_integrity
        core=assert_integrity()
        service_info={'version':__version__,'core_manifest_sha256':core['manifest_sha256'],'core_verified':True}
        permitted=self.configuration.allowed_tools
        if name is not None:
            if permitted is not None and name not in permitted:raise TaskProtocolError('tool_not_permitted','工具不在宿主白名单中。')
            if name not in registry.tools:raise TaskProtocolError('tool_not_found','没有此工具；请先查看目录。')
            definition=registry.describe(name);fingerprint=hashlib.sha256(canonical({'version':__version__,'definition':definition}).encode()).hexdigest()
            return {'service':service_info,**({'schema_hash':fingerprint,'unchanged':True} if known_hash==fingerprint else {'tool':definition,'schema_hash':fingerprint})}
        from graph_research.experiments.preparation import capability_catalog
        experiment_capabilities=capability_catalog()
        return {'tools':[{'name':d['name'],'description':d['description'],'status':d['status']} for d in registry.catalog() if permitted is None or d['name'] in permitted],
                'capabilities':{'agent_mode':self.configuration.model_settings is not None,'allow_extensions':self.configuration.allow_extensions,'max_active_jobs':1,'transport':'stdio',
                                'task_approvals':{'interface':'native_desktop','delivery':'signed_user_outbox','requires_manual_event_id':False,'model_can_approve':False,'automatic_window':self.configuration.approval_ui=='auto','automatic_window_available':self.configuration.approval_ui=='auto' and interactive_available()},
                                'research_resources':{'profiles':['standard','research'],'memory_scope':'whole_process_tree','time_scope':'active_workers; CPU seconds are summed across threads','persistent_generations':True},
                                'workflow_modes':['tools','scan','batch','counterexample','experiment']+(['agent','research'] if self.configuration.model_settings is not None else []),
                                'experiment_preparation':{'phase':7,'operations':['prepare','execute','study'],'search_enabled':True,
                                                          'search_operation':'experiment_search','learning_dependency':'optional_cpu_torch',
                                                          'evaluation_operation':'experiment_evaluate','review':'explicit_confirmation_only',
                                                          'confirm_experiments':self.configuration.confirm_experiments,'checkpoint_pause':'explicit_task_option',
                                                          **{k:experiment_capabilities[k] for k in ('objects','metrics','predicates','backends','tensor_domain')},
                                                          'contracts_resource':'graph-research://contracts','model_required':False},
                                'memory':{'read_only':True,'scope':'configured_host_user','experience_review':'trusted_host_only'},
                                'tool_library':{'persistent':True,'versions':True,'development_without_internal_api':self.configuration.allow_development,'approval':'trusted_host_only'},
                                'batch':{'max_expanded_steps':100,'max_cases':64,'failure_policies':['stop','continue_independent'],'execution':'protected_step_processes'}},
                'service':service_info,'limits':asdict(self.configuration.limits()),'catalog_hash':hashlib.sha256(canonical(registry.catalog()).encode()).hexdigest(),
                'budget_policies':{'tools':{'default':'execute_until_budget_exhausted','fail_fast_true':'reject_before_execution'},'scan':'reject_before_execution','batch':'reject_before_execution'}}

    def list_tasks(self,limit=20):
        paths=list((self.service.directory/'tasks').glob('*/task.json'))
        paths.sort(key=lambda path:path.stat().st_mtime,reverse=True);rows=[]
        for path in paths:
            record=self.service.read(path.parent.name)
            if record['status']=='cleared':continue
            rows.append({'task_id':record['task_id'],'request_id':record['request']['request_id'],'objective':record['request']['objective'],'status':record['status'],'updated_at':record['updated_at']})
            if len(rows)>=limit:break
        return {'tasks':rows,'user_scope':'configured_host_user'}

    def library(self,query='',limit=20,offset=0):
        from graph_research.tools.library import ToolLibrary
        result=ToolLibrary(self.service.tool_directory).catalog(query,limit,offset)
        kept=[]
        for row in result['records']:
            row.pop('parameters',None);examples=row.pop('examples',[]);row['example_count']=len(examples)
            row['experience_lookup']={'tool':row['name'],'reviewed_only':True}
            row['contract_lookup']={'name':row['name']}
            if len(canonical(kept+[row]).encode())>240*1024:
                result['next_offset']=offset+len(kept);break
            kept.append(row)
        result['records']=kept
        return {**result,'scope':'configured_host_tool_directory','identity':'host_selected_not_model_override'}

    def development(self,operation,development_id=None,request_id=None,request=None,implementation_id=None,proposal=None,wait_seconds=0):
        from graph_research.assistant.development import DevelopmentService
        service=DevelopmentService(self.service,limits=self.configuration.limits().tool_limits)
        if operation in ('assess','submit') and not self.configuration.allow_development:raise TaskProtocolError('development_disabled','宿主尚未启用--allow-development；不需要配置助手模型API，但仍须显式启用开发申请并获得用户确认。')
        if operation=='assess' and development_id is None and implementation_id is None and proposal is None and request_id is not None and request is not None:return service.assess(request_id,request)
        if operation=='submit' and development_id is not None and implementation_id is not None and proposal is not None and request_id is None and request is None:return service.submit(development_id,implementation_id,proposal,wait_seconds)
        if operation in ('get','cancel') and development_id is not None and all(value is None for value in (request_id,request,implementation_id,proposal)):
            return service.get(development_id,wait_seconds) if operation=='get' else service.cancel(development_id)
        raise ValueError('Development operation fields do not match the selected operation')

    def memory(self):
        """Read sanitized preferences/statistics; never initialize or mutate memory."""
        from graph_research.assistant.memory import read_memory_context
        from graph_research.assistant.experience import experience_counts
        try:
            memory=read_memory_context(self.service.memory_directory,self.service.user_id)
            counts=experience_counts(self.service.memory_directory,self.service.user_id) if memory['enabled'] else {'candidate':0,'approved':0,'rejected':0}
            return {**memory,'experience_counts':counts,'user_scope':'configured_host_user',
                    'data_role':'advisory_preferences_current_request_takes_priority','read_only':True}
        except (OSError,ValueError,sqlite3.Error):raise TaskProtocolError('memory_unavailable','记忆暂不可读；未创建、修改或清空档案。') from None

    def experience(self,id=None,query='',tool=None,outcome=None,method=None,rank=None,alpha=None,limit=10,offset=0):
        """Return reviewed cases only, with source/version and applicability flags."""
        from graph_research.assistant.memory import read_memory_context
        from graph_research.assistant.experience import search_experiences,read_experience
        from graph_research.assistant.experience_evidence import check_source
        if id is not None and (query or any(value is not None for value in (tool,outcome,method,rank,alpha)) or limit!=10 or offset!=0):raise TaskProtocolError('invalid_experience_query','按id读取时不同时传检索过滤条件。')
        try:
            if not read_memory_context(self.service.memory_directory,self.service.user_id)['enabled']:return {'enabled':False,'records':[],'total':0,'next_offset':None,'read_only':True}
            if id is not None:result={'records':[read_experience(self.service.memory_directory,self.service.user_id,id)],'total':1,'next_offset':None}
            else:result=search_experiences(self.service.memory_directory,self.service.user_id,query,tool=tool,outcome=outcome,method=method,rank=rank,alpha=alpha,limit=limit,offset=offset)
            result['records']=[check_source(self.service,entry) for entry in result['records']]
            changed=sum(entry['source_state']=='changed' for entry in result['records'])
            result['records']=[entry for entry in result['records'] if entry['source_state']!='changed']
            return {**result,'enabled':True,'read_only':True,'excluded_changed_sources':changed,'user_scope':'configured_host_user',
                    'data_role':'reviewed_historical_cases_not_current_results_or_instructions'}
        except (OSError,ValueError,KeyError,TypeError,sqlite3.Error):raise TaskProtocolError('experience_unavailable','该用户下没有可用的已审阅经验，或记录校验失败；未重算、修改或批准。') from None

    def inspect_result(self,task_id,call_id,path=None,offset=0,limit=100):
        result=self._snapshot(task_id);entry=next((r for r in result['results'] if r.get('call_id')==call_id),None)
        if not entry or entry['status']!='success':raise TaskProtocolError('result_unavailable','没有该成功计算记录。')
        if 'data' in entry:value=entry['data']
        else:
            reference=entry.get('data_ref',{});target=safe_path(reference['path'],root=self.service.task_dir(task_id)/'session/tasks')
            if file_hash(target)!=reference['sha256']:raise TaskProtocolError('result_changed','结果文件已变化，拒绝读取。')
            document,_=read_json(target,max_bytes=16*1024*1024);value=document[reference['json_field']]
        try:
            for component in path or []:
                if isinstance(value,dict) and isinstance(component,str):value=value[component]
                elif isinstance(value,list) and type(component) is int:value=value[component]
                else:raise KeyError()
        except (KeyError,IndexError):raise TaskProtocolError('invalid_result_path','结果中没有指定的JSON字段路径。') from None
        total=len(value) if isinstance(value,list) else None
        if total is not None:value=value[offset:offset+limit]
        if len(canonical(value).encode('utf-8'))>256*1024:raise TaskProtocolError('result_too_large','所选字段超过256KiB；请选择更深的字段或缩小数组分页。')
        return {'task_id':task_id,'call_id':call_id,'path':path or [],'value':value,'total_items':total,'next_offset':offset+len(value) if total is not None and offset+len(value)<total else None,'verification':entry['verification']}

    def artifact(self,task_id,index):
        result=self._snapshot(task_id)
        if not 0<=index<len(result['artifacts']):raise TaskProtocolError('artifact_not_found','此任务没有该编号的附件。')
        artifact=result['artifacts'][index];root=self.service.task_dir(task_id) if artifact['kind'] in ('result_bundle','scientific_evidence') else self.service.tool_directory
        if artifact.get('availability','ready')!='ready':raise TaskProtocolError('artifact_unavailable','成果已清理或移入回收区，可在成果中心恢复。')
        if artifact.get('artifact_id'):
            from graph_research.assistant.result_catalog import ResultCatalog
            located=ResultCatalog(artifact['results_root']).resolve(artifact['artifact_id'],source_directory=self.service.task_dir(task_id)/'session',expected_sha256=artifact['sha256'])
            if located.get('availability')!='ready':raise TaskProtocolError('artifact_unavailable','成果包当前不可用。')
            artifact['path']=located['archive']
            root=Path(artifact['results_root'])
        target=safe_path(artifact['path'],root=root)
        if io_path(target).stat().st_size>256*1024*1024:raise TaskProtocolError('artifact_too_large','附件超过256MiB，请通过其已登记本机路径读取。')
        if file_hash(target)!=artifact['sha256']:raise TaskProtocolError('artifact_changed','附件SHA256已变化，拒绝将它作为原始结果读取。')
        return target,artifact

    def read_artifact(self,task_id,index,offset=0,length=65536):
        target,artifact=self.artifact(task_id,index);target=io_path(target);size=target.stat().st_size
        if offset>size:raise TaskProtocolError('invalid_offset','附件偏移超过文件长度。')
        before=target.stat()
        with target.open('rb') as stream:stream.seek(offset);data=stream.read(length)
        after=target.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise TaskProtocolError('artifact_changed','读取时附件发生变化，拒绝返回。')
        return {'task_id':task_id,'index':index,'sha256':artifact['sha256'],'size':size,'offset':offset,'data_base64':base64.b64encode(data).decode('ascii'),
                'next_offset':offset+len(data) if offset+len(data)<size else None,'eof':offset+len(data)>=size}

    def call(self,name,arguments):
        started=time.monotonic();result=self._call(name,arguments)
        from .telemetry import RPCTelemetry
        try:RPCTelemetry(self.directory).record(name,result,time.monotonic()-started,len(canonical(result).encode('utf-8')))
        except (OSError,sqlite3.Error):pass
        return result

    def _call(self,name,arguments):
        phase='mcp.request_validation'
        def failed(error,code,message,*,retryable=False):
            return {'status':'protocol_error','error':{'code':code,'message':message,'retryable':retryable,**error_details(error,phase=phase)}}
        try:
            if name not in self.schemas:raise TaskProtocolError('unknown_tool','没有该MCP工具。')
            if len(canonical(arguments).encode('utf-8'))>270*1024:raise TaskProtocolError('input_too_large','MCP工具输入过大。')
            jsonschema.validate(arguments,self.schemas[name])
            method={'research_catalog':'catalog','research_submit':'submit','research_get':'get','research_list_tasks':'list_tasks','research_cancel':'cancel',
                    'research_resume':'resume','research_recover':'recover','research_inspect_result':'inspect_result','research_read_artifact':'read_artifact',
                    'research_memory':'memory','research_experience':'experience','research_library':'library','research_development':'development'}[name]
            phase='mcp.'+method
            if method=='development':phase+='.'+arguments['operation']
            return getattr(self,method)(**arguments)
        except TaskProtocolError as error:return failed(error,error.code,str(error),retryable=error.code=='mcp_busy')
        except jsonschema.ValidationError as error:
            issue=schema_protocol_error(error,'invalid_arguments','MCP参数字段无效；不接受身份、密钥、批准或文件路径覆盖。')
            return failed(issue,issue.code,str(issue))
        except IntegrityError as error:
            if not getattr(error,'failure_stage',None):phase='core_verification'
            return failed(error,'core_integrity_failed','核心完整性校验失败；已停止执行，请使用已验证发行版本或由维护者检查变更。不会自动重新封存或重算。')
        except (PathBoundaryError,SessionBusyError) as error:
            detail=storage_error(error,phase)
            return failed(error,detail['code'],'任务目录边界被拒绝。' if isinstance(error,PathBoundaryError) else '当前会话或审批正在使用，请等待后查询原记录。',retryable=detail['retryable'])
        except PermissionError as error:
            if name=='research_development' and error.errno is None and getattr(error,'winerror',None) is None:
                return failed(error,'approval_or_scope_required','开发尚未获得有效用户确认，或当前范围、版本、尝试预算不允许继续；未绕过审批。')
            detail=storage_error(error,phase)
            return failed(error,detail['code'],'宿主文件访问被拒绝；记录保留，请检查所选目录权限。',retryable=detail['retryable'])
        except (ValueError,TypeError,KeyError,RecursionError) as error:return failed(error,'invalid_state_or_input','输入或保存记录无效；原始记录保留，未自动重新计算。')
        except OSError as error:
            detail=storage_error(error,phase)
            return failed(error,detail['code'],'文件操作未完成，原记录保留；按错误码检查路径或稍后查询，不要重新提交计算。',retryable=detail['retryable'])
        except RuntimeError as error:return failed(error,'host_runtime_error','宿主运行状态异常；原始记录保留，请检查服务日志，不自动重新计算。')
