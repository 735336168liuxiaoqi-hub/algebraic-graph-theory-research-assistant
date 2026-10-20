"""The candidate removes reference tools while preserving provenance and rights gates."""
import hashlib
import json
import posixpath
import re
from pathlib import Path
import tempfile
import unittest
import zipfile
from urllib.parse import unquote

from graph_research.tools import ToolRegistry
from graph_research.assistant.offline import grouped_tools
from tools.check_public_release import publication_status
from tools.prepare_public_release import prepare,selected_files,_markdown


class ReleaseCandidateTests(unittest.TestCase):
    def test_runtime_candidate_versions_accept_rc_without_accepting_path_or_command_text(self):
        from tools.stage_runtime import valid_release_version
        for value in ('0.36.0rc1','0.36.0','1.2.3a1','1.2.3b2'):
            self.assertTrue(valid_release_version(value),value)
        for value in ('../0.36.0','v0.36.0','0.36.0rc1;echo bad','0.36.0\n',None):
            self.assertFalse(valid_release_version(value),value)

    def test_reference_tool_and_category_are_absent_but_provenance_is_preserved(self):
        root=Path(__file__).resolve().parents[1];registry=ToolRegistry()
        self.assertNotIn('lookup_legacy',registry.tools)
        self.assertNotIn('旧代码迁移参考',{group['name'] for group in grouped_tools(registry)})
        self.assertFalse((root/'graph_research/data/migration_catalog.json').exists())
        record=root/'docs/provenance/migration_catalog.json'
        data=json.loads(record.read_text(encoding='utf-8'))
        self.assertEqual(data['catalog_scope'],'retained_release_definitions')
        original=next(row for row in data['source_files'] if row['file']=='myCombinatorics.sage')
        self.assertEqual(original['sha256'],'4dd891cc173b9f16458075499e35d5f7d25f7dc943c75f9ef949975f8f5c2694')
        self.assertEqual(len(data['source_files']),11)
        self.assertTrue(data['definitions']);self.assertTrue(all('native_module' in row and 'source' in row for row in data['definitions']))
        self.assertTrue((root/'graph_research/data/sage_reference.json').is_file())

    def test_removed_optional_operation_is_unavailable_in_library_contract_and_execution(self):
        import jsonschema
        from graph_research.algebra import combinatorics
        from tools.build_migration_catalog import EXCLUDED_RELEASE_SYMBOLS
        registry=ToolRegistry();definition=registry.describe('combinatorial_calculation')
        self.assertNotIn('magic_square',definition['parameters']['properties']['operation']['enum'])
        for symbol in ('magicsquare_normal_odd','Siamese_magic_square'):
            self.assertFalse(hasattr(combinatorics,symbol))
            self.assertIn(('myCombinatorics.sage',symbol),EXCLUDED_RELEASE_SYMBOLS)
        with self.assertRaises(jsonschema.ValidationError):
            registry.call('combinatorial_calculation',{'operation':'magic_square','n':3})
        with self.assertRaises(ValueError):
            registry.tools['combinatorial_calculation'].function(operation='magic_square',n=3)
        self.assertEqual(registry.call('combinatorial_calculation',{'operation':'partition_number','n':8,'k':3})['result'],5)
        root=Path(__file__).resolve().parents[1]
        catalog=json.loads((root/'docs/provenance/migration_catalog.json').read_text(encoding='utf-8'))
        self.assertTrue(all((r['source_file'],r['symbol']) not in EXCLUDED_RELEASE_SYMBOLS for r in catalog['definitions']))

    def test_publication_gate_rejects_unconfirmed_rights_and_missing_license(self):
        root=Path(__file__).resolve().parents[1]
        actual=publication_status(root)
        if actual['status']!='cleared':self.assertFalse(actual['allowed'])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'docs/provenance').mkdir(parents=True)
            record={'status':'cleared','public_release_allowed':True,'confirmed_by_owner':False,'project_license':'MIT'}
            (root/'docs/provenance/rights-status.json').write_text(json.dumps(record),encoding='utf-8')
            (root/'pyproject.toml').write_text('[project]\nlicense="MIT"\n',encoding='utf-8')
            (root/'LICENSE').write_text('Test fixture, not an actual license. '*10,encoding='utf-8')
            self.assertFalse(publication_status(root)['allowed'])

    def test_publication_gate_allows_owner_confirmed_consistent_license(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'docs/provenance').mkdir(parents=True)
            record={'status':'cleared','public_release_allowed':True,'confirmed_by_owner':True,'project_license':'MIT'}
            (root/'docs/provenance/rights-status.json').write_text(json.dumps(record),encoding='utf-8')
            (root/'pyproject.toml').write_text('[project]\nlicense="MIT"\n',encoding='utf-8')
            self.assertFalse(publication_status(root)['allowed'])
            (root/'LICENSE').write_text('Test fixture, not an actual license. '*10,encoding='utf-8')
            self.assertTrue(publication_status(root)['allowed'])
            (root/'pyproject.toml').write_text('[project]\nlicense="Apache-2.0"\n',encoding='utf-8')
            self.assertFalse(publication_status(root)['allowed'])

    def test_clean_source_export_excludes_private_state_and_keeps_research_history(self):
        root=Path(__file__).resolve().parents[1];selection=selected_files(root)
        self.assertIn('docs/provenance/migration_catalog.json',selection)
        self.assertIn('docs/provenance/MIGRATION.md',selection);self.assertIn('NOTICE.md',selection)
        for name in ('使用指南.md','docs/README.md','start-desktop.cmd','algebraic graph theory research assistant.exe','graph_research/desktop/graph_actions.py','LICENSE','docs/releases/CURRENT.md','docs/QUICKSTART.md','docs/WORKFLOW.md','docs/diagrams/workflow-overview.svg'):
            self.assertIn(name,selection)
        self.assertNotIn('tools/power_check_paired.py',selection)
        self.assertNotIn('examples/external_v0351/report.json',selection)
        self.assertNotIn('graph_research/data/migration_catalog.json',selection)
        sanitized=_markdown(b'Example: `C:/Users/Researcher/Documents/project`', 'README.md',selection)
        self.assertNotIn(b'Researcher',sanitized);self.assertIn(b'<LOCAL_PATH>',sanitized)
        for name in selection:
            self.assertFalse(set(Path(name).parts)&{'outputs','dist','.git','.venv','tool_packages','legacy_sage'})
        with tempfile.TemporaryDirectory() as directory:
            result=prepare(root,Path(directory)/'candidate')
            self.assertFalse(result['public_upload_performed'])
            rights=json.loads((root/'docs/provenance/rights-status.json').read_text(encoding='utf-8'))
            self.assertEqual(result['publication_status'],rights['status'])
            with zipfile.ZipFile(result['source_archive']) as archive:
                names=archive.namelist();self.assertTrue(any(n.endswith('/NOTICE.md') for n in names))
                self.assertFalse(any('/legacy_sage/' in n or '/.git/' in n or '/outputs/' in n for n in names))

    def test_curated_documentation_links_survive_source_export(self):
        root=Path(__file__).resolve().parents[1];selection=selected_files(root)
        root_docs={name for name in selection if '/' not in name and name.endswith('.md')}
        self.assertEqual(root_docs,{'README.md','使用指南.md','CONTRIBUTING.md','NOTICE.md','LICENSE-STATUS.md'})
        for name,path in selection.items():
            if not name.endswith('.md') or ('/' in name and not name.startswith('docs/')):continue
            content=re.sub(r'```.*?```','',path.read_text(encoding='utf-8'),flags=re.S)
            for target in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)',content):
                if re.match(r'^[a-z][a-z0-9+.-]*:',target,re.I) or target.startswith(('/', '#')):continue
                target=unquote(target.split('#',1)[0])
                resolved=posixpath.normpath(posixpath.join(posixpath.dirname(name),target))
                with self.subTest(document=name,target=target):
                    self.assertTrue(resolved in selection or any(n.startswith(resolved.rstrip('/')+'/') for n in selection),
                                    'Document target missing from source export: '+resolved)


if __name__=='__main__':unittest.main()
