"""Verify the built wheel from an extracted copy outside the live source tree."""
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from graph_research import __version__


def main():
    wheel=root/'dist'/f'graph_research_assistant-{__version__}-py3-none-any.whl'
    with tempfile.TemporaryDirectory(prefix='graph-wheel-') as directory:
        target=Path(directory)/'installed';target.mkdir()
        with zipfile.ZipFile(wheel) as archive:archive.extractall(target)
        subprocess.run([sys.executable,'-I','-X','utf8',str(root/'tools/verify_wheel.py'),str(target)],cwd=directory,check=True)


if __name__=='__main__':main()
