"""Reviewed external probes with explicit oracles and reproducible failure cases."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import warnings
from unittest.mock import patch

import jsonschema
import numpy as np
import sympy as sp

from graph_research import Hypergraph,HyperStar,graphs
from graph_research.algebra.products import Quotient_Matrix
from graph_research.assistant import ResearchSession
from graph_research.assistant.offline import read_arguments
from graph_research.desktop.service import DesktopWorkspace
from graph_research.rendering.fonts import CJK_FAMILIES,available_families,label_font_families
from graph_research.runtime.storage import read_json,write_json,StateRecoveryError
from graph_research.tools import ToolRegistry

CASES=json.loads((Path(__file__).parent/'fixtures/external_probes_v018.json').read_text(encoding='utf-8'))


class ExternalProbeRegressions(unittest.TestCase):
    def test_integer_valued_float_partition_indices_match_integer_results(self):
        registry=ToolRegistry();expected={'quotient':[[1.,2.],[2.,1.]],'equitable':True}
        for blocks in CASES['quotient_valid_blocks']:
            with self.subTest(blocks=blocks):
                self.assertEqual(registry.call('quotient_matrix',{'matrix':[[1,2],[2,1]],'blocks':blocks}),expected)
                np.testing.assert_allclose(Quotient_Matrix([[1,2],[2,1]],blocks),expected['quotient'])
        np.testing.assert_allclose(Quotient_Matrix([[1,2],[2,1]],[[np.float64(0)],[np.int64(1)]],sym=True),expected['quotient'])

    def test_invalid_partitions_are_rejected_before_numpy_indexing(self):
        invalid=CASES['quotient_invalid_blocks']+[[[float('nan')],[1]],[[float('inf')],[1]],[[np.bool_(False)],[1]]]
        for blocks in invalid:
            with self.subTest(blocks=blocks),self.assertRaises(ValueError):Quotient_Matrix([[1,2],[2,1]],blocks)
        for matrix in (1,[1,2],[[1,2,3],[4,5,6]]):
            with self.subTest(matrix=matrix),self.assertRaises(ValueError):Quotient_Matrix(matrix,[[0],[1]])

    def test_registry_rejects_noninteger_json_indices_without_clipping_or_coercing(self):
        registry=ToolRegistry()
        for blocks in ([[0.5],[1]],[[True],[1]],[['0'],[1]]):
            with self.subTest(blocks=blocks),self.assertRaises(jsonschema.ValidationError):registry.call('quotient_matrix',{'matrix':[[1,2],[2,1]],'blocks':blocks})

    def test_corrupted_session_without_backup_reports_original_path_and_preserves_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);session=root/'session';session.mkdir();path=session/'session.json';path.write_bytes(b'{broken')
            with self.assertRaises(StateRecoveryError) as result:ResearchSession(session,root/'packages')
            error=result.exception;self.assertEqual(error.path,path)
            self.assertIn('没有可用备份',str(error));self.assertEqual(path.read_bytes(),b'{broken')
            self.assertFalse(path.with_name('session.json.previous').exists())

    def test_corrupt_primary_and_backup_preserve_both_and_valid_backup_still_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'session.json';backup=path.with_name('session.json.previous')
            path.write_text('{bad',encoding='utf-8');backup.write_text('{bad backup',encoding='utf-8')
            with self.assertRaises(StateRecoveryError):read_json(path,recover=True)
            self.assertEqual(backup.read_text(),'{bad backup')
            write_json(backup,{'valid':'record'})
            self.assertEqual(read_json(path,recover=True),({'valid':'record'},True))
            self.assertEqual(path.read_text(),'{bad')

    def test_desktop_restart_discloses_unrecoverable_previous_session(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace=DesktopWorkspace(directory);old=workspace.session.directory;old.mkdir(exist_ok=True);(old/'session.json').write_text('{broken',encoding='utf-8')
            reopened=DesktopWorkspace(directory)
            self.assertIn('session.json',reopened.recovery_warning)
            self.assertNotEqual(reopened.session.directory,old);self.assertEqual((old/'session.json').read_text(),'{broken')

    def test_local_font_fallback_selects_installed_fonts_without_mutating_global_style(self):
        with patch('graph_research.rendering.fonts.available_families',return_value={'Microsoft YaHei','DejaVu Sans'}):
            self.assertEqual(label_font_families('甲乙'),['Microsoft YaHei','DejaVu Sans'])
            self.assertIsNone(label_font_families('A_1'))

    def test_chinese_plot_exports_without_missing_glyphs_when_a_cjk_font_is_installed(self):
        if not set(CJK_FAMILIES)&available_families():self.skipTest('This host has no installed CJK font; fallback selection is tested separately')
        import matplotlib
        before=list(matplotlib.rcParams['font.family'])
        with tempfile.TemporaryDirectory() as directory,warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            h=Hypergraph([['甲','乙']],vertices=['甲','乙','孤立点'])
            h.save_plot(Path(directory)/'labels.png',legend=True,title='中文结构图')
            h.save_plot(Path(directory)/'labels.svg')
            missing=[str(warning.message) for warning in captured if 'Glyph' in str(warning.message) and 'missing' in str(warning.message)]
            self.assertFalse(missing,missing)
        self.assertEqual(list(matplotlib.rcParams['font.family']),before)

    def test_known_graph_spectra_and_binary_hypergraphs_agree(self):
        registry=ToolRegistry()
        for item in CASES['known_graph_spectra']:
            result=registry.call('graph_spectrum',{'kind':item['kind'],'n':item['n']})
            self.assertAlmostEqual(result['rho'],item['expected_rho'],places=10)
        h=Hypergraph([[0,1],[1,2],[2,3],[3,4]])
        for alpha in (0.,0.3,0.9):
            self.assertAlmostEqual(h.alpha_spectrum(alpha)['rho'],graphs.graph_spectrum('path',5,matrix='alpha',alpha=alpha)['rho'],places=9)

    def test_rectangular_incidence_row_sums_do_not_imply_bipartite_perron_root_one(self):
        h=HyperStar(3,4);b=h.weighted_incidence_from_result(h.alpha_spectrum(.3));n,m=b.shape
        self.assertNotEqual(n,m);np.testing.assert_allclose(b.sum(axis=1),1,atol=1e-10)
        adjacency=np.block([[np.zeros((n,n)),b],[b.T,np.zeros((m,m))]])
        rho=float(np.linalg.eigvalsh(adjacency).max());sigma=float(np.linalg.svd(b,compute_uv=False)[0])
        self.assertAlmostEqual(rho,sigma,places=10);self.assertGreater(abs(rho-1),.1)

    def test_single_hyperedge_exact_polynomial_uses_factorization_not_np_roots(self):
        polynomial=Hypergraph([[0,1,2]]).characteristic_polynomial();x=polynomial.gen
        self.assertEqual(sp.expand(polynomial.as_expr()-x**3*(x**3-1)**3),0)

    def test_fixed_malformed_json_cases_are_rejected_as_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'arguments.json'
            for text in CASES['malformed_json']:
                path.write_text(text,encoding='utf-8')
                with self.subTest(text=text),self.assertRaises(ValueError):read_arguments(path)

    @unittest.skipUnless(os.name=='nt','The protected calculation backend is Windows only')
    def test_protected_worker_supports_float_indices_and_chinese_plot_labels(self):
        from graph_research.runtime.runner import run_tool
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            result=run_tool('quotient_matrix',{'matrix':[[1,2],[2,1]],'blocks':[[0.0],[1.0]]},root/'packages',directory=root/'tasks')
            self.assertTrue(result['equitable'])
            output=run_tool('hypergraph_plot',{'edges':[['甲','乙']]},root/'packages',directory=root/'tasks')
            self.assertTrue(Path(output['files']['png']).is_file())
            if set(CJK_FAMILIES)&available_families():
                for log in (root/'tasks').glob('task_*/stderr.log'):self.assertNotIn('missing from font',log.read_text(encoding='utf-8'))


if __name__=='__main__':unittest.main()
