"""Run existing acceptance commands serially; preserve every exit code and log."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import zipfile


def main():
    parser=argparse.ArgumentParser(description='外部验收命令；不修复源码、不封存、不安装依赖、不调用模型')
    parser.add_argument('--python',default=sys.executable)
    parser.add_argument('--project',help='待测项目根目录；默认使用本脚本所在项目')
    parser.add_argument('--profile',choices=('quick','full'),default='quick')
    parser.add_argument('--repeat-mcp',type=int,default=5)
    parser.add_argument('--runtime',help='可选固定运行目录；full默认检查dist/runtimes/v0.35.1')
    parser.add_argument('--output',help='必须是尚不存在的新报告目录')
    args=parser.parse_args()
    if not 1<=args.repeat_mcp<=20:parser.error('--repeat-mcp必须为1..20')
    root=Path(args.project).resolve() if args.project else Path(__file__).resolve().parents[1]
    python=Path(args.python).resolve()
    if not python.is_file():parser.error('Python解释器不存在')
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    output=Path(args.output).resolve() if args.output else root/'outputs/external-v0351'/stamp
    protected=[root/'graph_research',root/'dist/runtimes']
    if any(output==p or output.is_relative_to(p) for p in protected):parser.error('测试报告不能写入基础包或固定运行副本')
    output.mkdir(parents=True,exist_ok=False)
    env={**os.environ,'PYTHONUTF8':'1','PYTHONIOENCODING':'utf-8','QT_QPA_PLATFORM':'offscreen'}
    identity="import json,sys; from pathlib import Path; import graph_research; from importlib.metadata import version; p=Path(graph_research.__file__).resolve(); print(json.dumps({'version':graph_research.__version__,'metadata':version('graph-research-assistant'),'package_file':str(p),'python':sys.executable})); assert graph_research.__version__==version('graph-research-assistant')=='0.35.1'; assert p==Path(sys.argv[1]).resolve()"
    commands=[('identity',['-I','-X','utf8','-c',identity,str(root/'graph_research/__init__.py')]),
              ('doctor',['-I','-X','utf8','-m','graph_research','doctor']),
              ('integrity-before',['-I','-X','utf8','-m','graph_research','protect','check']),
              ('long-paths',['-X','utf8','-m','unittest','tests.test_long_paths','-v'])]
    for i in range(args.repeat_mcp):
        commands.append((f'mcp-development-{i+1:02d}',['-X','utf8','-m','unittest','tests.test_mcp_integration.SDKTests.test_real_stdio_external_development_host_approval_library_and_reuse_without_api','-v']))
    if args.profile=='full':
        commands.extend([('full-strict',['-X','utf8','tools/checks.py','--full','--strict-lock']),
                         ('installed-wheel',['-X','utf8','tools/verify_release.py'])])
        runtime=Path(args.runtime).resolve() if args.runtime else root/'dist/runtimes/v0.35.1'
        commands.append(('fixed-runtime-health',['-I','-B','-X','utf8',str(runtime/'mcp.py'),'--check']))
    elif args.runtime:
        commands.append(('fixed-runtime-health',['-I','-B','-X','utf8',str(Path(args.runtime).resolve()/'mcp.py'),'--check']))
    commands.append(('integrity-after',['-I','-X','utf8','-m','graph_research','protect','check']))
    results=[];passed=True
    print('报告目录：'+str(output),flush=True)
    for name,arguments in commands:
        start=time.monotonic();log=output/(name+'.log')
        print('运行：'+name,flush=True)
        try:
            with log.open('xb') as stream:
                result=subprocess.run([str(python),*arguments],cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT)
            code=result.returncode
        except OSError as error:
            with log.open('ab') as stream:stream.write((type(error).__name__+': '+str(error)).encode('utf-8'))
            code=2
        item={'name':name,'command':[str(python),*arguments],'returncode':code,'seconds':round(time.monotonic()-start,3),
              'log':log.name,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest()}
        results.append(item)
        (output/'commands.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
        print(name+'：退出码 '+str(code),flush=True)
        if code:passed=False;break
    summary={'format':'graph-research-external-validation/1','created_at':datetime.now(timezone.utc).isoformat(),
             'profile':args.profile,'passed':passed,'planned_commands':len(commands),'executed_commands':len(results),
             'unexecuted':[name for name,_ in commands[len(results):]],'results':results,
             'source_repaired':False,'dependencies_installed':False,'host_configuration_modified':False,
             'note':'首次失败即停止，未执行项不算通过；宿主agent自身的token不在本脚本计量范围。'}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=output.with_name(output.name+'.zip')
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as bundle:
        for path in output.iterdir():
            if path.is_file():bundle.write(path,path.name)
    with archive.with_suffix('.zip.sha256').open('x',encoding='utf-8') as stream:
        stream.write(hashlib.sha256(archive.read_bytes()).hexdigest()+'  '+archive.name+'\n')
    print(json.dumps({'passed':passed,'summary':str(output/'summary.json'),'archive':str(archive)},ensure_ascii=False),flush=True)
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
