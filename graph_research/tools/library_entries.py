"""Reviewed JSON adapters for existing Python drawing and layout capabilities."""
import json
from pathlib import Path
import uuid

import numpy as np


def _save_figure(figure, stem):
    from graph_research.runtime.storage import safe_path, staged_file
    output = safe_path(Path.cwd()/'outputs'/'combinatorial-plots'/uuid.uuid4().hex)
    output.mkdir(parents=True)
    paths = {}
    try:
        for extension in ('png', 'svg', 'pdf'):
            path = output/f'{stem}.{extension}'
            with staged_file(path) as temporary:
                figure.savefig(temporary, dpi=160, bbox_inches='tight', facecolor='white')
            paths[extension] = str(path.resolve())
    finally:
        figure.clear()
    return paths


def combinatorial_plot(operation='grid_path', steps=None, total_steps=6, right_steps=None,
                       matrix=None, bounds=None, fill=True, row_labels=None, column_labels=None):
    """Save existing lattice/rectangle/board Figures; accept only explicit data."""
    from graph_research.rendering import lattice
    from graph_research.rendering.fonts import label_font_families
    from matplotlib import rc_context
    result = {'operation':operation}
    if operation == 'grid_path':
        if steps is None or len(steps) > 2048:
            raise ValueError('格路径需要steps，由至多2048个0/1组成；0向上，1向右。')
        figure, points = lattice.gridPath(steps, withPoints=True)
        result.update(points=points, steps=list(steps), endpoint=points[-1])
    elif operation == 'lattice_path':
        if type(total_steps) is not int or not 0 <= total_steps <= 2048 or right_steps is None:
            raise ValueError('需提供0..2048总步数和右移步序号right_steps（可为空）。')
        figure, points = lattice.lattice_path(total_steps, right_steps, withPoints=True)
        result.update(points=points, total_steps=total_steps, right_steps=list(right_steps), endpoint=points[-1])
    elif operation == 'rectangle':
        if bounds is None or len(bounds) != 4:
            raise ValueError('矩形需填写bounds=[最小x,最小y,最大x,最大y]。')
        figure = lattice.rectangle(*bounds, f=fill)
        result.update(bounds=list(bounds), fill=fill)
    elif operation == 'chessboard':
        board = np.asarray(matrix, dtype=float)
        if board.ndim != 2 or not all(board.shape) or max(board.shape) > 32 or not np.isfinite(board).all():
            raise ValueError('棋盘需要非空有限数值矩阵，每维最多32；非零格着色，零格留白。')
        figure = lattice.chess_board(board, lambda i,j: '#dbeafe' if board[i,j] != 0 else 'white',
                                     row_label=row_labels, col_label=column_labels)
        result.update(matrix=board.tolist(), shape=list(board.shape),
                      row_labels=list(range(board.shape[0])) if row_labels is None else row_labels,
                      column_labels=list(range(board.shape[1])) if column_labels is None else column_labels)
        font = label_font_families(' '.join(map(str, result['row_labels'] + result['column_labels'])))
        for text in figure.axes[0].get_xticklabels() + figure.axes[0].get_yticklabels():
            text.set_fontfamily(font)
        result['interpretation'] = '行号沿y轴自下向上，列号沿x轴自左向右；非零格着色，零格留白。'
    else:
        raise ValueError('未知组合绘图操作。')
    # Labels are literal data; do not let a user's rcParams invoke TeX.
    with rc_context({'text.usetex':False}):
        for text in figure.findobj(match=lambda artist: hasattr(artist, 'set_parse_math')):
            text.set_parse_math(False)
            text.set_usetex(False)
        result['files'] = _save_figure(figure, operation)
    return result


def graph_layout(operation='spring', kind='path', n=5, edges=None, positions=None,
                  fixed_vertices=None, vertices=None, root=0, iterations=150, seed=42,
                  angle=0, scale=1, offset=None,graph_document=None):
    """Expose bounded layouts with preview and reusable JSON coordinates."""
    from graph_research.graphs import make_graph
    from graph_research.rendering.layouts import graph_layout_positions
    from graph_research.rendering.plotting import hypergraph_plot_tool
    from graph_research.runtime.storage import atomic_text, safe_path
    graph = None if graph_document is not None else make_graph(kind, n, edges)
    drawing_document=None
    if graph_document is not None:
        from graph_research.graph_input.document import GraphDocument
        drawing_document=GraphDocument(graph_document)
        index={v:i for i,v in enumerate(drawing_document.vertices)}
        numbered=[[index[v] for v in e['vertices']] for e in drawing_document.edges]
        if drawing_document.graph_type!='graph' or kind!='edges' or n!=drawing_document.order or numbered!=list(map(list,edges or [])):raise ValueError('完整图对象与布局结构参数不一致。')
        stored=drawing_document.to_dict().get('positions')
        if stored is not None:
            if positions is None:positions=[{'vertex':i,'xy':xy} for i,xy in enumerate(stored)]
            elif {r['vertex']:r['xy'] for r in positions}!={i:xy for i,xy in enumerate(stored)}:raise ValueError('完整图对象与布局坐标不一致。')
        # Layout uses undirected, unweighted support, retaining original arcs separately.
        import networkx as nx
        graph=nx.empty_graph(n);graph.add_edges_from(numbered)
    if graph.number_of_edges() > 128:
        raise ValueError('布局预览入口至多支持128条边。')
    coordinates = graph_layout_positions(graph, operation, positions, fixed_vertices, vertices,
                                          root, iterations, seed, angle, scale, offset)
    specification = {'kind':'edges', 'n':len(graph), 'edges':[list(e) for e in graph.edges]}
    warnings = []
    if len({tuple(item['xy']) for item in coordinates}) != len(coordinates):
        # Preserve the actual spectral/transform result, never silently jitter it.
        output = safe_path(Path.cwd()/'outputs'/'graph-layouts'/uuid.uuid4().hex)
        output.mkdir(parents=True)
        coordinate_path = output/'positions.json'
        drawing = {'files':{}, 'order':len(graph), 'size':graph.number_of_edges()}
        warnings.append('结果有重合顶点，已保存原始坐标，未生成结构预览；请改变布局或调整坐标后绘图。')
    else:
        if drawing_document is not None:
            drawing_document=drawing_document.with_updates(positions=[r['xy'] for r in coordinates])
            drawing=hypergraph_plot_tool([e['vertices'] for e in drawing_document.edges],vertices=list(drawing_document.vertices),graph_document=drawing_document.to_dict(),edge_labels=False,legend=False)
        else:drawing = hypergraph_plot_tool(list(map(list, graph.edges)), vertices=list(graph),positions=coordinates, edge_labels=False, legend=False)
        coordinate_path = Path(drawing['files']['png']).with_name('positions.json')
    atomic_text(coordinate_path, json.dumps({'graph_spec':specification, 'positions':coordinates}, ensure_ascii=False, indent=2))
    metadata={}
    if drawing_document is not None:
        data=drawing_document.to_dict()
        if warnings:data.pop('positions',None)
        metadata={'graph_document':data}
    return {**drawing,**metadata, 'operation':operation, 'positions':coordinates, 'graph_spec':specification,
            'graph_spec_is_support_only':bool(drawing_document and (drawing_document.directed or drawing_document.weighted)),
             'normalization':{'purpose':'layout_support_only','directed_to_undirected':bool(drawing_document and drawing_document.directed),
                 'weights_ignored_for_layout':bool(drawing_document and drawing_document.weighted),'original_graph_field':'graph_document' if drawing_document else 'graph_spec'},
            'vertices':list(graph), 'edges':specification['edges'],
            'fixed_vertices':list(fixed_vertices or []),
            'preview_status':'not_rendered' if warnings else 'rendered', 'warnings':warnings,
            'files':{**drawing['files'], 'coordinates':str(coordinate_path)},
            'interpretation':'布局按无向无权支撑结构，仅改变坐标，完整图对象保留原方向和权重。graph_spec仅用于布局支撑，后续原图计算复用graph_document。谱布局不构成同构判定；重特征值时坐标基可能变化。'}


def library_entry_definitions(obj, graph_args):
    from graph_research.graph_input.styles import GRAPH_DOCUMENT_SCHEMA
    integer = {'type':'integer', 'minimum':0, 'maximum':127}
    vector = {'type':'array', 'minItems':2, 'maxItems':2,
              'items':{'type':'number', 'minimum':-1e9, 'maximum':1e9}}
    labels = {'type':'array', 'maxItems':32, 'items':{'type':['integer','string'], 'maxLength':80}}
    return [
        ('combinatorial_plot', '格路径、矩形与矩阵棋盘绘图', combinatorial_plot, obj({
            'operation':{'enum':['grid_path','lattice_path','rectangle','chessboard']},
            'steps':{'type':'array','maxItems':2048,'items':{'type':'integer','enum':[0,1]}},
            'total_steps':{'type':'integer','minimum':0,'maximum':2048},
            'right_steps':{'type':'array','maxItems':2048,'uniqueItems':True,'items':{'type':'integer','minimum':0,'maximum':2047}},
            'matrix':{'type':'array','minItems':1,'maxItems':32,'items':{'type':'array','minItems':1,'maxItems':32,'items':{'type':'number','minimum':-1e9,'maximum':1e9}}},
            'bounds':{'type':'array','minItems':4,'maxItems':4,'items':{'type':'number','minimum':-1e6,'maximum':1e6}},
            'fill':{'type':'boolean'}, 'row_labels':labels, 'column_labels':labels})),
        ('graph_layout', '普通图自动布局与坐标调整', graph_layout, obj({
            'graph_document':GRAPH_DOCUMENT_SCHEMA,
            'operation':{'enum':['spring','circular','spectral','tree','transform','align_horizontal','align_vertical']}, **graph_args,
            'positions':{'type':'array','minItems':1,'maxItems':128,'items':obj({'vertex':integer,'xy':vector}, ['vertex','xy'])},
            'fixed_vertices':{'type':'array','maxItems':128,'uniqueItems':True,'items':integer},
            'vertices':{'type':'array','minItems':1,'maxItems':128,'uniqueItems':True,'items':integer},
            'root':integer, 'iterations':{'type':'integer','minimum':1,'maximum':5000},
            'seed':{'type':'integer','minimum':0,'maximum':4294967295},
            'angle':{'type':'number','minimum':-360000,'maximum':360000},
            'scale':{'type':'number','exclusiveMinimum':0,'maximum':1e6}, 'offset':vector}))
    ]
