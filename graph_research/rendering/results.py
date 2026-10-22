"""Read-only presentation of recorded results; no tools, models or network."""
import base64
from html import escape
import hashlib
from importlib.resources import files
import json
import math
from pathlib import PurePosixPath
import re
from urllib.parse import quote


TITLES={'combinatorial_plot':'格路径与棋盘绘图','graph_layout':'图布局与坐标调整',
        'graph_counterexample_round':'反例搜索轮次','graph_counterexample_verify':'反例独立核验',
        'graph_invariants':'图的基本信息','graph_spectrum':'普通图数值谱','generate_hypergraph':'超图构造',
        'weighted_graph_spectrum':'带权图矩阵与谱','graph_recipe':'参数化构图','hypergraph_path_analysis':'超图内部路分析','graph_batch_study':'批量图研究',
        'symbolic_analysis':'符号求和与级数','block_matrix_analysis':'分块与伴随块','graph_class_certificate':'广义线图证书','graph_energy_study':'精确能量比较','research_environment':'可选科研环境',
        'hypergraph_spectrum':'超图谱半径','graph_characteristic_polynomial':'图特征多项式','matching_polynomial':'匹配生成多项式',
        'matrix_analysis':'数值矩阵分析','exact_matrix_operation':'精确矩阵计算','quotient_matrix':'商矩阵',
        'polynomial_roots':'多项式实根','tensor_spectrum':'张量谱半径','tensor_operation':'张量操作',
        'tensor_charpoly':'张量特征多项式','hypergraph_tensor_charpoly':'超图张量特征多项式','combinatorial_calculation':'组合计算',
        'linear_recurrence':'线性递推','integer_linear_system':'整数线性方程','graph_edit':'图结构变换','graph_construction':'普通图构造','graph_symmetry':'图对称与商',
        'graph_spectral_analysis':'图谱分析','compare_graphs':'图比较','graph_enumeration':'图枚举',
        'hypergraph_structure':'超图结构分析','hypergraph_transform':'超图变换','hypergraph_quotient_spectrum':'超图对称约化',
        'directed_graph_spectrum':'有向图数值谱','hypergraph_plot':'超图结构图','hypergraph_editor':'交互布局',
        'hypergraph_tikz':'超图 TikZ','graph_tikz':'普通图 TikZ','hypergraph_schematic':'超图论文示意图'}
LABELS={'points':'路径坐标','endpoint':'路径终点','bounds':'矩形边界','fill':'填充矩形','row_labels':'行标签','column_labels':'列标签',
        'board':'可放车棋盘','fixed_vertices':'固定顶点','preview_status':'预览状态','warnings':'提示','total_steps':'路径总步数','right_steps':'向右步序号','side':'乘法侧',
        'group_order':'群阶','action_degree':'置换作用点数','arcs':'有向边','elements':'群元素编号表','latex':'LaTeX过程','matrices':'拆分矩阵','term_determinants':'各项行列式','original_determinant':'原行列式','laplacian_equations':'拉普拉斯张量特征方程','recurrence_order':'递推阶数','status':'求解状态','solution':'解','terms':'序列项','conditions':'成立条件','particular':'特解','kernel_basis':'整数零空间基','free_parameters':'自由整数参数','graph_spec':'可联动图参数','order':'顶点数','size':'边数','rank':'秩','rho':'谱半径','relative_residual':'相对残差',
        'case_count':'项目数','rows':'逐项研究结果','directed':'是否有向','hermitian':'是否厄米','degree_mode':'加权度约定','exact_matrix':'精确矩阵','max_relative_residual':'最大相对残差',
        'dominant_eigenvalue':'主模特征值','dominant_eigenvector':'主模特征向量','spectral_modulus_sum':'特征值模之和','graph_input':'完整带权输入','graph_type':'图类型','graph_spec_labels':'原顶点标签','hypergraph_spec':'可联动超图参数','construction_steps':'构图与断言记录','parameters':'参数',
        'spine_vertices':'有向路主干','edge_indices':'超边编号序列','path_edges':'路径超边','internal_loose_path':'是否内部松路','incidence_submatrix':'关联子矩阵','weighted_incidence_submatrix':'赋权关联子矩阵','violations':'结构违规','normalization':'归一化约定',
        'expression':'表达式','requested':'原始请求','result':'结果','truncated':'截断式','remainder':'余项','center':'展开中心','expansion_order':'展开阶数','export_errors':'导出失败说明','blocks':'矩阵分块','block_contributions':'分块乘积贡献','row_indices':'实际行索引','column_indices':'实际列索引','monic_polynomials':'首一多项式','verified':'证据是否通过复核',
        'states':'搜索状态数','generalized_line_graph':'是否广义线图','certificate':'证书','parameter':'研究参数','domain':'有限参数域','python':'Python版本','executable':'解释器','packages':'可选组件','tex_compilers':'TeX程序','three_dimensional_workflow':'三维工作流状态','tex_compilation_workflow':'编译工作流状态','next_steps':'接入要求',
        'iterations':'迭代次数','converged':'是否收敛','connected':'是否连通','bipartite':'是否二分图',
        'components':'连通分量','degrees':'度序列','degree_sequence':'度序列','shape':'形状','matrix':'矩阵',
        'spectrum':'特征值','eigenvalues':'特征值','determinant':'精确行列式','determinant_numeric':'数值行列式',
        'polynomial':'多项式','generating_polynomial':'生成多项式','perron_vector':'Perron向量',
        'weighted_incidence':'赋权关联矩阵','incidence':'关联矩阵','distances':'距离矩阵','diameter':'直径',
        'equitable':'是否等价划分','quotient':'商矩阵','quotient_spectrum':'商矩阵特征值','count':'数量',
        'energy':'图能量','estrada_index':'Estrada指数','original_rho':'原超图谱半径','quotient_rho':'商算子谱半径',
        'absolute_difference':'绝对差','original_residual':'原图相对残差','quotient_residual':'商算子相对残差',
        'isomorphic':'是否同构','cospectral':'是否同谱','non_induced_copies':'非诱导子图份数','uniform':'是否一致',
        'degree':'多项式次数','vertices':'顶点','nodes':'顶点','edges':'边表','pivot_columns':'主元列',
        'arithmetic':'运算类型','elapsed_seconds':'用时（秒）','alpha':'α','estimate_only':'是否仅估计规模',
        'alpha_equations':'α特征方程','matching_polynomial':'匹配多项式','coefficients_ascending':'系数（按升幂）',
        'matrix_type':'矩阵类型','positions':'布局坐标','edge_members':'超边成员','interpretation':'结构图说明',
        'tikz':'TikZ代码','requires':'使用说明','code_in_file':'代码是否写入文件'}
METRIC_KEYS=('group_order','action_degree','status','recurrence_order','rho','original_rho','quotient_rho','absolute_difference','relative_residual','rank','order','size','diameter',
             'determinant','determinant_numeric','degree','count','connected','bipartite','components','converged','equitable',
             'isomorphic','cospectral','energy','estrada_index','non_induced_copies','uniform','iterations')
EVIDENCE={'verified_execution':'执行记录已核验','legacy_record':'旧记录 · 缺少回执',
          'incomplete_evidence':'执行证据不完整','failed_call':'未计作成功结果'}


def display_value(value):
    if value is None:return '—'
    if type(value) is bool:return '是' if value else '否'
    if type(value) is float:return format(value,'.9g') if math.isfinite(value) else str(value)
    if isinstance(value,dict) and set(value)=={'real','imag'}:
        a,b=value['real'],value['imag']
        if type(a) in (int,float) and type(b) in (int,float):
            return display_value(a) if not b else display_value(a)+(' + ' if b>=0 else ' − ')+display_value(abs(b))+'i'
    return str(value)


def display_field(key,value):
    if key=='status' and isinstance(value,str):
        return {'solved':'有整数解','conditional':'需满足所列条件','no_solution':'无整数解',
                'recognized':'已识别并复核','not_generalized_line':'已证不是广义线图','indeterminate':'预算内未能判定','evaluated':'已求值','unevaluated':'保留未求值表达式','divergent':'发散或非有限结果','expanded':'已展开',
                'certified_finite_domain':'指定有限域已认证','partly_undetermined':'部分比较未能判定','detected':'环境检测完成','partial':'部分完成','failed':'失败','complete':'完成',
                'verified_closed_form':'闭式已校验','unverified_closed_form':'闭式尚未校验通过','terms_only':'已生成精确序列项，未找到闭式'}.get(value,value)
    return display_value(value)


def _json(value):return json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)
def _scalar(value):return value is None or isinstance(value,(str,int,float,bool)) or (isinstance(value,dict) and set(value)=={'real','imag'})
def _e(value):return escape(str(value),quote=True)


def display_error(error):
    text=re.sub(r'^(?:(?:RuntimeError|ValueError|TypeError|KeyError):\s*)+','',str(error))
    if text=='Edges must be pairs of vertex indices in range(n)':return '边的端点编号必须在 0 到 n−1 之间，请核对顶点编号与总顶点数。'
    return text


def terminal_result(observation):
    title=TITLES.get(observation.get('tool'),str(observation.get('tool','计算结果')))
    if observation.get('ok') is not True:return '【未完成】'+title+'\n'+display_error(observation.get('error','计算失败'))
    data=observation.get('result');lines=['','━ '+title+' ━']
    if not isinstance(data,dict):lines.append(_json(data)[:1200]);return '\n'.join(lines)
    keys=[k for k in METRIC_KEYS if k in data and _scalar(data[k])]
    if not keys:keys=[k for k,v in data.items() if _scalar(v) and k not in ('editor','note','operation')][:8]
    for key in keys:lines.append('  '+LABELS.get(key,key)+'：'+display_field(key,data[key]))
    for key,value in data.items():
        if key in keys or key in ('files','editor'):continue
        if isinstance(value,list) and value and all(isinstance(row,list) and all(_scalar(v) for v in row) for row in value):
            width=max(map(len,value));lines.append('  '+LABELS.get(key,key)+f'：{len(value)}行 × {width}列')
            for row in value[:6]:lines.append('    '+'  '.join(display_value(v) for v in row[:8]))
            if len(value)>6 or width>8:lines.append('    …（此处为预览，完整矩阵见结果页和JSON）')
        elif key=='shape' and isinstance(value,list):lines.append('  形状：'+' × '.join(str(v) for v in value))
        elif isinstance(value,list) and all(_scalar(v) for v in value):
            text='，'.join(display_value(v) for v in value[:10]);lines.append('  '+LABELS.get(key,key)+'：'+text+(' …' if len(value)>10 else ''))
        elif key=='tikz':lines.append('  TikZ代码：已保存，结果页可展开或下载')
        elif isinstance(value,str):lines.append('  '+LABELS.get(key,key)+'：'+value[:500]+(' …' if len(value)>500 else ''))
        elif _scalar(value):lines.append('  '+LABELS.get(key,key)+'：'+display_field(key,value))
        elif key not in ('execution',):lines.append('  '+LABELS.get(key,key)+'：已保存，结果页可查看详情')
        if len(lines)>24:lines.append('  其他字段已保存在完整数据中。');break
    if data.get('files'):lines.append('  输出文件：'+'、'.join(str(k) for k in data['files']))
    if data.get('editor'):lines.append('  布局编辑器：已生成，可从结果页打开')
    lines.append('  数值按展示格式显示；完整精度保存在JSON中。')
    return '\n'.join(lines)


def _matrix(value):
    return isinstance(value,list) and bool(value) and all(isinstance(row,list) and bool(row) and all(_scalar(v) for v in row) for row in value) and len({len(row) for row in value})==1


def _table(value):
    rows,cols=len(value),len(value[0]);shown_rows=min(rows,12);shown_cols=min(cols,12)
    html=['<div class="table-note">'+str(rows)+' 行 × '+str(cols)+' 列 · 行列索引从 0 开始'+(' · 当前仅预览前 12 行 / 列' if rows>12 or cols>12 else '')+'</div>',
          '<div class="table-scroll"><table class="matrix"><thead><tr><th scope="col">索引</th>']
    html.extend('<th scope="col">'+str(i)+'</th>' for i in range(shown_cols));html.append('</tr></thead><tbody>')
    for index,row in enumerate(value[:shown_rows]):
        html.append('<tr><th scope="row">'+str(index)+'</th>')
        html.extend('<td title="'+_e(display_value(v) if not isinstance(v,float) else repr(v))+'">'+_e(display_value(v))+'</td>' for v in row[:shown_cols]);html.append('</tr>')
    html.append('</tbody></table></div>');return ''.join(html)


def _vector(value):
    cells=['<div class="table-note">左侧为数据索引，右侧为数值</div><div class="value-list">']
    for i,item in enumerate(value[:24]):cells.append('<div><span class="index">#'+str(i)+'</span><span title="'+_e(item)+'">'+_e(display_value(item))+'</span></div>')
    cells.append('</div>')
    if len(value)>24:cells.append('<p class="muted">仅预览前 24 项，共 '+str(len(value))+' 项。完整数据可下载。</p>')
    return ''.join(cells)


def _spectrum(value):
    points=[]
    for item in value[:80]:
        if type(item) in (int,float):real,imag=item,0
        elif isinstance(item,dict) and set(item)=={'real','imag'}:real,imag=item['real'],item['imag']
        else:return ''
        if type(real) not in (int,float) or type(imag) not in (int,float):return ''
        try:
            if not math.isfinite(real) or not math.isfinite(imag):return ''
        except OverflowError:return ''
        points.append((real,imag))
    if not points:return ''
    xmin,xmax=min(p[0] for p in points),max(p[0] for p in points);ymin,ymax=min(p[1] for p in points),max(p[1] for p in points)
    complex_plane=any(y for _,y in points)
    sx=max(abs(xmin),abs(xmax),1);sy=max(abs(ymin),abs(ymax),1)
    dx=xmax/sx-xmin/sx or 1;dy=ymax/sy-ymin/sy or 1
    html=['<div class="spectrum-chart"><svg viewBox="0 0 640 170" role="img" aria-label="'+('复特征值分布预览' if complex_plane else '实特征值分布预览')+'">',
          '<line class="chart-axis" x1="42" y1="130" x2="600" y2="130"/>']
    if complex_plane:html.append('<line class="chart-axis" x1="42" y1="25" x2="42" y2="130"/>')
    for real,imag in points:
        x=42+558*(real/sx-xmin/sx)/dx if xmax!=xmin else 321
        y=130-100*(imag/sy-ymin/sy)/dy if complex_plane and ymax!=ymin else 88
        html.append(f'<circle class="spectrum-dot" cx="{x:.3f}" cy="{y:.3f}" r="5"><title>'+_e(display_value({'real':real,'imag':imag}))+'</title></circle>')
    html.extend(['<text x="42" y="154">'+_e(display_value(xmin))+'</text>',
                 '<text x="600" y="154" text-anchor="end">'+_e(display_value(xmax))+'</text>',
                 '<text x="320" y="154" text-anchor="middle">实部</text>'])
    if complex_plane:html.append('<text x="45" y="17">虚部 '+_e(display_value(ymin))+' … '+_e(display_value(ymax))+'</text>')
    html.append('</svg><div class="table-note">特征值分布预览'+(' · 仅展示前 80 项' if len(value)>80 else '')+'；重合点可能覆盖，完整值见下表或JSON。</div></div>')
    return ''.join(html)


def _href(path,prefix):
    if not isinstance(path,str) or not path.startswith(prefix) or '\\' in path or ':' in path or any(ord(ch)<32 for ch in path):return None
    if any(part in ('','..','.') for part in path.split('/')):return None
    return quote(path,safe='/')


def _fields(data,media=''):
    if not isinstance(data,dict):return media+'<pre class="code">'+_e(_json(data)[:5000])+'</pre>'
    parts=[];metrics=[k for k in METRIC_KEYS if k in data and _scalar(data[k])]
    if not metrics:metrics=[k for k,v in data.items() if _scalar(v) and len(str(v))<=64 and k not in ('editor','note','operation','polynomial','generating_polynomial','tikz','code_in_file')][:8]
    if metrics:
        parts.append('<div class="result-metrics">')
        for key in metrics:parts.append('<div><span>'+_e(LABELS.get(key,key))+'</span><strong title="'+_e(data[key])+'">'+_e(display_field(key,data[key]))+'</strong></div>')
        parts.append('</div>')
    parts.append(media)
    for key,value in data.items():
        if key in metrics or key in ('files','editor','code_in_file'):continue
        title=_e(LABELS.get(key,key));body=''
        if key=='shape' and isinstance(value,list):body='<p class="scalar">'+_e(' × '.join(str(v) for v in value))+'</p>'
        elif key=='tikz' and value is None:body='<p class="muted">完整代码保存在上方的.tex文件中。</p>'
        elif key in ('tikz','positions','edge_members'):
            text=value if isinstance(value,str) else _json(value)
            body='<details class="nested"><summary>查看'+title+'</summary><pre class="code">'+_e(text[:6000])+'</pre>'+('<p class="muted">预览已截断，完整数据见原始结果。</p>' if len(text)>6000 else '')+'</details>'
        elif key=='interpretation' and isinstance(value,str) and value.startswith('Members lie ON each unfilled curve'):
            body='<p class="muted">成员顶点位于超边曲线上；曲线内部或未标记的交叉点不表示关联。</p>'
        elif key=='requires' and value=='TikZ; Chinese labels use XeLaTeX with ctex. No TeX runtime is needed to export.':
            body='<p class="muted">导出无需安装TeX；编译需要TikZ，含中文标签的文档可使用XeLaTeX与ctex。</p>'
        elif _matrix(value):body=_table(value)
        elif isinstance(value,list) and value and all(_scalar(v) for v in value):
            body=(_spectrum(value) if key in ('spectrum','eigenvalues','quotient_spectrum') else '')+_vector(value)
        elif isinstance(value,str):
            text=_e(value[:6000])
            if 'polynomial' in key:
                text=re.sub(r'\*\*([0-9]+)',r'<sup>\1</sup>',text)
                text=re.sub(r'(?<!\*)\*(?!\*)',' · ',text)
            body='<pre class="'+('expression' if 'polynomial' in key else 'code')+'">'+text+(' …（显示已截断）' if len(value)>6000 else '')+'</pre>'
        elif _scalar(value):body='<p class="scalar">'+_e(display_value(value))+'</p>'
        else:body='<details class="nested"><summary>展开结构化内容</summary><pre class="code">'+_e(_json(value)[:6000])+'</pre><p class="muted">此处最多预览 6000 字符；完整数据见原始结果。</p></details>'
        parts.append('<div class="field"><h4>'+title+'</h4>'+body+'</div>')
    return ''.join(parts)


def _artifacts(call):
    parts=[];seen=set()
    for path in call.get('artifacts',[]):
        href=_href(path,'artifacts/')
        if href is None:continue
        file=PurePosixPath(path);suffix=file.suffix.lower();stem=str(file.with_suffix(''))
        if suffix in ('.png','.svg') and stem not in seen:
            parts.append('<figure class="artifact-image"><img loading="lazy" src="'+href+'" alt="'+_e(file.name)+'"><figcaption>'+_e(file.name)+'</figcaption></figure>');seen.add(stem)
        label='打开布局编辑器' if suffix=='.html' else '下载 '+file.name
        if file.name in ('hypergraph.tex','graph.tex'):label='下载完整 LaTeX 文档'
        elif file.name in ('hypergraph-tikz.tex','graph-tikz.tex'):label='下载 TikZ 片段'
        parts.append('<a class="file-link" href="'+href+'" target="_blank" rel="noopener"'+(' download' if suffix!='.html' else '')+'><span>'+_e(label)+'</span><small>'+_e(suffix.lstrip('.').upper() or 'FILE')+'</small></a>')
    return '<div class="field"><h4>图形与文件</h4>'+''.join(parts)+'</div>' if parts else ''


def render_result_report(data,labels=None):
    labels=labels or {};summary=data['summary'];calculations=data['calculations'];content=[];nav=[]
    batch=data.get('batch_workflow')
    if batch:
        titles={'success':'成功','failed':'失败','partial':'部分成功','pending':'待执行','running':'执行中','skipped':'跳过','paused':'暂停'}
        aliases=list(batch['output_definitions']);headers='<th>案例</th><th>状态</th>'+''.join('<th>'+_e(name)+'</th>' for name in aliases)
        rows=[]
        for row in batch['rows']:
            cells=['<td>'+_e(row['case_id'])+'</td>','<td>'+_e(titles.get(row['status'],row['status']))+'</td>']
            for alias in aliases:
                output=row['outputs'][alias]
                value=output['value'] if 'value' in output else '完整数据见 '+output['call_id'] if output['status']=='available' else '未取得结果'
                cells.append('<td>'+_e(str(value))+'</td>')
            rows.append('<tr>'+''.join(cells)+'</tr>')
        counts=batch['counts']
        content.append('<article class="result-card" id="batch-overview"><header class="card-heading"><h3>批量工作流汇总</h3></header><p>'+str(counts['success'])+' 步成功 · '+str(counts['failed'])+' 步失败 · '+str(counts['skipped'])+' 步跳过</p><div class="table-wrap"><table><thead><tr>'+headers+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div><div class="call-actions"><a href="batch-results.csv" download>下载汇总CSV</a><a href="batch-summary.json" download>步骤状态与结果定位</a><a href="batch-plan.json" download>批量输入与计划</a></div></article>')
    for index,call in enumerate(calculations):
        anchor='result-'+str(index);success=call['status']=='success';state='success' if success else 'failed'
        title=TITLES.get(call['tool'],call['tool']);identifier=call['id']
        nav.append('<a class="result-nav" data-status="'+state+'" href="#'+anchor+'"><span class="nav-dot '+state+'"></span><span>'+_e(title)+'<small>'+_e(identifier)+'</small></span></a>')
        evidence=call.get('evidence_status','legacy_record')
        content.append('<article class="result-card" id="'+anchor+'" data-status="'+state+'" data-search="'+_e(title+' '+call['tool']+' '+identifier)+'"><header class="card-heading"><div><span class="eyebrow">第 '+str(call['turn'])+' 轮 · '+_e(identifier)+'</span><h3>'+_e(title)+'</h3><code>'+_e(call['tool'])+'</code></div><span class="badge '+state+'">'+('计算成功' if success else '计算失败')+'</span></header>')
        content.append('<div class="evidence '+('verified' if evidence=='verified_execution' else 'attention')+'">'+_e(EVIDENCE.get(evidence,evidence))+'</div>')
        if call.get('tool_status')=='fixture_tested_experimental':content.append('<p class="call-notice">实验工具，仅通过登记的验收样例，需要独立复核。</p>')
        if call.get('reused_execution'):content.append('<p class="call-notice">复用已核验的相同输入结果，本条记录未重新计算。</p>')
        if success:content.append(_fields(call.get('result'),_artifacts(call)))
        else:content.append('<div class="error-box"><strong>此次调用未完成</strong><pre>'+_e(display_error(call.get('error','没有返回有效计算结果')))+'</pre><p>此前成功的计算仍然保留。</p></div>')
        if call.get('graph_inputs'):
            from graph_research.graph_input.adapters import mapping_summary
            links=''.join('<a class="file-link" download href="calls/'+_e(identifier)+'/input-graph-'+str(i)+'.json">下载原始输入图 '+str(i)+'</a>' for i in range(1,len(call['graph_inputs'])+1))
            content.append('<details class="raw-data"><summary>输入图与顶点编号对照</summary><pre class="code">'+_e(mapping_summary(call['graph_inputs']))+'</pre>'+links+'</details>')
        if re.fullmatch(r'calc-[0-9]{4,}',identifier):
            prefix='calls/'+identifier+'/'
            content.append('<div class="call-actions"><a href="'+prefix+'arguments.json" download>下载输入参数</a><a href="'+prefix+('result.json' if success else 'error.json')+'" download>下载'+('原始结果' if success else '错误记录')+'</a></div>')
        content.append('<details class="raw-data"><summary>输入参数与完整原始记录</summary><pre class="code">'+_e(_json(call))+'</pre></details></article>')
    if not calculations:content.append('<div class="empty-state"><h3>本次只有分析记录</h3><p>尚无实际工具计算结果。可在下方查看请求与回答。</p></div>')
    turns=[]
    for turn in data['turns']:
        turns.append('<details class="turn-context"><summary><span>第 '+str(turn['number'])+' 轮 · '+_e(labels.get(turn['status'],turn['status']))+'</span><small>查看请求与回答</small></summary><div><h4>用户请求</h4><pre class="code">'+_e(turn['user_request'])+'</pre><h4>本轮回答</h4><pre class="code">'+_e(turn['answer'])+'</pre>')
        if turn.get('legacy_conversation'):turns.append('<h4>旧版历史问答</h4><pre class="code">'+_e(_json(turn['legacy_conversation']))+'</pre>')
        if turn.get('plan'):
            from graph_research.assistant.planning import plan_text
            turns.append('<h4>任务计划</h4><pre class="code">'+_e(plan_text(turn['plan']))+'</pre>')
        if turn.get('workflow_usage'):
            usage=turn['workflow_usage'];turns.append('<h4>任务累计用量</h4><p>模型请求 '+str(usage.get('model_calls',0))+' 次；计算尝试 '+str(usage.get('tool_calls',0))+' 次；未知用量请求 '+str(usage.get('unknown_usage_requests',0))+' 次。金额按配置单价估算，未知不计为零。</p>')
        for claim in turn.get('claims',[]):
            from graph_research.assistant.claims import claim_text
            turns.append('<h4>结论与依据</h4><pre class="code">'+_e(claim_text(claim))+'</pre>')
            for source in claim.get('sources',[]):
                target=next((i for i,c in enumerate(calculations) if c.get('observation_index')==source.get('observation')),None)
                if source.get('verified_execution') and target is not None:turns.append('<p><a href="#result-'+str(target)+'">查看对应计算与原始结果</a> · 字段 '+_e(_json(source.get('path',[])))+'</p>')
        if turn.get('development_brief'):turns.append('<h4>独立开发说明</h4><a download href="development-briefs/turn-'+str(turn['number'])+'.json">下载完整范围与验收依据</a>')
        turns.append('</div></details>')
    warnings=''.join('<div class="notice">'+_e(warning)+'</div>' for warning in data.get('warnings',[]))
    template=files('graph_research').joinpath('assets/result_report.html').read_text(encoding='utf-8')
    script=re.search(r'<script id="report-ui">([\s\S]*?)</script>',template).group(1)
    digest=base64.b64encode(hashlib.sha256(script.encode('utf-8')).digest()).decode('ascii')
    replacements={'NAV':''.join(nav),'CONTENT':''.join(content),'TURNS':''.join(turns),'WARNINGS':warnings,
                  'SUCCESS':str(summary['successful_calls']),'FAILED':str(summary['failed_calls']),'VERIFIED':str(summary['verified_calls']),
                  'ARTIFACTS':str(summary['artifact_count']),'COUNT':str(len(calculations)),'TURN_COUNT':str(summary['turn_count']),
                  'STATUS':_e(labels.get(summary['record_status'],summary['record_status'])),
                  'EXPORTED':_e(data['exported_at'].replace('T',' ')[:19]+' UTC'),'BUNDLE_ID':_e(data['bundle_id'][:12]),'SCRIPT_HASH':digest}
    # One pass: user-provided text resembling a template token remains text.
    return re.sub(r'\{\{([A-Z_]+)\}\}',lambda m:replacements.get(m.group(1),m.group(0)),template)
