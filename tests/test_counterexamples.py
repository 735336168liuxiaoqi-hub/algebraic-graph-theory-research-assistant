"""Real bounded search and independent certificates; no paid model requests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import networkx as nx
from sympy import Rational

from graph_research.workflows.counterexamples import graph_counterexample_round, graph_counterexample_verify
from graph_research.assistant import create_subagent, SubagentLimits
from graph_research.assistant.task_contract import TaskProtocolError, validate_task


def search_task(request_id='counterexample-1', **changes):
    problem = {'reference': {'kind': 'path', 'n': 4}, 'planner': 'rules', 'max_rounds': 3, 'candidates_per_round': 4}
    problem.update(changes)
    return {'version': 1, 'request_id': request_id, 'objective': '寻找固定n/m连通简单图中邻接谱半径更大的反例',
            'execution': {'mode': 'counterexample', 'counterexample': problem}}


class CounterexampleMathTests(unittest.TestCase):
    def test_path_four_is_refuted_by_star_with_exact_polynomials(self):
        result = graph_counterexample_verify({'kind': 'path', 'n': 4}, {'kind': 'star', 'n': 4})
        self.assertEqual(result['status'], 'counterexample_found')
        self.assertTrue(result['counterexample_verified'])
        self.assertEqual(result['reference_certificate']['coefficients_descending'], ['1', '0', '-3', '0', '1'])
        self.assertEqual(result['candidate_certificate']['coefficients_descending'], ['1', '0', '-3', '0', '0'])
        self.assertGreater(Rational(result['difference_bounds'][0]), 0)
        self.assertEqual(result['constraints_verified']['m'], 3)
        self.assertFalse(result['universal_optimality_proved'])

    def test_same_graph_is_not_a_counterexample(self):
        result = graph_counterexample_verify({'kind': 'path', 'n': 3}, {'kind': 'path', 'n': 3})
        self.assertEqual(result['status'], 'not_counterexample')
        self.assertFalse(result['counterexample_verified'])

    def test_input_constraints_are_rechecked_in_verifier(self):
        reference = {'kind': 'path', 'n': 4}
        invalid = [
            {'kind': 'complete', 'n': 4}, {'kind': 'path', 'n': 5},
            {'kind': 'edges', 'n': 4, 'edges': [[0, 1], [1, 2]]},
            {'kind': 'edges', 'n': 4, 'edges': [[0, 0], [0, 1], [1, 2]]},
            {'kind': 'edges', 'n': 4, 'edges': [[0, 1], [1, 0], [2, 3]]},
            {'kind': 'path', 'n': 4, 'directed': True}, {'kind': 'path', 'n': True}]
        for candidate in invalid:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                graph_counterexample_verify(reference, candidate)

    def test_seeded_search_is_reproducible_bounded_and_never_certifies(self):
        arguments = {'reference': {'kind': 'path', 'n': 7}, 'strategy': 'edge_move', 'candidates': 5, 'seed': 19}
        a, b = graph_counterexample_round(**arguments), graph_counterexample_round(**arguments)
        self.assertEqual(a, b)
        self.assertLessEqual(a['evaluated_candidates'], 5)
        self.assertLessEqual(a['generated_attempts'], 80)
        self.assertFalse(a['counterexample_verified'])
        candidate = nx.Graph()
        candidate.add_nodes_from(range(7))
        candidate.add_edges_from(a['best_graph']['edges'])
        self.assertTrue(nx.is_connected(candidate))
        self.assertEqual(candidate.number_of_edges(), 6)

    def test_enumeration_cursor_and_visited_set_continue_without_duplicate_scores(self):
        first = graph_counterexample_round({'kind': 'path', 'n': 4}, strategy='enumerate', candidates=1)
        second = graph_counterexample_round({'kind': 'path', 'n': 4}, strategy='enumerate', candidates=2,
                                            seen=first['seen'], cursor=first['cursor'], incumbent=first['best_graph'])
        self.assertGreater(second['cursor'], first['cursor'])
        self.assertFalse({r['graph6'] for r in first['evaluations']} & {r['graph6'] for r in second['evaluations']})

    def test_unbounded_enumeration_is_rejected(self):
        with self.assertRaises(ValueError):
            graph_counterexample_round({'kind': 'path', 'n': 12}, strategy='enumerate')


class CounterexampleAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def create(self, **kwargs):
        return create_subagent(self.root, user_id='counterexample-test', **kwargs)

    def test_rules_search_delivers_verified_witness_and_bundle_without_model(self):
        parent, _ = self.create(model_factory=lambda: (_ for _ in ()).throw(AssertionError('No model allowed')))
        result = parent.submit(search_task())
        self.assertEqual(result['status'], 'completed', result)
        summary = result['summary']['counterexample']
        self.assertEqual(summary['outcome'], 'counterexample_found')
        self.assertTrue(summary['counterexample_verified'])
        self.assertEqual(summary['rounds_completed'], 1)
        self.assertEqual(result['budget']['used'], {'model_calls': 0, 'tool_calls': 2})
        self.assertFalse(result['summary']['mathematical_proof'])
        with zipfile.ZipFile(result['artifacts'][0]['path']) as bundle:
            evidence = json.loads(bundle.read('counterexample-summary.json'))
            self.assertGreater(Rational(evidence['witness']['difference_bounds'][0]), 0)
            self.assertEqual(json.loads(bundle.read('results.json'))['counterexample_search'], evidence)

    def test_repeated_submission_does_not_recompute_or_reset_budget(self):
        parent, _ = self.create()
        task = search_task()
        first = parent.submit(task)
        again = parent.submit(copy.deepcopy(task))
        self.assertEqual(first['task_id'], again['task_id'])
        self.assertEqual(first['budget']['used'], again['budget']['used'])
        self.assertEqual(again['summary']['reuse']['task_reused'], 1)
        task['execution']['counterexample']['seed'] = 5
        with self.assertRaises(TaskProtocolError):
            parent.submit(task)

    def test_finite_search_without_witness_does_not_claim_optimality(self):
        parent, _ = self.create()
        result = parent.submit(search_task(reference={'kind': 'star', 'n': 4}))
        summary = result['summary']['counterexample']
        self.assertEqual(summary['outcome'], 'not_found_within_budget')
        self.assertFalse(summary['universal_optimality_proved'])
        self.assertFalse(summary['counterexample_verified'])
        self.assertIn('不证明', result['answer'])

    def test_budget_and_whitelist_rejected_before_any_execution(self):
        for limits in (SubagentLimits(max_tool_calls=1), SubagentLimits(allowed_tools=('graph_counterexample_round',))):
            with self.subTest(limits=limits):
                parent, _ = self.create(limits=limits)
                with self.assertRaises(TaskProtocolError):
                    parent.submit(search_task())
        self.assertEqual(list(self.root.glob('users/*/tasks/*/task.json')), [])

    def test_extra_constraints_and_mixed_modes_are_not_silently_ignored(self):
        for index, task in enumerate((search_task(), search_task(), search_task())):
            if index == 0:
                task['definitions'] = ['额外要求三角形自由']
            elif index == 1:
                task['execution']['steps'] = [{'id': 'x', 'tool': 'graph_invariants', 'arguments': {}}]
            else:
                task['execution']['counterexample']['reference']['directed'] = True
            with self.subTest(index=index), self.assertRaises(TaskProtocolError):
                validate_task(task)

    def test_model_selects_strategy_then_stops_using_feedback(self):
        class Planner:
            def __init__(self):
                self.contexts = []
            def complete(self, messages):
                self.contexts.append(json.loads(messages[1]['content']))
                return {'strategy': 'random' if len(self.contexts) == 1 else 'stop', 'reason': '停止本次有限搜索'}
        planner = Planner()
        parent, _ = self.create(model_factory=lambda: planner)
        result = parent.submit(search_task(reference={'kind': 'complete', 'n': 4}, planner='model'))
        self.assertEqual(result['summary']['counterexample']['stop_reason'], 'planner_stopped')
        self.assertEqual(result['budget']['used'], {'model_calls': 2, 'tool_calls': 1})
        self.assertEqual(planner.contexts[1]['previous_strategies'][0]['strategy'], 'random')
        self.assertEqual(planner.contexts[1]['feedback'][0]['strategy'], 'random')
        self.assertEqual(planner.contexts[1]['feedback'][0]['evaluated_candidates'], 0)

    def test_model_cannot_declare_a_witness_or_change_budget(self):
        class BadPlanner:
            def complete(self, messages):
                return {'strategy': 'random', 'counterexample_verified': True, 'max_tool_calls': 100}
        parent, _ = self.create(model_factory=BadPlanner)
        result = parent.submit(search_task(planner='model'))
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['summary']['counterexample']['counterexample_verified'])
        self.assertEqual(result['budget']['used'], {'model_calls': 1, 'tool_calls': 0})

    def test_verification_failure_is_unverified_not_found(self):
        from graph_research.runtime.runner import run_tool
        def fail_verify(name, *args, **kwargs):
            if name == 'graph_counterexample_verify':
                raise ArithmeticError('Injected verification failure')
            return run_tool(name, *args, **kwargs)
        parent, _ = self.create()
        with patch('graph_research.runtime.runner.run_tool', side_effect=fail_verify):
            result = parent.submit(search_task())
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['summary']['counterexample']['outcome'], 'candidate_unverified')
        self.assertFalse(result['summary']['counterexample']['counterexample_verified'])

    def test_cancel_then_trusted_continue_retains_search_and_counts_retry(self):
        from graph_research.runtime.runner import run_tool
        def cancel_verify(name, *args, **kwargs):
            if name == 'graph_counterexample_verify':
                raise InterruptedError('Injected interruption')
            return run_tool(name, *args, **kwargs)
        parent, portal = self.create()
        with patch('graph_research.runtime.runner.run_tool', side_effect=cancel_verify):
            first = parent.submit(search_task())
        self.assertEqual(first['status'], 'cancelled')
        self.assertEqual(first['budget']['used']['tool_calls'], 2)
        interaction = first['interaction']
        event = portal.continue_task(first['task_id'], interaction['interaction_id'], first['revision'])
        reloaded, _ = self.create()
        result = reloaded.resume(first['task_id'], event['event_id'])
        self.assertEqual(result['summary']['counterexample']['outcome'], 'counterexample_found')
        self.assertEqual(result['budget']['used']['tool_calls'], 3)
        self.assertEqual(sum(r['tool'] == 'graph_counterexample_round' for r in result['results']), 1)

    def test_mcp_rejects_unconfigured_model_before_creating_a_task(self):
        from graph_research.mcp.runtime import HostConfiguration, MCPResearchRuntime
        runtime = MCPResearchRuntime(HostConfiguration(str(self.root), 'mcp-search'))
        with self.assertRaises(TaskProtocolError) as caught:
            runtime.submit(search_task(planner='model'))
        self.assertEqual(caught.exception.code, 'agent_mode_disabled')
        self.assertEqual(list(self.root.glob('users/*/tasks/*/task.json')), [])

    def test_real_mcp_background_search_and_result_lookup(self):
        from graph_research.mcp.runtime import HostConfiguration, MCPResearchRuntime
        import subprocess
        import time
        runtime = MCPResearchRuntime(HostConfiguration(str(self.root), 'mcp-search'))
        try:
            result = runtime.submit(search_task(), wait_seconds=1, detail='full')
            task_id = result['task_id']
            deadline = time.monotonic()+40
            while result['status'] in ('queued', 'running') and time.monotonic() < deadline:
                result = runtime.get(task_id, wait_seconds=1, until='terminal', detail='full')
            self.assertEqual(result['status'], 'completed', result)
            self.assertEqual(result['summary']['counterexample']['outcome'], 'counterexample_found')
            replay = runtime.submit(search_task(), detail='full')
            self.assertEqual(replay['task_id'], task_id)
            self.assertEqual(replay['budget']['used']['tool_calls'], 2)
        finally:
            for process in runtime.children.values():
                if isinstance(process, subprocess.Popen):
                    if process.poll() is None:
                        entry = runtime._current_job()
                        if entry:
                            runtime.cancel(entry[1]['task_id'])
                    process.wait(10)

    def test_corrupted_pending_candidate_is_not_accepted_after_resume(self):
        from graph_research.runtime.runner import run_tool
        from graph_research.runtime.storage import read_json, write_json
        def pause(name, *args, **kwargs):
            if name == 'graph_counterexample_verify':
                raise InterruptedError('Pause before verification')
            return run_tool(name, *args, **kwargs)
        parent, portal = self.create()
        with patch('graph_research.runtime.runner.run_tool', side_effect=pause):
            first = parent.submit(search_task())
        path = parent._service.task_dir(first['task_id'])/'session/session.json'
        document, _ = read_json(path)
        document['state']['counterexample_search']['pending_candidate'] = {'kind': 'complete', 'n': 4}
        write_json(path, document)
        interaction = first['interaction']
        event = portal.continue_task(first['task_id'], interaction['interaction_id'], first['revision'])
        reloaded, _ = self.create()
        result = reloaded.resume(first['task_id'], event['event_id'])
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['summary']['counterexample']['counterexample_verified'])
        self.assertEqual(result['budget']['used']['tool_calls'], 2)

    def test_model_budget_ends_search_without_an_extra_request(self):
        class Planner:
            def complete(self, messages):
                return {'strategy': 'random', 'reason': 'bounded restart'}
        parent, _ = self.create(model_factory=Planner, limits=SubagentLimits(max_model_calls=1))
        result = parent.submit(search_task(reference={'kind': 'complete', 'n': 4}, planner='model'))
        self.assertEqual(result['summary']['counterexample']['stop_reason'], 'model_budget_exhausted')
        self.assertEqual(result['budget']['used'], {'model_calls': 1, 'tool_calls': 1})

    def test_user_cancel_during_model_stop_is_respected_without_starting_tools(self):
        from graph_research.runtime.storage import read_json
        class Planner:
            def complete(model_self, messages):
                path = next(parent._service.directory.glob('tasks/*/task.json'))
                parent.cancel(read_json(path)[0]['task_id'])
                return {'strategy': 'stop', 'reason': 'The caller cancelled'}
        parent, _ = self.create(model_factory=Planner)
        result = parent.submit(search_task(planner='model'))
        self.assertEqual(result['status'], 'cancelled')
        self.assertEqual(result['budget']['used'], {'model_calls': 1, 'tool_calls': 0})
        self.assertFalse(result['summary']['counterexample']['counterexample_verified'])


if __name__ == '__main__':
    unittest.main()
