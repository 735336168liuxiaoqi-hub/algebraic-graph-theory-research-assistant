"""Install a verified extracted baseline into its own adjacent Python environment."""
import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_baseline import verify_baseline


def main():
    parser=argparse.ArgumentParser(description='校验、安装并准备封存版本；实际安装需要联网下载依赖')
    parser.add_argument('--check',action='store_true',help='只校验，不创建环境或安装依赖');options=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    report=verify_baseline(root)
    if sys.version_info<(3,11):raise RuntimeError('Python 3.11 or later is required')
    if sys.platform!='win32':raise RuntimeError('The protected desktop release currently requires Windows')
    print('Baseline verified:',report['version'],report['files_checked'],'files')
    if options.check:return
    environment=root/'.venv'
    if environment.is_symlink() or (environment.exists() and getattr(environment.lstat(),'st_file_attributes',0)&0x400):raise RuntimeError('The environment must be a regular local directory')
    python=environment/'Scripts/python.exe'
    if environment.exists() and not python.is_file():raise RuntimeError('An incomplete .venv already exists; choose a fresh extraction directory')
    if not environment.exists():subprocess.run([sys.executable,'-m','venv',str(environment)],check=True)
    wheel=root/'release'/('graph_research_assistant-'+report['version']+'-py3-none-any.whl')
    subprocess.run([str(python),'-m','pip','install','--constraint',str(root/'requirements-lock.txt'),str(wheel)+'[all]'],check=True)
    print('Setup complete. Open the desktop launcher in this folder.')


if __name__=='__main__':main()
