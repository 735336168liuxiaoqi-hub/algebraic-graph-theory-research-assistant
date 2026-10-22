"""Large-graph capacity and independent rational certificate regressions."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fractions import Fraction
from graph_research.workflows.counterexamples import graph_counterexample_round, graph_counterexample_verify
from graph_research.workflows.graph_spectral_certificate import adjacency_bounds, verify_adjacency_certificate
from graph_research.assistant.task_contract import validate_task, TaskProtocolError
from graph_research.assistant import create_subagent
from tests.test_counterexamples import search_task


class RationalGraphCertificateTests(unittest.TestCase):
    def test_hand_computed_path_three_bounds(self):
        bounds = adjacency_bounds(3, [[0, 1], [1, 2]], [1, 2, 1])
        self.assertEqual(bounds['rayleigh_lower'], '4/3')
        self.assertEqual(bounds['rho_interval'], ['4/3', '2'])
        certificate = {'vector': [1, 2, 1], **bounds}
        with patch('numpy.linalg.eigh', side_effect=AssertionError('Checker must not solve eigenvalues')):
            self.assertTrue(verify_adjacency_certificate(3, [[0, 1], [1, 2]], certificate)['passed'])

    def test_tampered_bounds_and_graph_identity_are_rejected(self):
        edges = [[0, 1], [1, 2]]
        certificate = {'vector': [1, 2, 1], **adjacency_bounds(3, edges, [1, 2, 1])}
        forged = copy.deepcopy(certificate)
        forged['rho_interval'][0] = '3/2'
        self.assertFalse(verify_adjacency_certificate(3, edges, forged)['passed'])
        self.assertFalse(verify_adjacency_certificate(3, [[0, 1], [0, 2]], certificate)['passed'])

    def test_nonpositive_nan_disconnected_and_duplicate_inputs_rejected(self):
        for vector in ([0, 1, 1], [1, float('nan'), 1], [1, -1, 1]):
            with self.subTest(vector=vector), self.assertRaises(ValueError):
                adjacency_bounds(3, [[0, 1], [1, 2]], vector)
        for edges in ([[0, 1]], [[0, 1], [1, 0]], [[0, 0], [1, 2]]):
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                adjacency_bounds(3, edges, [1, 1, 1])

    def test_regular_large_graph_has_exact_singleton_bounds(self):
        result = graph_counterexample_verify({'kind': 'cycle', 'n': 64}, {'kind': 'cycle', 'n': 64})
        self.assertEqual(result['status'], 'not_counterexample')
        self.assertEqual(result['reference_certificate']['rho_interval'], ['2', '2'])
        self.assertIsNone(result['isolation_digits'])

    def test_128_vertex_comparison_never_uses_characteristic_polynomials(self):
        with patch('graph_research.workflows.counterexamples._certificate', side_effect=AssertionError('No large resultant/root isolation')):
            result = graph_counterexample_verify({'kind': 'path', 'n': 128}, {'kind': 'star', 'n': 128})
        self.assertEqual(result['status'], 'counterexample_found')
        self.assertEqual(result['verification_method'], 'exact_rational_rayleigh_collatz')
        self.assertGreater(Fraction(result['difference_bounds'][0]), 0)
        witness = result['candidate_certificate']
        self.assertTrue(verify_adjacency_certificate(128, result['candidate']['edges'], witness)['passed'])

    def test_overlapping_valid_bounds_never_become_a_verified_witness(self):
        # Deliberately coarse but valid bounds for two nonidentical P16 labellings.
        reference = {'kind': 'path', 'n': 16}
        candidate = {'kind': 'edges', 'n': 16, 'edges': [[0, 2], [2, 1], [1, 3]]+[[i, i+1] for i in range(3, 15)]}
        def coarse(graph, steps):
            vector = [1]*len(graph)
            return {'vector': vector, **adjacency_bounds(len(graph), list(map(list, graph.edges)), vector)}
        with patch('graph_research.workflows.counterexamples._rational_certificate', side_effect=coarse), patch('graph_research.workflows.counterexamples._key', return_value='forced-cache-collision'):
            result = graph_counterexample_verify(reference, candidate)
        self.assertEqual(result['status'], 'candidate_unverified')
        self.assertFalse(result['counterexample_verified'])


class LargeSearchTests(unittest.TestCase):
    def test_order_and_edge_caps_are_enforced(self):
        for reference in ({'kind': 'path', 'n': 129}, {'kind': 'complete', 'n': 46}):
            with self.subTest(reference=reference), self.assertRaises(TaskProtocolError):
                validate_task(search_task(reference=reference))

    def test_large_round_uses_bounded_compact_visited_hashes(self):
        import hashlib
        seen = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(512)]
        arguments = {'reference': {'kind': 'path', 'n': 128}, 'incumbent': {'kind': 'path', 'n': 128},
                     'strategy': 'rewire', 'candidates': 2, 'seen': seen, 'seed': 41}
        self.assertLess(len(json.dumps(arguments)), 100000)
        result = graph_counterexample_round(**arguments)
        self.assertLessEqual(len(result['seen']), 512)
        self.assertTrue(all(len(key) == 64 for key in result['seen']))
        self.assertGreater(result['visited_cache_evictions'], 0)
        self.assertFalse(result['counterexample_verified'])

    def test_large_task_has_real_protected_search_and_rational_verification(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent, _ = create_subagent(root/'state', user_id='capacity', results_directory=root/'results')
            task = search_task(reference={'kind': 'path', 'n': 64}, candidates_per_round=4, max_rounds=3)
            result = parent.submit(task)
            self.assertEqual(result['status'], 'completed', result)
            study = result['summary']['counterexample']
            self.assertEqual(study['outcome'], 'counterexample_found')
            self.assertEqual(study['witness']['constraints_verified']['n'], 64)
            self.assertEqual(study['witness']['verification_method'], 'exact_rational_rayleigh_collatz')
            self.assertEqual(result['budget']['used']['model_calls'], 0)
            self.assertLessEqual(result['budget']['used']['tool_calls'], 6)


if __name__ == '__main__':
    unittest.main()
