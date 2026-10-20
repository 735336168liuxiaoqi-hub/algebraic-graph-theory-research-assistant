"""Read-only result presentation, browser-safe HTML and verified previews."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from graph_research.assistant import OfflineToolSession,ResearchSession,verify_bundle
from graph_research.rendering.results import render_result_report,terminal_result,display_value


def document():
    return {'scope':'conversation','summary':{'successful_calls':1,'failed_calls':0,'verified_calls':1,'artifact_count':0,'record_status':'recorded','turn_count':1},
            'exported_at':'2026-10-16T12:00:00+00:00','bundle_id':'a'*32,'warnings':[],
            'turns':[{'number':1,'status':'tool_results_available','user_request':'计算P3','answer':'完成'}],
            'calculations':[{'id':'calc-0001','turn':1,'tool':'graph_spectrum','status':'success','tool_status':'native_tested',
                             'arguments':{'kind':'path','n':3},'evidence_status':'verified_execution','artifacts':[],
                             'result':{'rho':2**0.5,'matrix':[[0,1,0],[1,0,1],[0,1,0]],'spectrum':[-2**0.5,0,2**0.5]}}]}


class ResultDisplayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def session(self):return OfflineToolSession(self.root/'session',self.root/'packages')

    def test_metrics_matrix_spectrum_and_raw_precision_are_preserved(self):
        data=document();before=copy.deepcopy(data);html=render_result_report(data)
        self.assertIn('class="result-metrics"',html);self.assertIn('class="matrix"',html)
        self.assertIn('class="spectrum-chart"',html);self.assertIn('普通图数值谱',html)
        self.assertIn(repr(2**0.5),html);self.assertIn('下载原始结果',html)
        self.assertEqual(data,before)

    def test_display_values_keep_tiny_residuals_complex_numbers_and_large_integers(self):
        self.assertEqual(display_value(1e-14),'1e-14');self.assertEqual(display_value(False),'否')
        self.assertEqual(display_value(10**100),str(10**100))
        self.assertEqual(display_value({'real':1,'imag':-2}),'1 − 2i')
        item={'tool':'matrix_analysis','ok':True,'result':{'rank':2,'matrix':[[0,1],[1,0]]}}
        text=terminal_result(item);self.assertIn('数值矩阵分析',text);self.assertIn('2行 × 2列',text)
        self.assertNotIn('"matrix":',text)

    def test_large_data_previews_are_labelled_and_do_not_truncate_raw_record(self):
        data=document();data['calculations'][0]['result']={'matrix':[[i*100+j for j in range(15)] for i in range(14)],'spectrum':list(range(81))}
        html=render_result_report(data)
        self.assertIn('前 12 行 / 列',html);self.assertIn('前 80 项',html)
        self.assertIn('1314',html);self.assertIn('完整原始记录',html)

    def test_extreme_finite_values_do_not_create_invalid_svg_coordinates(self):
        data=document();data['calculations'][0]['result']['spectrum']=[-1e308,0,1e308]
        html=render_result_report(data)
        self.assertNotIn('cx="nan',html);self.assertNotIn('cx="inf',html)
        self.assertIn('class="spectrum-chart"',html)

    def test_untrusted_text_paths_and_template_tokens_stay_inert(self):
        data=document();attack='<script>alert("bad")</script><img src=x onerror=alert(1)>'
        data['turns'][0]['answer']=attack+' {{SUCCESS}}'
        data['calculations'][0]['result']['polynomial']=attack
        data['calculations'][0]['artifacts']=['javascript:alert(1)','../../secret','artifacts/a/outputs/plot.svg']
        html=render_result_report(data)
        self.assertNotIn('<script>alert',html);self.assertIn('&lt;script&gt;',html)
        self.assertNotIn('href="javascript:',html);self.assertNotIn('href="../../secret',html)
        self.assertIn('{{SUCCESS}}',html)
        script=re.search(r'<script id="report-ui">([\s\S]*?)</script>',html).group(1)
        digest=base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        self.assertIn("script-src 'sha256-"+digest+"'",html)
        self.assertEqual(html.count('<script '),1)

    def test_failed_experimental_and_analysis_only_records_are_not_mislabelled(self):
        data=document();data['calculations'][0].update(status='failed',error='bad input',tool_status='fixture_tested_experimental',evidence_status='failed_call')
        html=render_result_report(data)
        self.assertIn('此次调用未完成',html);self.assertIn('实验工具',html)
        data['calculations']=[]
        self.assertIn('本次只有分析记录',render_result_report(data))

    def test_view_is_a_verified_copy_with_current_style_and_no_reexecution(self):
        session=self.session();session.call_tool('graph_invariants',{'n':3})
        archive=Path(session.result_bundle['archive']);before=archive.read_bytes();state=(session.directory/'session.json').read_bytes()
        with patch('graph_research.assistant.offline.run_tool',side_effect=AssertionError('No recomputation')),patch('webbrowser.open',side_effect=AssertionError('Not requested')):
            view=session.view_results()
        html=Path(view['html']).read_text(encoding='utf-8');self.assertIn('result-card',html)
        metadata=json.loads((Path(view['directory'])/'view.json').read_text(encoding='utf-8'))
        self.assertEqual(metadata['calculations_reexecuted'],0)
        self.assertEqual(metadata['source_bundle_sha256'],session.result_bundle['sha256'])
        self.assertEqual(archive.read_bytes(),before);self.assertEqual((session.directory/'session.json').read_bytes(),state)
        self.assertTrue(verify_bundle(archive,session.result_bundle['sha256'])['ok'])
        self.assertEqual(json.loads((Path(view['directory'])/'results.json').read_text(encoding='utf-8'))['calculations'][0]['result']['diameter'],2)

    def test_bad_bundle_is_not_opened_and_empty_session_does_not_request_browser(self):
        session=self.session()
        with patch('webbrowser.open') as browser:
            with self.assertRaises(ValueError):session.view_results(open_browser=True)
            browser.assert_not_called()
        session.call_tool('graph_invariants',{'n':3})
        Path(session.result_bundle['archive']).write_bytes(b'corrupted')
        with patch('webbrowser.open') as browser:
            with self.assertRaises(ValueError):session.view_results(open_browser=True)
            browser.assert_not_called()

    def test_archived_html_is_regenerated_instead_of_executed(self):
        session=self.session();session.call_tool('graph_invariants',{'n':3})
        source=Path(session.result_bundle['archive']);changed=self.root/'changed.zip'
        with zipfile.ZipFile(source) as archive:
            content={name:archive.read(name) for name in archive.namelist()}
        malicious=b'<script>ARCHIVED_SCRIPT_MUST_NOT_RUN()</script>'
        content['report.html']=malicious;manifest=json.loads(content['manifest.json'])
        manifest['files']['report.html']={'bytes':len(malicious),'sha256':hashlib.sha256(malicious).hexdigest()}
        content['manifest.json']=json.dumps(manifest).encode()
        with zipfile.ZipFile(changed,'w') as archive:
            for name,raw in content.items():archive.writestr(name,raw)
        session.result_bundle={**session.result_bundle,'archive':str(changed),'sha256':hashlib.sha256(changed.read_bytes()).hexdigest()}
        view=session.view_results();html=Path(view['html']).read_text(encoding='utf-8')
        self.assertNotIn('ARCHIVED_SCRIPT_MUST_NOT_RUN',html);self.assertIn('图的基本信息',html)

    def test_view_cli_needs_no_model_credentials(self):
        session=self.session();session.call_tool('graph_invariants',{'n':3})
        result=subprocess.run([sys.executable,'-X','utf8','-m','graph_research','view',str(session.directory)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue(Path(json.loads(result.stdout)['html']).is_file())

    def test_console_view_actions_never_request_a_model_or_another_calculation(self):
        from graph_research.assistant.offline import run_offline_console
        from graph_research.assistant.onboarding import run_console
        session=self.session();session.call_tool('graph_invariants',{'n':3})
        with patch('graph_research.assistant.offline.run_tool',side_effect=AssertionError('No recomputation')),patch('webbrowser.open',return_value=True) as browser:
            values=iter(['v','0'])
            run_offline_console(session,input_fn=lambda _:next(values),print_fn=lambda _:None)
            browser.assert_called_once()
        with patch('webbrowser.open',return_value=True) as browser:
            values=iter(['/查看','/退出'])
            run_console(session,model_factory=lambda:(_ for _ in ()).throw(AssertionError('No model')),
                        input_fn=lambda _:next(values),print_fn=lambda _:None)
            browser.assert_called_once()
        self.assertEqual(len(session.state['observations']),1)


if __name__=='__main__':unittest.main()
