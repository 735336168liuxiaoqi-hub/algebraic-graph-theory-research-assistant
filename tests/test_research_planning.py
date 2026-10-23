"""Research plans and exact finite experiments, without paid model requests."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from graph_research.workflows.graph_properties import graph_property_scan
from graph_research.workflows.property_certificate import graph_property_verify
from graph_research.assistant import create_subagent, SubagentLimits
from graph_research.assistant.task_contract import TaskProtocolError, validate_task


class Scripted:
    def __init__(self, *decisions):
        self.decisions = list(decisions)
        self.contexts = []

    def complete(self, messages):
        self.contexts.append(json.loads(messages[1]['content']))
        if not self.decisions:
            raise AssertionError('Unexpected model call')
        return copy.deepcopy(self.decisions.pop(0))


def plan(*, finite=True, verify=True, arguments=None):
    spec = {'title': '有限图性质实验', 'research': {'question': '单谱性、可控性和Wronskian顶点的关系',
            'scope': {'matrix': 'A', 'source': 'provided'}, 'assumptions': ['无向无权简单图，全一输入'],
            'expected_outputs': ['精确性质及证据'], 'validation': '独立Fraction实现复核选定样例',
            'completion': 'finite_enumeration' if finite else 'fixed_computation'},
            'steps': [{'id': 'scan', 'description': '扫描输入集合', 'tool': 'graph_property_scan',
                       'arguments': arguments or {'source': 'provided', 'graphs': [{'kind': 'path', 'n': 3}]}}]}
    if verify:
        spec['steps'].append({'id': 'verify', 'description': '独立复核样例', 'tool': 'graph_property_verify', 'arguments': {},
                             'bindings': {'graph': {'step': 'scan', 'path': ['rows', 0, 'graph']}, 'certificate': {'step': 'scan', 'path': ['rows', 0, 'certificate']}}})
    return {'action': 'plan', 'plan': spec}


def task(**options):
    return {'version': 1, 'request_id': 'research-test', 'objective': '研究单谱图的可控性',
            'execution': {'mode': 'research', 'research': options}, 'constraints': {'allow_extensions': False}}


FINAL = {'action': 'final', 'answer': '报告有限范围结果，不宣称一般定理。'}


class PropertyTests(unittest.TestCase):
    def test_property_input_examples_roundtrip_without_rational_type_ambiguity(self):
        from graph_research.tools import ToolRegistry
        from graph_research.tools.input_guides import input_guide
        from graph_research.assistant.offline import parse_parameter
        registry=ToolRegistry()
        for name in ('graph_property_scan','graph_property_verify'):
            definition=registry.describe(name)
            for field in input_guide(definition)['fields']:
                with self.subTest(tool=name,parameter=field['name']):
                    self.assertIsNotNone(field['input_example'])
                    self.assertEqual(parse_parameter(field['input_example'],definition['parameters']['properties'][field['name']]),field['example'])
    def test_paper_order_seven_complete_counts(self):
        totals = {}
        arguments = {'orders': [7], 'filters': {'connected': True}, 'batch_size': 128}
        while True:
            page = graph_property_scan(**arguments)
            for key, value in page['counts_by_order']['7'].items():
                totals[key] = totals.get(key, 0)+value
            if page['finished']:
                break
            arguments.update(cursor=page['cursor_next'], source_id=page['source_id'])
        self.assertEqual([totals[k] for k in ('eligible', 'simple_spectrum', 'controllable', 'has_wronskian_vertex', 'controllable_with_wronskian')], [853, 539, 85, 414, 85])

    def test_path_three_is_simple_spectrum_but_not_all_ones_controllable(self):
        result = graph_property_scan(source='provided', graphs=[{'kind': 'path', 'n': 3}])
        row = result['rows'][0]
        self.assertTrue(row['properties']['simple_spectrum'])
        self.assertFalse(row['properties']['controllable'])
        self.assertEqual(row['certificate']['walk_rank'], 2)
        self.assertEqual(row['certificate']['characteristic_coefficients'], ['1', '0', '-2', '0'])
        check = graph_property_verify(row['graph'], row['certificate'])
        self.assertTrue(check['passed'])
        self.assertEqual(check['wronskian_vertices'], [0, 2])
        self.assertFalse(result['nonisomorphic'])

    def test_reproduce_paper_order_six_counts_using_contiguous_pages(self):
        a = graph_property_scan(orders=[6], filters={'connected': True}, batch_size=128)
        b = graph_property_scan(orders=[6], filters={'connected': True}, batch_size=128, cursor=a['cursor_next'], source_id=a['source_id'])
        totals = {k: a['counts_by_order']['6'][k]+b['counts_by_order']['6'][k] for k in a['counts_by_order']['6']}
        self.assertEqual([totals[k] for k in ('eligible', 'simple_spectrum', 'controllable', 'has_wronskian_vertex', 'controllable_with_wronskian')], [112, 54, 8, 37, 8])
        self.assertTrue(b['finished'])
        controlled = next(row for row in a['rows']+b['rows'] if row['properties']['controllable'])
        self.assertTrue(graph_property_verify(controlled['graph'], controlled['certificate'])['passed'])

    def test_verifier_is_independent_of_sympy_and_rejects_tampering(self):
        row = graph_property_scan(source='provided', graphs=[{'kind': 'path', 'n': 3}])['rows'][0]
        with patch('sympy.matrices.matrixbase.MatrixBase.charpoly', side_effect=AssertionError('No primary algorithm')):
            self.assertTrue(graph_property_verify(row['graph'], row['certificate'])['passed'])
        for field, value in [('walk_rank', 3), ('scope_sha256', '0'*64), ('properties', {})]:
            certificate = copy.deepcopy(row['certificate']);certificate[field] = value
            self.assertFalse(graph_property_verify(row['graph'], certificate)['passed'])

    def test_laplacian_minor_and_rational_alpha_follow_matrix_definition(self):
        row = graph_property_scan(source='provided', graphs=[{'kind': 'path', 'n': 3}], matrix='L')['rows'][0]
        self.assertEqual(row['certificate']['walk_rank'], 1)
        self.assertEqual(row['certificate']['vertex_gcds'], [['1'], ['1', '-1'], ['1']])
        self.assertTrue(graph_property_verify(row['graph'], row['certificate'], matrix='L')['passed'])
        row = graph_property_scan(source='provided', graphs=[{'kind': 'path', 'n': 3}], matrix='alpha', alpha='1/3')['rows'][0]
        self.assertTrue(graph_property_verify(row['graph'], row['certificate'], matrix='alpha', alpha='1/3')['passed'])
        self.assertFalse(graph_property_verify(row['graph'], row['certificate'])['passed'])

    def test_pagination_must_preserve_scope_and_not_claim_complete_early(self):
        first = graph_property_scan(orders=[6], batch_size=1)
        self.assertFalse(first['finished'])
        with self.assertRaises(ValueError):
            graph_property_scan(orders=[6], cursor=1)
        with self.assertRaises(ValueError):
            graph_property_scan(orders=[6], filters={'connected': True}, cursor=1, source_id=first['source_id'])
        with self.assertRaises(ValueError):
            graph_property_scan(orders=[8])

    def test_nonisomorphic_trees_and_bad_or_oversized_graphs(self):
        result = graph_property_scan(source='trees', orders=[5], filters={'connected': True})
        self.assertTrue(result['nonisomorphic']);self.assertTrue(result['finished'])
        self.assertEqual(result['counts_by_order']['5']['eligible'], 3)
        for graph in ({'kind': 'path', 'n': 13}, {'kind': 'path', 'n': True}, {'kind': 'edges', 'n': 2, 'edges': [[0, 1], [1, 0]]}):
            with self.subTest(graph=graph), self.assertRaises(ValueError):
                graph_property_scan(source='provided', graphs=[graph])


class ResearchAgentTests(unittest.TestCase):
    def test_failed_step_feedback_allows_bounded_replanning_with_records(self):
        failed = plan(finite=False, verify=False)
        failed['plan']['steps'] = [{'id': 'bad', 'description': '尝试不连通图的距离矩阵', 'tool': 'graph_spectrum', 'arguments': {'kind': 'empty', 'n': 3, 'matrix': 'D'}}]
        model = Scripted(failed, plan(), FINAL)
        parent, _ = self.create(model)
        result = parent.submit(task(max_plans=2))
        self.assertEqual(result['summary']['research']['plan_count'], 2, result)
        self.assertEqual(result['summary']['research']['plans'][0]['status'], 'failed')
        self.assertEqual(result['summary']['research']['plans'][1]['status'], 'completed')
        self.assertTrue(result['summary']['research']['independent_witnesses'])
        self.assertFalse(model.contexts[1]['observations'][0]['ok'])
        self.assertEqual(result['budget']['used']['tool_calls'], 3)

    def test_replanning_limit_cannot_be_expanded_by_model(self):
        model = Scripted(plan(verify=False), plan(), FINAL)
        parent, _ = self.create(model)
        result = parent.submit(task(max_plans=1))
        self.assertEqual(result['summary']['research']['plan_count'], 1)
        self.assertEqual(result['budget']['used']['tool_calls'], 1)
        self.assertEqual(result['status'], 'partial')

    def test_user_can_revise_a_reviewed_plan_and_then_accept_the_new_scope(self):
        model = Scripted(plan(), plan(verify=False), FINAL)
        parent, portal = self.create(model)
        waiting = parent.submit(task(require_review=True))
        original = waiting['interaction']['plan']['scope_sha256']
        event = portal.answer(waiting['task_id'], waiting['interaction']['interaction_id'], waiting['revision'], '暂不复核，只计算性质')
        revised = parent.resume(waiting['task_id'], event['event_id'])
        self.assertEqual(revised['status'], 'waiting_for_user', revised)
        self.assertNotEqual(revised['interaction']['plan']['scope_sha256'], original)
        self.assertEqual(revised['budget']['used']['tool_calls'], 0)
        event = portal.answer(revised['task_id'], revised['interaction']['interaction_id'], revised['revision'], '确认')
        result = parent.resume(revised['task_id'], event['event_id'])
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(result['summary']['research']['plans'][0]['status'], 'superseded')
        self.assertEqual(result['budget']['used']['tool_calls'], 1)

    def test_cancellation_requires_trusted_resume_and_preserves_tool_debits(self):
        from graph_research.runtime.runner import run_tool
        def cancel_verify(name, *args, **kwargs):
            if name == 'graph_property_verify':
                raise InterruptedError('Injected cancellation')
            return run_tool(name, *args, **kwargs)
        model = Scripted(plan(), FINAL)
        parent, portal = self.create(model)
        with patch('graph_research.runtime.runner.run_tool', side_effect=cancel_verify):
            first = parent.submit(task())
        self.assertIn(first['status'], ('cancelled', 'interrupted'))
        self.assertEqual(first['budget']['used']['tool_calls'], 2)
        event = portal.continue_task(first['task_id'], first['interaction']['interaction_id'], first['revision'])
        result = parent.resume(first['task_id'], event['event_id'])
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(result['budget']['used']['tool_calls'], 3)
        self.assertEqual(sum(r['tool']=='graph_property_scan' for r in result['results']), 1)

    def test_standalone_new_requests_do_not_mix_previous_enumeration_counts(self):
        from graph_research.assistant import ResearchSession
        session = ResearchSession(self.root/'standalone')
        session.set_research_mode(True)
        model = Scripted(plan(verify=False), FINAL, plan(verify=False), FINAL)
        first = session.ask('第一次实验', model)
        from graph_research.assistant.research_protocol import summary
        self.assertEqual(summary(first)['families'][0]['visited_positions'], 1)
        result = session.reply('开始第二个独立实验', model)
        self.assertEqual(summary(result)['families'][0]['visited_positions'], 1)
        self.assertEqual(summary(result)['plan_count'], 1)
        with self.assertRaises(ValueError):
            session.set_research_mode(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def create(self, model, **kwargs):
        return create_subagent(self.root, user_id='research-test', model_factory=lambda: model, **kwargs)

    def test_model_plans_executes_verifies_and_exports_without_paid_api(self):
        model = Scripted(plan(), FINAL)
        parent, _ = self.create(model)
        result = parent.submit(task(verification='independent'))
        self.assertEqual(result['status'], 'completed', result)
        research = result['summary']['research']
        self.assertEqual(research['outcome'], 'completed')
        self.assertTrue(research['enumeration_complete']);self.assertFalse(research['general_theorem_proved'])
        self.assertEqual(result['budget']['used'], {'model_calls': 2, 'tool_calls': 2})
        self.assertTrue(model.contexts[1]['research_progress']['enumeration_complete'])
        with zipfile.ZipFile(result['artifacts'][0]['path']) as archive:
            self.assertEqual(json.loads(archive.read('research-summary.json'))['outcome'], 'completed')
            self.assertIn('research-plans.json', archive.namelist())
            self.assertIn('research-counts.csv', archive.namelist())

    def test_fixed_scope_cannot_be_relabelled_or_changed_by_model(self):
        fixed={'source':'provided','graphs':[{'kind':'path','n':3}],'matrix':'A'}
        decision=plan();decision['plan']['research']['scope']=fixed
        decision['plan']['steps'][0]['arguments']={'source':'provided','graphs':[{'kind':'star','n':4}]}
        parent,_=self.create(Scripted(decision,FINAL))
        result=parent.submit(task(scope=fixed))
        self.assertEqual(result['status'],'blocked',result)
        self.assertEqual(result['budget']['used']['tool_calls'],0)

    def test_mcp_research_rejects_model_calls_without_explicit_host_configuration(self):
        from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root/'mcp'),'research'))
        with self.assertRaises(TaskProtocolError):runtime.submit(task())
        self.assertEqual(list((self.root/'mcp').glob('users/*/tasks/*/task.json')),[])

    def test_model_cannot_skip_planning(self):
        parent, _ = self.create(Scripted({'action': 'call', 'tool': 'graph_invariants', 'arguments': {'n': 3}}))
        result = parent.submit(task())
        self.assertEqual(result['status'], 'blocked', result)
        self.assertEqual(result['budget']['used']['tool_calls'], 0)

    def test_review_pause_and_trusted_acceptance_preserve_plan_and_budget(self):
        model = Scripted(plan(), FINAL)
        parent, portal = self.create(model)
        waiting = parent.submit(task(require_review=True))
        self.assertEqual(waiting['status'], 'waiting_for_user', waiting)
        self.assertEqual(waiting['budget']['used']['tool_calls'], 0)
        self.assertEqual(waiting['interaction']['plan']['estimate']['tool_attempts'], 2)
        event = portal.answer(waiting['task_id'], waiting['interaction']['interaction_id'], waiting['revision'], '确认')
        result = parent.resume(waiting['task_id'], event['event_id'])
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(result['summary']['research']['plan_count'], 1)
        self.assertEqual(parent.resume(waiting['task_id'], event['event_id'])['budget']['used'], result['budget']['used'])
        self.assertEqual(parent.submit(task(require_review=True))['budget']['used'], result['budget']['used'])

    def test_clarification_is_propagated_before_planning(self):
        model = Scripted({'action': 'clarify', 'questions': ['使用邻接矩阵还是其他矩阵？']}, plan(), FINAL)
        parent, portal = self.create(model)
        waiting = parent.submit(task())
        self.assertEqual(waiting['status'], 'waiting_for_user')
        self.assertEqual(waiting['budget']['used']['tool_calls'], 0)
        event = portal.answer(waiting['task_id'], waiting['interaction']['interaction_id'], waiting['revision'], '使用邻接矩阵A')
        result = parent.resume(waiting['task_id'], event['event_id'])
        self.assertEqual(result['status'], 'completed', result)
        self.assertIn('使用邻接矩阵A', json.dumps(model.contexts[1], ensure_ascii=False))

    def test_partial_coverage_cannot_be_declared_a_complete_enumeration(self):
        model = Scripted(plan(verify=False, arguments={'orders': [6], 'batch_size': 1}), FINAL)
        parent, _ = self.create(model)
        result = parent.submit(task())
        self.assertEqual(result['status'], 'partial', result)
        self.assertFalse(result['summary']['research']['enumeration_complete'])

    def test_independent_verification_requirement_is_not_satisfied_by_scan(self):
        parent, _ = self.create(Scripted(plan(verify=False), FINAL))
        result = parent.submit(task(verification='independent'))
        self.assertEqual(result['status'], 'partial')
        self.assertFalse(result['summary']['research']['verification_requirement_met'])

    def test_general_existing_tools_also_use_the_research_plan_protocol(self):
        decision = plan(finite=False, verify=False)
        decision['plan']['steps'] = [{'id': 'structure', 'description': '分析路径图结构', 'tool': 'graph_invariants', 'arguments': {'kind': 'path', 'n': 5}}]
        parent, _ = self.create(Scripted(decision, FINAL))
        result = parent.submit(task())
        self.assertEqual(result['status'], 'completed', result)
        self.assertEqual(result['results'][0]['data']['size'], 4)
        self.assertFalse(result['summary']['research']['enumeration_complete'])

    def test_missing_metadata_and_over_budget_plans_do_not_execute(self):
        malformed = plan();del malformed['plan']['research']
        parent, _ = self.create(Scripted(malformed, FINAL))
        self.assertEqual(parent.submit(task())['budget']['used']['tool_calls'], 0)
        parent, _ = create_subagent(self.root/'budget', user_id='research-test', limits=SubagentLimits(max_tool_calls=1), model_factory=lambda: Scripted(plan(), FINAL))
        result = parent.submit(task())
        self.assertEqual(result['budget']['used']['tool_calls'], 0)

    def test_mode_mixing_and_disabled_model_are_rejected(self):
        mixed = task();mixed['execution']['steps'] = [{'id': 'x', 'tool': 'graph_invariants', 'arguments': {}}]
        with self.assertRaises(TaskProtocolError):
            validate_task(mixed)
        parent, _ = self.create(Scripted(), limits=SubagentLimits(max_model_calls=0))
        with self.assertRaises(TaskProtocolError):
            parent.submit(task())
