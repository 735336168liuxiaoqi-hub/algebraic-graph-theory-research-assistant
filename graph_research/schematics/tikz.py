"""Paper SVG/TikZ from common geometry; no TeX engine needed to export."""
from html import escape
import json
from pathlib import Path
from graph_research.rendering.tikz import escape_latex,tex_number
from graph_research.runtime.storage import atomic_text
from .document import SchematicDocument
from .geometry import primitives,bounds


def _number(v):return tex_number(round(float(v),7))


def to_tikz(scene,*,standalone=False,vertex_labels=False):
    """Self-contained picture: cubic curves, grey edges, red nodes and distinct ellipses.

    Symbolic stubs illustrate a family and do not imply a lower bound equal to
    the number of drawn stubs. Instantiate numeric lengths before calculation.
    No user-provided TeX commands, input macros or tkz-euclide are evaluated.
    """
    if not isinstance(scene,SchematicDocument):scene=SchematicDocument(scene)
    items=primitives(scene,vertex_labels);style=scene.to_dict()['style'];lines=['% Paper schematic only; use explicit integer expansion for numerical tools.',
        '% Edge-interior dots omit vertices; route-middle dots omit edges.',
        r'\begin{tikzpicture}[x=1cm,y=1cm,line cap=round,line join=round,font=\small]']
    for key,name in [('line_color','grsline'),('vertex_color','grsvertex'),('edge_fill','grsfill')]:lines.append(r'\definecolor{'+name+'}{HTML}{'+style[key][1:].upper()+'}')
    for item in items:
        if item['kind']=='path':
            commands=[]
            for c in item['commands']:
                points=['('+_number(c[i])+','+_number(c[i+1])+')' for i in range(1,len(c),2)]
                commands.append(points[0] if c[0]=='M' else '-- '+points[0] if c[0]=='L' else '.. controls '+points[0]+' and '+points[1]+' .. '+points[2] if c[0]=='C' else '-- cycle')
            if item['stroke']=='none':lines.append(r'\path[draw=none,fill=grsfill] '+' '.join(commands)+';')
            else:lines.append(r'\draw[grsline,line width='+_number(item['width'])+'cm] '+' '.join(commands)+';')
        elif item['kind']=='circle':
            xy='('+','.join(_number(t) for t in item['xy'])+')';r=_number(item['r'])
            lines.append((r'\shade[ball color=grsvertex] ' if item['role'] in ('anchor','junction') else r'\fill[grsline] ')+xy+' circle[radius='+r+'cm];')
        else:
            text=item.get('tex',escape_latex(item['text']))
            lines.append(r'\node[text=grsline,inner sep=0pt] at ('+','.join(_number(t) for t in item['xy'])+') {'+text+'};')
    lines.append(r'\end{tikzpicture}');fragment='\n'.join(lines)+'\n'
    if not standalone:return fragment
    chinese=any('\u3400'<=c<='\u9fff' for item in items if item['kind']=='label' for c in item['text'])
    header=[r'\documentclass[tikz,border=5pt]{standalone}']
    if chinese:header.append(r'\usepackage[UTF8]{ctex}')
    return '\n'.join(['% !TeX program = '+('xelatex' if chinese else 'pdflatex'),*header,r'\begin{document}',fragment,r'\end{document}',''])


def to_svg(scene,*,vertex_labels=False):
    """Portable vector preview with the same control points as the native editor and TeX."""
    if not isinstance(scene,SchematicDocument):scene=SchematicDocument(scene)
    items=primitives(scene,vertex_labels);style=scene.to_dict()['style'];x0,y0,x1,y1=bounds(items);scale=120
    f=lambda v:_number(v*scale)
    lines=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{f(x0)} {f(-y1)} {f(x1-x0)} {f(y1-y0)}">',
           '<defs><radialGradient id="gr-red"><stop offset="0" stop-color="#fff"/><stop offset=".6" stop-color="'+style['vertex_color']+'"/><stop offset="1" stop-color="'+style['vertex_color']+'"/></radialGradient></defs>',
           '<rect x="'+f(x0)+'" y="'+f(-y1)+'" width="'+f(x1-x0)+'" height="'+f(y1-y0)+'" fill="white"/>']
    for item in items:
        if item['kind']=='path':
            commands=[]
            for c in item['commands']:commands.append(c[0]+' '+' '.join(f(t if i%2 else -t) for i,t in enumerate(c[1:],1)))
            lines.append('<path d="'+' '.join(commands)+'" fill="'+item['fill']+'" stroke="'+item['stroke']+'" stroke-width="'+f(item['width'])+'" stroke-linecap="round" stroke-linejoin="round"/>')
        elif item['kind']=='circle':
            color='url(#gr-red)' if item['role'] in ('anchor','junction') else item['color']
            lines.append(f'<circle cx="{f(item["xy"][0])}" cy="{f(-item["xy"][1])}" r="{f(item["r"])}" fill="{color}"/>')
        else:
            text=escape(item['text']);text='<tspan font-style="italic">P</tspan><tspan baseline-shift="sub" font-size="11">'+escape(item['text'][2:])+'</tspan>' if item['role']=='path_label' else text
            lines.append(f'<text x="{f(item["xy"][0])}" y="{f(-item["xy"][1])}" fill="{style["line_color"]}" text-anchor="middle" dominant-baseline="middle" font-family="Times New Roman,serif" font-size="16">{text}</text>')
    return '\n'.join(lines+['</svg>',''])


def save(scene,path,*,standalone=True,vertex_labels=False,overwrite=False):
    """Save .tex, .svg or the independent .json scene; protect core and existing files."""
    if not isinstance(scene,SchematicDocument):scene=SchematicDocument(scene)
    path=Path(path);suffix=path.suffix.lower()
    text=to_tikz(scene,standalone=standalone,vertex_labels=vertex_labels) if suffix=='.tex' else to_svg(scene,vertex_labels=vertex_labels) if suffix=='.svg' else json.dumps(scene.to_dict(),ensure_ascii=False,indent=2) if suffix=='.json' else None
    if text is None:raise ValueError('示意图保存为.tex、.svg或.json。')
    atomic_text(path,text,overwrite=overwrite);return path.resolve()
