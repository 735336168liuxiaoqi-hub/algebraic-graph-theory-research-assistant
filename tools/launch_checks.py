"""Select a developer's explicit/activated Python before the project default."""
import os
from pathlib import Path
import subprocess
import sys


def select_python(root,environment=None,current=None):
    environment=os.environ if environment is None else environment
    relative=Path('Scripts/python.exe') if os.name=='nt' else Path('bin/python')
    explicit=environment.get('RESEARCH_PYTHON')
    if explicit:
        target=Path(explicit).expanduser()
    elif environment.get('VIRTUAL_ENV'):
        target=Path(environment['VIRTUAL_ENV'])/relative
    elif environment.get('CONDA_PREFIX'):
        target=Path(environment['CONDA_PREFIX'])/('python.exe' if os.name=='nt' else 'bin/python')
    elif (Path(root)/'.venv'/relative).is_file():
        target=Path(root)/'.venv'/relative
    else:
        target=Path(current or sys.executable)
    if not target.is_file():raise ValueError('所选Python不存在：'+str(target)+'。请检查激活的环境或RESEARCH_PYTHON。')
    return target.resolve()


def main(arguments=None):
    root=Path(__file__).resolve().parents[1]
    python=select_python(root)
    return subprocess.run([str(python),'-X','utf8',str(root/'tools/checks.py'),*(sys.argv[1:] if arguments is None else arguments)],cwd=root).returncode


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,OSError) as exc:
        print(str(exc),file=sys.stderr);raise SystemExit(2)
