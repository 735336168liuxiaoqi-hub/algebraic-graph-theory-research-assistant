"""Read-only optional capability discovery: no installation or process launch."""
from importlib.util import find_spec
from importlib.metadata import version,PackageNotFoundError
import shutil
import sys


def research_environment():
    """Report discoverability, not a successful renderer/compiler smoke test."""
    packages=[]
    for module,distribution,purpose in [('matplotlib','matplotlib','二维图及显式三维曲面绘图组件'),('skimage','scikit-image','三维隐式曲面的marching-cubes提取组件'),('scipy','scipy','可选数值算法组件')]:
        present=find_spec(module) is not None
        try:installed=version(distribution) if present else None
        except PackageNotFoundError:installed=None
        packages.append({'module':module,'installed':present,'version':installed,'purpose':purpose})
    compilers=[{'name':name,'path':shutil.which(name),'detected':shutil.which(name) is not None} for name in ('tectonic','xelatex','lualatex','pdflatex')]
    return {'status':'detected','python':sys.version.split()[0],'executable':sys.executable,'packages':packages,'tex_compilers':compilers,
            'three_dimensional_workflow':'assessment_only','tex_compilation_workflow':'assessment_only',
            'interpretation':'仅检查当前Python包及PATH中的编译器；发现程序不等于已成功编译。未安装、下载、启动编译器或接入远程服务。已有PNG/SVG/PDF结构图和TikZ源码导出可独立使用。',
            'next_steps':['三维隐式面需要明确等值面、采样区域、分辨率和内存上限，再接入网格提取及导出。','TeX编译需用户自行选择独立运行时；后续应隔离工作目录、禁用shell-escape、限制时间并核验输出。','Windows安装器开发继续搁置。']}
