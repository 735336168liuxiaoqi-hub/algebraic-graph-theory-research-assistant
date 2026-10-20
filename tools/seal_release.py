"""MAINTAINER ONLY: build a new integrity inventory after reviewing source.

Never called automatically on a failed check, or by an assistant/model tool.
Regenerating the inventory is a release operation, not corruption recovery.
"""
import json
from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from graph_research.runtime.integrity import inventory,MANIFEST


def seal(package):
    manifest={'format':'graph-research-integrity-v1','files':inventory(package)}
    (package/MANIFEST).write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    return len(manifest['files'])


if __name__=='__main__':print('Sealed reviewed source files:',seal(root/'graph_research'))
