"""Independent scientific and MCP regressions from the two Codex field tests."""
import copy
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from graph_research.hypergraphs import HyperPath,HyperCycle,Hypergraph
from graph_research.hypergraphs.spectral_certificate import verify_spectrum_certificate
from graph_research.mcp.presentation import result_view
from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
from graph_research.assistant import create_subagent,SubagentLimits
from tests.test_subagent import direct_task,agent_task
from tests.test_feature_workflow import ScriptedModel


class ScientificFeedbackTests(unittest.TestCase):
    def test_endpoint_uses_actual_weighted_or_explicit_diagonal_without_positive_vector(self):
        for graph,expected in [(Hypergraph([[0,1,2]],vertex_degrees=[3,7,2]),7),
                               (Hypergraph([[0,1,2],[2,3,4]],weights=[.1,.2]),.1+.2),
                               (Hypergraph([[0,1],[2,3]]),1),(Hypergraph([[0,1]],vertices=[0,1,2]),1)]:
            result=graph.alpha_spectrum(1);self.assertAlmostEqual(result['rho'],expected)
            self.assertIsNone(result['perron_vector']);self.assertEqual(result['iterations'],0);self.assertTrue(result['verification']['passed'])
            with self.assertRaises(ValueError):graph.weighted_incidence_from_result(result)

    def test_loose_cycle_formula_and_certified_interval_across_parameters(self):
        for m in (3,6):
            graph=HyperCycle(m,4)
            for alpha in (0,.3,.9,.99,.999):
                result=graph.alpha_spectrum(alpha,method='auto');expected=(3*alpha+math.sqrt(alpha*alpha+8*(1-alpha)**2))/2
                self.assertAlmostEqual(result['rho'],expected,places=9);self.assertTrue(result['verification']['passed'])
                self.assertLess(result['iterations'],150);self.assertEqual(result['method'],'equitable_two_block_bisection')
                self.assertIn('equitable_blocks',result);self.assertNotIn('orbit_blocks',result)
                self.assertLessEqual(result['collatz_lower']-1e-14,expected);self.assertGreaterEqual(result['collatz_upper']+1e-14,expected)

    def test_independent_checker_rejects_tampered_vector_labels_weights_and_rho(self):
        graph=HyperPath(3,3);result=graph.alpha_spectrum(.3)
        for field in ('perron_vector','vertex_order','rho'):
            changed=copy.deepcopy(result)
            if field=='perron_vector':changed[field][0]*=1.2
            elif field=='vertex_order':changed[field][0]='wrong-label'
            else:changed[field]*=1.1
            try:verified=verify_spectrum_certificate(graph.hyperedges(),changed)
            except ValueError:continue
            self.assertFalse(verified['passed'])
        self.assertFalse(verify_spectrum_certificate(graph.hyperedges(),result,weights=[2,1,1])['passed'])
        with patch.object(Hypergraph,'alpha_spectrum',side_effect=AssertionError('Verifier must not solve')):
            self.assertTrue(verify_spectrum_certificate(graph.hyperedges(),result)['passed'])

    def test_auto_result_reports_achieved_tolerance_and_cross_method_consistency(self):
        graph=HyperPath(3,3);result=graph.alpha_spectrum(.3)
        self.assertIsNotNone(result['achieved_tolerance'])
        consistency=result['method_consistency']
        self.assertTrue(consistency['checked']);self.assertTrue(consistency['consistent'],consistency)
        direct=graph.alpha_spectrum(.3,method='iteration')
        self.assertIn('achieved_tolerance',direct);self.assertNotIn('method_consistency',direct)

    def test_hot_start_is_reproducible_and_invalid_vectors_do_not_silently_fallback(self):
        graph=HyperPath(3,3);cold=graph.alpha_spectrum(.7)
        warm=graph.alpha_spectrum(.7,initial_vector=cold['perron_vector'])
        self.assertLessEqual(warm['iterations'],2);self.assertEqual(warm['initialization'],'provided_vector');self.assertTrue(warm['verification']['passed'])
        for vector in ([1],[-1]*graph.order(),[float('nan')]*graph.order()):
            with self.assertRaises(ValueError):graph.alpha_spectrum(.7,initial_vector=vector)
        for alpha in (-.1,1.1):
            with self.assertRaises(ValueError):graph.alpha_spectrum(alpha)

    def test_auto_falls_back_without_claiming_reduction_for_weighted_input(self):
        graph=Hypergraph([[0,1,2],[2,3,4]],weights=[1,2]);result=graph.alpha_spectrum(.3,method='auto')
        self.assertEqual(result['method'],'shifted_power_iteration');self.assertTrue(result['verification']['passed'])

    def test_equitable_reduction_matches_cold_solver_across_ranks_and_cycle_lengths(self):
        for rank in (3,5,8):
            for m in (3,4):
                graph=HyperCycle(m,rank)
                for alpha in (.2,.7):
                    reduced=graph.alpha_spectrum(alpha,method='auto');original=graph.alpha_spectrum(alpha,method='iteration')
                    self.assertAlmostEqual(reduced['rho'],original['rho'],places=9)
                    self.assertTrue(reduced['verification']['passed'])

    def test_endpoint_text_does_not_claim_an_unavailable_vector_was_saved(self):
        from graph_research.rendering.results import terminal_result
        result=Hypergraph([[0,1,2]]).alpha_spectrum(1)
        text=terminal_result({'tool':'hypergraph_spectrum','ok':True,'result':result})
        self.assertIn('Perron向量：—',text)
        self.assertNotIn('Perron向量：已保存',text)


class MCPFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_summary_omits_vectors_but_full_is_unchanged(self):
        full={'summary':{},'results':[{'call_id':'call-0001','arguments':{'edges':[[0,1,2]]},'data':{'rho':2,'perron_vector':[.3,.3,.4]}}]}
        shown=result_view(full);self.assertEqual(shown['results'][0]['data']['rho'],2)
        self.assertNotIn('perron_vector',shown['results'][0]['data']);self.assertIn('perron_vector',full['results'][0]['data'])
        self.assertEqual(result_view(full,'full'),full)

    def test_running_inflight_step_has_no_interruption_warning(self):
        parent,_=create_subagent(self.root,user_id='a');queued=parent.submit(direct_task(),defer=True)
        record=parent._service.read(queued['task_id']);record.update(status='running',inflight_step='matrix');parent._service.save(record)
        self.assertFalse(any('中断时' in w for w in parent.get(queued['task_id'])['warnings']))
        record['status']='interrupted';parent._service.save(record)
        self.assertTrue(any('中断时' in w for w in parent.get(queued['task_id'])['warnings']))

    def test_contract_fingerprint_allows_safe_reuse(self):
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root),'a'))
        first=runtime.catalog('hypergraph_spectrum');same=runtime.catalog('hypergraph_spectrum',known_hash=first['schema_hash'])
        self.assertTrue(same['unchanged']);self.assertNotIn('tool',same)
        self.assertIn('tool',runtime.catalog('hypergraph_spectrum',known_hash='a'*64))

    def test_finished_worker_refreshes_stale_task_snapshot_before_returning(self):
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root),'a'))
        queued=runtime.parent.submit(direct_task(),defer=True);final=copy.deepcopy(queued)
        final.update(status='budget_exhausted',terminal=True,revision=queued['revision']+2)
        final['budget']['used']['tool_calls']=1
        job={'state':'finished','job_id':'a'*32,'operation':'start','result_revision':final['revision'],'result_status':final['status']}
        for status in ('queued','running','waiting_for_user'):
            stale=copy.deepcopy(queued);stale['status']=status
            with self.subTest(status=status),patch.object(runtime,'_current_job',return_value=(self.root/'job.json',job)),patch.object(runtime,'_live',return_value=False),patch.object(runtime,'_snapshot',return_value=final) as refreshed:
                result=runtime._decorate(stale)
                self.assertEqual(result['status'],'budget_exhausted');self.assertEqual(result['budget']['used']['tool_calls'],1)
                refreshed.assert_called_once_with(queued['task_id'])

    def test_short_submit_can_wait_for_completion_and_records_rpc_measurements(self):
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root),'a'))
        task={'version':1,'request_id':'p5-short','objective':'P5直径','execution':{'mode':'tools','steps':[{'id':'diameter','tool':'graph_invariants','arguments':{'n':5}}]}}
        result=runtime.call('research_submit',{'task':task,'wait_seconds':10})
        self.assertEqual(result['status'],'completed');self.assertEqual(result['results'][0]['data']['diameter'],4)
        measurements=result['results'][0]['measurements'];self.assertTrue(measurements['available']);self.assertGreater(measurements['cpu_seconds'],0)
        self.assertGreater(measurements['peak_job_memory_bytes'],0)
        from graph_research.mcp.telemetry import RPCTelemetry
        costs=RPCTelemetry(runtime.directory).report();self.assertEqual(costs['calls'],1);self.assertIsNone(costs['main_model_token_usage'])


def scan_task(request_id='alpha-scan',**settings):
    scan={'generator':{'family':'cycle','m':6,'k':4},'alphas':[0,.9,1]};scan.update(settings)
    return {'version':1,'request_id':request_id,'objective':'固定4一致松圈α扫描','execution':{'mode':'scan','scan':scan}}


class ScanFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_budget_is_rejected_before_registration_not_hidden_in_one_batch_call(self):
        from graph_research.assistant.task_contract import TaskProtocolError
        parent,_=create_subagent(self.root,user_id='a',limits=SubagentLimits(max_tool_calls=10))
        with self.assertRaises(TaskProtocolError) as error:parent.submit(scan_task(alphas=[i/10 for i in range(11)]))
        self.assertEqual(error.exception.code,'scan_budget_insufficient');self.assertFalse(list(self.root.rglob('task.json')))

    def test_scan_uses_per_point_receipts_endpoint_and_independent_certificates(self):
        parent,_=create_subagent(self.root,user_id='a',limits=SubagentLimits(max_tool_calls=4,max_model_calls=0))
        result=parent.submit(scan_task())
        self.assertEqual(result['status'],'completed',
            f"points={result['summary'].get('scan',{}).get('points')} warnings={result['warnings']} error={result['error']}")
        self.assertEqual(result['budget']['used'],{'model_calls':0,'tool_calls':4})
        rows=result['summary']['scan']['points'];self.assertEqual(len(rows),3);self.assertTrue(all(row['status']=='success' for row in rows));self.assertEqual(rows[-1]['rho'],2)
        for item in result['results'][1:]:self.assertTrue(item['data']['verification']['passed'])
        self.assertEqual(parent.submit(scan_task())['budget']['used']['tool_calls'],4)

    def test_scan_keeps_failed_points_and_delivers_later_endpoint_without_fake_precision(self):
        parent,_=create_subagent(self.root,user_id='a',limits=SubagentLimits(max_tool_calls=3,max_model_calls=0))
        result=parent.submit(scan_task(alphas=[.3,1],method='iteration',max_iterations=1))
        self.assertEqual(result['status'],'partial');rows=result['summary']['scan']['points']
        self.assertEqual(rows[0]['status'],'unresolved');self.assertNotIn('rho',rows[0]);self.assertEqual(rows[1]['rho'],2)

    def test_cancelled_scan_requires_user_event_and_reuses_verified_points_without_resetting_budget(self):
        from graph_research.runtime.runner import run_tool
        parent,portal=create_subagent(self.root,user_id='a',limits=SubagentLimits(max_tool_calls=4,max_model_calls=0))
        calls=[]
        def interrupt_after_first_point(*args,**kwargs):
            result=run_tool(*args,**kwargs);calls.append(args[0])
            if len(calls)==2:kwargs['cancel_file'].write_text('cancel')
            return result
        with patch('graph_research.runtime.runner.run_tool',side_effect=interrupt_after_first_point):paused=parent.submit(scan_task())
        detail=str({'status':paused.get('status'),'error':paused.get('error'),'warnings':paused.get('warnings'),'calls':calls})[:800]
        self.assertEqual(paused['status'],'cancelled',detail);self.assertEqual(paused['budget']['used']['tool_calls'],2)
        p=paused['interaction'];event=portal.continue_task(paused['task_id'],p['interaction_id'],paused['revision'])
        resumed=parent.resume(paused['task_id'],event['event_id']);self.assertEqual(resumed['status'],'completed')
        self.assertEqual(resumed['budget']['used']['tool_calls'],4);self.assertEqual(len(resumed['results']),4)
        self.assertEqual(resumed['summary']['reused_calculations'],2)


if __name__=='__main__':unittest.main()
