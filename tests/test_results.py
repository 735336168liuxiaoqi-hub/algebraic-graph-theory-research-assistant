"""Multi-request snapshots, real receipts, artifact tampering and portable ZIPs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from graph_research.assistant import ResearchSession,verify_bundle
from graph_research.runtime.evidence import file_hash
from graph_research.runtime.integrity import CORE,verify
from graph_research.runtime.storage import write_json
from tests.test_feature_workflow import ScriptedModel


def model_for(tool='graph_invariants',arguments=None,answer='计算完成'):
    return ScriptedModel([{'action':'call','tool':tool,'arguments':arguments or {'kind':'path','n':3}},
                          {'action':'final','answer':answer}])


def data_from(path):
    with zipfile.ZipFile(path) as bundle:return json.loads(bundle.read('results.json'))


class ResultBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)

    def session(self,auto=False,**kwargs):
        return ResearchSession(self.root/'session',self.root/'packages',auto_export=auto,**kwargs)

    def test_multiple_calculations_and_requests_export_all_or_one_turn(self):
        session=self.session()
        first=ScriptedModel([{'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':3}},
                            {'action':'call','tool':'graph_spectrum','arguments':{'kind':'path','n':3}},
                            {'action':'final','answer':'FIRST_ANSWER：P3直径为2，谱半径为sqrt(2)。'}])
        session.ask('FIRST_REQUEST：计算P3结构和谱',first)
        session.reply('SECOND_REQUEST：导出三顶点路图的TikZ',model_for('graph_tikz',{'edges':[[0,1],[1,2]]},'SECOND_ANSWER：TikZ已生成。'))
        whole=session.export_results(self.root/'all.zip')
        data=data_from(whole['archive'])
        self.assertEqual(data['summary'],{'record_status':'recorded','turn_count':2,'successful_calls':3,'failed_calls':0,'verified_calls':3,'artifact_count':2})
        self.assertEqual([c['turn'] for c in data['calculations']],[1,1,2])
        self.assertIn('FIRST_ANSWER',data['turns'][0]['answer']);self.assertIn('SECOND_ANSWER',data['turns'][1]['answer'])
        self.assertEqual(data['calculations'][0]['result']['diameter'],2)
        self.assertAlmostEqual(data['calculations'][1]['result']['rho'],2**0.5)
        self.assertEqual(data['calculations'][2]['result']['order'],3)
        with zipfile.ZipFile(whole['archive']) as bundle:
            artifact=data['calculations'][2]['result']['files']['standalone']
            self.assertTrue(artifact.startswith('artifacts/'))
            self.assertIn(artifact,bundle.namelist());self.assertIn(b'tikzpicture',bundle.read(artifact))
            self.assertIn('calls/calc-0001/arguments.json',bundle.namelist())
            self.assertIn('calls/calc-0001/execution.json',bundle.namelist())
            self.assertNotIn(str(self.root).encode(),bundle.read('results.json'))
        selected=session.export_results(self.root/'first.zip',turn=1)
        one=data_from(selected['archive'])
        self.assertEqual(one['summary']['successful_calls'],2);self.assertEqual(one['summary']['artifact_count'],0)
        self.assertEqual([t['number'] for t in one['turns']],[1])
        self.assertNotIn('SECOND_REQUEST',json.dumps(one,ensure_ascii=False))
        self.assertTrue(verify_bundle(whole['archive'],whole['sha256'])['ok'])

    def test_automatic_snapshots_preserve_previous_answers_and_do_not_mislabel_old_success(self):
        session=self.session(auto=True)
        session.ask('第一轮',model_for(answer='第一轮回答'))
        first=dict(session.result_bundle)
        self.assertIsNotNone(first);self.assertIsNone(session.export_error)
        session.reply('第二轮无可用工具',model_for('no_such_tool',{},'本轮工具失败。'))
        self.assertEqual(session.state['status'],'model_analysis_only')
        latest=session.result_bundle;data=data_from(latest['archive'])
        self.assertNotEqual(first['archive'],latest['archive'])
        self.assertEqual(file_hash(first['archive']),first['sha256'])
        self.assertEqual(data['summary']['record_status'],'partial')
        self.assertEqual(data['summary']['failed_calls'],1)
        self.assertEqual(data['turns'][0]['answer'],'第一轮回答')
        self.assertTrue(Path(latest['sha256_file']).is_file())

    def test_interrupted_resume_keeps_same_turn_and_never_duplicates_successful_calls(self):
        session=self.session(auto=True)
        session.ask('先计算，再整理',ScriptedModel([{'action':'call','tool':'graph_invariants','arguments':{'kind':'path','n':3}}]))
        self.assertEqual(session.state['status'],'execution_error')
        self.assertEqual(data_from(session.result_bundle['archive'])['summary']['record_status'],'partial')
        reloaded=ResearchSession(session.directory)
        reloaded.continue_run(ScriptedModel([{'action':'final','answer':'直径为2。'}]))
        data=data_from(reloaded.result_bundle['archive'])
        self.assertEqual(len(reloaded.turns),1);self.assertEqual(reloaded.turns[0]['attempts'],2)
        self.assertEqual(len(data['calculations']),1);self.assertEqual(data['summary']['verified_calls'],1)

    def test_missing_attachment_blocks_strict_export_and_explicit_partial_is_labelled(self):
        session=self.session()
        session.ask('导出图',model_for('graph_tikz',{'edges':[[0,1]]}))
        self.assertTrue(session.state['observations'][0].get('ok'),session.state['observations'][0])
        artifact=Path(session.state['observations'][0]['result']['files']['standalone']);artifact.unlink()
        with self.assertRaises(OSError):session.export_results(self.root/'strict.zip')
        self.assertFalse((self.root/'strict.zip').exists())
        result=session.export_results(self.root/'partial.zip',allow_incomplete=True)
        data=data_from(result['archive'])
        self.assertEqual(data['summary']['record_status'],'partial');self.assertEqual(data['summary']['artifact_count'],1)
        self.assertEqual(data['calculations'][0]['evidence_status'],'incomplete_evidence')
        self.assertTrue(data['warnings']);self.assertTrue(verify_bundle(result['archive'])['ok'])

    def test_altered_artifact_and_forged_result_are_detected_before_publication(self):
        session=self.session();session.ask('导出图',model_for('graph_tikz',{'edges':[[0,1]]}))
        item=session.state['observations'][0]
        artifact=Path(item['result']['files']['standalone']);original=artifact.read_bytes();artifact.write_bytes(original+b'changed')
        with self.assertRaises(ValueError):session.export_results(self.root/'tampered.zip')
        self.assertFalse((self.root/'tampered.zip').exists())
        artifact.write_bytes(original);item['result']['order']=999
        with self.assertRaisesRegex(ValueError,'differs'):session.export_results(self.root/'forged.zip')
        self.assertFalse((self.root/'forged.zip').exists())

    def test_attachments_cannot_read_outside_session_or_follow_forged_inventory(self):
        session=self.session();session.ask('图计算',model_for())
        item=session.state['observations'][0];original=dict(item['execution'])
        outside=self.root/'private';outside.mkdir();(outside/'secret').write_text('PRIVATE_CONTENT',encoding='utf-8')
        item['execution']['directory']=str(outside)
        with self.assertRaises(PermissionError):session.export_results(self.root/'leak.zip')
        self.assertFalse((self.root/'leak.zip').exists())
        item['execution']=original
        receipt_file=Path(original['directory'])/'execution.json'
        receipt=json.loads(receipt_file.read_text());receipt['artifacts']=[{'path':'../../secret','bytes':1,'sha256':'0'*64}]
        receipt_file.write_text(json.dumps(receipt),encoding='utf-8');item['execution']['receipt_sha256']=file_hash(receipt_file)
        with self.assertRaises(ValueError):session.export_results(self.root/'escape.zip')
        self.assertFalse((self.root/'escape.zip').exists())

    def test_export_failure_keeps_calculations_and_does_not_offer_stale_latest_zip(self):
        session=self.session(auto=True);session.ask('图代码',model_for('graph_tikz',{'edges':[[0,1]]}))
        first=dict(session.result_bundle)
        Path(session.state['observations'][0]['result']['files']['standalone']).write_text('changed',encoding='utf-8')
        session.reply('仅分析刚才的结果',ScriptedModel([{'action':'final','answer':'后续分析已记录。'}]))
        self.assertEqual(session.state['status'],'model_analysis_only')
        self.assertIsNone(session.result_bundle);self.assertIsNotNone(session.export_error)
        self.assertEqual(len(session.state['observations']),1)
        self.assertTrue(verify_bundle(first['archive'],first['sha256'])['ok'])
        loaded=ResearchSession(session.directory)
        self.assertIsNone(loaded.result_bundle);self.assertIsNotNone(loaded.export_error)

    def test_no_profile_keys_or_host_configuration_is_packaged_and_html_is_escaped(self):
        session=self.session(user_id='PRIVATE_USER_ID',memory_directory=self.root/'private-memory')
        session.memory.set_preference('PRIVATE_USER_ID','language','en')
        model=ScriptedModel([{'action':'final','answer':'<script>alert("ANSWER")</script>'}])
        with patch.dict(os.environ,{'RESEARCH_API_KEY':'PRIVATE_API_KEY'}):session.ask('<script>alert("QUESTION")</script>',model)
        result=session.export_results(self.root/'safe.zip')
        self.assertEqual(len(model.contexts),1)
        with zipfile.ZipFile(result['archive']) as bundle:
            contents=b'\n'.join(bundle.read(name) for name in bundle.namelist())
            self.assertNotIn(b'PRIVATE_API_KEY',contents);self.assertNotIn(b'PRIVATE_USER_ID',contents)
            self.assertNotIn(b'private-memory',contents)
            html=bundle.read('report.html').decode()
            self.assertNotIn('<script>',html);self.assertIn('&lt;script&gt;',html)
            self.assertNotIn('session.json',bundle.namelist());self.assertNotIn('approval.json',bundle.namelist())

    def test_legacy_history_is_not_falsely_split_or_given_new_execution_provenance(self):
        directory=self.root/'session';directory.mkdir()
        write_json(directory/'session.json',{'version':2,'tool_directory':str(self.root/'packages'),'state':{
            'question':'旧问题','conversation':[{'role':'user','content':'旧问题1'},{'role':'user','content':'旧问题2'}],
            'observations':[{'tool':'graph_invariants','arguments':{'kind':'path','n':3},'ok':True,'result':{'diameter':2},'tool_status':'native_tested'}],
            'status':'tool_results_available','answer':'旧回答'}})
        session=ResearchSession(directory,auto_export=False)
        result=session.export_results(self.root/'legacy.zip');data=data_from(result['archive'])
        self.assertEqual(len(data['turns']),1);self.assertEqual(data['turns'][0]['origin'],'legacy_unsegmented')
        self.assertEqual([m['content'] for m in data['turns'][0]['legacy_conversation']],['旧问题1','旧问题2'])
        self.assertEqual(data['calculations'][0]['evidence_status'],'legacy_record')
        self.assertEqual(data['summary']['verified_calls'],0);self.assertTrue(data['warnings'])
        session.reply('新的问题',ScriptedModel([{'action':'final','answer':'新的回答'}]))
        self.assertEqual(len(session.turns),2)

    def test_zip_tampering_pinned_hash_and_path_attacks_are_rejected_without_extraction(self):
        session=self.session();session.ask('记录',ScriptedModel([{'action':'final','answer':'仅分析'}]))
        result=session.export_results(self.root/'valid.zip')
        with self.assertRaises(ValueError):verify_bundle(result['archive'],'0'*64)
        changed=self.root/'changed.zip'
        with zipfile.ZipFile(result['archive']) as original,zipfile.ZipFile(changed,'w') as target:
            for name in original.namelist():target.writestr(name,original.read(name)+(b' ' if name=='results.json' else b''))
        with self.assertRaises(ValueError):verify_bundle(changed)
        bad=self.root/'unsafe.zip'
        with zipfile.ZipFile(bad,'w') as bundle:bundle.writestr('../escape','not allowed')
        with self.assertRaises(ValueError):verify_bundle(bad)
        self.assertFalse((self.root.parent/'escape').exists())

    def test_cli_export_and_verification_require_no_model_credentials(self):
        session=self.session();session.ask('仅分析',ScriptedModel([{'action':'final','answer':'完成'}]))
        env={k:v for k,v in os.environ.items() if k not in ('RESEARCH_API_KEY','RESEARCH_MODEL','RESEARCH_BASE_URL')}
        process=subprocess.run([sys.executable,'-X','utf8','-m','graph_research','export',str(session.directory),'--output',str(self.root/'cli.zip')],
                               capture_output=True,text=True,encoding='utf-8',env=env)
        self.assertEqual(process.returncode,0,process.stderr);result=json.loads(process.stdout)
        checked=subprocess.run([sys.executable,'-X','utf8','-m','graph_research','verify-results',result['archive'],'--sha256',result['sha256']],
                               capture_output=True,text=True,encoding='utf-8',env=env)
        self.assertEqual(checked.returncode,0,checked.stderr);self.assertTrue(json.loads(checked.stdout)['ok'])

    def test_existing_bundle_and_core_cannot_be_overwritten(self):
        session=self.session();session.ask('记录',ScriptedModel([{'action':'final','answer':'ok'}]))
        output=self.root/'existing.zip';output.write_bytes(b'previous research')
        with self.assertRaises(FileExistsError):session.export_results(output)
        self.assertEqual(output.read_bytes(),b'previous research')
        with self.assertRaises(PermissionError):session.export_results(CORE/'accidental-results.zip')
        self.assertFalse((CORE/'accidental-results.zip').exists());self.assertTrue(verify()['ok'])
        with self.assertRaises(ValueError):session.export_results(turn=99)


if __name__=='__main__':unittest.main()
