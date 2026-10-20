"""Fail when reviewed tool contracts and generated manuals/examples drift apart."""
import json
from pathlib import Path
import sys
import tempfile
import zipfile

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from graph_research.tools import ToolRegistry
from graph_research.tools.contracts import export_documentation
from graph_research.tools.input_guides import input_guide,render_manual


def main():
    registry=ToolRegistry();definitions=registry.catalog();mismatches=[]
    with tempfile.TemporaryDirectory() as directory:
        generated=export_documentation(registry,directory)
        for name,path in generated.items():
            target=root/'docs/model'/name
            if not target.is_file() or target.read_text(encoding='utf-8')!=Path(path).read_text(encoding='utf-8'):mismatches.append(str(target.relative_to(root)))
    guides=[input_guide(definition) for definition in definitions]
    expected={'format':'graph-research-offline-inputs','version':1,'tools':guides}
    if json.loads((root/'docs/offline-inputs.json').read_text(encoding='utf-8'))!=expected:mismatches.append('docs/offline-inputs.json')
    if (root/'docs/OFFLINE_INPUTS.md').read_text(encoding='utf-8')!=render_manual(definitions):mismatches.append('docs/OFFLINE_INPUTS.md')
    with zipfile.ZipFile(root/'examples/offline-inputs.zip') as archive:
        for guide in guides:
            if not guide['examples']:continue
            name=guide['name']+'.json';value=guide['examples'][0]['arguments']
            if json.loads((root/'examples/offline-inputs'/name).read_text(encoding='utf-8'))!=value:mismatches.append('examples/offline-inputs/'+name)
            if json.loads(archive.read(name))!=value:mismatches.append('examples/offline-inputs.zip:'+name)
    from tools.build_sage_review import build
    review,report=build()
    if json.loads((root/'docs/sage-replacement-review.json').read_text(encoding='utf-8'))!=review:mismatches.append('docs/sage-replacement-review.json')
    if (root/'docs/provenance/SAGE_REVIEW.md').read_text(encoding='utf-8')!=report:mismatches.append('docs/provenance/SAGE_REVIEW.md')
    from graph_research.mcp.contracts import tool_definitions
    if json.loads((root/'docs/model/mcp-tools.json').read_text(encoding='utf-8'))!={'transport':'stdio','tools':tool_definitions()}:
        mismatches.append('docs/model/mcp-tools.json')
    from graph_research.assistant.task_contract import contracts
    if json.loads((root/'docs/model/subagent-contracts.json').read_text(encoding='utf-8'))!=contracts():
        mismatches.append('docs/model/subagent-contracts.json')
    if mismatches:raise SystemExit('Generated files differ; refresh the manuals and input guides:\n'+'\n'.join(mismatches))
    print('Generated tool contracts, manuals and examples agree:',len(definitions),'tools')


if __name__=='__main__':main()
