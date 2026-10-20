"""Timing attribution, diagnostic propagation and honest acceptance accounting."""
from contextlib import redirect_stdout
import copy
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from graph_research.runtime.observability import Timings,recording,measure,annotate,error_details,bounded_timings
from graph_research.runtime.storage import read_json


class ObservabilityTests(unittest.TestCase):
    def test_nested_spans_have_nonoverlapping_exclusive_costs(self):
        clock=[0.0];timings=Timings(clock=lambda:clock[0])
        with recording(timings):
            with measure('outer'):
                clock[0]=2
                with measure('inner'):clock[0]=5
                clock[0]=7
        clock[0]=8;value=timings.snapshot()
        self.assertEqual(value['stages']['outer'],{'seconds':7,'exclusive_seconds':4,'calls':1})
        self.assertEqual(value['stages']['inner']['exclusive_seconds'],3)
        self.assertEqual(value['unattributed_seconds'],1)

    def test_handled_exception_is_recorded_without_marking_result_failed(self):
        timings=Timings()
        with recording(timings):
            try:
                with measure('export.csv'):raise OSError('handled')
            except OSError as error:self.assertEqual(error.failure_stage,'export.csv')
        self.assertEqual(timings.snapshot()['failed_stage'],'export.csv')
        self.assertNotIn('status',timings.snapshot())

    def test_original_error_codes_and_identifier_survive_wrapping_without_paths(self):
        from graph_research.runtime.runner import WorkerFailure
        original=PermissionError(13,'PRIVATE_SECRET','C:/private/token')
        original.winerror=5;original.failure_stage='export.csv'
        identifier='d'*32;detail=annotate(original,identifier=identifier)
        wrapped=WorkerFailure('PRIVATE_SECRET',phase='worker_reported');wrapped.error_details=detail
        current=error_details(wrapped,phase='mcp.submit')
        self.assertEqual(current['diagnostic_id'],identifier);self.assertEqual(current['phase'],'export.csv')
        self.assertEqual(current['errno'],13);self.assertEqual(current['winerror'],5)
        self.assertNotIn('PRIVATE_SECRET',json.dumps(current));self.assertNotIn('C:/private',json.dumps(current))

    def test_timing_reader_rejects_nonfinite_and_unbounded_data(self):
        timings=Timings()
        with recording(timings),measure('work'):pass
        value=timings.snapshot();self.assertIsNotNone(bounded_timings(value))
        bad=copy.deepcopy(value);bad['stages']['work']['seconds']=float('nan');self.assertIsNone(bounded_timings(bad))
        bad=copy.deepcopy(value);bad['stages']['work']['exclusive_seconds']=-1;self.assertIsNone(bounded_timings(bad))

    def test_full_inventory_includes_root_tests_with_unique_ids(self):
        from tools.test_inventory import collect
        root=Path(__file__).resolve().parents[1];_,inventory=collect(root,'full')
        self.assertEqual(inventory['root_count'],7)
        self.assertEqual(len(inventory['test_ids']),len(set(inventory['test_ids'])))
        self.assertTrue(any(name.startswith('test_workflow.') for name in inventory['test_ids']))
        self.assertEqual(inventory['collected_tests'],inventory['tests_directory_count']+7)

    def test_unregistered_root_test_fails_closed(self):
        from tools.test_inventory import module_sets
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'tests').mkdir();(root/'tests/gates.json').write_text('{"fast":[],"full":[],"root":[]}')
            (root/'test_forgotten.py').write_text('')
            with self.assertRaisesRegex(ValueError,'root'):module_sets(root)

    def test_source_fingerprint_detects_test_change_without_core_change(self):
        from tools.test_inventory import source_files,fingerprint
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'tests').mkdir();p=root/'tests/test_one.py';p.write_text('one')
            before=fingerprint(source_files(root));p.write_text('two')
            self.assertNotEqual(before,fingerprint(source_files(root)))

    def test_outcomes_count_subtest_failure_and_skip_separately(self):
        from tools.run_test_suite import EvidenceResult
        class Sample(unittest.TestCase):
            def test_good(self):pass
            def test_bad(self):
                for i in (0,1):
                    with self.subTest(i=i):self.assertEqual(i,0)
            @unittest.skip('synthetic skip')
            def test_skip(self):pass
        result=unittest.TextTestRunner(stream=io.StringIO(),resultclass=EvidenceResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(Sample))
        self.assertEqual(result.testsRun,3);self.assertFalse(result.wasSuccessful())
        self.assertEqual(sorted(v['status'] for v in result.outcomes.values()),['failed','passed','skipped'])
        self.assertEqual(len(result.subtest_events),1)

    def test_class_fixture_error_is_not_a_successful_test(self):
        from tools.run_test_suite import EvidenceResult
        class Broken(unittest.TestCase):
            @classmethod
            def setUpClass(cls):raise RuntimeError('fixture blocked')
            def test_never_started(self):self.fail('must not execute')
        result=unittest.TextTestRunner(stream=io.StringIO(),resultclass=EvidenceResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(Broken))
        self.assertEqual(result.testsRun,0);self.assertFalse(result.wasSuccessful())
        self.assertEqual(result.fixture_events[0]['status'],'error');self.assertFalse(result.outcomes)

    def test_rpc_diagnostics_extend_legacy_database_without_recording_error_text(self):
        from graph_research.mcp.telemetry import RPCTelemetry
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);connection=sqlite3.connect(root/'rpc-metrics.sqlite3')
            connection.execute('CREATE TABLE calls(at REAL,version TEXT,operation TEXT,task_id TEXT,status TEXT,elapsed REAL,response_bytes INTEGER)');connection.close()
            telemetry=RPCTelemetry(root);identifier='a'*32
            result={'status':'protocol_error','error':{'code':'io_path_missing','diagnostic_id':identifier,'phase':'development.submit','errno':2,'exception_type':'FileNotFoundError','message':'PRIVATE_SECRET'}}
            telemetry.record('research_development',result,.1,10)
            record=telemetry.diagnostic(identifier);self.assertTrue(record['found']);self.assertEqual(record['error']['errno'],2)
            self.assertNotIn('PRIVATE_SECRET',json.dumps(record));self.assertEqual(telemetry.report()['calls'],1)


@unittest.skipUnless(os.name=='nt','Actual protected Windows execution')
class ProtectedObservabilityTests(unittest.TestCase):
    def test_success_has_correlated_host_and_worker_timing_and_preserved_result(self):
        from graph_research.runtime.runner import run_tool
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);result=run_tool('graph_invariants',{'kind':'path','n':3},root/'tools',directory=root/'runs',include_receipt=True)
            self.assertEqual(result['result']['diameter'],2)
            receipt=read_json(Path(result['execution']['directory'])/'execution.json')[0]
            self.assertEqual(receipt['diagnostic_id'],result['execution']['diagnostic_id'])
            host=receipt['timings']['host']['stages'];worker=receipt['timings']['worker']['stages']
            self.assertGreater(host['host.process_startup']['seconds'],0);self.assertGreater(worker['tool_function']['seconds'],0)
            self.assertGreater(worker['worker.registry']['seconds'],0);self.assertIn('worker.result_publication',worker)
            self.assertEqual(receipt['limits']['wall_seconds'],30)

    def test_failed_worker_preserves_original_type_phase_and_receipt_id(self):
        from graph_research.runtime.runner import run_tool,WorkerFailure
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with self.assertRaises(WorkerFailure) as caught:run_tool('bogus_tool_name',{},root/'tools',directory=root/'runs')
            error=caught.exception;self.assertEqual(error.phase,'worker_reported');self.assertEqual(error.error_type,'TaskProtocolError')
            receipt=read_json(Path(error.execution_directory)/'execution.json')[0]
            self.assertEqual(error.diagnostic_id,receipt['diagnostic_id']);self.assertEqual(receipt['error_details']['phase'],'worker.tool_dispatch')

    def test_failure_receipt_io_error_does_not_replace_original_calculation_error(self):
        from graph_research.runtime.runner import run_tool,WorkerFailure
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            with patch('graph_research.runtime.runner.atomic_text',side_effect=PermissionError(13,'synthetic receipt failure')):
                with self.assertRaises(WorkerFailure) as caught:run_tool('bogus_tool_name',{},root/'tools',directory=root/'runs')
            self.assertEqual(caught.exception.error_type,'TaskProtocolError')
            self.assertEqual(error_details(caught.exception)['failure_receipt_error']['errno'],13)

    def test_certificate_and_export_are_separately_observed(self):
        from graph_research.runtime.runner import run_tool
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,args,key in [('hypergraph_spectrum',{'edges':[[0,1,2]],'alpha':.99},'certificate_verification'),
                                  ('graph_batch_study',{'cases':[{'name':'P3','input':{'kind':'path','n':3}}]},'export.csv')]:
                result=run_tool(name,args,root/'tools',directory=root/'runs',include_receipt=True)
                receipt=read_json(Path(result['execution']['directory'])/'execution.json')[0]
                self.assertGreater(receipt['timings']['worker']['stages'][key]['seconds'],0)

    def test_mcp_error_response_can_be_looked_up_without_disclosing_message(self):
        from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
        from graph_research.mcp.telemetry import RPCTelemetry
        with tempfile.TemporaryDirectory() as tmp:
            runtime=MCPResearchRuntime(HostConfiguration(tmp,'diagnostics'))
            error=FileNotFoundError(2,'PRIVATE_SECRET','C:/private/token')
            with patch.object(runtime,'catalog',side_effect=error):response=runtime.call('research_catalog',{})
            detail=response['error'];self.assertEqual(detail['errno'],2);self.assertEqual(detail['phase'],'mcp.catalog')
            self.assertNotIn('PRIVATE_SECRET',json.dumps(response));self.assertTrue(RPCTelemetry(runtime.directory).diagnostic(detail['diagnostic_id'])['found'])

    def test_subagent_failure_keeps_structured_diagnostics_in_portable_results(self):
        from graph_research.assistant.subagent import create_subagent
        from graph_research.assistant.task_control import SubagentLimits
        with tempfile.TemporaryDirectory() as tmp:
            parent,_=create_subagent(tmp,user_id='failure',limits=SubagentLimits(max_model_calls=0,max_tool_calls=1,allow_extensions=False),results_directory=str(Path(tmp)/'results'))
            task={'version':1,'request_id':'duplicate-edges','objective':'diagnostic test','execution':{'mode':'tools','steps':[{'id':'bad','tool':'graph_spectrum','arguments':{'kind':'edges','n':3,'edges':[[0,1],[1,0]]}}]}}
            response=parent.submit(task)
            self.assertEqual(response['status'],'failed');self.assertEqual(response['budget']['used']['tool_calls'],1)
            self.assertEqual(response['results'][0]['error_details']['exception_type'],'ValueError')
            self.assertEqual(len(response['results'][0]['error_details']['diagnostic_id']),32)
            with zipfile.ZipFile(response['artifacts'][0]['path']) as archive:
                error=json.loads(archive.read('calls/calc-0001/error.json'))
                self.assertEqual(error['error_details']['diagnostic_id'],response['results'][0]['error_details']['diagnostic_id'])


if __name__=='__main__':unittest.main()
