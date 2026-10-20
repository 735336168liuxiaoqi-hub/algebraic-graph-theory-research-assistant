"""Build from a fresh staged source tree; never delete an old build directory."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import zipfile


def main():
    root=Path(__file__).resolve().parents[1]
    sys.path.insert(0,str(root))
    from graph_research.runtime.integrity import assert_integrity
    assert_integrity()
    stage=(root/'tmp'/('release-stage-'+uuid.uuid4().hex)).resolve()
    if not stage.is_relative_to(root):raise ValueError('Stage must stay in workspace')
    stage.mkdir(parents=True)
    for name in ['pyproject.toml','README.md','NOTICE.md']:
        shutil.copy2(root/name,stage/name)
    for path in root.glob('LICENSE*'):
        if path.is_file():shutil.copy2(path,stage/path.name)
    shutil.copytree(root/'graph_research',stage/'graph_research',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    from seal_release import seal
    seal(stage/'graph_research')
    destination=root/'dist';destination.mkdir(exist_ok=True)
    subprocess.run([sys.executable,'-X','utf8','-m','pip','wheel',str(stage),'--no-deps','--no-build-isolation','--wheel-dir',str(destination)],check=True)
    from graph_research import __version__
    version=__version__
    wheel=destination/f'graph_research_assistant-{version}-py3-none-any.whl'
    with zipfile.ZipFile(wheel) as archive:
        names=set(archive.namelist())
        for removed in ['graphs.py','hypergraphs.py','tensors.py','assistant/extensions.py','assistant/extension_worker.py','data/migration_catalog.json']:
            if 'graph_research/'+removed in names:raise AssertionError(f'Stale source in wheel: {removed}')
        for needed in ['graphs/matrices.py','graphs/adapters.py','algebra/elementary.py','algebra/groups.py','hypergraphs/attachments.py','rendering/lattice.py','hypergraphs/model.py','tensors/elimination.py','rendering/tikz.py','tools/registry.py','assistant/agent.py','assistant/memory.py','assistant/session.py','assistant/model_config.py','assistant/onboarding.py','assistant/subagent.py','assistant/task_contract.py','assistant/task_control.py','assistant/host_events.py','assistant/subagent_cli.py','assistant/offline.py']:
            if 'graph_research/'+needed not in names:raise AssertionError(f'Missing implementation: {needed}')
        if 'graph_research/tools/input_guides.py' not in names:raise AssertionError('Missing offline input guides')
        for needed in ('graph_research/rendering/layouts.py','graph_research/tools/library_entries.py'):
            if needed not in names:raise AssertionError('Missing Python capability adapter: '+needed)
        for needed in ('graph_research/rendering/results.py','graph_research/assets/result_report.html'):
            if needed not in names:raise AssertionError('Missing result presentation: '+needed)
        for needed in ('graph_research/desktop/app.py','graph_research/desktop/localization.py','graph_research/desktop/service.py','graph_research/desktop/layout.py',
                       'graph_research/desktop/shell.py','graph_research/desktop/chat.py',
                       'graph_research/desktop/model_service.py','graph_research/desktop/configuration.py'):
            if needed not in names:raise AssertionError('Missing native desktop component: '+needed)
        if 'graph_research/_integrity.json' not in names:raise AssertionError('Missing release integrity manifest')
        for needed in ('schematics/__init__.py','schematics/document.py','schematics/geometry.py','schematics/tikz.py','desktop/schematic.py','tools/schematic.py'):
            if 'graph_research/'+needed not in names:raise AssertionError('Missing paper schematic component: '+needed)
        for needed in ('assistant/result_catalog.py','assistant/result_cleanup.py','desktop/results_center.py','assistant/spectral_scan.py','assistant/batch_workflow.py','assistant/experience.py','assistant/experience_evidence.py','assistant/experience_cli.py','tools/library.py','assistant/development.py','assistant/development_worker.py','assistant/library_cli.py','desktop/tool_library.py','hypergraphs/spectral_certificate.py','hypergraphs/spectral_methods.py','hypergraphs/newton_noda.py','mcp/presentation.py','mcp/telemetry.py'):
            if 'graph_research/'+needed not in names:raise AssertionError('Missing result management component: '+needed)
        if 'graph_research/runtime/observability.py' not in names:raise AssertionError('Missing bounded timing and diagnostics component')
        for needed in ('__init__.py','contracts.py','runtime.py','server.py','worker.py','cli.py'):
            if 'graph_research/mcp/'+needed not in names:raise AssertionError('Missing MCP component: '+needed)
    shutil.copy2(root/'tools/recover_release.py',destination/f'recover_graph_research_{version}.py')
    print(json.dumps({'wheel':str(wheel),'fresh_stage':str(stage),'stale_sources_rejected':True},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
