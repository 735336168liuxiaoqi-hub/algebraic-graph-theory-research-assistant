"""Publish the manual plus importable examples from the runtime input guide."""
import argparse
import json
from pathlib import Path
import sys
import zipfile

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from graph_research.tools import ToolRegistry
from graph_research.tools.input_guides import input_guide,render_manual
from graph_research.runtime.storage import atomic_text,staged_file


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--overwrite',action='store_true');options=parser.parse_args()
    definitions=ToolRegistry().catalog();guides=[input_guide(d) for d in definitions]
    manual=root/'docs/OFFLINE_INPUTS.md';data=root/'docs/offline-inputs.json';examples=root/'examples/offline-inputs'
    atomic_text(manual,render_manual(definitions),overwrite=options.overwrite)
    atomic_text(data,json.dumps({'format':'graph-research-offline-inputs','version':1,'tools':guides},ensure_ascii=False,indent=2),overwrite=options.overwrite)
    example_files={}
    for guide in guides:
        if not guide['examples']:continue
        content=json.dumps(guide['examples'][0]['arguments'],ensure_ascii=False,indent=2)+'\n'
        example_files[guide['name']+'.json']=content
        atomic_text(examples/(guide['name']+'.json'),content,overwrite=options.overwrite)
    archive=root/'examples/offline-inputs.zip'
    with staged_file(archive,overwrite=options.overwrite) as temporary:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as bundle:
            for name,content in example_files.items():bundle.writestr(name,content)
            bundle.writestr('README.txt','这些文件是工具参数数据，不会自动执行。无API菜单选择对应工具，再选方式3导入同名JSON文件。\n')
    print(json.dumps({'tools':len(guides),'parameter_examples':sum(len(g['fields']) for g in guides),
                      'manual':str(manual),'importable_examples':str(examples),'archive':str(archive)},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
