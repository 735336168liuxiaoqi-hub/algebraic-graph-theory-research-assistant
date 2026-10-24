"""Read-only runtime identity; never read credentials or contact a service."""
import importlib.metadata as metadata
import os
from pathlib import Path
import platform
import sys

from graph_research import __version__


def environment_report():
    import graph_research
    package=Path(graph_research.__file__).resolve()
    distributions=[{'version':dist.version,'location':str(dist.locate_file('').resolve())}
                   for dist in metadata.distributions()
                   if (dist.metadata.get('Name') or '').lower().replace('_','-')=='graph-research-assistant']
    versions=sorted({item['version'] for item in distributions})
    environment=Path(sys.prefix).resolve();configuration=environment/'pyvenv.cfg'
    inherited=None
    if configuration.is_file():
        values=dict(line.split('=',1) for line in configuration.read_text(encoding='utf-8').splitlines() if '=' in line)
        inherited=next((value.strip().lower()=='true' for key,value in values.items() if key.strip()=='include-system-site-packages'),None)
    issues=[];warnings=[]
    if not distributions:issues.append('未安装当前项目，请在目标环境安装本项目。')
    elif versions!=[__version__]:issues.append('源码版本与安装信息不一致，请在目标环境重新安装本项目。')
    if sys.version_info<(3,11):issues.append('本程序需要Python 3.11或更高版本。')
    if inherited:warnings.append('当前虚拟环境继承了全局包，请留意依赖来源。')
    integration={'pythonpath_present':bool(os.environ.get('PYTHONPATH')),
                 'sitecustomize_loaded':'sitecustomize' in sys.modules,'usercustomize_loaded':'usercustomize' in sys.modules,
                 'protected_execution':'not_probed'}
    if integration['sitecustomize_loaded'] or integration['usercustomize_loaded']:
        warnings.append('当前Python加载了宿主定制模块；若文件写入或受保护启动受阻，请保留原错误及宿主诊断，不自动禁用定制模块。')
    source=package.parent.parent
    project_environment=(source/'.venv').resolve() if (source/'pyproject.toml').is_file() else None
    kind='conda' if (environment/'conda-meta').is_dir() else 'venv' if sys.prefix!=sys.base_prefix else 'system'
    return {'ok':not issues,'package_version':__version__,'package_file':str(package),'python_executable':sys.executable,
            'python_version':platform.python_version(),'environment':str(environment),'base_environment':sys.base_prefix,
            'is_virtual_environment':sys.prefix!=sys.base_prefix,'environment_kind':kind,'inherits_system_packages':inherited,
            'uses_project_environment':environment==project_environment if project_environment is not None else None,
            'installed_versions':versions,'distributions':distributions,'platform':sys.platform,'host_integration':integration,'issues':issues,'warnings':warnings}
