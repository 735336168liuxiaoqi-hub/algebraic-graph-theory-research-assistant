"""Render the documentation's shared graph data to SVG, PNG and Mermaid.

Run with the desktop extra installed: python docs/diagrams/render_workflows.py
Only files beside this script are generated. No service or model is called.
"""
from pathlib import Path
import hashlib
import html
import json
import os

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtCore import QRectF,Qt
from PySide6.QtGui import QGuiApplication,QFont,QFontDatabase,QFontMetricsF,QImage,QPainter
from PySide6.QtSvg import QSvgRenderer

HERE=Path(__file__).resolve().parent
PALETTE={
    'process':('#f5f7fa','#c6d1da','#233845'),
    'manual':('#eaf5f1','#8dbbb0','#175a4a'),
    'model':('#edf2fc','#a1b8e7','#284f91'),
    'host':('#f0edfa','#b5a7da','#5b438c'),
    'guard':('#e9f3f7','#8fb1c3','#224d64'),
    'data':('#f0f6f4','#adc7bc','#2b574a'),
    'warning':('#fcf4e7','#d7b985','#805b26'),
    'decision':('#ffffff','#9fadb9','#344c5c'),
}
FAMILY='Microsoft YaHei, Noto Sans CJK SC, sans-serif'


def font(size,weight=400):
    value=QFont('Microsoft YaHei');value.setPixelSize(size)
    value.setWeight(QFont.Weight.DemiBold if weight>=600 else QFont.Weight.Normal)
    return value


def port(node,name):
    x,y=node['x'],node['y'];w,h=node['w']/2,node['h']/2
    return {'t':(x,y-h),'b':(x,y+h),'l':(x-w,y),'r':(x+w,y)}[name]


def label(x,y,text,size=18,color='#526575',weight=400,anchor='middle'):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" dominant-baseline="central" '
            f'font-family="{FAMILY}" font-size="{size}" font-weight="{weight}" fill="{color}">'
            +html.escape(text)+'</text>')


def mermaid(chart):
    lines=['flowchart TB']
    for node in chart['nodes']:
        text=json.dumps('<br/>'.join(node['lines']),ensure_ascii=False)
        shape='{'+text+'}' if node['kind']=='decision' else '['+text+']'
        lines.append('    '+node['id']+shape+':::'+node['kind'])
    for edge in chart['edges']:
        mark=' -->'+('|'+edge['label']+'|' if edge['label'] else '')+' '
        lines.append('    '+edge['source']+mark+edge['target'])
    for kind,(fill,stroke,color) in PALETTE.items():
        lines.append(f'    classDef {kind} fill:{fill},stroke:{stroke},color:{color},stroke-width:1.5px')
    return '\n'.join(lines)+'\n'


def render(chart):
    width,height=chart['width'],chart['height'];nodes={node['id']:node for node in chart['nodes']}
    if len(nodes)!=len(chart['nodes']):raise ValueError('Duplicate node ID')
    bounds=[]
    for node in nodes.values():
        if node['kind'] not in PALETTE:raise ValueError('Unknown node style')
        rect=QRectF(node['x']-node['w']/2,node['y']-node['h']/2,node['w'],node['h'])
        if rect.left()<30 or rect.right()>width-30 or rect.top()<100 or rect.bottom()>height-90:
            raise ValueError('Node is outside its content area: '+chart['id']+'/'+node['id'])
        for other,previous in bounds:
            if rect.intersects(previous):raise ValueError('Overlapping nodes: '+node['id']+'/'+other)
        bounds.append((node['id'],rect))
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">'+html.escape(chart['title'])+'</title>',
        '<desc id="desc">'+html.escape(chart['subtitle'])+'</desc>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#8a9aa6"/></marker></defs>',
        f'<rect width="{width}" height="{height}" rx="16" fill="#ffffff"/>',
        '<rect x="44" y="35" width="5" height="31" rx="2" fill="#167467"/>',
        label(67,51,chart['title'],27,'#1b3440',600,'start'),
        label(67,86,chart['subtitle'],18,'#647481',400,'start')]
    edge_labels=[]
    for edge in chart['edges']:
        source,target=nodes[edge['source']],nodes[edge['target']]
        points=[port(source,edge['from_port']),*map(tuple,edge['via']),port(target,edge['to_port'])]
        if any(not 25<=x<=width-25 or not 105<=y<=height-80 for x,y in points):raise ValueError('Edge is outside content')
        path='M '+' L '.join(f'{x:g} {y:g}' for x,y in points)
        parts.append(f'<path d="{path}" fill="none" stroke="#8a9aa6" stroke-width="1.8" stroke-linejoin="round" marker-end="url(#arrow)"/>')
        if edge['label']:
            x,y=edge['label_position'] or ((points[0][0]+points[-1][0])/2,(points[0][1]+points[-1][1])/2)
            metrics=QFontMetricsF(font(16));text_width=metrics.horizontalAdvance(edge['label'])+14
            edge_labels.extend([f'<rect x="{x-text_width/2:g}" y="{y-12:g}" width="{text_width:g}" height="24" rx="5" fill="#ffffff"/>',label(x,y,edge['label'],16)])
    for node in nodes.values():
        fill,stroke,color=PALETTE[node['kind']];x,y=node['x'],node['y'];w,h=node['w'],node['h']
        if node['kind']=='decision':
            parts.append(f'<path d="M {x:g} {y-h/2:g} L {x+w/2:g} {y:g} L {x:g} {y+h/2:g} L {x-w/2:g} {y:g} Z" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        else:parts.append(f'<rect x="{x-w/2:g}" y="{y-h/2:g}" width="{w:g}" height="{h:g}" rx="14" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
        count=len(node['lines']);spacing=27
        for i,text in enumerate(node['lines']):
            size=20 if i==0 else 17
            if 'en' in chart['id']:size=19 if i==0 else 16
            if node['w']<300:size=18 if i==0 else 16
            available=node['w']-24
            if node['kind']=='decision':available=node['w']*.78
            if QFontMetricsF(font(size,600 if i==0 else 400)).horizontalAdvance(text)>available:
                raise ValueError('Label exceeds node width: '+chart['id']+'/'+node['id']+'/'+text)
            parts.append(label(x,y+(i-(count-1)/2)*spacing,text,size,color,600 if i==0 else 400))
    parts.extend(edge_labels)
    footer_top=height-32-24*len(chart['footer'])
    parts.append(f'<line x1="60" x2="{width-60}" y1="{footer_top}" y2="{footer_top}" stroke="#e3e9ec"/>')
    for i,text in enumerate(chart['footer']):parts.append(label(60,footer_top+26+i*24,text,16,'#647481',400,'start'))
    parts.append('</svg>');svg='\n'.join(parts)+'\n'
    target=HERE/(chart['id']+'.svg');target.write_text(svg,encoding='utf-8')
    renderer=QSvgRenderer(svg.encode('utf-8'))
    if not renderer.isValid():raise ValueError('Invalid SVG')
    image=QImage(width,height,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.white)
    painter=QPainter(image);renderer.render(painter);painter.end()
    if not image.save(str(HERE/(chart['id']+'.png'))):raise OSError('PNG could not be saved')
    (HERE/(chart['id']+'.mmd')).write_text(mermaid(chart),encoding='utf-8')
    return {'id':chart['id'],'nodes':len(nodes),'edges':len(chart['edges']),
            'svg_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}


def main():
    app=QGuiApplication.instance() or QGuiApplication([])
    windows_font=Path('C:/Windows/Fonts/msyh.ttc')
    if windows_font.is_file():QFontDatabase.addApplicationFont(str(windows_font))
    data=json.loads((HERE/'workflows.json').read_text(encoding='utf-8'))
    rows=[render(chart) for chart in data['charts']]
    page=['# 工作流程 · Mermaid 版本','','由workflows.json生成；图像版本与使用说明见[工作流程](../WORKFLOW.md)。','']
    for chart in data['charts']:
        page.extend(['## '+chart['title'],'','```mermaid',mermaid(chart).rstrip(),'```',''])
    (HERE/'MERMAID.md').write_text('\n'.join(page),encoding='utf-8')
    print(json.dumps({'rendered':rows,'source':'workflows.json'},ensure_ascii=False,indent=2))
    app.quit()


if __name__=='__main__':main()
