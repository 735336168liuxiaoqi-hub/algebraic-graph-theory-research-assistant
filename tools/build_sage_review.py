"""Build a Chinese, per-definition review from the preserved baseline and catalog."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def _route(row):
    name=row['symbol'];file=row['source_file']
    if name.startswith('MyIdentity') or name=='my_print':return 'symbolic_analysis已提供受控符号求和及LaTeX，保留条件、未求值与发散状态；不复刻旧状态对象。'
    if name=='MyPowerSeries':return 'symbolic_analysis已提供Taylor/Laurent局部展开、O项及截断式；不使用原eval和隐式幂级数环。'
    if file=='MyTools.sage':return '已有显式文本矩阵解析；原函数的自动读剪贴板和符号求值副作用未移植。'
    if name=='Tensor.__call__':return '原数组不可调用；现有Tensor方括号索引和array可取元素，不编造额外调用语义。'
    if name.startswith('TCBSpline'):return '现有NumPy/Matplotlib hyperedge_path已覆盖TCB闭合超边曲线；旧类和开曲线采样接口尚未兼容。'
    if name in ('Latex2Image','Graph2Image','latex_draw','Graph2TeX','GraphList2TeX','GL2TeX'):return '现有TikZ源码及graph_batch_study多图PNG/SVG/PDF导出覆盖主要出图用途；research_environment仅检测TeX，完整文档自动编译仍未接入。'
    if name in ('gline_graph_forbidden_subgraphs','is_gline_graph'):return 'graph_class_certificate已提供≤10顶点的广义线图精确覆盖判定、正证书和可重放负证书；预算耗尽为未判定，不复刻旧禁图列表接口。'
    if name.startswith('De_subdivide') or name=='energy_polynomial':return '图能量差已可直接计算；graph_energy_study提供有限参数域的精确根区间比较及复核。不迁移旧积分路线，特定积分公式及无限域证明另议。'
    if name in ('HyperTree1','U1','U2','LinkG'):return 'graph_recipe提供参数化超图组合、结构选根和结构断言；按结构定义研究图族，不沿用旧U1/U2固定编号或假定同名等价。'
    if name in ('HyperG.edge_coloring',):return '原函数仅返回空字典；需明确着色定义并新增算法，不能把占位结果当已实现。'
    if name=='WeigthedIncidenceMatrixForQuotientGraph':return '已有轨道商算子Quotient_Graph；旧代表超图与当前算子不是相同对象，不伪造等价别名。'
    if name.startswith('Jordan_'):return 'block_matrix_analysis已提供多项式伴随块对角构造并验证特征多项式乘积；不误用Jordan分解，未复刻旧返回对象。'
    if name.startswith('bk_rop'):return 'block_matrix_analysis已提供显式块尺寸的提取、排列和分块乘积贡献；不要求旧Sage分块元数据对象。'
    if name in ('subdivide','subdivide1','perm_block'):return '已有基础分块/商矩阵，block_matrix_analysis另提供统一精确入口；旧分块对象和个别归一化接口不逐项兼容。'
    if name in ('add_blossom','Merge_And_Append_Edge'):return 'NetworkX多重图可表达；当前主要谱入口要求简单图，须另定自环/重边约定后接入。'
    if name in ('plotequs','plot3dequs','movelines'):return 'research_environment检测可选组件及TeX，接入边界见RESEARCH_WORKFLOWS.md；完整隐式绘图和移动直线仍不在本轮实现范围。'
    if name in ('list2dtopanda','Table','htmlview','table_add'):return '现有原生数据表和结果包覆盖基本展示；旧Pandas Styler/Sage表格接口仍不同。'
    if name=='variable_name':return '对象可能有多个变量别名；现用显式名称，不承诺由对象唯一反查变量。'
    if file=='LinearAlgebra.sage':return '现有SymPy基础运算可组合使用；旧演示排版接口尚未等价适配。'
    if file=='GraphTheory.sage' or file.startswith('hypergraph_'):return '现有结构图、坐标编辑及TikZ覆盖部分用途；旧布局/标签/富显示对象或特定接口未完全兼容。'
    return '现有绘图与结果包覆盖基本显示；旧Sage.Graphics、HTML或对象协议仍需单独适配。'


def _completed_note(row):
    name=row['symbol']
    if name=='edge' or name.startswith('edge.'):return '复用既有边容器；顶点元组不可变，超图边权仅支持正实数。普通图负权/复权改用NetworkX。'
    if name in ('edge2graph','replace_edges_by_graph'):return '识别替换端点、隔离内部顶点、保留孤立点；图结构变换工具提供单边替换，Python接口还可批量替换。'
    if name in ('getGridPath','gridPath','lattice_path','rectangle','chess_board'):return '返回Matplotlib Figure；可选绘图依赖。棋盘的矩形行列标签错误已修正。'
    if name=='getCycleIndex1':return '保留旧分拆指数编码；不是标准循环指标，不用于Pólya计数。仅Python库入口。'
    if name=='getCycleIndex':return '对完整有限置换群求标准循环指标；已接组合计算工具。'
    if name=='cayley_graph':return '支持左右/双侧及有限半群；桌面入口使用右侧简单有向图，原值和方向保留。'
    if name in ('set_edge_weight','weight_edges','complex_weight'):return '默认复制或返回数值矩阵；不隐式改动原图。set_edge_weight可显式copy=False；原无权谱工具不会自动读取这些权重。'
    if name in ('HyperG.add_star','HyperG.add_stars'):return '保留原权重和孤立点，新边权为1；共享根集，不是附接链式路径。已接超图变换工具。'
    if name=='HyperG.eigenVfun':return '非空一致超图；返回SymPy列向量，生成L张量方程而不求解。已接结构工具。'
    if name=='polynomials_for_addstarsgraph':return '无权简单图L/Q的精确Schur表达式；拒绝旧代码不正确的A分支。'
    if row['source_file']=='LinearAlgebra.sage':return '返回SymPy矩阵、DomainMatrix或显式LaTeX；不调用Sage显示。行列变换和行列式拆行已接精确矩阵工具。'
    if name=='random_symmetric_matrix':return '返回NumPy整数对称数组，区间两端均包含；可固定局部随机种子。'
    return '使用NetworkX/NumPy/SymPy明确返回结果；复制输入，保留孤立点。详细限制见函数说明。'


def build():
    baseline=json.loads((ROOT/'docs/sage-pending-baseline-v0211.json').read_text(encoding='utf-8'))
    catalog=json.loads((ROOT/'docs/provenance/migration_catalog.json').read_text(encoding='utf-8'))
    key=lambda row:(row['source_file'],row['symbol'],row['line'])
    original={key(row):row for row in baseline['definitions']}
    corrections={key(row):row for row in baseline.get('review_corrections',[])}
    current={key(row):row for row in catalog['definitions']}
    completed=[{**original[k],'native_module':current[k]['native_module'],'native_symbol':current[k]['native_symbol'],
                'validation_scope':current[k]['validation_scope']} for k in original if current[k]['status']=='native_implementation_available']
    pending=[]
    for row in catalog['definitions']:
        if row['status']!='pending':continue
        reviewed=original.get(key(row)) or corrections.get(key(row))
        if reviewed is None:raise ValueError('Missing reviewed description: '+str(key(row)))
        pending.append({**reviewed,'alternative_or_limit':_route(reviewed)})
    result={'baseline_version':'0.21.1','baseline_pending':len(original),'newly_available_records':len(completed),
            'corrected_false_available_records':len(corrections),'remaining_pending':len(pending),
            'remaining':pending,'completed':completed}
    text=['# 旧Sage接口追溯台账（v0.23）','',
          '验收标准见[科研能力覆盖表](FUNCTIONAL_COVERAGE.md)：整体科研用途能够完成即可，不要求逐项迁移旧函数。以下仅保留源码追溯，不作为功能缺口数量或开发待办。','',
          f'追溯统计：原有{len(original)}条待适配定义；补齐/复用{len(completed)}条，并修正{len(corrections)}条旧目录误判，现有{len(pending)}条旧定义尚未逐项适配。这不等于仍缺{len(pending)}项科研功能。',
          '定义记录包括类、方法及两份超图文件中的同用途定义，不等于独立算法数。GraphTheory1.sage的165条完整重复定义单独记录，不算剩余功能。','',
          '本批仅复用现有NetworkX、SymPy、NumPy及可选Matplotlib，没有新增安装依赖。详细新接口、调用示例与限制见[替代功能说明](PACKAGE_REPLACEMENTS.md)。','',
          '## 尚未逐项兼容的旧接口（仅供追溯）','']
    for file in catalog['source_files']:
        rows=[row for row in pending if row['source_file']==file['file']]
        if not rows:continue
        text += ['','### '+file['file']+f'（{len(rows)}条）','','| 旧定义（原行号） | 功能 | 现有替代与剩余限制 |','| --- | --- | --- |']
        text += [f"| `{row['symbol']}`（{row['line']}） | {row['meaning']} | {row['alternative_or_limit']} |" for row in rows]
    text += ['','## 本轮已经补齐或复用的定义','','以下是Python库适配，不声称完整复刻Sage类型与所有参数；只有工具目录中的名称可供模型直接调用。',
             '','| 原定义 | 功能 | 新Python入口 | 适配范围 |','| --- | --- | --- | --- |']
    for row in completed:
        text.append(f"| `{row['source_file']}:{row['line']} {row['symbol']}` | {row['meaning']} | `{row['native_module']}.{row['native_symbol']}` | {_completed_note(row)} |")
    text += ['','## 清单修正','',
             '缺失类不能因为None对象本身有__init__/__repr__就标为可用。MyIdentity.__init__、MyIdentity.__repr__及TCBSpline.__init__已恢复待迁移状态；所有可用记录现在逐个验证真实模块路径可调用。',
             '','源码提取现在跨过多行字符串中的TeX内容，并保留带字符串默认参数的真实函数；不执行旧Sage源码。原始11个文件未修改。',
             '','替换前的完整180条基线保存在[JSON](docs/sage-pending-baseline-v0211.json)，本报告的机器可读结果见[审计JSON](docs/sage-replacement-review.json)。']
    return result,'\n'.join(text)+'\n'


def main():
    result,text=build()
    (ROOT/'SAGE_REMAINING_REVIEW.md').write_text(text,encoding='utf-8')
    (ROOT/'docs/sage-replacement-review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:result[key] for key in ('baseline_pending','newly_available_records','corrected_false_available_records','remaining_pending')}))


if __name__=='__main__':main()
