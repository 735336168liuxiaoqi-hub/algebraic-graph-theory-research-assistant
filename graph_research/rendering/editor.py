"""Offline hypergraph layout editor and validated, typed coordinate files."""
import json
import math
from importlib.resources import files
from pathlib import Path
import uuid

from graph_research.rendering.geometry import vertex_positions


FORMAT = "graph-research-layout"
MAX_FILE_BYTES = 2_000_000


def validate_layout(data, hypergraph=None):
    """Validate coordinates AND topology before applying any changes.

    Labels are safe JSON integers/strings, not object keys, so 1 and '1' stay
    distinct. Edges reference vertex indices; isolated vertices are retained.
    """
    from graph_research.hypergraphs import Hypergraph
    if not isinstance(data, dict) or data.get("format") != FORMAT or type(data.get("version")) is not int or data["version"] != 1:
        raise ValueError("Expected a graph-research-layout version1 file")
    labels, edges, xy = data.get("vertices"), data.get("edges"), data.get("positions")
    if not isinstance(labels, list) or any(type(v) not in (int,str) or (type(v) is int and abs(v)>2**53-1) for v in labels):
        raise ValueError("Layout labels must be strings or safe JSON integers")
    if len(set(labels)) != len(labels):
        raise ValueError("Repeated vertex labels in layout file")
    if not isinstance(edges,list) or any(not isinstance(e,list) or len(e)<2 or
            any(type(i) is not int or not 0<=i<len(labels) for i in e) for e in edges):
        raise ValueError("Layout edges must reference valid vertex indices")
    if not isinstance(xy,list) or len(xy)!=len(labels) or any(
            not isinstance(p,list) or len(p)!=2 or any(type(c) not in (int,float) or abs(c)>1e9 or not math.isfinite(c) for c in p) for p in xy):
        raise ValueError("One finite coordinate pair per vertex required (absolute value <=1e9)")
    graph = Hypergraph([[labels[i] for i in e] for e in edges],vertices=labels,weights=data.get("weights"))
    positions = vertex_positions(graph,dict(zip(labels,xy)))
    if 'style' in data:
        from graph_research.graph_input.styles import validate_style
        validate_style(data['style'],labels,[{'vertices':list(e)} for e in graph.Edges])
    if hypergraph is not None:
        supplied = {frozenset(e) for e in graph.Edges}
        expected = {frozenset(e) for e in hypergraph.Edges}
        if set(labels)!=set(hypergraph.Vertices) or supplied!=expected:
            raise ValueError("Layout topology does not match this hypergraph; coordinates were not changed")
    return graph,positions


def layout_document(hypergraph, pos=None, *, seed=42, layout="spring"):
    stored = getattr(hypergraph,"_pos",None)
    positions = vertex_positions(hypergraph,stored if pos is None and stored else pos,seed=seed,layout=layout)
    labels = hypergraph.vertices()
    index = {v:i for i,v in enumerate(labels)}
    document = {"format":FORMAT,"version":1,"vertices":labels,
                "edges":[[index[v] for v in e] for e in hypergraph.Edges],
                "weights":hypergraph.weights.tolist(),
                "positions":[positions[v].tolist() for v in labels]}
    validate_layout(document)
    return document


def read_layout(path, hypergraph=None):
    path = Path(path)
    if path.stat().st_size>MAX_FILE_BYTES:
        raise ValueError("Layout file exceeds2MB")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    graph,positions = validate_layout(data,hypergraph)
    return data,graph,positions


def save_positions(hypergraph, path, **options):
    from graph_research.runtime.storage import atomic_text
    overwrite=options.pop('overwrite',False)
    document = layout_document(hypergraph,**options)
    path = Path(path)
    atomic_text(path,json.dumps(document,ensure_ascii=False,indent=2,allow_nan=False),overwrite=overwrite)
    hypergraph.set_pos(dict(zip(document["vertices"],document["positions"])))
    return path.resolve()


def load_positions(hypergraph, path):
    _,_,positions = read_layout(path,hypergraph)
    hypergraph.set_pos(positions)
    return hypergraph.get_pos()


def write_editor(hypergraph, path, *, pos=None, seed=42, layout="spring", open_browser=False,overwrite=False):
    """Create a self-contained page; saving downloads a reloadable JSON file."""
    path = Path(path)
    if path.suffix.lower() not in (".html",".htm"):
        raise ValueError("Editor output must be an HTML file")
    document = layout_document(hypergraph,pos,seed=seed,layout=layout)
    encoded = json.dumps(document,ensure_ascii=False,allow_nan=False)
    # Labels are text, never executable markup, even if they contain </script>.
    for character,replacement in (("&","\\u0026"),("<","\\u003c"),(">","\\u003e"),("\u2028","\\u2028"),("\u2029","\\u2029")):
        encoded = encoded.replace(character,replacement)
    template = files("graph_research").joinpath("assets/hypergraph_editor.html").read_text(encoding="utf-8")
    from graph_research.runtime.storage import atomic_text
    atomic_text(path,template.replace("__LAYOUT_JSON__",encoded),overwrite=overwrite)
    if open_browser:
        import webbrowser
        webbrowser.open(path.resolve().as_uri())
    return path.resolve()


def hypergraph_editor_tool(edges, vertices=None, seed=42, layout="spring"):
    """生成离线编辑器文件，不替用户拖动，也不回读浏览器当前状态。

    返回HTML路径；后续处理需用户保存JSON，由宿主load_pos/from_layout
    读取，或将其中positions传入导出工具。可非一致、含孤立点或为空。
    """
    from graph_research.hypergraphs import Hypergraph
    h = Hypergraph(edges,vertices=vertices)
    if h.order()>128 or sum(map(len,h.Edges))>2048:
        raise ValueError("Editor tool supports at most128 vertices and2048 incidences")
    output = Path.cwd()/"outputs"/"hypergraph-editors"/uuid.uuid4().hex
    path = write_editor(h,output/"editor.html",seed=seed,layout=layout)
    return {"editor":str(path),"order":h.order(),"size":h.size(),"uniform":h.is_uniform(),
            "instructions":"Open editor.html, drag vertices, save layout JSON; reload with h.load_pos(path). No model or server is required."}


def editor_tool_definitions(object_schema):
    label = {"type":["integer","string"]}
    return [("hypergraph_editor","生成离线超图布局编辑器：拖动顶点实时更新超边曲线，撤销/重做，保存/导入坐标JSON及导出SVG。",
             hypergraph_editor_tool,object_schema({
                 "edges":{"type":"array","maxItems":128,"items":{"type":"array","minItems":2,"maxItems":128,"items":label}},
                 "vertices":{"type":"array","maxItems":128,"items":label},
                 "seed":{"type":"integer","minimum":0,"maximum":4294967295},
                 "layout":{"enum":["spring","circular"]}},["edges"]))]
