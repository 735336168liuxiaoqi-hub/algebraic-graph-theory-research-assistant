"""Portable whole-figure labels, independent of vertex identities and computation."""
import copy
from html import escape
import math
import re


DEFAULTS={'text':'','position':'below','offset':[0.,0.],'font_size':12,'color':'#233c47'}
_SUB=dict(zip('₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ','0123456789+-=()aehijklmnoprstuvx'))
_SUPER=dict(zip('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾','0123456789+-=()'))
_TO_SUB={v:k for k,v in _SUB.items()}
_TO_SUPER={v:k for k,v in _SUPER.items()}


def schema():
    return {'type':'object','description':'整张图的可见标签，仅影响绘图；保存在style.graph_label。','additionalProperties':False,'properties':{
        'text':{'type':'string','maxLength':128,'description':'单行显示文本，例如G_1、H_k、图(a)；不执行TeX命令。'},
        'position':{'enum':['below','above'],'description':'下方below或上方above，默认below。'},
        'offset':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'number','minimum':-5,'maximum':5},'description':'相对最长图跨度的偏移[x,y]，向右/向上为正；默认[0,0]。'},
        'font_size':{'type':'number','minimum':6,'maximum':36,'description':'标签字号pt，默认12。'},
        'color':{'type':'string','pattern':'^#[0-9a-fA-F]{6}$','description':'标签颜色#RRGGBB，默认#233c47。'}},'required':['text']}


def validate(value):
    """Offsets are fractions of the drawing's longest span; positive y is up."""
    if not isinstance(value,dict) or set(value)-set(DEFAULTS) or 'text' not in value:
        raise ValueError('图标签需要text，可选position、offset、font_size、color。')
    result={**copy.deepcopy(DEFAULTS),**copy.deepcopy(value)}
    text=result['text']
    if not isinstance(text,str) or len(text)>128 or any(ord(c)<32 for c in text):
        raise ValueError('图标签使用至多128字符的单行文本。')
    if result['position'] not in ('below','above'):raise ValueError('图标签位置使用below或above。')
    xy=result['offset']
    if not isinstance(xy,list) or len(xy)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>5 for v in xy):
        raise ValueError('图标签偏移为±5倍图跨度内的有限二维数。')
    size=result['font_size']
    if type(size) not in (int,float) or not math.isfinite(size) or not 6<=size<=36:
        raise ValueError('图标签字号为6..36pt。')
    if not isinstance(result['color'],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',result['color']):
        raise ValueError('图标签颜色使用#RRGGBB。')
    return result


def display_text(text):
    """Recognize simple G_1, H_k, G_{n+1} notation; never evaluate TeX."""
    def convert(match):
        base,operator,tail=match.groups();table=_TO_SUB if operator=='_' else _TO_SUPER
        tail=tail.strip('{}')
        return base+''.join(table[c] for c in tail) if all(c in table for c in tail) else match[0]
    return re.sub(r'([A-Za-z])([_^])(\{[A-Za-z0-9+\-=()]{1,32}\}|[A-Za-z0-9]+)',convert,text)


def text_runs(text):
    result=[]
    for char in display_text(text):
        kind='sub' if char in _SUB else 'sup' if char in _SUPER else 'text'
        value=_SUB.get(char,_SUPER.get(char,char))
        if result and result[-1][0]==kind:result[-1]=(kind,result[-1][1]+value)
        else:result.append((kind,value))
    return result


def html_text(text):
    return ''.join(escape(v) if k=='text' else '<'+k+'>'+escape(v)+'</'+k+'>' for k,v in text_runs(text))


def tex_text(text):
    from graph_research.rendering.tikz import escape_latex
    return ''.join(escape_latex(v) if k=='text' else '\\text'+('subscript' if k=='sub' else 'superscript')+'{'+escape_latex(v)+'}' for k,v in text_runs(text))


def layout(points,label):
    """Position relative to unlabelled geometry; labels never change its scale."""
    points=[(float(p[0]),float(p[1])) for p in points]
    low=[min(p[i] for p in points) for i in (0,1)] if points else [-.5,-.5]
    high=[max(p[i] for p in points) for i in (0,1)] if points else [.5,.5]
    span=max(high[i]-low[i] for i in (0,1)) or 1.
    above=label['position']=='above'
    return [(low[0]/2+high[0]/2)+label['offset'][0]*span,
            (high[1]+.06*span if above else low[1]-.06*span)+label['offset'][1]*span],span
