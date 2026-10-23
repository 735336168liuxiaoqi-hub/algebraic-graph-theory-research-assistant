"""Editable TikZ using the exact cubic geometry of the Python renderer.

Generating source needs no TeX installation. Compile standalone output using
pdfLaTeX for ASCII labels, or XeLaTeX with ctex for Chinese labels.
"""
from graph_research.graph_input.document import display_label
import json
import math
from pathlib import Path
import re
import uuid

import numpy as np

from graph_research.rendering.geometry import COLORS, hyperedge_path, vertex_positions
from graph_research.rendering.tex_coordinates import for_paths as _for_paths
from graph_research.runtime.observability import timed


def escape_latex(label):
    """Treat labels as text, including backslashes and TeX special characters."""
    escapes = {"\\":r"\textbackslash{}", "{":r"\{", "}":r"\}",
               "$":r"\$", "&":r"\&", "%":r"\%", "#":r"\#",
               "_":r"\_", "^":r"\textasciicircum{}", "~":r"\textasciitilde{}"}
    return "".join(escapes.get(c," " if c.isspace() else c) for c in str(label) if ord(c)>=32 or c.isspace())


def tex_number(value):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("TikZ coordinates must be finite")
    return "0" if value==0 else np.format_float_positional(value,unique=True,trim="-")


def _label_offset(h, positions, v):
    neighbors = list(dict.fromkeys(u for e in h.Edges if v in e for u in e if u!=v))
    if not neighbors:
        return 8.,0.,"west"
    rays = np.array([positions[u]-positions[v] for u in neighbors])
    angles = np.sort(np.arctan2(rays[:,1],rays[:,0]))
    ends = np.append(angles[1:],angles[0]+2*math.pi)
    gap = int(np.argmax(ends-angles))
    direction = (angles[gap]+ends[gap])/2
    dx,dy = math.cos(direction),math.sin(direction)
    vertical = "south" if dy>.2 else "north" if dy<-.2 else ""
    horizontal = "west" if dx>.2 else "east" if dx<-.2 else ""
    return 8*dx,8*dy," ".join(s for s in (vertical,horizontal) if s) or "center"


def hypergraph_to_tikz(h, *, pos=None, standalone=False, vertex_labels=True,
                       edge_labels=False, edge_colors=None, normalize=True,
                       size_cm=10, seed=42, tension=.5, continuity=.5, bias=0,weight_labels=True,style=None):
    """Return a tikzpicture fragment or complete document.

    Normalization uniformly scales/translates all geometry to a longest span
    of size_cm, retaining proportions and curve control points. Set normalize
    False for literal original coordinates in cm (must fit TeX dimensions).
    Labels are escaped text; use the generated source to customize math labels.
    """
    from matplotlib.colors import to_hex
    if style is not None or np.any(h.weights!=1):
        from .presentation import from_hypergraph,document_to_tikz,coordinates
        graph=from_hypergraph(h,pos);graph=graph.with_updates(positions=[p.tolist() for p in coordinates(graph,seed=seed).values()])
        drawing={'vertex_labels':vertex_labels is not False,'edge_labels':edge_labels,'weight_labels':weight_labels,'tension':tension,'continuity':continuity,'bias':bias,**(style or {})}
        if isinstance(vertex_labels,dict):drawing['vertex_texts']=[{'vertex':v,'text':str(vertex_labels.get(v,display_label(v)))} for v in h.Vertices]
        if edge_colors is not None:drawing['edge_colors']=[to_hex(edge_colors.get(i,COLORS[i%len(COLORS)]) if isinstance(edge_colors,dict) else edge_colors[i]) for i in range(h.size())]
        return document_to_tikz(graph.with_updates(style=drawing),standalone=standalone,normalize=normalize,size_cm=size_cm)
    if not math.isfinite(size_cm) or not 0<size_cm<=50:
        raise ValueError("size_cm must be finite in (0,50]")
    stored = getattr(h,"_pos",None)
    positions = vertex_positions(h,stored if pos is None and stored else pos,seed=seed)
    paths = [hyperedge_path([positions[v] for v in e],tension=tension,continuity=continuity,bias=bias) for e in h.Edges]
    simple = all(len(edge)==2 for edge in h.Edges)
    coords = _for_paths(positions,paths,normalize=normalize,size_cm=size_cm)
    point = coords.point
    index = {v:i for i,v in enumerate(h.Vertices)}
    palette = []
    for i,e in enumerate(h.Edges):
        if edge_colors is None:
            color = getattr(e,"color","black" if simple else COLORS[i%len(COLORS)])
        elif isinstance(edge_colors,dict):
            color = edge_colors.get(i,COLORS[i%len(COLORS)])
        else:
            if len(edge_colors)!=h.size():
                raise ValueError("One edge color per hyperedge required")
            color = edge_colors[i]
        palette.append(to_hex(color).lstrip("#").upper())
    lines = ["% Members are ON each unfilled curve; enclosed vertices are not members.",
             "% Requires \\usepackage{tikz}. Cubic control points preserve the edited curves."]
    if normalize:
        lines.append(f"% Layout uniformly scaled to a longest span of {tex_number(size_cm)} cm.")
    for i,color in enumerate(palette):
        lines.append(r"\definecolor{hgcolor"+str(i)+"}{HTML}{"+color+"}")
    lines.append(r"\begin{tikzpicture}[x=1cm,y=1cm,line cap=round,line join=round,font=\small]")
    if not h.Vertices:
        lines.append(r"\path[use as bounding box] (-.2,-.2) rectangle (.2,.2);")
    for v in h.Vertices:
        lines.append(r"\coordinate (v"+str(index[v])+") at "+point(positions[v])+";")
    for i,(e,path) in enumerate(zip(h.Edges,paths)):
        members = [index[v] for v in e]
        lines.append(f"% e{i}: vertex indices {json.dumps(members)}")
        style = f"draw=hgcolor{i},line width=0.9pt"
        if i>=len(COLORS) and not simple:
            style += ",dashed" if (i//len(COLORS))%3==1 else ",dotted" if (i//len(COLORS))%3==2 else ""
        p = path.vertices
        if len(e)==2:
            lines.append(r"\draw["+style+f"] (v{members[0]}) -- (v{members[1]});")
            midpoint = (p[0]+p[1])/2
        else:
            parts = [r"\draw["+style+"] "+point(p[0])]
            for j in range(1,len(p)-1,3):
                parts.append("  .. controls "+point(p[j])+" and "+point(p[j+1])+" .. "+point(p[j+2]))
            lines.extend(parts+["  -- cycle;"])
            midpoint = (p[0]+3*p[1]+3*p[2]+p[3])/8
        if edge_labels:
            lines.append(r"\node[text=hgcolor"+str(i)+r",anchor=south west,inner sep=1pt] at "+point(midpoint)+r" {$e_{"+str(i)+r"}$};")
    labels = vertex_labels if isinstance(vertex_labels,dict) else getattr(h,"vLabels",{})
    for v in h.Vertices:
        name = f"v{index[v]}"
        lines.append(r"\fill[black] ("+name+r") circle[radius=1.6pt];")
        if vertex_labels is not False:
            dx,dy,anchor = _label_offset(h,positions,v)
            label = escape_latex(labels.get(v,display_label(v)))
            lines.append(r"\node[anchor="+anchor+r",inner sep=0pt,xshift="+coords.number(dx)+r"pt,yshift="+coords.number(dy)+"pt] at ("+name+") {"+label+"};")
    lines.append(r"\end{tikzpicture}")
    fragment = "\n".join(lines)+"\n"
    if not standalone:
        return fragment
    text = "".join(str(labels.get(v,display_label(v))) for v in h.Vertices) if vertex_labels is not False else ""
    chinese = bool(re.search(r"[\u3400-\u9fff\uf900-\ufaff]",text))
    preamble = ["% !TeX program = "+("xelatex" if chinese else "pdflatex"),
                r"\documentclass[tikz,border=5pt]{standalone}"]
    if chinese:
        preamble.append(r"\usepackage[UTF8]{ctex}")
    return "\n".join(preamble+[r"\begin{document}",fragment.rstrip(),r"\end{document}",""])


@timed('artifact_export')
def save_hypergraph_tikz(h, path, *, standalone=True, **options):
    from graph_research.runtime.storage import atomic_text
    overwrite=options.pop('overwrite',False)
    path = Path(path)
    if path.suffix.lower()!=".tex":
        raise ValueError("TikZ output must use the .tex extension")
    code = hypergraph_to_tikz(h,standalone=standalone,**options)
    atomic_text(path,code,overwrite=overwrite)
    return path.resolve()


def graph_to_tikz(graph, *, pos=None, **options):
    """NetworkX undirected simple graphs use the binary-edge drawing case."""
    import networkx as nx
    from graph_research.hypergraphs import Hypergraph
    if graph.is_multigraph() or nx.number_of_selfloops(graph):
        raise ValueError("Ordinary TikZ export currently requires a loopless undirected simple graph")
    if graph.is_directed() or graph.graph.get('style') or options.get('style') is not None or any(d.get('weight',1)!=1 for _,_,d in graph.edges(data=True)):
        from .presentation import from_networkx,document_to_tikz,coordinates
        drawing=from_networkx(graph,pos);style={**drawing.to_dict().get('style',{}),**(options.pop('style',None) or {})}
        for key in ('vertex_labels','edge_labels','weight_labels'):
            if key in options:
                value=options.pop(key)
                if key=='vertex_labels' and isinstance(value,dict):style['vertex_texts']=[{'vertex':v,'text':str(value.get(v,v))} for v in graph];value=True
                style[key]=value
        for key in ('tension','continuity','bias'):
            if key in options:style[key]=options.pop(key)
        if 'edge_colors' in options:
            from matplotlib.colors import to_hex
            colors=options.pop('edge_colors');style['edge_colors']=[to_hex(colors.get(i,'black') if isinstance(colors,dict) else colors[i]) for i in range(graph.number_of_edges())]
        seed=options.pop('seed',42);drawing=drawing.with_updates(positions=[p.tolist() for p in coordinates(drawing,seed=seed).values()],style=style)
        return document_to_tikz(drawing,**options)
    h = Hypergraph(graph)
    if pos is None:
        pos = graph.graph.get("pos")
    options.setdefault("edge_colors",["black"]*h.size())
    return hypergraph_to_tikz(h,pos=pos,**options)


@timed('artifact_export')
def save_graph_tikz(graph,path,*,standalone=True,**options):
    from graph_research.runtime.storage import atomic_text
    overwrite=options.pop('overwrite',False)
    path = Path(path)
    if path.suffix.lower()!=".tex":
        raise ValueError("TikZ output must use the .tex extension")
    code = graph_to_tikz(graph,standalone=standalone,**options)
    atomic_text(path,code,overwrite=overwrite)
    return path.resolve()


def _tikz_tool_export(edges,vertices=None,positions=None,edge_labels=False,vertex_labels=True,seed=42,simple=False,graph_document=None):
    if graph_document is not None:
        from .presentation import presentation_document,document_to_tikz,coordinates
        from graph_research.runtime.storage import atomic_text
        graph=presentation_document(edges,vertices,positions,graph_document,'graph' if simple else 'hypergraph')
        style={'edge_labels':edge_labels,'vertex_labels':vertex_labels,**graph.to_dict().get('style',{})}
        graph=graph.with_updates(style=style,positions=[p.tolist() for p in coordinates(graph,seed=seed).values()])
        output=Path.cwd()/'outputs'/'tikz'/uuid.uuid4().hex;stem='graph' if graph.graph_type=='graph' else 'hypergraph';files={}
        for key,standalone,suffix in [('standalone',True,'.tex'),('fragment',False,'-tikz.tex')]:
            path=output/(stem+suffix);atomic_text(path,document_to_tikz(graph,standalone=standalone));files[key]=str(path.resolve())
        path=output/(stem+'-drawing.json');atomic_text(path,json.dumps(graph.to_dict(),ensure_ascii=False,indent=2));files['drawing']=str(path.resolve())
        code=document_to_tikz(graph)
        return {'files':files,'tikz':code if len(code)<=60000 else None,'code_in_file':len(code)>60000,'order':graph.order,'size':graph.size,'graph_document':graph.to_dict(),
            'positions':[{'vertex':v,'xy':xy} for v,xy in zip(graph.vertices,graph.to_dict()['positions'])],'requires':'TikZ; Chinese labels use XeLaTeX with ctex.'}
    from graph_research.hypergraphs import Hypergraph
    h = Hypergraph(edges,vertices=vertices)
    if h.order()>128 or sum(map(len,h.Edges))>2048:
        raise ValueError("TikZ tool supports at most128 vertices and2048 incidences")
    if positions is not None:
        if len({record['vertex'] for record in positions})!=len(positions):
            raise ValueError("Repeated position labels")
        h.set_pos({record['vertex']:record['xy'] for record in positions})
    else:
        h.set_pos(vertex_positions(h,seed=seed))
    output = Path.cwd()/"outputs"/"tikz"/uuid.uuid4().hex
    options = {"edge_labels":edge_labels,"vertex_labels":vertex_labels}
    if simple:
        options['edge_colors'] = ['black']*h.size()
    fragment = h.to_tikz(**options)
    stem='graph' if simple else 'hypergraph'
    full = h.save_tikz(output/(stem+'.tex'),**options)
    part = h.save_tikz(output/(stem+'-tikz.tex'),standalone=False,**options)
    return {"files":{"standalone":str(full),"fragment":str(part)},
            "tikz":fragment if len(fragment)<=60000 else None,
            "code_in_file":len(fragment)>60000,"order":h.order(),"size":h.size(),
            "requires":"TikZ; Chinese labels use XeLaTeX with ctex. No TeX runtime is needed to export."}


def hypergraph_tikz_tool(edges,vertices=None,positions=None,edge_labels=False,vertex_labels=True,seed=42,graph_document=None):
    return _tikz_tool_export(edges,vertices,positions,edge_labels,vertex_labels,seed,graph_document=graph_document)


def graph_tikz_tool(edges,vertices=None,positions=None,edge_labels=False,vertex_labels=True,seed=42,graph_document=None):
    if any(len(e)!=2 for e in edges):
        raise ValueError("Simple graph edges must have exactly two vertices")
    return _tikz_tool_export(edges,vertices,positions,edge_labels,vertex_labels,seed,simple=True,graph_document=graph_document)


def tikz_tool_definitions(object_schema):
    from graph_research.graph_input.styles import GRAPH_DOCUMENT_SCHEMA
    label = {"type":["integer","string"]}
    coordinate = {"type":"array","minItems":2,"maxItems":2,"items":{"type":"number","minimum":-1e9,"maximum":1e9}}
    properties = {
                 'graph_document':GRAPH_DOCUMENT_SCHEMA,
                 "edges":{"type":"array","maxItems":128,"items":{"type":"array","minItems":2,"maxItems":128,"items":label}},
                 "vertices":{"type":"array","maxItems":128,"items":label},
                 "positions":{"type":"array","maxItems":128,"items":object_schema({"vertex":label,"xy":coordinate},["vertex","xy"])},
                 "edge_labels":{"type":"boolean"},"vertex_labels":{"type":"boolean"},
                 "seed":{"type":"integer","minimum":0,"maximum":4294967295}}
    graph_properties = {**properties,"edges":{"type":"array","maxItems":128,"items":{"type":"array","minItems":2,"maxItems":2,"items":label}}}
    return [("hypergraph_tikz","将一致/非一致超图导出为LaTeX/TikZ，保留指定布局的贝塞尔曲线，返回完整.tex及论文插图片段。",
             hypergraph_tikz_tool,object_schema(properties,["edges"])),
            ("graph_tikz","将普通无向简单图导出为LaTeX/TikZ，支持给定坐标、文本标签和孤立点，默认黑色直线边。",
             graph_tikz_tool,object_schema(graph_properties,["edges"]))]
