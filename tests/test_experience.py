"""Read-only memory, evidence-bound review and scoped case learning."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from graph_research.assistant import create_subagent,SubagentLimits
from graph_research.assistant.memory import UserMemoryStore,read_memory_context
from graph_research.assistant.experience import ExperienceStore,search_experiences,read_experience,experience_counts,canonical
from graph_research.assistant.experience_evidence import derive_candidate,capture_call
from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime


def payload():
    return {'format':'graph-research-experience/1','title':'高α计算案例','tool':'hypergraph_spectrum','outcome':'success',
            'conditions':{'rank':3,'alpha':.999},'facts':{'method':'newton_noda','rho':2.0,'independent_verification_passed':True},
            'tags':['高α'],'scope_note':'Only this input.',
            'evidence':{'task_id':'a'*32,'call_id':'call-0001','receipt_sha256':'b'*64,'request_sha256':'c'*64,
                        'result_sha256':'d'*64,'core_manifest_sha256':'e'*64,'environment':{'package_version':'test'}}}


class ExperienceStoreTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_read_only_empty_discovery_creates_no_memory_database(self):
        directory=self.root/'missing'
        self.assertFalse(read_memory_context(directory,'a')['available'])
        self.assertEqual(search_experiences(directory,'a')['records'],[]);self.assertFalse(directory.exists())
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root/'host'),'a',max_tool_calls=0))
        self.assertEqual(runtime.call('research_memory',{})['preferences'],{})
        self.assertEqual(runtime.call('research_experience',{})['records'],[])
        self.assertFalse((self.root/'host/memory/memory.sqlite3').exists())

    def test_candidate_hidden_until_hash_bound_review_then_readonly_search(self):
        store=ExperienceStore(self.root);record=store.capture('a',payload(),'event1');identifier=record['id']
        self.assertEqual(search_experiences(self.root,'a')['total'],0)
        shown=store.show('a',identifier)
        with self.assertRaises(ValueError):store.review('a',identifier,'0'*64,'approved')
        store.review('a',identifier,shown['content_sha256'],'approved','只适用于记录中的输入，其他图需重算')
        before=hashlib.sha256(store.memory.path.read_bytes()).hexdigest()
        found=search_experiences(self.root,'a','高α',tool='hypergraph_spectrum',method='newton_noda',rank=3,alpha=.999)
        self.assertEqual(found['total'],1);self.assertEqual(found['records'][0]['id'],identifier)
        self.assertEqual(hashlib.sha256(store.memory.path.read_bytes()).hexdigest(),before)
        self.assertEqual(search_experiences(self.root,'a',alpha=.99)['total'],0)

    def test_user_isolation_rejection_and_forgotten_tombstone(self):
        store=ExperienceStore(self.root);a=store.capture('a',payload(),'same');b=store.capture('b',payload(),'same')
        with self.assertRaises(ValueError):store.show('b',a['id'])
        shown=store.show('a',a['id']);store.review('a',a['id'],shown['content_sha256'],'rejected','不作为推荐')
        self.assertEqual(search_experiences(self.root,'a')['records'],[])
        store.forget('a',a['id']);self.assertEqual(store.capture('a',payload(),'same')['status'],'forgotten')
        self.assertEqual(store.show('b',b['id'])['status'],'candidate')

    def test_disable_hides_reads_and_clear_removes_both_kinds_of_memory(self):
        store=ExperienceStore(self.root);store.capture('a',payload(),'a');store.capture('b',payload(),'b')
        store.memory.set_preference('a','language','en');store.memory.set_enabled('a',False)
        self.assertFalse(read_memory_context(self.root,'a')['enabled']);self.assertEqual(store.capture('a',payload(),'c')['status'],'disabled')
        store.memory.clear('a')
        self.assertEqual(experience_counts(self.root,'a')['candidate'],0);self.assertEqual(experience_counts(self.root,'b')['candidate'],1)
        self.assertFalse(store.memory.profile('a')['enabled'])

    def test_scientific_store_rejects_arbitrary_payload_and_detects_corruption(self):
        store=ExperienceStore(self.root);data=payload();data['raw_prompt']='private'
        with self.assertRaises(ValueError):store.capture('a',data,'x')
        data=payload();data['facts']['command']='approve_all'
        with self.assertRaises(ValueError):store.capture('a',data,'x')
        record=store.capture('a',payload(),'x');shown=store.show('a',record['id'])
        store.review('a',record['id'],shown['content_sha256'],'approved')
        with store.memory._connection() as db:db.execute('UPDATE experience_entries SET payload=? WHERE user_key IS NOT NULL',('{}',))
        with self.assertRaises(ValueError):search_experiences(self.root,'a')

    def test_scope_filters_do_not_confuse_matrix_rank_with_uniform_rank(self):
        data=derive_candidate({'tool':'matrix_analysis','ok':True,'arguments':{'matrix':[[1,0],[0,1]]},'result':{'rank':2}},payload()['evidence'])
        self.assertNotIn('rank',data['conditions']);self.assertEqual(data['facts']['rank'],2)
        self.assertNotIn('matrix',data['conditions'])

    def test_preferences_sanitized_and_host_identity_not_model_selectable(self):
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root),'a'));store=UserMemoryStore(self.root/'memory')
        store.set_preference('a','language','zh-CN');store.set_preference('b','language','en')
        result=runtime.call('research_memory',{});self.assertEqual(result['preferences'],{'language':'zh-CN'})
        self.assertEqual(runtime.call('research_memory',{'user_id':'b'})['status'],'protocol_error')
        self.assertEqual(runtime.call('research_experience',{'decision':'approve'})['status'],'protocol_error')
        store.set_enabled('a',False);self.assertEqual(runtime.call('research_memory',{})['preferences'],{})
        self.assertFalse(runtime.call('research_experience',{})['enabled'])


def small_task(request_id='learn-1',*,failure=False):
    return {'version':1,'request_id':request_id,'objective':'Private question that must not enter experience memory',
            'execution':{'mode':'tools','steps':[{'id':'compute','tool':'graph_invariants','arguments':{'kind':'cycle' if failure else 'path','n':2 if failure else 3}}]},
            'constraints':{'max_model_calls':0,'max_tool_calls':2,'allow_extensions':False}}


@unittest.skipUnless(os.name=='nt','Real protected Windows evidence')
class ExperienceExecutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.parent,self.portal=create_subagent(self.root,user_id='a',limits=SubagentLimits(max_tool_calls=8,max_model_calls=0,allow_extensions=False))
        self.store=ExperienceStore(self.root/'memory');self.runtime=MCPResearchRuntime(HostConfiguration(str(self.root),'a',max_tool_calls=8))

    def approve_first(self):
        entry=search_experiences(self.root/'memory','a',reviewed_only=False,status='candidate')['records'][0]
        return self.store.review('a',entry['id'],entry['content_sha256'],'approved','经审阅的单次案例，不能当作一般定理')

    def test_real_call_auto_candidate_review_readonly_evidence_and_dedup(self):
        result=self.parent.submit(small_task());self.assertEqual(result['summary']['experience_collection']['created'],1)
        self.assertEqual(self.runtime.call('research_experience',{})['records'],[])
        entry=self.approve_first();before=result['budget']['used'].copy()
        read=self.runtime.call('research_experience',{'id':entry['id']})
        self.assertEqual(read['records'][0]['source_state'],'verified');self.assertTrue(read['records'][0]['current_core_matches'])
        self.assertEqual(read['records'][0]['content']['facts']['diameter'],2)
        self.assertNotIn('Private question',canonical(read));self.assertNotIn('arguments',read['records'][0]['content'])
        with self.store.memory._connection() as db:self.assertNotIn('Private question','\n'.join(db.iterdump()))
        self.parent.submit(small_task());self.parent.get(result['task_id'])
        self.assertEqual(self.parent.get(result['task_id'])['budget']['used'],before);self.assertEqual(experience_counts(self.root/'memory','a')['approved'],1)
        self.assertEqual(experience_counts(self.root/'memory','a')['candidate'],0)

    def test_real_failed_execution_is_evidence_not_inferred_causality(self):
        result=self.parent.submit(small_task(failure=True));self.assertEqual(result['status'],'failed')
        self.assertEqual(result['summary']['experience_collection']['created'],1)
        entry=self.approve_first();found=self.runtime.call('research_experience',{'outcome':'failure'})
        self.assertEqual(found['records'][0]['source_state'],'verified')
        self.assertEqual(entry['content']['evidence']['verification'],'verified_failed_attempt')
        self.assertEqual(entry['content']['facts']['reported_failure'],'tool_execution_failed')
        record=self.parent._service.read(result['task_id']);state,_,_=self.parent._service.snapshot_state(record)
        request=Path(state['observations'][0]['failed_execution']['directory'])/'request.json'
        request.write_bytes(request.read_bytes()+b' ')
        changed=self.runtime.call('research_experience',{'outcome':'failure'})
        self.assertEqual(changed['records'],[]);self.assertEqual(changed['excluded_changed_sources'],1)

    def test_source_tampering_is_excluded_and_missing_source_marked_archived(self):
        result=self.parent.submit(small_task());entry=self.approve_first()
        record=self.parent._service.read(result['task_id']);state,_,_=self.parent._service.snapshot_state(record)
        path=Path(state['observations'][0]['execution']['directory'])/'result.json';original=path.read_bytes();path.write_bytes(original+b' ')
        found=self.runtime.call('research_experience',{})
        self.assertEqual(found['records'],[]);self.assertEqual(found['excluded_changed_sources'],1)
        path.write_bytes(original);path.unlink()
        found=self.runtime.call('research_experience',{'id':entry['id']})
        self.assertEqual(found['records'][0]['source_state'],'unavailable')

    def test_disabled_memory_collects_nothing_and_does_not_mine_on_reenable(self):
        self.store.memory.set_enabled('a',False);result=self.parent.submit(small_task())
        self.assertEqual(result['summary']['experience_collection']['status'],'disabled')
        self.store.memory.set_enabled('a',True);self.parent.get(result['task_id'])
        self.assertEqual(experience_counts(self.root/'memory','a')['candidate'],0)

    def test_session_opt_out_also_prevents_experience_collection(self):
        queued=self.parent.submit(small_task(),defer=True)
        record=self.parent._service.read(queued['task_id']);session=self.parent._service.session(record)
        session.memory_enabled=False;session._save()
        result=self.parent.start_queued(queued['task_id']);self.assertEqual(result['status'],'completed')
        self.assertEqual(result['summary']['experience_collection']['status'],'disabled')
        self.assertEqual(experience_counts(self.root/'memory','a')['candidate'],0)

    def test_version_difference_is_explicit_without_recomputation(self):
        self.parent.submit(small_task());entry=self.approve_first()
        from graph_research.assistant import experience_evidence
        from graph_research.runtime.integrity import CORE,MANIFEST
        real=experience_evidence.file_hash
        def changed(path):return '0'*64 if Path(path)==CORE/MANIFEST else real(path)
        with patch.object(experience_evidence,'file_hash',side_effect=changed),patch('graph_research.runtime.runner.run_tool') as run:
            read=self.runtime.call('research_experience',{'id':entry['id']})
        run.assert_not_called();self.assertFalse(read['records'][0]['current_core_matches']);self.assertEqual(read['records'][0]['source_state'],'verified')

    def test_collection_failure_does_not_change_calculation_success(self):
        with patch('graph_research.assistant.experience_evidence.collect_task',side_effect=sqlite3.OperationalError('locked')):
            result=self.parent.submit(small_task())
        self.assertEqual(result['status'],'completed');self.assertEqual(result['summary']['experience_collection']['status'],'storage_unavailable')
        self.assertEqual(self.parent._service.read(result['task_id'])['experience_cursor'],1)

    def test_explicit_capture_can_import_existing_verified_calls(self):
        result=self.parent.submit(small_task());self.store.clear('a')
        captured=capture_call(self.parent._service,result['task_id'],'call-0001')
        self.assertTrue(captured['created']);self.assertEqual(captured['status'],'candidate')

    def test_cli_review_uses_exact_inspected_hash_and_no_api(self):
        self.parent.submit(small_task())
        def cli(*args):
            result=subprocess.run([sys.executable,'-X','utf8','-m','graph_research','experience',*args,'--root',str(self.root),'--user','a'],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(result.returncode,0,result.stderr);return json.loads(result.stdout)
        entry=cli('list','--status','candidate')['records'][0]
        approved=cli('review','--id',entry['id'],'--content-sha256',entry['content_sha256'],'--decision','approve','--note','合成样例的审阅流程验证')
        self.assertEqual(approved['status'],'approved');self.assertEqual(len(self.runtime.call('research_experience',{})['records']),1)

    def test_clear_before_resume_does_not_relearn_completed_calls(self):
        from tests.test_batch_workflow import batch_task
        from graph_research.runtime.runner import run_tool
        calls=[]
        def run(*args,**kwargs):
            result=run_tool(*args,**kwargs);calls.append(result)
            if len(calls)==1:
                task_id=next(self.root.glob('users/*/tasks/*/task.json')).parent.name;self.parent.cancel(task_id)
            return result
        with patch('graph_research.runtime.runner.run_tool',side_effect=run):paused=self.parent.submit(batch_task())
        self.assertEqual(paused['status'],'cancelled');self.assertEqual(experience_counts(self.root/'memory','a')['candidate'],1)
        self.store.memory.clear('a');p=paused['interaction'];event=self.portal.continue_task(paused['task_id'],p['interaction_id'],paused['revision'])
        done=self.parent.resume(paused['task_id'],event['event_id']);self.assertEqual(done['status'],'completed')
        self.assertEqual(experience_counts(self.root/'memory','a')['candidate'],3)
