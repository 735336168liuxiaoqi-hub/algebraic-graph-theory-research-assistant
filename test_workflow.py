import math
import os
import unittest

from assistant import NativeBackend, build_workflow, validate_task, verify_result


def task(edges=None):
    return {"graphs": [{"name": "H", "edges": edges or [[0, 1, 2]]}],
            "alphas": [0.0], "seed": 42}


def valid_result():
    return {"rho": 1.0, "perron_vector": [1 / 3] * 3, "relative_residual": 0.0,
            "min_degree": 1, "max_degree": 1,
            "collatz_lower": 1.0, "collatz_upper": 1.0,
            "order": 3, "size": 1, "rank": 3}


class WorkflowTests(unittest.TestCase):
    def test_rejects_disconnected_nonuniform_and_ambiguous_vertices(self):
        for edges in [[[0, 1], [2, 3]], [[0, 1], [1, 2, 3]],
                      [[1, 2]], [[0, 1], [1, 0]], [[0, True]]]:
            with self.subTest(edges=edges), self.assertRaises(ValueError):
                validate_task(task(edges))

    def test_rejects_nonfinite_and_out_of_domain_alpha(self):
        for alpha in [float("nan"), float("inf"), -0.1, 1.0, True]:
            data = task()
            data["alphas"] = [alpha]
            with self.subTest(alpha=alpha), self.assertRaises(ValueError):
                validate_task(data)

    def test_retries_failed_verification_and_keeps_provenance(self):
        seeds = []
        def backend(request):
            seeds.append(request["seed"])
            result = valid_result()
            if len(seeds) == 1:
                result["relative_residual"] = 0.1
            return result
        result = build_workflow(backend).invoke({"task": task()})
        self.assertEqual(seeds, [42, 43])
        self.assertEqual(result["status"], "complete")
        self.assertEqual(len(result["rows"][0]["attempts"]), 2)
        self.assertNotIn("error", result["rows"][0])

    def test_permanent_failure_stops_and_does_not_report_success(self):
        calls = []
        def backend(request):
            calls.append(request)
            raise RuntimeError("simulated solver failure")
        result = build_workflow(backend).invoke({"task": task()})
        self.assertEqual(len(calls), 2)
        self.assertEqual(result["status"], "needs_review")
        self.assertIn("暂不作完整比较", result["report"])

    def test_rejects_false_positive_eigen_result(self):
        result = valid_result()
        result["rho"] = 9
        self.assertIsNotNone(verify_result(result, 1e-5))

    def test_native_default_backend(self):
        result = build_workflow().invoke({"task": task()})
        self.assertEqual(result["rows"][0]["result"]["backend"], "native-python")


class NativeIntegrationTests(unittest.TestCase):
    def test_known_spectra_against_analytic_values(self):
        bridge = NativeBackend()
        cases = [
            ([[0, 1, 2]], 0.6, 1.0),
            ([[0, 1, 2], [0, 3, 4], [0, 5, 6]], 0.0, 3 ** (1 / 3)),
            ([[0, 1], [1, 2], [2, 0]], 0.4, 2.0),
            ([[0, 1], [0, 2], [0, 3]], 0.3,
             (0.3 * 4 + math.sqrt(0.3**2 * 2**2 + 4 * 0.7**2 * 3)) / 2),
        ]
        for edges, alpha, expected in cases:
            with self.subTest(edges=edges, alpha=alpha):
                result = bridge({"edges": edges, "alpha": alpha, "seed": 42})
                self.assertAlmostEqual(result["rho"], expected, places=8)
                self.assertIsNone(verify_result(result, 1e-5))


if __name__ == "__main__":
    unittest.main()
