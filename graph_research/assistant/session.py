"""Durable human interaction; approval actions are host APIs, never model tools."""
import json
from pathlib import Path
import uuid
import hashlib
from functools import wraps
from threading import Event
from datetime import datetime,timezone
from graph_research.runtime.storage import write_json,read_json,atomic_text,exclusive_lock


def _session_action(fn):
    @wraps(fn)
    def wrapped(self,*args,**kwargs):
        with exclusive_lock(self.directory/'.session.lock'):
            if (self.directory/'.results-cleanup.json').exists():raise RuntimeError('该会话有未完成的清理，请先在成果中心回收区恢复。')
            if self._disk_revision()!=self._revision:raise RuntimeError('Session changed in another instance; reload before continuing')
            return fn(self,*args,**kwargs)
    return wrapped

from graph_research.tools.change_control import ChangeController,external_directory
from graph_research.tools.extensions import ToolStore
from graph_research.tools.registry import ToolRegistry


class ResearchSession:
    def __init__(self,directory,tool_directory=None,pricing=None,*,user_id=None,memory_directory=None,memory_enabled=None,auto_export=None,execution_control=None,task_context=None,results_directory=None,results_mode=None):
        self.directory=external_directory(directory)
        manifest=self.directory/'session.json'
        if (self.directory/'.results-cleanup.json').exists():raise ValueError('该会话有未完成的清理，请先在成果中心回收区恢复。')
        recovered=False
        saved,recovered=read_json(manifest,recover=True) if manifest.is_file() or manifest.with_name('session.json.previous').is_file() else ({},False)
        if saved.get('cleared'):raise ValueError('此会话已清理，请在成果中心的回收区恢复后再打开。')
        tool_directory=tool_directory or saved.get('tool_directory') or Path.cwd()/'tool_packages'
        self.store=ToolStore(tool_directory)
        supplied=pricing if pricing is not None else saved.get('pricing')
        self.pricing={k:supplied[k] for k in ('input_per_million','output_per_million','currency') if k in supplied} if supplied is not None else None
        self.changes=ChangeController(self.directory/'changes',self.pricing)
        self.state=saved.get('state',saved if 'question' in saved else {})
        from .research_objects import empty_objects,validate_objects
        self.research_objects=validate_objects(saved.get('research_objects',empty_objects()))
        self.review_plans=saved.get('review_plans',False)
        from .governance import WorkflowJournal
        self.workflow=WorkflowJournal(self.directory)
        if saved.get('workflow_journal_expected') and not self.workflow.path.exists():raise ValueError('工作流预算日志缺失，不能重置用量后继续。原会话已保留，请恢复完整日志或新建对话。')
        prior_usage=saved.get('turns',[{}])[-1].get('workflow_usage',{}) if saved.get('turns') else {}
        task_id=self.state.get('workflow_task_id')
        current_usage=self.workflow.summary(task_id) if task_id else {}
        if any(current_usage.get(k,0)<prior_usage.get(k,0) for k in ('model_calls','tool_calls')):raise ValueError('工作流日志比已保存用量更旧，拒绝回退预算。')
        if not self.workflow.path.exists() and self.pricing is not None:self.workflow.configure(self.pricing)
        if type(self.review_plans) is not bool:raise ValueError('review_plans must be boolean')
        if recovered:
            self.state['recovery_notice']='会话主文件损坏，已读取上一次完整保存；未自动恢复或重放审批。'
            self.state['status']='execution_error'
        from .memory import UserMemoryStore,_user_key,default_memory_directory
        previous=saved.get('memory',{})
        if previous.get('user_id') is not None and user_id is not None and previous['user_id']!=user_id:
            raise ValueError('This session belongs to a different user')
        self.user_id=user_id if user_id is not None else previous.get('user_id')
        if self.user_id is not None:_user_key(self.user_id)
        self.memory_enabled=memory_enabled if memory_enabled is not None else previous.get('enabled',self.user_id is not None)
        if type(self.memory_enabled) is not bool:raise ValueError('memory_enabled must be a boolean')
        if self.memory_enabled and self.user_id is None:raise ValueError('Memory requires an explicit user_id')
        self.memory_directory=external_directory(memory_directory or previous.get('directory') or default_memory_directory())
        if previous.get('directory') and self.memory_directory!=Path(previous['directory']).resolve():
            raise ValueError('Resume must use the original memory directory')
        self.memory=UserMemoryStore(self.memory_directory) if self.user_id is not None else None
        self.session_id=saved.get('session_id') or uuid.uuid4().hex
        # Binding an old anonymous session must not mine its historical inputs.
        self._memory_cursor=previous.get('observation_cursor',len(self.state.get('observations',[])))
        self._cancel=Event();self._revision=self._disk_revision()
        self.turns=saved.get('turns',[])
        exports=saved.get('exports',{})
        root=exports.get('results_root') or results_directory
        self.results_directory=external_directory(root) if root else None
        self.results_mode=exports.get('mode') or results_mode or ('mcp' if execution_control is not None else 'api')
        self.export_notice=exports.get('retention_notice')
        self.auto_export=exports.get('auto',True) if auto_export is None else auto_export
        if type(self.auto_export) is not bool:raise ValueError('auto_export must be a boolean')
        self.result_bundle=exports.get('latest');self.export_history=exports.get('history',[]);self.export_error=exports.get('error')
        if self.results_directory and self.result_bundle:
            from .result_catalog import resolve_bundle
            self.result_bundle=resolve_bundle(self.result_bundle,source_directory=self.directory,results_root=self.results_directory)
        self._ensure_turn()
        self.execution_control=execution_control
        self.task_context=task_context if task_context is not None else saved.get('task_context',{})

    def _ensure_turn(self):
        if self.state and not self.turns:
            now=datetime.now(timezone.utc).isoformat()
            self.turns=[{'number':1,'id':uuid.uuid4().hex,'user_request':'历史会话（旧版未记录轮次边界）：'+self.state.get('question',''),
                         'observation_start':0,'observation_end':len(self.state.get('observations',[])),
                         'started_at':now,'updated_at':now,'attempts':0,'origin':'legacy_unsegmented',
                         'legacy_conversation':self.state.get('conversation',[]),
                         'status':self.state.get('status','unknown'),'answer':self.state.get('answer','')}]

    def _begin_turn(self,text,*,continue_task=False):
        task_id=self.state.get('workflow_task_id') if continue_task else None
        now=datetime.now(timezone.utc).isoformat();start=len(self.state.get('observations',[]))
        self.turns.append({'number':len(self.turns)+1,'id':uuid.uuid4().hex,'user_request':text,
                           'observation_start':start,'observation_end':start,'started_at':now,'updated_at':now,
                           'attempts':0,'origin':'recorded','status':'running','answer':''})
        self.state.update(answer='',current_request=text,turn_observation_start=start)
        self.state['workflow_task_id']=task_id or uuid.uuid4().hex
        self.turns[-1]['workflow_task_id']=self.state['workflow_task_id']
        self.state.pop('plan',None);self.state.pop('inspection',None);self.state['tool_steps']=0
        self.state.pop('claims',None);self.state.pop('audited_claims',None)
        self.state.pop('decision',None);self.state.pop('decision_id',None)
        self.state.pop('development_brief',None)
        self.result_bundle=None;self.export_error=None

    def _sync_turn(self):
        self._ensure_turn()
        if self.turns:
            self.turns[-1].update(observation_end=len(self.state.get('observations',[])),status=self.state.get('status','unknown'),
                                  answer=self.state.get('answer',''),updated_at=datetime.now(timezone.utc).isoformat())
            if self.state.get('plan'):
                import copy
                self.turns[-1]['plan']=copy.deepcopy(self.state['plan'])
            if self.state.get('workflow_task_id'):self.turns[-1]['workflow_usage']=self.workflow.summary(self.state['workflow_task_id'])
            if self.state.get('audited_claims'):self.turns[-1]['claims']=self.state['audited_claims']
            if self.state.get('development_brief'):self.turns[-1]['development_brief']=self.state['development_brief']

    def _disk_revision(self):
        path=self.directory/'session.json'
        if not path.is_file():return None
        with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

    def _save(self):
        self.directory.mkdir(parents=True,exist_ok=True)
        self._sync_turn()
        document={'version':3,'session_id':self.session_id,'tool_directory':str(self.store.directory),'pricing':self.pricing,'state':self.state,'turns':self.turns,'task_context':self.task_context,'research_objects':self.research_objects,'review_plans':self.review_plans,'workflow_journal_expected':self.workflow.path.exists(),
                  'exports':{'auto':self.auto_export,'latest':self.result_bundle,'history':self.export_history,'error':self.export_error,
                             'results_root':str(self.results_directory) if self.results_directory else None,'mode':self.results_mode,'retention_notice':self.export_notice},
                  'memory':{'user_id':self.user_id,'directory':str(self.memory_directory),'enabled':self.memory_enabled,'observation_cursor':self._memory_cursor}}
        write_json(self.directory/'session.json',document,backup=True)
        self._revision=self._disk_revision()
        atomic_text(self.directory/'answer.md',self.state.get('answer',''),overwrite=True)

    def _export_results(self,output=None,*,turn=None,allow_incomplete=False,automatic=False):
        from .results import export_session
        self._sync_turn()
        catalog=None;fingerprint=None;copy_target=None
        if self.results_directory:
            from .result_catalog import ResultCatalog
            from graph_research.runtime.storage import safe_path
            catalog=ResultCatalog(self.results_directory)
            if output:
                copy_target=safe_path(output)
                if copy_target.exists():raise FileExistsError('导出文件已存在，请选择其他文件名。')
            from graph_research import __version__
            document={'state':self.state,'turns':[{k:v for k,v in t.items() if k not in ('updated_at','started_at')} for t in self.turns],
                      'research_objects':self.research_objects,'scope':turn,'version':__version__}
            fingerprint=hashlib.sha256(json.dumps(document,ensure_ascii=False,sort_keys=True,allow_nan=False).encode('utf-8')).hexdigest()
            existing=catalog.reusable(self.session_id,fingerprint) if automatic else None
            if existing:
                self.result_bundle=existing;self.export_error=None;self._save();return existing
            identifier,target=catalog.reserve(self,automatic=automatic)
            result=export_session(self,target,turn=turn,allow_incomplete=allow_incomplete,bundle_id=identifier)
            result=catalog.publish(identifier,result,fingerprint=fingerprint if automatic else None)
        else:result=export_session(self,output,turn=turn,allow_incomplete=allow_incomplete)
        self.result_bundle=result;self.export_history.append(result);self.export_error=None
        if catalog and automatic:
            try:
                removed=catalog.prune_automatic(self.session_id,result['artifact_id'])
                self.export_history=[entry for entry in self.export_history if entry.get('artifact_id') not in removed]
                self.export_notice=None
            except (OSError,ValueError):self.export_notice='最新成果已保存；部分历史自动包暂未清理，可在成果中心查看。'
        self._save()
        if copy_target:
            import shutil
            from graph_research.runtime.storage import staged_file
            from .results import verify_bundle
            with staged_file(copy_target) as temporary:
                shutil.copyfile(result['archive'],temporary);verify_bundle(temporary,result['sha256'])
            sidecar=str(copy_target)+'.sha256';atomic_text(sidecar,result['sha256']+'  '+copy_target.name+'\n')
            return {**result,'archive':str(copy_target),'sha256_file':sidecar,'managed_archive':result['archive']}
        return result

    @_session_action
    def export_results(self,output=None,*,turn=None,allow_incomplete=False):
        """Export all requests or one numbered turn; no model or recomputation."""
        return self._export_results(output,turn=turn,allow_incomplete=allow_incomplete)

    @_session_action
    def view_results(self,*,open_browser=False):
        """Open a verified result view without another model/tool invocation."""
        from .results import publish_result_view
        bundle=self.result_bundle or self._export_results()
        result=publish_result_view(bundle['archive'],bundle['sha256'],self.directory/'views')
        if open_browser:
            import webbrowser
            result['browser_requested']=webbrowser.open(Path(result['html']).as_uri())
        return result

    def _finalize_output(self):
        if not self.auto_export:return
        import time
        started=time.monotonic()
        from graph_research.runtime.observability import Timings,recording
        export_timings=Timings()
        if self.execution_control is not None:
            self.execution_control.record['phase']='verifying_and_exporting';self.execution_control.save(self.execution_control.record)
        self.result_bundle=None
        try:
            with recording(export_timings):self._export_results(automatic=True)
        except Exception as exc:
            self.export_error=type(exc).__name__+': '+str(exc)
            # Export failure must not discard completed calculations or claim a
            # stale ZIP is the latest result. Previous snapshots remain intact.
            self._save()
        finally:
            self.last_export_timings=export_timings.snapshot()
            if self.execution_control is not None:
                record=self.execution_control.record;metrics=record.setdefault('metrics',{})
                metrics['verification_and_export_seconds']=metrics.get('verification_and_export_seconds',0)+time.monotonic()-started
                metrics['last_export_timings']=self.last_export_timings
                self.execution_control.save(record)

    def cancel(self):
        """Request cooperative cancellation; active calculation trees are killed."""
        self._cancel.set()
        atomic_text(self.directory/'.cancel','cancel',overwrite=True)

    def _registry(self):
        registry=ToolRegistry();self.store.load_into(registry)
        self.state['extension_warnings']=self.store.load_errors
        return registry

    @_session_action
    def bind_graph(self,graph,*,object_id=None):
        """Explicit host action; no model or calculation. Preserve every old version."""
        from .research_objects import add_graph
        self.research_objects,ref=add_graph(self.research_objects,graph,object_id)
        if self.state:self.state['research_objects']=self.research_objects
        self._save()
        return ref

    @_session_action
    def select_graph(self,ref):
        from .research_objects import get_object,validate_ref
        if ref is not None:get_object(self.research_objects,ref)
        self.research_objects['active']=validate_ref(ref) if ref is not None else None
        if self.state:self.state['research_objects']=self.research_objects
        self._save()

    @_session_action
    def set_plan_review(self,enabled):
        if type(enabled) is not bool:raise ValueError('计划查看开关应为布尔值。')
        self.review_plans=enabled;self._save()

    @_session_action
    def set_workflow_budget(self,policy):
        """Explicit local user action; never a model tool or delegation approval."""
        if self.execution_control is not None:raise ValueError('委派任务的预算由宿主接口配置。')
        self.workflow.configure(policy,self.state.get('workflow_task_id'))
        current=self.workflow.data['policy'];self.pricing={k:current[k] for k in ('input_per_million','output_per_million','currency')} if current['input_per_million'] is not None and current['output_per_million'] is not None else None
        self.changes.pricing=self.pricing;self._save()

    def workflow_usage(self):return self.workflow.summary(self.state.get('workflow_task_id'))

    def present_graph(self,name,arguments,*,cancel_event=None,graph_inputs=None):
        from .manual_presentation import present_graph
        return present_graph(self,name,arguments,cancel_event=cancel_event,graph_inputs=graph_inputs)

    def _remember_message(self,text):
        if self.memory is not None and self.memory_enabled:
            self.memory.remember_message(self.user_id,text)

    def _observe_tools(self,registry):
        observations=self.state.get('observations',[])
        if self.memory is not None and self.memory_enabled:
            for index in range(self._memory_cursor,len(observations)):
                item=observations[index]
                if item.get('ok') is True and item.get('tool') in registry.tools:
                    self.memory.observe(self.user_id,f'{self.session_id}:{index}',item['tool'])
        self._memory_cursor=len(observations)

    def _run(self,model,*,cancel_event=None,on_update=None):
        from .feature_agent import build_agent
        if model is None:raise ValueError('A configured model or offline test model is required to continue')
        self._cancel.clear()
        # A desktop stop request may arrive before this worker starts. Preserve
        # the caller's event instead of clearing it along with the local event.
        class Cancellation:
            def is_set(inner):return self._cancel.is_set() or (cancel_event is not None and cancel_event.is_set())
        cancellation=Cancellation()
        if self.execution_control is None:(self.directory/'.cancel').unlink(missing_ok=True)
        elif (self.directory/'.cancel').exists():raise InterruptedError('用户在任务开始前取消了计算')
        self.state.pop('control_error',None)
        self._ensure_turn()
        if not self.state.get('workflow_task_id'):
            self.state['workflow_task_id']=uuid.uuid4().hex
            self.workflow.start(self.state['workflow_task_id'],legacy_models=max(0,self.state.get('steps',0)),legacy_tools=max(0,self.state.get('tool_steps',len(self.state.get('observations',[])))))
        self.workflow.start(self.state['workflow_task_id'])
        self.turns[-1]['attempts']+=1
        self.state['turn_observation_start']=self.turns[-1]['observation_start']
        self.state['delegated_task']=self.task_context
        self.state.update(steps=0,status='running')
        self.state['research_objects']=self.research_objects
        if self.state.get('assessment_id'):
            try:
                _,receipt=self.changes._approved(self.state['assessment_id'])
                if receipt.get('consumed'):self.state['extension_installed']=receipt['result']
            except PermissionError:pass
        self._save()
        try:
            if on_update is not None:
                import copy
                on_update(copy.deepcopy(self.state))
            if cancellation.is_set():raise InterruptedError('用户在任务开始前取消了计算')
            registry=self._registry()
            memory_context=self.memory.context(self.user_id) if self.memory is not None and self.memory_enabled else {}
            graph=build_agent(model,registry,self.store,changes=self.changes,memory_context=memory_context,
                              task_directory=self.directory/'tasks',cancel=cancellation,cancel_file=self.directory/'.cancel',execution_control=self.execution_control,review_plans=self.review_plans,
                              governance=self.workflow,workflow_task_id=self.state['workflow_task_id'])
            # Save each completed node, retaining tool observations if a later
            # network request fails. No provider credentials are in this state.
            policy=self.workflow.summary(self.state['workflow_task_id'])['policy']
            for chunk in graph.stream(self.state,config={'recursion_limit':2*policy['max_model_calls']+3*policy['max_tool_calls']+20},stream_mode='updates'):
                for update in chunk.values():
                    if isinstance(update,dict):self.state.update(update)
                if 'research_objects' in self.state:
                    from .research_objects import validate_objects
                    self.research_objects=validate_objects(self.state['research_objects'])
                self._observe_tools(registry)
                self._save()
                if on_update is not None:
                    import copy
                    on_update(copy.deepcopy(self.state))
                if cancellation.is_set() or (self.directory/'.cancel').exists():raise InterruptedError('用户取消了本次任务')
        except (InterruptedError,KeyboardInterrupt):
            self.state.update(status='cancelled',answer='本轮已取消；已保存的结果保留，未完成计算不作为有效结果。')
            self._save()
        except Exception as exc:
            from .task_control import TaskControlError
            status=exc.status if isinstance(exc,TaskControlError) else 'execution_error'
            self.state.update(status=status,answer=f'本轮未完成：{type(exc).__name__}: {exc}')
            if isinstance(exc,TaskControlError):self.state['control_error']={'code':exc.code,'message':str(exc)}
            if getattr(exc,'key',None):self.state['uncertain_call_key']=exc.key
            self._save()
        from .claims import audit_claims
        from .results import _execution
        def verified(index):return _execution(self,self.state['observations'][index],'claim-source',False,[])[0]=='verified_execution'
        self.state['audited_claims']=audit_claims(self.state.get('claims',[]),self.state.get('observations',[]),verified)
        self._save();self._finalize_output()
        return self.state

    def _require_model_mode(self):
        if self.task_context.get('interaction_mode')=='offline_tools':
            raise ValueError('这是无API工具会话，请使用offline --session继续；模型对话请另建会话。')

    @_session_action
    def ask(self,question,model,*,cancel_event=None,on_update=None):
        self._require_model_mode()
        if self.state:raise ValueError('This session already exists; reply or resume it instead')
        if not isinstance(question,str) or not question.strip():raise ValueError('Question is required')
        self.state={'question':question,'conversation':[{'role':'user','content':question}]}
        self._begin_turn(question)
        self._remember_message(question)
        return self._run(model,cancel_event=cancel_event,on_update=on_update)

    @_session_action
    def reply(self,text,model,*,cancel_event=None,on_update=None):
        self._require_model_mode()
        if not self.state:raise ValueError('No session to reply to')
        if not isinstance(text,str) or not text.strip():raise ValueError('A reply is required')
        continuing=self.state.get('status') in ('awaiting_clarification','awaiting_plan','awaiting_approval','execution_error','cancelled','budget_exhausted','recovery_required')
        self.state['conversation']=self.state.get('conversation',[])+[
            {'role':'assistant','content':self.state.get('answer','')},{'role':'user','content':text}]
        # A changed requirement is not consent to the previous assessment.
        self.state.update(assessment_id='',assessment={},extensions=0,extension_installed={})
        self._begin_turn(text,continue_task=continuing)
        self._remember_message(text)
        return self._run(model,cancel_event=cancel_event,on_update=on_update)

    @_session_action
    def approve(self,assessment_id,model,*,cancel_event=None,on_update=None):
        self._require_model_mode()
        if self.state.get('status')!='awaiting_approval' or self.state.get('assessment_id')!=assessment_id:
            raise ValueError('Approval must name the assessment currently shown to the user')
        if model is None:raise ValueError('Configure a model before approving execution')
        if cancel_event is not None and cancel_event.is_set():raise InterruptedError('用户在批准执行前取消了操作')
        self.changes.approve(assessment_id,self._registry())
        return self._run(model,cancel_event=cancel_event,on_update=on_update)

    @_session_action
    def reject(self,assessment_id,reason='用户拒绝此次功能开发'):
        if self.state.get('status')!='awaiting_approval' or self.state.get('assessment_id')!=assessment_id:
            raise ValueError('Rejection must name the current assessment')
        self.changes.reject(assessment_id,reason)
        self.state.update(status='extension_rejected',answer='已取消本次功能开发，未生成代码或创建扩展包。')
        self._save()
        self._finalize_output()
        return self.state

    @_session_action
    def continue_run(self,model,*,cancel_event=None,on_update=None):
        self._require_model_mode()
        if self.state.get('status') not in ('execution_error','cancelled','budget_exhausted'):raise ValueError('Only interrupted execution can be continued this way')
        return self._run(model,cancel_event=cancel_event,on_update=on_update)

    @_session_action
    def retry_uncertain_calculation(self,model,*,cancel_event=None,on_update=None):
        """Explicitly authorize another local attempt; keep the previous budget debit."""
        if self.state.get('status')!='recovery_required' or not self.state.get('uncertain_call_key'):raise ValueError('当前没有需要确认重算的步骤。')
        self.workflow.permit_retry(self.state['workflow_task_id'],self.state.pop('uncertain_call_key'))
        return self._run(model,cancel_event=cancel_event,on_update=on_update)

    @_session_action
    def accept_plan(self,plan_id,scope_sha256,model,*,cancel_event=None,on_update=None):
        """Resume only the currently displayed existing-tool plan; no extension consent."""
        plan=self.state.get('plan',{})
        if self.state.get('status')!='awaiting_plan' or plan.get('status')!='awaiting_review' or (plan.get('id'),plan.get('scope_sha256'))!=(plan_id,scope_sha256):raise ValueError('计划已过期，请查看当前计划。')
        if model is None:raise ValueError('请先配置模型。')
        if cancel_event is not None and cancel_event.is_set():raise InterruptedError('已取消开始执行计划。')
        from .planning import validate_saved_plan,new_plan
        validate_saved_plan(plan);new_plan(plan['spec'],self._registry(),self.research_objects,self.execution_control)
        plan['status']='running'
        return self._run(model,cancel_event=cancel_event,on_update=on_update)
