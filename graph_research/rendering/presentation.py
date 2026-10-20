"""Lossless graph presentation shared by Qt, static images and TikZ."""
import json
import math
from pathlib import Path
import uuid

import numpy as np
from matplotlib.path import Path as Curve

from graph_research.graph_input.document import GraphDocument,document,weight_parts,from_networkx,from_hypergraph,display_label
from graph_research.graph_input.styles import resolved_style
from .geometry import COLORS,hyperedge_path,vertex_positions


def presentation_document(edges,vertices=None,positions=None,graph_document=None,graph_type='hypergraph'):
    if graph_document is None:
        members=list(dict.fromkeys(v for e in edges for v in e)) if vertices is None else vertices
        graph=document(members,[{'vertices':list(e)} for e in edges],graph_type=graph_type)
    else:
        graph=GraphDocument(graph_document)
        if [e['vertices'] for e in graph.edges]!=list(map(list,edges)) or (vertices is not None and list(graph.vertices)!=list(vertices)):
            raise ValueError('完整图对象与外层顶点/边参数不一致。')
        if graph_type=='graph' and graph.graph_type!='graph':raise ValueError('普通图导出需要明确的普通图对象。')
    if positions is not None:
        mapping={r['vertex']:r['xy'] for r in positions}
        if len(mapping)!=len(positions) or set(mapping)!=set(graph.vertices):raise ValueError('坐标须恰好覆盖当前图顶点。')
        coords=[list(mapping[v]) for v in graph.vertices]
        if 'positions' in graph.to_dict() and coords!=graph.to_dict()['positions']:raise ValueError('完整图对象与外层坐标不一致。')
        graph=graph.with_updates(positions=coords)
    return graph


def coordinates(graph,layout='spring',seed=42):
    data=graph.to_dict()
    if 'positions' in data:return {v:np.array(xy,dtype=float) for v,xy in zip(graph.vertices,data['positions'])}
    from graph_research.hypergraphs import Hypergraph
    edges=[];seen=set()
    for edge in graph.edges:
        key=frozenset(edge['vertices'])
        if key not in seen:edges.append(edge['vertices']);seen.add(key)
    return vertex_positions(Hypergraph(edges,vertices=list(graph.vertices)),layout=layout,seed=seed)


def geometry(graph,pos):
    """Opposite arcs bend on different sides; weights never alter incidence."""
    directed=graph.directed;arcs={tuple(e['vertices']) for e in graph.edges};paths=[];style=resolved_style(graph)
    for edge in graph.edges:
        members=edge['vertices'];points=[np.asarray(pos[v],dtype=float) for v in members]
        if directed and tuple(reversed(members)) in arcs:
            start,end=points;delta=end-start;normal=np.array([-delta[1],delta[0]])*.18
            paths.append(Curve([start,start+delta/3+normal,start+2*delta/3+normal,end],[1,4,4,4]))
        else:paths.append(hyperedge_path(points,tension=style['tension'],continuity=style['continuity'],bias=style['bias']))
    return paths


def midpoint(path):
    p=path.vertices
    return (p[0]+3*p[1]+3*p[2]+p[3])/8 if len(p)>2 else (p[0]+p[1])/2


def arrow_triangle(path,span):
    p=path.vertices;direction=p[-1]-p[-2];norm=float(np.linalg.norm(direction))
    if not norm:return None
    unit=direction/norm;length=float(np.linalg.norm(p[-1]-p[0]));gap=min(.025*span,.15*length);size=min(.035*span,.18*length)
    tip=p[-1]-unit*gap;base=tip-unit*size;side=np.array([-unit[1],unit[0]])*size*.42
    return np.array([tip,base+side,base-side])


def weight_text(weight):
    real,imag=weight_parts(weight)
    def number(v):return str(int(v)) if v==int(v) else str(v)
    if not imag:return number(real)
    return (number(real)+('+' if imag>0 else '-')+number(abs(imag))+'i') if real else number(imag)+'i'


def edge_text(graph,index,style):
    parts=[]
    if style['edge_labels']:parts.append('e'+str(index))
    if style['weight_labels'] and graph.weighted:parts.append(weight_text(graph.edges[index]['weight']))
    return ' : '.join(parts)


def edge_color(graph,index,style):
    if 'edge_colors' in style:return style['edge_colors'][index]
    return style.get('edge_color','black' if graph.graph_type=='graph' or all(len(e['vertices'])==2 for e in graph.edges) else COLORS[index%len(COLORS)])


def plot_document(graph,*,ax=None,layout='spring',seed=42,legend=False,title=None):
    from matplotlib.figure import Figure
    from matplotlib.patches import PathPatch,Polygon
    from matplotlib import rc_context
    from .fonts import label_font_families
    from .tikz import _label_offset
    from graph_research.hypergraphs import Hypergraph
    style=resolved_style(graph);pos=coordinates(graph,layout,seed);paths=geometry(graph,pos)
    texts={r['vertex']:r['text'] for r in style.get('vertex_texts',[])}
    figure=Figure(figsize=(7,5),layout='constrained') if ax is None else ax.figure
    ax=figure.add_subplot() if ax is None else ax
    families={'sans':'sans-serif','serif':'serif','monospace':'monospace'}
    font=(label_font_families(' '.join(str(texts.get(v,display_label(v))) for v in graph.vertices)+' '+str(title or '')) or [])+[families[style['font_family']]]
    span=float(np.ptp(np.array(list(pos.values())),axis=0).max()) if pos else 1.;span=span or 1.
    vo={r['vertex']:r['xy'] for r in style.get('vertex_label_offsets',[])};eo={r['edge_index']:r['xy'] for r in style.get('edge_label_offsets',[])}
    supports=[];seen=set()
    for e in graph.edges:
        key=frozenset(e['vertices'])
        if key not in seen:supports.append(e['vertices']);seen.add(key)
    h=Hypergraph(supports,vertices=list(graph.vertices))
    with rc_context({'text.usetex':False,'text.parse_math':False}):
        for i,path in enumerate(paths):
            color=edge_color(graph,i,style);patch=PathPatch(path,fill=False,edgecolor=color,linewidth=style['line_width'],linestyle=style['line_style'],zorder=2)
            patch.set_gid('hyperedge-'+str(i));ax.add_patch(patch)
            if graph.directed:
                triangle=arrow_triangle(path,span)
                if triangle is not None:ax.add_patch(Polygon(triangle,closed=True,color=color,zorder=4))
            text=edge_text(graph,i,style)
            if text:ax.annotate(text,midpoint(path),xytext=eo.get(i,[3,4]),textcoords='offset points',fontsize=style['font_size'],fontfamily=font,color=color,zorder=7,bbox={'facecolor':'white','edgecolor':'none','alpha':.85,'pad':1})
        if pos:
            xy=np.array(list(pos.values()));ax.scatter(xy[:,0],xy[:,1],s=(2*style['vertex_size'])**2,c=style['vertex_color'],zorder=6)
        if style['vertex_labels']:
            for v in graph.vertices:
                dx,dy,anchor=_label_offset(h,pos,v);offset=vo.get(v,[dx,dy])
                ax.annotate(str(texts.get(v,display_label(v))),pos[v],xytext=offset,textcoords='offset points',fontsize=style['font_size'],fontfamily=font,zorder=8,
                    ha='left' if offset[0]>.2 else 'right' if offset[0]<-.2 else 'center',va='bottom' if offset[1]>.2 else 'top' if offset[1]<-.2 else 'center')
        if legend and graph.size:
            from matplotlib.lines import Line2D
            ax.legend(handles=[Line2D([],[],color=edge_color(graph,i,style),label='e'+str(i)+': '+', '.join(map(display_label,e['vertices']))+(' ; w='+weight_text(e['weight']) if graph.weighted else '')) for i,e in enumerate(graph.edges)],loc='upper left',bbox_to_anchor=(1,1),prop={'family':font,'size':style['font_size']})
        if title:ax.set_title(title,fontfamily=font)
    ax.set_aspect('equal');ax.autoscale_view();ax.margins(.18);ax.axis('off')
    figure.hypergraph_positions={v:p.copy() for v,p in pos.items()};figure.hypergraph_paths=paths
    figure.graph_document=graph.with_updates(positions=[pos[v].tolist() for v in graph.vertices]).to_dict()
    return figure


def document_to_tikz(graph,*,standalone=False,normalize=True,size_cm=10):
    from .tikz import escape_latex,tex_number,_label_offset
    from graph_research.hypergraphs import Hypergraph
    if not math.isfinite(size_cm) or not 0<size_cm<=50:raise ValueError('size_cm须为(0,50]内有限数。')
    style=resolved_style(graph);pos=coordinates(graph);paths=geometry(graph,pos)
    texts={r['vertex']:r['text'] for r in style.get('vertex_texts',[])}
    points=list(pos.values())+[p for path in paths for p in path.vertices]
    low,high=(np.min(points,axis=0),np.max(points,axis=0)) if points else (np.zeros(2),np.zeros(2))
    span=float((high-low).max()) or 1.;offset=(low+high)/2 if normalize else np.zeros(2);factor=size_cm/span if normalize else 1.
    def point(xy):
        value=(np.asarray(xy)-offset)*factor
        if not normalize and np.max(np.abs(value))>100:raise ValueError('原始坐标超过100cm，请启用归一化。')
        return '('+tex_number(value[0])+','+tex_number(value[1])+')'
    lines=['% Graph type: '+graph.graph_type+'; directed: '+str(graph.directed).lower()+'; weighted: '+str(graph.weighted).lower(),
           '% Labels are literal escaped text. Requires \\usepackage{tikz}.',
           r'\definecolor{vertexcolor}{HTML}{'+style['vertex_color'][1:]+'}']
    index={v:i for i,v in enumerate(graph.vertices)};vo={r['vertex']:r['xy'] for r in style.get('vertex_label_offsets',[])};eo={r['edge_index']:r['xy'] for r in style.get('edge_label_offsets',[])}
    font={'sans':r'\sffamily','serif':r'\rmfamily','monospace':r'\ttfamily'}[style['font_family']]
    lines.append(r'\begin{tikzpicture}[x=1cm,y=1cm,line cap=round,line join=round,font={'+font+r'\fontsize{'+tex_number(style['font_size'])+'}{'+tex_number(style['font_size']*1.2)+r'}\selectfont}]')
    if not graph.order:lines.append(r'\path[use as bounding box] (-.2,-.2) rectangle (.2,.2);')
    for v in graph.vertices:lines.append(r'\coordinate (v'+str(index[v])+') at '+point(pos[v])+';')
    for i,(edge,path) in enumerate(zip(graph.edges,paths)):
        from matplotlib.colors import to_hex
        color=to_hex(edge_color(graph,i,style))[1:]
        lines.append(r'\definecolor{edgecolor'+str(i)+'}{HTML}{'+color+'}')
        lines.append('% e'+str(i)+': members '+json.dumps([index[v] for v in edge['vertices']])+', weight '+weight_text(edge['weight']))
        option='draw=edgecolor'+str(i)+',line width='+tex_number(style['line_width'])+'pt,'+style['line_style']
        p=path.vertices
        if len(p)==2:curve=point(p[0])+' -- '+point(p[1])
        else:curve=point(p[0])+''.join(' .. controls '+point(p[j])+' and '+point(p[j+1])+' .. '+point(p[j+2]) for j in range(1,len(p)-1,3))+(' -- cycle' if len(edge['vertices'])>2 else '')
        lines.append(r'\draw['+option+'] '+curve+';')
        if graph.directed:
            triangle=arrow_triangle(path,span)
            if triangle is not None:lines.append(r'\fill[edgecolor'+str(i)+'] '+' -- '.join(point(p) for p in triangle)+' -- cycle;')
        text=edge_text(graph,i,style)
        if text:
            dx,dy=eo.get(i,[3,4]);lines.append(r'\node[fill=white,inner sep=1pt,anchor=south west,xshift='+tex_number(dx)+'pt,yshift='+tex_number(dy)+'pt] at '+point(midpoint(path))+' {'+escape_latex(text)+'};')
    supports=list({frozenset(e['vertices']):e['vertices'] for e in graph.edges}.values());h=Hypergraph(supports,vertices=list(graph.vertices))
    for v in graph.vertices:
        name='v'+str(index[v]);lines.append(r'\fill[vertexcolor] ('+name+') circle[radius='+tex_number(style['vertex_size'])+'pt];')
        if style['vertex_labels']:
            dx,dy,anchor=_label_offset(h,pos,v)
            if v in vo:dx,dy=vo[v];anchor=('south' if dy>0 else 'north' if dy<0 else '')+(' west' if dx>0 else ' east' if dx<0 else '');anchor=anchor.strip() or 'center'
            lines.append(r'\node[inner sep=0pt,anchor='+anchor+',xshift='+tex_number(dx)+'pt,yshift='+tex_number(dy)+'pt] at ('+name+') {'+escape_latex(texts.get(v,display_label(v)))+'};')
    lines.append(r'\end{tikzpicture}');fragment='\n'.join(lines)+'\n'
    if not standalone:return fragment
    chinese=any('\u3400'<=c<='\u9fff' for v in graph.vertices for c in str(texts.get(v,display_label(v))))
    preamble=['% !TeX program = '+('xelatex' if chinese else 'pdflatex'),r'\documentclass[tikz,border=5pt]{standalone}']
    if chinese:preamble.append(r'\usepackage[UTF8]{ctex}')
    return '\n'.join(preamble+[r'\begin{document}',fragment.rstrip(),r'\end{document}',''])


def save_document_images(graph,*,layout='spring',seed=42,legend=False):
    from graph_research.runtime.storage import safe_path,staged_file,atomic_text
    output=safe_path(Path.cwd()/'outputs'/'graph-drawings'/uuid.uuid4().hex);output.mkdir(parents=True)
    figure=plot_document(graph,layout=layout,seed=seed,legend=legend);stem='graph' if graph.graph_type=='graph' else 'hypergraph';files={}
    for ext in ('png','svg','pdf'):
        path=output/(stem+'.'+ext)
        with staged_file(path) as temporary:figure.savefig(temporary,dpi=180,bbox_inches='tight',facecolor='white')
        files[ext]=str(path)
    graph=GraphDocument(figure.graph_document);path=output/(stem+'-drawing.json');atomic_text(path,json.dumps(graph.to_dict(),ensure_ascii=False,indent=2));files['drawing']=str(path)
    return {'files':files,'graph_document':graph.to_dict(),'positions':[{'vertex':v,'xy':xy} for v,xy in zip(graph.vertices,graph.to_dict()['positions'])],
        'order':graph.order,'size':graph.size,'uniform':graph.uniform,'edge_members':[e['vertices'] for e in graph.edges],
        'interpretation':'保留方向、原权重、标签、孤立点及样式；交叉点不是顶点。自动初始布局按无向无权支撑结构生成。'}
