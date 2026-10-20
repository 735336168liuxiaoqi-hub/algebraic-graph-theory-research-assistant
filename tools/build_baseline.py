"""Freeze reviewed source and a verified wheel without copying user state/runtime."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from graph_research.runtime.integrity import verify,backup
from verify_baseline import verify_baseline


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def copy_file(source,destination):
    for part in (source,*source.parents):
        if part==root:break
        if part.is_symlink() or getattr(part.lstat(),'st_file_attributes',0)&0x400:raise ValueError('Release files cannot pass through links')
    destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)


def main():
    parser=argparse.ArgumentParser(description='封存已完成测试的当前源码与安装包')
    parser.add_argument('--test-report',required=True);parser.add_argument('--wheel-report',required=True)
    options=parser.parse_args()
    from graph_research import __version__
    version=__version__
    report_directory=root/'outputs'/('baseline-v'+version.replace('.',''));report_directory.mkdir(parents=True,exist_ok=True)
    core=verify()
    if not core['ok']:raise RuntimeError('Core integrity failed; the baseline has not been created')
    tests=Path(options.test_report).resolve()
    test_text=tests.read_text(encoding='utf-8')
    if not test_text.rstrip().endswith('OK'):raise RuntimeError('The current full test suite has not passed')
    counts=re.findall(r'Ran (\d+) tests? in ',test_text)
    if not counts:raise RuntimeError('The full test count is missing')
    tests_passed=int(counts[-1])
    installed=Path(options.wheel_report).resolve()
    wheel_result=json.loads(installed.read_text(encoding='utf-8').strip())
    wheel=root/'dist'/f'graph_research_assistant-{version}-py3-none-any.whl'
    receipt=json.loads((root/'dist'/f'graph_research_assistant-{version}.release.json').read_text(encoding='utf-8'))
    if wheel_result['version']!=version or sha(wheel)!=receipt['wheel_sha256']:raise RuntimeError('The verified wheel does not match this release')
    with zipfile.ZipFile(wheel) as archive:
        for path in (root/'graph_research').rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix=='.pyc':continue
            if archive.read(path.relative_to(root).as_posix())!=path.read_bytes():raise RuntimeError('Source differs from the installed wheel')
    shanghai=timezone(timedelta(hours=8))
    stamp=datetime.now(shanghai).strftime('%Y%m%d-%H%M%S')
    destination=root/'dist'/'baselines'/f'graph-research-assistant-{version}-{stamp}'
    destination.mkdir(parents=True,exist_ok=False)
    for name in ('graph_research','tests','tools','docs','examples','.github','.githooks'):
        for path in (root/name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.pyo'):
                copy_file(path,destination/path.relative_to(root))
    for path in root.iterdir():
        if path.is_file() and (path.suffix in ('.md','.cmd','.ps1') or path.name in ('pyproject.toml','requirements.txt','requirements-lock.txt','assistant.py','test_workflow.py','.gitignore','.gitattributes','requirements-dev.txt','图论科研助手.exe')):
            copy_file(path,destination/path.name)
    for path in (wheel,root/'dist'/f'graph_research_assistant-{version}.release.json'):
        copy_file(path,destination/'release'/path.name)
    copy_file(tests,destination/'release/full-tests.txt')
    copy_file(installed,destination/'release/wheel-verification.txt')
    recovery=backup(destination/'release/core-backup.zip')
    validation={'version':version,'tests_passed':tests_passed,'test_report_sha256':sha(tests),'core_integrity':core,'installed_wheel_verification':wheel_result,'wheel_sha256':sha(wheel),'core_recovery_sha256':recovery['sha256'],'real_provider_requests':0}
    (destination/'release/baseline-validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
    (destination/'安装并启动.cmd').write_text('@echo off\nchcp 65001 >nul\nsetlocal\ncd /d "%~dp0"\nwhere py >nul 2>&1\nif errorlevel 1 goto use_python\npy -3 tools\\setup_baseline.py\ngoto setup_done\n:use_python\npython tools\\setup_baseline.py\n:setup_done\nif errorlevel 1 goto setup_failed\nstart "" "%~dp0图论科研助手.exe"\nexit /b 0\n:setup_failed\necho Setup failed. Review the error above. No existing source was replaced.\npause\nexit /b 1\n',encoding='utf-8',newline='\r\n')
    (destination/'先读我-封存版.md').write_text(f'''# 图论科研助手 {version} 封存版

封存日期：{stamp[:8]}（Asia/Shanghai）。此目录是下一步开发前的源码、工具和桌面界面基线。

## 使用

1. 解压整个ZIP到一个新目录，保留全部文件。
2. Windows上准备Python 3.11或更高版本（本机验证版本为3.13.9）。双击“安装并启动.cmd”：先校验文件，再创建本目录的.venv，按锁定版本联网安装依赖，最后打开程序。此ZIP不包含Python运行时或完整离线依赖。
3. 安装后可直接双击“图论科研助手.exe”。本地工具无需API；科研对话在“模型设置”中配置。密钥不会随封存包提供。

现有项目目录可继续使用原启动器；这个ZIP用于保存基线、迁移安装和回滚。

## 验证与恢复

- 运行 `python tools/verify_baseline.py` 检查BASELINE.json列出的发布文件。
- `release/full-tests.txt`为本版完整测试结果，`release/wheel-verification.txt`记录独立wheel验证；真实服务商请求0次。
- 整个程序回滚：解压到新目录并安装后，从新目录运行。不要覆盖正在使用的项目或研究数据。
- 独立核心恢复：`python tools/recover_release.py release/core-backup.zip --sha256 {recovery['sha256']} --destination 新的恢复目录`。它只恢复核心源码；完整程序请使用整个ZIP。

## 范围

包含本地分类工具、API科研对话、需求澄清及开发审批、图/超图计算、结构绘图与拖动布局、TikZ、记忆和结果打包接口，及测试、文档、例子和源码迁移记录。旧代码查找及桥接模块已移除。

不含本机API配置、密钥、用户记忆、聊天与计算历史、输出成果、实验扩展包、.venv和临时构建文件；它们在原位置保留。迁移记录只在docs/provenance中供开发追溯，不进入运行时工具包。程序不依赖Sage/WSL。功能与规模限制见对应说明文档。
''',encoding='utf-8')
    files={path.relative_to(destination).as_posix():sha(path) for path in sorted(destination.rglob('*')) if path.is_file()}
    manifest={'format':'graph-research-baseline-v1','version':version,'created_at':datetime.now(shanghai).isoformat(),'core_manifest_sha256':core['manifest_sha256'],'wheel_sha256':sha(wheel),'tests_passed':tests_passed,'real_provider_requests':0,'files':files}
    (destination/'BASELINE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    verify_baseline(destination)
    subprocess.run([sys.executable,'-I','-X','utf8',str(destination/'tools/setup_baseline.py'),'--check'],cwd=destination,check=True)
    archive=root/'dist'/f'图论科研助手-v{version}-封存版-{stamp}.zip'
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
        for path in sorted(destination.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix!='.pyc':bundle.write(path,destination.name+'/'+path.relative_to(destination).as_posix())
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:raise RuntimeError('ZIP checksum verification failed')
        for name,pin in files.items():
            if hashlib.sha256(bundle.read(destination.name+'/'+name)).hexdigest()!=pin:raise RuntimeError('Archived file differs from the source snapshot')
    pin=sha(archive);archive.with_suffix('.zip.sha256').write_text(pin+'  '+archive.name+'\n',encoding='utf-8')
    report={'version':version,'archive':str(archive),'archive_sha256':pin,'archive_bytes':archive.stat().st_size,'directory':str(destination),'files_checked':len(files),'core_files_checked':core['files_checked'],'wheel_sha256':sha(wheel),'tests_passed':tests_passed,'verified':True,'installation_performed':False,'real_provider_requests':0}
    (report_directory/'baseline-package.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
