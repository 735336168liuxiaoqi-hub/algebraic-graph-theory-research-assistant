"""Preview-bound cleanup, reversible moves, task tombstones and budget safety."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from graph_research.assistant import ResearchSession,create_subagent,SubagentLimits
from graph_research.assistant.result_catalog import ResultCatalog
from graph_research.assistant.result_cleanup import ResultCleanup
from graph_research.assistant.results import verify_bundle
from graph_research.assistant.task_contract import TaskProtocolError
from tests.test_feature_workflow import ScriptedModel
from tests.test_subagent import agent_task


class ResultCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.catalog=ResultCatalog(self.root/'成果');self.cleanup=ResultCleanup(self.catalog)
    def session(self):
        session=ResearchSession(self.root/'session',results_directory=self.catalog.root)
        session.ask('P5直径',ScriptedModel([{'action':'final','answer':'分析结果'}]));return session
    def test_whole_task_cleanup_preserves_unmanaged_files_and_can_restore(self):
        session=self.session();bundle=dict(session.result_bundle);notes=session.directory/'用户笔记.txt';notes.write_text('保留',encoding='utf-8')
        preview=self.cleanup.preview([session.session_id],'task');self.assertEqual(len(preview['plans']),1)
        operation=self.cleanup.apply(preview['plans'][0]['id'])
        self.assertTrue(notes.is_file());self.assertFalse(Path(bundle['archive']).exists())
        with self.assertRaises(ValueError):ResearchSession(session.directory)
        self.assertEqual(self.catalog.resolve(bundle['artifact_id'])['availability'],'trashed')
        self.cleanup.restore(operation['id']);loaded=ResearchSession(session.directory)
        self.assertTrue(verify_bundle(loaded.result_bundle['archive'],loaded.result_bundle['sha256'])['ok']);self.assertEqual(notes.read_text(encoding='utf-8'),'保留')
    def test_preview_scope_change_is_rejected_without_touching_files(self):
        session=self.session();preview=self.cleanup.preview([session.session_id],'task');before=Path(session.result_bundle['archive']).read_bytes()
        session.reply('新需求',ScriptedModel([{'action':'final','answer':'新结果'}]))
        with self.assertRaises(ValueError):self.cleanup.apply(preview['plans'][0]['id'])
        self.assertTrue(Path(session.result_bundle['archive']).exists());self.assertFalse((session.directory/'.results-cleanup.json').exists())
    def test_pending_and_pinned_sources_are_excluded(self):
        session=self.session();self.catalog.pin(session.session_id,True)
        self.assertFalse(self.cleanup.preview([session.session_id],'task')['plans']);self.catalog.pin(session.session_id,False)
        session.reply('条件不明',ScriptedModel([{'action':'clarify','questions':['顶点数？']}]))
        self.assertFalse(self.cleanup.preview([session.session_id],'task')['plans'])
    def test_move_failure_rolls_back_without_destroying_original_results(self):
        session=self.session();bundle=dict(session.result_bundle);preview=self.cleanup.preview([session.session_id],'task')
        import os
        original=os.replace;count=[]
        def fail_once(source,target):
            if '.成果回收' in str(target):
                count.append(1)
                if len(count)==2:raise OSError('simulated move failure')
            return original(source,target)
        with patch('graph_research.assistant.result_cleanup.os.replace',side_effect=fail_once):
            with self.assertRaises(OSError):self.cleanup.apply(preview['plans'][0]['id'])
        self.assertTrue(Path(bundle['archive']).is_file());self.assertFalse((session.directory/'.results-cleanup.json').exists());self.assertTrue(ResearchSession(session.directory).state)
    def test_permanent_purge_only_removes_registered_trash_payload(self):
        session=self.session();preview=self.cleanup.preview([session.session_id],'task');operation=self.cleanup.apply(preview['plans'][0]['id'])
        self.assertGreater(self.cleanup.purge_preview(operation['id'])['files'],0);self.cleanup.purge(operation['id'])
        with self.assertRaises(ValueError):self.cleanup.restore(operation['id'])
        self.assertTrue((session.directory/'session.json').is_file());self.assertTrue(self.catalog.database.is_file())
    def test_temporary_cleanup_keeps_scientific_receipts_and_outputs(self):
        session=self.session();worker=session.directory/'tasks'/('task_'+'a'*32);(worker/'temp').mkdir(parents=True);(worker/'temp/cache.dat').write_bytes(b'x'*1024)
        (worker/'execution.json').write_text('{}');(worker/'outputs').mkdir();(worker/'outputs/data.txt').write_text('science')
        preview=self.cleanup.preview([session.session_id],'temporary');operation=self.cleanup.apply(preview['plans'][0]['id'])
        self.assertFalse((worker/'temp').exists());self.assertTrue((worker/'execution.json').exists());self.assertTrue((worker/'outputs/data.txt').exists())
        self.cleanup.restore(operation['id']);self.assertTrue((worker/'temp/cache.dat').exists())
    def test_delegated_tombstone_keeps_request_id_and_budget_without_reexecution(self):
        model=ScriptedModel([{'action':'final','answer':'分析完成'}]);parent,_=create_subagent(self.root/'host',user_id='a',model_factory=lambda:model,
            limits=SubagentLimits(max_model_calls=1,allow_extensions=False),results_directory=self.catalog.root)
        request=agent_task('clear-delegated');done=parent.submit(request);source_id=done['artifacts'][0]['result_id']
        operation=self.cleanup.apply(self.cleanup.preview([source_id],'task')['plans'][0]['id'])
        cleared=parent.submit(request);self.assertEqual(cleared['task_id'],done['task_id']);self.assertEqual(cleared['status'],'cleared');self.assertEqual(cleared['budget']['used']['model_calls'],1)
        with self.assertRaises(TaskProtocolError):parent.resume(done['task_id'],'b'*32)
        self.assertEqual(len(model.contexts),1);self.cleanup.restore(operation['id'])
        restored=parent.get(done['task_id']);self.assertEqual(restored['status'],'analysis_only');self.assertEqual(restored['budget']['used']['model_calls'],1);self.assertEqual(len(model.contexts),1)

    def test_existing_session_instance_cannot_bypass_an_interrupted_cleanup(self):
        from graph_research.runtime.storage import write_json
        session=self.session();write_json(session.directory/'.results-cleanup.json',{'operation_id':'a'*32})
        with self.assertRaises((ValueError,RuntimeError)):session.export_results()

    def test_recovery_preserves_unpublished_artifact_state(self):
        session=self.session();identifier,path=self.catalog.reserve(session)
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'unpublished export')
        operation=self.cleanup.apply(self.cleanup.preview([session.session_id],'task')['plans'][0]['id']);self.cleanup.restore(operation['id'])
        self.assertEqual(self.catalog.artifact(identifier)['state'],'preparing');self.assertEqual(path.read_bytes(),b'unpublished export')

    def test_restore_cannot_reset_a_changed_delegated_budget(self):
        from graph_research.runtime.storage import read_json,write_json
        parent,_=create_subagent(self.root/'host',user_id='a',model_factory=lambda:ScriptedModel([{'action':'final','answer':'分析'}]),results_directory=self.catalog.root)
        done=parent.submit(agent_task('preserve-usage'));source_id=done['artifacts'][0]['result_id']
        operation=self.cleanup.apply(self.cleanup.preview([source_id],'task')['plans'][0]['id'])
        record,_=read_json(operation['task_path']);record['usage']['model_calls']+=1;write_json(operation['task_path'],record)
        with self.assertRaises(ValueError):self.cleanup.restore(operation['id'])
        self.assertEqual(read_json(operation['task_path'])[0]['usage']['model_calls'],2)

    def test_modified_recycle_content_and_occupied_original_are_never_overwritten(self):
        session=self.session();operation=self.cleanup.apply(self.cleanup.preview([session.session_id],'task')['plans'][0]['id'])
        move=next(m for m in operation['moves'] if m['source'].endswith('.zip'))
        Path(move['trash']).write_bytes(b'externally changed')
        with self.assertRaises(ValueError):self.cleanup.purge(operation['id'])
        with self.assertRaises(ValueError):self.cleanup.restore(operation['id'])
        self.assertTrue(Path(move['trash']).exists());self.assertEqual(self.cleanup.list_operations()[0]['state'],'moving')

    def test_symlink_in_managed_directory_blocks_cleanup_without_following_it(self):
        from tests.host_fixtures import real_link_or_skip
        session=self.session();directory=session.directory/'views';directory.mkdir();outside=self.root/'outside.txt';outside.write_text('keep')
        real_link_or_skip(self,directory/'link.txt',outside)
        preview=self.cleanup.preview([session.session_id],'task');self.assertFalse(preview['plans']);self.assertTrue(preview['blocked']);self.assertEqual(outside.read_text(),'keep')


if __name__=='__main__':unittest.main()
