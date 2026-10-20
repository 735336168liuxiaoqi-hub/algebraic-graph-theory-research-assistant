"""External-agent development: scoped assessment, host consent, bounded attempts.

No model is constructed here. All approval methods belong to trusted UI/CLI;
MCP exposes only assessment, status, implementation submission and cancellation.
"""
import copy
from contextlib import ExitStack
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

from graph_research.runtime.storage import safe_path,read_json,write_json,exclusive_lock
from graph_research.runtime.runner import TaskLimits
from graph_research.tools.change_control import ChangeController,InstallAuthorization,digest,core_fingerprint,catalog_fingerprint
from graph_research.tools.extensions import ToolStore
from graph_research.tools.registry import ToolRegistry
from .task_contract import check_id,TaskProtocolError
from graph_research.runtime.observability import measure,error_details,timed
from .feature_routes import feature_route,development_brief


def now():return datetime.now(timezone.utc).isoformat()


_CHILDREN={}


class DevelopmentService:
    def __init__(self,service,*,limits=None):
        self.host=service;self.directory=safe_path(service.directory/'development')
        self.store=ToolStore(service.tool_directory);self.changes=ChangeController(self.directory/'changes')
        self.limits=limits or TaskLimits()

    def registry(self):
        registry=ToolRegistry();self.store.load_into(registry);return registry

    def path(self,identifier):return safe_path(self.directory/'requests'/check_id(identifier),root=self.directory)

    def read(self,identifier):
        record,_=read_json(self.path(identifier)/'state.json',max_bytes=512*1024)
        if not isinstance(record,dict) or record.get('owner_key')!=self.host.owner_key or record.get('id')!=identifier or digest(record['request'])!=record.get('request_sha256') or record.get('tool_directory')!=str(self.store.directory):raise ValueError('Development request identity, tool directory or content changed')
        return record

    def save(self,record):
        record['updated_at']=now();write_json(self.path(record['id'])/'state.json',record)

    def assess(self,request_id,request):
        if not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',request_id):raise ValueError('Invalid development request_id')
        if not isinstance(request,dict) or len(json.dumps(request,ensure_ascii=False,allow_nan=False).encode())>100000:raise ValueError('Invalid development requirements')
        with exclusive_lock(self.directory/'.dispatch.lock'):
            index=self.directory/'request-index'/(hashlib.sha256(request_id.encode()).hexdigest()+'.json')
            if index.exists():
                previous,_=read_json(index);record=self.read(previous['id'])
                if record['request_sha256']!=digest(request):raise ValueError('Same request_id requires identical development requirements')
                return self.get(record['id'])
            registry=self.registry();route=feature_route(request,registry);identifier=uuid.uuid4().hex
            if route['kind']=='restricted' and not request.get('replaces'):
                from graph_research.tools.library import ToolLibrary
                matches=[row for row in ToolLibrary(self.store.directory).catalog(query=str(request.get('name','')),limit=100)['records'] if row.get('name')==request.get('name') and row.get('state') not in ('quarantined','disabled_legacy')]
                if matches:route={'kind':'existing_tool','versions':[{key:row.get(key) for key in ('name','version','state','source_sha256')} for row in matches[:20]]}
            record={'id':identifier,'request_id':request_id,'owner_key':self.host.owner_key,'request':copy.deepcopy(request),
                    'request_sha256':digest(request),'created_at':now(),'status':'waiting_for_approval','attempts':[],'limits':self.limits.__dict__,'tool_directory':str(self.store.directory)}
            if route['kind']=='composition':record.update(status='composition',message='使用现有工具联动，不创建新包。')
            elif route['kind']=='existing_tool':record.update(status='existing_tool',message='工具库已有同名工具，请复用或由用户启用已有版本；确需升级时明确replaces当前package_id。',existing_versions=route['versions'])
            elif route['kind']=='clarify':record.update(status='waiting_for_user',questions=route['questions'])
            elif route['kind']=='manual':record.update(status='manual_development',brief=development_brief(request,route,self.path(identifier)/'brief'))
            else:
                assessment=self.changes.assess(request,registry)
                if assessment.get('kind')=='composition':raise ValueError('Composition should remain in the workflow')
                record['assessment_id']=assessment['id']
                estimate=assessment['estimate']
                estimate.update(provider_scope='external_agent_host_controls_model_budget',money=None,
                    model_usage_note='宿主模型调用、token和费用由主agent计量；本服务不调用模型，不以参考范围冒充宿主硬上限。')
                self.changes._write(self.changes._path(assessment['id'])/'assessment.json',assessment)
            self.save(record);write_json(index,{'id':identifier});return self.get(identifier)

    def _live(self,record):
        try:
            with exclusive_lock(self.path(record['id'])/'.worker.lock'):pass
        except RuntimeError:return True
        if record['status'] not in ('queued','validating'):return False
        return record['status']=='queued' and time.time()-record.get('queued_at',0)<15

    def get(self,identifier,wait_seconds=0):
        if type(wait_seconds) not in (int,float) or not 0<=wait_seconds<=5:raise ValueError('Invalid development wait')
        deadline=time.monotonic()+wait_seconds
        while True:
            record=self.read(identifier);live=self._live(record)
            if not live or time.monotonic()>=deadline:break
            time.sleep(min(.1,max(0,deadline-time.monotonic())))
        result={key:copy.deepcopy(record[key]) for key in ('id','request_id','status','created_at','updated_at','message','questions','brief','result','error','existing_versions') if key in record}
        approved_limits=TaskLimits(**record['limits'])
        for key,child in list(_CHILDREN.items()):
            if child.poll() is not None:_CHILDREN.pop(key,None)
        if record['status'] in ('queued','validating') and not live:result.update(status='interrupted',message='验证进程已中断；保留已用尝试，不自动重新执行。需重新评估并由用户确认。')
        if record.get('assessment_id'):
            assessment=self.changes.read(record['assessment_id']);approval=self.changes._path(assessment['id'])/'approval.json'
            decision=read_json(approval)[0] if approval.is_file() else {}
            result['assessment']=assessment
            result['approval_card']=(f"拟新增/升级：{assessment['request']['name']}\n需求：{assessment['request']['requirements']}\n"
                f"现有工具不足：{assessment['request']['why_not_composition']}\n算法：{assessment['request']['new_algorithm']}\n"
                f"验收样例{len(assessment['request']['acceptance_tests'])}项；最多2次实现尝试，每样例最多{min(15,approved_limits.wall_seconds)}秒，"
                f"内存上限{approved_limits.memory_mb}MiB。生成及修订的宿主模型消耗由主agent控制，token和费用尚未知；参考耗时范围{assessment['estimate']['wall_seconds_range']}秒。\n"
                '用户确认后才生成代码，独立封包；通过样例不代表一般正确。')
            if result['status']=='waiting_for_approval' and decision.get('decision')=='approved':result['status']='awaiting_implementation'
            elif decision.get('decision')=='rejected':result['status']='rejected'
            if result['status'] in ('waiting_for_approval','awaiting_implementation','validation_failed'):
                if assessment['core_sha256']!=core_fingerprint() or assessment['catalog_sha256']!=catalog_fingerprint(self.registry()):
                    result.update(status='stale_assessment',message='核心、工具目录或启用版本已改变；请重新评估并由用户确认，不生成或执行旧批准范围的代码。')
            result['budget']={'implementation_attempts_used':decision.get('implementation_attempts',0),'implementation_attempts_limit':assessment['estimate']['limits']['implementation_attempts'],
                              'fixtures_per_attempt':len(assessment['request']['acceptance_tests']),'fixture_timeout_seconds':min(15,approved_limits.wall_seconds),
                              'local_model_calls':0,'external_model_tokens':None,'external_model_money':None}
        result.update(active=live,attempts=[{key:copy.deepcopy(attempt[key]) for key in ('implementation_id','status','proposal_sha256','error') if key in attempt} for attempt in record['attempts']],
                      data_role='development_record_not_user_approval_or_mathematical_proof')
        if result['status']=='waiting_for_approval':result['interaction']={'kind':'approval','development_id':identifier,
            'scope_sha256':result['assessment']['scope_sha256'],'message':'请向用户完整展示需求、验收及消耗；可信本机工具库CLI取得实际确认，MCP不能批准。'}
        exhausted=result['status']=='validation_failed' and result.get('budget',{}).get('implementation_attempts_used',0)>=2
        result['terminal']=exhausted or result['status'] in ('installed','composition','existing_tool','manual_development','rejected','cancelled','interrupted','stale_assessment')
        result['next_actions']=('reassess_with_user_confirmation',) if exhausted else {
            'waiting_for_approval':('get','trusted_user_confirmation'),'waiting_for_user':('ask_user','assess_new_request'),
            'awaiting_implementation':('submit',),'queued':('get','cancel'),'validating':('get','cancel'),
            'installed':('research_catalog','research_submit'),'validation_failed':('get','submit_within_remaining_budget'),
            'existing_tool':('research_catalog',),'composition':('research_catalog','research_submit'),
            'manual_development':('manual_development',),'rejected':('assess_new_request',),
            'cancelled':('reassess_with_user_confirmation',),'interrupted':('reassess_with_user_confirmation',),'stale_assessment':('assess_new_request',)}.get(result['status'],('get',))
        result['next_actions']=list(result['next_actions'])
        return result

    def approve(self,identifier,scope_sha256):
        """Trusted host only, after showing the current assessment to the user."""
        with exclusive_lock(self.directory/'.dispatch.lock'):
            record=self.read(identifier);assessment=self.changes.read(record['assessment_id'])
            if assessment['scope_sha256']!=scope_sha256:raise ValueError('Approval scope changed; inspect the current assessment')
            self.changes.approve(assessment['id'],self.registry());return self.get(identifier)

    def reject(self,identifier,reason='用户拒绝'):
        with exclusive_lock(self.directory/'.dispatch.lock'):
            record=self.read(identifier);self.changes.reject(record['assessment_id'],reason);return self.get(identifier)

    @timed('development.submit')
    def submit(self,identifier,implementation_id,proposal,wait_seconds=0):
        if not isinstance(implementation_id,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',implementation_id):raise ValueError('Invalid implementation_id')
        if not isinstance(proposal,dict) or set(proposal)!={'name','description','parameters','source','tests'}:raise ValueError('Implementation accepts only name, description, parameters, source and tests')
        if len(json.dumps(proposal,ensure_ascii=False,allow_nan=False).encode())>100000:raise ValueError('Implementation exceeds100KB')
        with exclusive_lock(self.directory/'.dispatch.lock'),ExitStack() as stack:
            with measure('development.request_read'):record=self.read(identifier);pin=digest(proposal)
            previous=next((a for a in record['attempts'] if a['implementation_id']==implementation_id),None)
            if previous:
                if previous['proposal_sha256']!=pin:raise ValueError('Same implementation_id cannot change source or fixtures')
                return self.get(identifier,wait_seconds)
            with measure('development.approval_check'):
                if self.get(identifier)['status'] not in ('awaiting_implementation','validation_failed'):raise PermissionError('Current development is not approved or is interrupted, cancelled or complete')
            if any(value>getattr(self.limits,key) for key,value in record['limits'].items()):raise PermissionError('Host tightened validation limits; obtain a new assessment under the current limits')
            stack.enter_context(exclusive_lock(self.store.directory/'.development-dispatch.lock'))
            slot=self.store.directory/'.development-slot.json'
            if slot.exists():
                previous_slot,_=read_json(slot,max_bytes=4096)
                if previous_slot.get('status')=='queued' and time.time()-previous_slot.get('queued_at',0)<15:raise RuntimeError('Another library validation is starting; query it before submitting')
            with exclusive_lock(self.store.directory/'.development-worker.lock'):pass
            reservation=uuid.uuid4().hex
            with measure('development.reserve_attempt'):self.changes.verify_install(record['assessment_id'],proposal,self.registry(),reservation_id=reservation,reserve_only=True)
            attempt={'implementation_id':implementation_id,'reservation_id':reservation,'proposal_sha256':pin,'status':'queued','sequence':len(record['attempts'])+1}
            record['attempts'].append(attempt);record.update(status='queued',queued_at=time.time());record.pop('error',None)
            write_json(self.path(identifier)/('proposal-'+str(attempt['sequence'])+'.json'),proposal);self.save(record)
            write_json(slot,{'id':identifier,'reservation':reservation,'status':'queued','queued_at':time.time()})
            source=Path(__file__).resolve().parents[2]
            bootstrap='import sys;sys.path.insert(0,'+repr(str(source))+');from graph_research.assistant.development_worker import main;main()'
            config={'root':str(self.host.root),'user_id':self.host.user_id,'tool_directory':str(self.host.tool_directory),'id':identifier,'reservation':reservation,'limits':record['limits'],'sequence':attempt['sequence']}
            job=self.path(identifier)/('job-'+str(attempt['sequence'])+'.json');write_json(job,config)
            environment={k:v for k,v in os.environ.items() if not re.search(r'KEY|SECRET|TOKEN|PASSWORD',k,re.I) and not k.startswith(('DSH_','RESEARCH_'))}
            environment.update(PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
            try:
                with measure('development.spawn'):_CHILDREN[reservation]=subprocess.Popen([sys.executable,'-I','-B','-X','utf8','-c',bootstrap,str(job)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                 env=environment,cwd=self.host.root,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),close_fds=True)
            except OSError as error:
                record['status']='interrupted';attempt['status']='interrupted'
                record['error']={'code':'worker_start_failed','message':'开发验证进程启动失败；已有尝试保留，不自动重试。',**error_details(error)};self.save(record)
                write_json(slot,{'id':identifier,'reservation':reservation,'status':'interrupted'})
        return self.get(identifier,wait_seconds)

    def cancel(self,identifier):
        from graph_research.runtime.storage import atomic_text
        record=self.read(identifier)
        if self._live(record):atomic_text(self.path(identifier)/'.cancel','cancel',overwrite=True)
        return self.get(identifier)

    def execute(self,identifier,reservation):
        """Fixed background worker entry, never callable as an unapproved model tool."""
        with exclusive_lock(self.store.directory/'.development-worker.lock'),exclusive_lock(self.path(identifier)/'.worker.lock'):
            record=self.read(identifier);attempt=next(a for a in record['attempts'] if a['reservation_id']==reservation)
            if record['status']!='queued' or attempt['status']!='queued':return
            slot=self.store.directory/'.development-slot.json';selection,_=read_json(slot,max_bytes=4096)
            if selection.get('id')!=identifier or selection.get('reservation')!=reservation:
                record['status']='interrupted';attempt['status']='interrupted';self.save(record);return
            record['status']='validating';attempt['status']='validating';self.save(record)
            try:
                if (self.path(identifier)/'.cancel').exists():raise InterruptedError('Cancelled before validation')
                proposal,_=read_json(self.path(identifier)/('proposal-'+str(attempt['sequence'])+'.json'),max_bytes=100000)
                if digest(proposal)!=attempt['proposal_sha256']:raise ValueError('Staged implementation changed')
                result=self.store.install(proposal,self.registry(),authorization=InstallAuthorization(self.changes,record['assessment_id'],reservation),
                    cancel_file=self.path(identifier)/'.cancel',validation_limits=self.limits)
                record.update(status='installed',result=result);attempt['status']='installed'
            except Exception as error:
                record['status']='cancelled' if isinstance(error,InterruptedError) else 'validation_failed'
                record['error']={'type':type(error).__name__,'message':str(error)[:1000],**error_details(error,phase='development.validation')};attempt.update(status=record['status'],error=record['error'])
            self.save(record)
            write_json(slot,{'id':identifier,'reservation':reservation,'status':'finished'})


def from_host(root,user_id,tool_directory=None,limits=None):
    from .subagent import create_subagent
    parent,_=create_subagent(root,user_id=user_id,tool_directory=tool_directory)
    return DevelopmentService(parent._service,limits=limits)
