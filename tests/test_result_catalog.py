"""Managed result versions and retention preserve original execution evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from graph_research.assistant.session import ResearchSession
from graph_research.assistant.offline import OfflineToolSession
from graph_research.assistant.result_catalog import ResultCatalog,ResultPreferences,resolve_bundle
from graph_research.assistant.results import verify_bundle
from tests.test_feature_workflow import ScriptedModel


class ResultCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.catalog=ResultCatalog(self.root/'成果')
    def session(self):return ResearchSession(self.root/'session',self.root/'packages',results_directory=self.catalog.root)
    def test_automatic_latest_retention_reuse_and_snapshot(self):
        session=self.session();session.ask('P5直径',ScriptedModel([{'action':'final','answer':'待计算'}]));first=dict(session.result_bundle)
        session._finalize_output();self.assertEqual(first['artifact_id'],session.result_bundle['artifact_id'])
        snapshot=session.export_results();self.assertFalse(snapshot['automatic'])
        session.reply('补充说明',ScriptedModel([{'action':'final','answer':'补充分析'}]));latest=session.result_bundle
        self.assertFalse(Path(first['archive']).exists());self.assertTrue(Path(snapshot['archive']).exists());self.assertTrue(Path(latest['archive']).exists())
        self.assertEqual(sum(v['availability']=='ready' and v['automatic'] for v in self.catalog.list_versions(session.session_id)),1)
        self.assertTrue(verify_bundle(latest['archive'],latest['sha256'])['ok'])
    def test_rename_preserves_hash_and_stable_identifier(self):
        session=self.session();session.ask('文件名 <测试> / P5',ScriptedModel([{'action':'final','answer':'分析'}]));before=dict(session.result_bundle)
        self.catalog.rename(session.session_id,'路径图研究','谱研究');located=resolve_bundle(before,source_directory=session.directory)
        self.assertEqual(located['artifact_id'],before['artifact_id']);self.assertEqual(located['sha256'],before['sha256']);self.assertIn('谱研究',located['archive'])
        self.assertTrue(verify_bundle(located['archive'],located['sha256'])['ok'])
        sidecar=Path(located['sha256_file']).read_text(encoding='utf-8');self.assertIn(Path(located['archive']).name,sidecar)
        loaded=ResearchSession(session.directory);self.assertEqual(loaded.result_bundle['archive'],located['archive'])
    def test_managed_native_calculations_keep_receipts_while_old_auto_zip_is_removed(self):
        session=OfflineToolSession(self.root/'native',self.root/'packages',results_directory=self.catalog.root)
        session.call_tool('graph_invariants',{'n':3});first=dict(session.result_bundle)
        session.call_tool('graph_invariants',{'n':5});self.assertFalse(Path(first['archive']).exists())
        self.assertEqual(session.result_bundle['summary']['verified_calls'],2,str([(o.get('tool'),o.get('ok'),o.get('error')) for o in session.state['observations']])[:800])
        for observation in session.state['observations']:self.assertTrue((Path(observation['execution']['directory'])/'execution.json').is_file())
    def test_explicit_export_copy_and_unmanaged_legacy_behavior_remain_valid(self):
        session=self.session();session.ask('分析',ScriptedModel([{'action':'final','answer':'答案'}]));copy=session.export_results(self.root/'copy.zip')
        self.assertEqual(Path(copy['archive']),self.root/'copy.zip');self.assertTrue(Path(copy['managed_archive']).is_file())
        legacy=ResearchSession(self.root/'legacy',auto_export=False);legacy.ask('旧入口',ScriptedModel([{'action':'final','answer':'答案'}]));one=legacy.export_results();two=legacy.export_results()
        self.assertTrue(Path(one['archive']).is_file());self.assertTrue(Path(two['archive']).is_file())
    def test_pin_prevents_automatic_removal_and_modified_files_are_not_deleted(self):
        session=self.session();session.ask('分析',ScriptedModel([{'action':'final','answer':'一'}]));first=dict(session.result_bundle)
        self.catalog.pin(session.session_id,True);session.reply('第二轮',ScriptedModel([{'action':'final','answer':'二'}]));self.assertTrue(Path(first['archive']).exists())
        self.catalog.pin(session.session_id,False);Path(first['archive']).write_bytes(b'changed')
        session.reply('第三轮',ScriptedModel([{'action':'final','answer':'三'}]));self.assertEqual(Path(first['archive']).read_bytes(),b'changed')
    def test_preferences_change_new_location_but_keep_known_roots(self):
        preferences=ResultPreferences(self.root/'preferences.json',self.root/'first');self.assertFalse(preferences.path.exists())
        preferences.select(self.root/'second');self.assertEqual(preferences.active,self.root/'second');self.assertEqual(len(preferences.read()['roots']),2)
    def test_legacy_import_keeps_originals_and_resolves_original_path(self):
        legacy=ResearchSession(self.root/'old');legacy.ask('旧成果',ScriptedModel([{'action':'final','answer':'分析'}]));original=dict(legacy.result_bundle)
        imported=self.catalog.import_legacy(legacy);self.assertEqual(len(imported),1);self.assertTrue(Path(original['archive']).is_file())
        resolved=resolve_bundle(original,source_directory=legacy.directory,results_root=self.catalog.root)
        self.assertEqual(resolved['sha256'],original['sha256']);self.assertNotEqual(resolved['archive'],original['archive'])

    def test_mcp_cached_receipt_survives_rename_and_automatic_retention(self):
        from graph_research.assistant import create_subagent,SubagentLimits
        from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
        from tests.test_subagent import agent_task
        model=ScriptedModel([{'action':'final','answer':'主机分析'}])
        parent,_=create_subagent(self.root/'host',user_id='a',model_factory=lambda:model,
            limits=SubagentLimits(max_model_calls=1,allow_extensions=False),results_directory=self.catalog.root)
        request=agent_task('stable-artifact');done=parent.submit(request);bundle=done['artifacts'][0]
        source=self.catalog.source(bundle['result_id']);session=ResearchSession(source['directory'])
        session.reply('另一条本地说明',ScriptedModel([{'action':'final','answer':'新说明'}]))
        self.assertTrue(Path(bundle['path']).is_file(),'Receipt-referenced version must be retained')
        self.catalog.rename(source['id'],'改名后的成果','新课题');again=parent.submit(request)
        self.assertEqual(again['artifacts'][0]['sha256'],bundle['sha256']);self.assertIn('新课题',again['artifacts'][0]['path']);self.assertEqual(len(model.contexts),1)
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root/'host'),'a',results_directory=str(self.catalog.root)))
        target,artifact=runtime.artifact(done['task_id'],0)
        self.assertTrue(target.is_file());self.assertEqual(artifact['sha256'],bundle['sha256'])

    def test_empty_old_sidecar_does_not_break_new_automatic_export(self):
        session=self.session();session.ask('分析',ScriptedModel([{'action':'final','answer':'一'}]));old=dict(session.result_bundle)
        Path(old['sha256_file']).write_text('',encoding='utf-8');session.reply('继续',ScriptedModel([{'action':'final','answer':'二'}]))
        self.assertIsNone(session.export_error);self.assertTrue(verify_bundle(session.result_bundle['archive'],session.result_bundle['sha256'])['ok'])

    def test_imported_legacy_mcp_task_still_has_clear_tombstone_and_list_skips_it(self):
        from graph_research.assistant import create_subagent
        from graph_research.assistant.result_cleanup import ResultCleanup
        from graph_research.mcp.runtime import HostConfiguration,MCPResearchRuntime
        from tests.test_subagent import agent_task
        parent,_=create_subagent(self.root/'host',user_id='a',model_factory=lambda:ScriptedModel([{'action':'final','answer':'分析'}]))
        older=parent.submit(agent_task('older-task'));newer=parent.submit(agent_task('newer-task'))
        directory=Path(newer['artifacts'][0]['path']).parent.parent;legacy=ResearchSession(directory)
        self.catalog.import_legacy(legacy);self.assertEqual(self.catalog.source(legacy.session_id)['mode'],'mcp')
        cleaner=ResultCleanup(self.catalog);operation=cleaner.apply(cleaner.preview([legacy.session_id],'task')['plans'][0]['id'])
        self.assertEqual(parent.get(newer['task_id'])['status'],'cleared')
        runtime=MCPResearchRuntime(HostConfiguration(str(self.root/'host'),'a'))
        self.assertEqual(runtime.list_tasks(limit=1)['tasks'][0]['task_id'],older['task_id'])
        cleaner.restore(operation['id']);self.assertEqual(parent.get(newer['task_id'])['status'],'analysis_only')

    def test_initial_mcp_reply_bundle_remains_referenced_after_user_resume(self):
        from graph_research.assistant import create_subagent,SubagentLimits
        from tests.test_subagent import agent_task
        model=ScriptedModel([{'action':'clarify','questions':['请确认图。']},{'action':'final','answer':'已确认。'}])
        parent,portal=create_subagent(self.root/'host',user_id='a',model_factory=lambda:model,
            limits=SubagentLimits(max_model_calls=2,allow_extensions=False),results_directory=self.catalog.root)
        waiting=parent.submit(agent_task('retain-initial-response'));original=dict(waiting['artifacts'][0]);p=waiting['interaction']
        event=portal.answer(waiting['task_id'],p['interaction_id'],waiting['revision'],'确认。')
        completed=parent.resume(waiting['task_id'],event['event_id'])
        self.assertEqual(completed['status'],'analysis_only');self.assertTrue(Path(original['path']).is_file())
        self.assertTrue(verify_bundle(original['path'],original['sha256'])['ok'])


if __name__=='__main__':unittest.main()
