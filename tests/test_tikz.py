"""LaTeX export geometry, label escaping and ordinary-graph support."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import networkx as nx
import numpy as np

from graph_research import Hypergraph
from graph_research import graphs
from graph_research.plotting import COLORS,hyperedge_path
from graph_research.tikz import escape_latex,hypergraph_to_tikz,tex_number
from graph_research.registry import ToolRegistry


PAIR = r"\((-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)\)"


class TikzTests(unittest.TestCase):
    def test_graph_and_hypergraph_save_preserve_extension_and_no_clobber_rules(self):
        from graph_research.rendering import tikz
        for producer,save,obj in [('graph_to_tikz',tikz.save_graph_tikz,nx.path_graph(2)),
                                  ('hypergraph_to_tikz',tikz.save_hypergraph_tikz,Hypergraph([[0,1,2]]))]:
            with self.subTest(producer=producer),tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/'drawing.TeX'
                path.write_text('existing scientific figure',encoding='utf-8')
                with self.assertRaises(FileExistsError):save(obj,path)
                self.assertEqual(path.read_text(encoding='utf-8'),'existing scientific figure')
                save(obj,path,overwrite=True,standalone=False)
                self.assertIn(r'\begin{tikzpicture}',path.read_text(encoding='utf-8'))
                self.assertNotIn(r'\documentclass',path.read_text(encoding='utf-8'))
                with patch.object(tikz,producer,side_effect=AssertionError('Invalid suffix must fail before rendering')):
                    with self.assertRaises(ValueError):save(obj,Path(folder)/'invalid.txt')
                self.assertFalse((Path(folder)/'invalid.txt').exists())

    def test_hyperedge_control_points_match_existing_renderer(self):
        h=Hypergraph([[0,1,2],[2,3],[3,4,5,6]],vertices=list(range(8)))
        pos={0:(-2,0),1:(-1,1),2:(0,0),3:(1,0),4:(2,1),5:(3,0),6:(2,-1),7:(0,1.7)}
        code=h.to_tikz(pos=pos,normalize=False)
        controls=re.findall(r"\.\. controls "+PAIR+r" and "+PAIR+r" \.\. "+PAIR,code)
        actual=np.array(controls,dtype=float).reshape(-1,3,2)
        expected=[]
        for e in h.Edges:
            if len(e)>2:
                p=hyperedge_path([pos[v] for v in e]).vertices
                expected.extend(p[j:j+3] for j in range(1,len(p)-1,3))
        # Export coordinates are now rounded; renderer geometry remains exact.
        np.testing.assert_allclose(actual,expected,atol=5e-5,rtol=0)
        self.assertIn(r'(v2) -- (v3);',code)
        self.assertEqual(code.count(r'\fill[black]'),8)
        self.assertNotIn('hobby',code)

    def test_simple_graph_has_black_straight_edges_and_isolates(self):
        g=nx.Graph();g.add_nodes_from(['a','b','isolated']);g.add_edge('a','b')
        pos={'a':(-1,0),'b':(1,0),'isolated':(0,1)}
        code=graphs.to_tikz(g,pos=pos)
        self.assertIn(r'\definecolor{hgcolor0}{HTML}{000000}',code)
        self.assertIn('(v0) -- (v1)',code)
        self.assertNotIn('.. controls',code)
        self.assertIn('{isolated};',code)
        self.assertEqual(code.count(r'\fill[black]'),3)
        directed=graphs.to_tikz(nx.DiGraph([(0,1)]));self.assertIn('directed: true',directed)
        with self.assertRaises(ValueError):graphs.to_tikz(nx.Graph([(0,0)]))

    def test_labels_escaped_and_chinese_document_selects_xelatex(self):
        label=r'点_甲%&#${}^~\input{secret}'
        h=Hypergraph([[label,'乙']])
        code=h.to_tikz(standalone=True)
        self.assertIn(r'\usepackage[UTF8]{ctex}',code)
        self.assertIn('% !TeX program = xelatex',code)
        self.assertIn(escape_latex(label),code)
        self.assertNotIn(r'\input{secret}',code)
        self.assertIn(r'\textbackslash{}input\{secret\}',code)
        self.assertNotIn(r'\documentclass',h.to_tikz())

    def test_normalization_extreme_coordinates_and_empty_graph(self):
        h=Hypergraph([[0,1]])
        code=h.to_tikz(pos={0:(1e9,1e9),1:(1e9+1,1e9)},size_cm=8)
        points=np.array(re.findall(PAIR,code),dtype=float)
        self.assertLessEqual(np.max(np.abs(points)),4)
        with self.assertRaises(ValueError):h.to_tikz(pos={0:(1e9,0),1:(1e9+1,0)},normalize=False)
        self.assertIn('use as bounding box',Hypergraph().to_tikz(standalone=True))
        self.assertEqual(tex_number(1e-12),'0.000000000001')
        self.assertEqual(tex_number(-0.),'0')

    def test_save_and_model_tools_export_complete_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            h=Hypergraph([[0,1,2]])
            path=h.save_tikz(root/'diagram.tex')
            self.assertIn(r'\end{document}',path.read_text(encoding='utf-8'))
            graphs.save_tikz(nx.path_graph(3),root/'graph.tex')
            with patch('graph_research.tikz.Path.cwd',return_value=root):
                for name,edges in [('hypergraph_tikz',[[0,1,2]]),('graph_tikz',[[0,1],[1,2]])]:
                    result=ToolRegistry().call(name,{'edges':edges})
                    self.assertIn(r'\begin{tikzpicture}',result['tikz'])
                    self.assertTrue(all(Path(p).is_file() for p in result['files'].values()))

    @unittest.skipUnless(shutil.which('node'),'Node is only used for cross-language development checks')
    def test_browser_and_python_tikz_geometry_and_escaping_match(self):
        source=(Path(__file__).resolve().parents[1]/'graph_research/assets/hypergraph_editor.html').read_text(encoding='utf-8')
        geometry=source[source.index('function geometry(ids)'):source.index('function pathData(g)')]
        label_offset=source[source.index('function labelOffset(id)'):source.index('function render()')]
        exporter=source[source.index('function texNumber(value)'):source.index('function updateLatex()')]
        h=Hypergraph([[0,1,2],[2,3]],vertices=list(range(5)))
        pos={0:(0,0),1:(2,1),2:(3,-1),3:(4,0),4:(2,-2)}
        data={'positions':[pos[v] for v in h.Vertices],'labels':h.vertices(),'edges':[list(e) for e in h.Edges],'colors':COLORS}
        harness="const data=JSON.parse(require('fs').readFileSync(0,'utf8'));const {positions,labels,edges,colors}=data;"+geometry+label_offset+exporter+";process.stdout.write(JSON.stringify({code:tikzCode({standalone:false,edgeLabels:true}),escaped:texEscape('点_甲%&#${}^~\\\\input{secret}')}));"
        output=json.loads(subprocess.run([shutil.which('node'),'-e',harness],input=json.dumps(data),capture_output=True,text=True,encoding='utf-8',check=True).stdout)
        python=h.to_tikz(pos=pos,edge_labels=True)
        np.testing.assert_allclose(np.array(re.findall(PAIR,output['code']),dtype=float),np.array(re.findall(PAIR,python),dtype=float),atol=1e-12)
        self.assertEqual(output['escaped'],escape_latex(r'点_甲%&#${}^~\input{secret}'))


class CoordinateFormattingTests(unittest.TestCase):
    def test_short_decimal_pairs_negative_zero_and_round_trip_fallback(self):
        from graph_research.rendering.tex_coordinates import TexCoordinates
        coords=TexCoordinates()
        self.assertEqual(coords.point([1.234567891234,-2e-12]),'(1.2346,0)')
        self.assertEqual(coords.point([2.5,3]),'(2.5,3)')
        self.assertEqual(coords.point([.03125,-.03125]),'(0.0312,-0.0312)')
        for point in ([float('nan'),0],[float('inf'),0]):
            with self.assertRaises(ValueError):coords.point(point)
        close=TexCoordinates(vertices=[[0,0],[1e-30,0]])
        self.assertIsNone(close.places)
        self.assertNotEqual(close.point([0,0]),close.point([1e-30,0]))
        self.assertNotIn('e',close.point([1e-30,0]))

    def test_precision_increases_for_close_vertices_and_nonzero_segments(self):
        from graph_research.rendering.tex_coordinates import TexCoordinates
        coords=TexCoordinates(vertices=[[1,2],[1.000001,2]])
        self.assertGreater(coords.places,4)
        self.assertNotEqual(coords.point([1,2]),coords.point([1.000001,2]))
        segment=[[0,0],[1e-7,0],[1e-7,0],[0,0]]
        coords=TexCoordinates(vertices=[[0,0]],segments=[segment])
        self.assertGreater(coords.places,4)
        self.assertGreater(len({coords.point(p) for p in segment}),1)

    def test_all_graph_export_routes_round_coordinates_but_keep_data_and_styles(self):
        from graph_research.graph_input.document import document
        from graph_research.rendering.presentation import document_to_tikz
        from graph_research.rendering.tex_coordinates import for_paths
        from graph_research.rendering.presentation import coordinates,geometry
        graphs=[document([0,1,2],[{'vertices':[0,1],'weight':2},{'vertices':[1,0],'weight':3}],
                         directed=True,weighted=True,positions=[[.123456789,0],[2,1.987654321],[4,-1]]),
                document([0,1,2],[{'vertices':[0,1,2],'weight':2}],graph_type='hypergraph',weighted=True,
                         positions=[[.123456789,0],[2,1.987654321],[4,-1]])]
        for graph in graphs:
            data=graph.to_dict();code=document_to_tikz(graph)
            pairs=np.array(re.findall(PAIR,code),dtype=float)
            self.assertTrue(np.isfinite(pairs).all())
            self.assertTrue(all(len(v.split('.')[-1])<=4 for pair in re.findall(PAIR,code) for v in pair if '.' in v))
            pos=coordinates(graph);fmt=for_paths(pos,geometry(graph,pos))
            for i,v in enumerate(graph.vertices):self.assertIn(f'\\coordinate (v{i}) at '+fmt.point(pos[v])+';',code)
            self.assertEqual(graph.to_dict(),data)
        h=Hypergraph([[0,1,2]]);pos={0:(.123456789,0),1:(2,1.987654321),2:(4,-1)}
        before={v:tuple(p) for v,p in pos.items()};h.to_tikz(pos=pos)
        self.assertEqual(pos,before)

    @unittest.skipUnless(shutil.which('node'),'Node is needed for browser export parity')
    def test_browser_fixed_rounding_and_adaptive_coordinates_match_python(self):
        from graph_research.rendering.tex_coordinates import TexCoordinates
        source=(Path(__file__).resolve().parents[1]/'graph_research/assets/hypergraph_editor.html').read_text(encoding='utf-8')
        functions=source[source.index('function texNumber(value)'):source.index('function texEscape(label)')]
        geometry=source[source.index('function geometry(ids)'):source.index('function pathData(g)')]
        samples=[.03125,-.03125,1.23456789,-2e-12,2.5,3.,.00005,.00015]
        script='const samples='+json.dumps(samples)+';let positions=[[0,0],[.000001,0],[2,1]],edges=[[0,1],[1,2]];'+geometry+functions+";process.stdout.write(JSON.stringify({fixed:samples.map(v=>texFixed(v,4)),places:texCoordinates({normalize:false}).places,points:positions.map(texCoordinates({normalize:false}).point)}));"
        result=json.loads(subprocess.run([shutil.which('node'),'-e',script],capture_output=True,text=True,check=True).stdout)
        fmt=TexCoordinates(vertices=[[0,0],[.000001,0],[2,1]])
        self.assertEqual(result['fixed'],[TexCoordinates().number(v) for v in samples])
        self.assertEqual(result['places'],fmt.places)
        self.assertEqual(result['points'],[fmt.point(p) for p in [[0,0],[.000001,0],[2,1]]])


os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPointF,Qt
    from PySide6.QtTest import QTest
    QT_AVAILABLE=True
except ImportError:QT_AVAILABLE=False


@unittest.skipUnless(QT_AVAILABLE,'Optional native desktop unavailable')
class LiveCoordinateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def test_all_native_editors_update_live_match_tex_and_leave_documents_untouched(self):
        from graph_research.desktop.graph_canvas import GraphCanvas
        from graph_research.desktop.schematic import SchematicCanvas
        from graph_research.desktop.layout import LayoutDialog
        from graph_research.graph_input.document import document
        from graph_research.schematics import template,to_tikz
        from graph_research.rendering.presentation import document_to_tikz
        from graph_research.desktop.i18n import set_language
        canvas=GraphCanvas();canvas.set_graph(document([0,1,2],[{'vertices':[0,1]},{'vertices':[1,0]}],directed=True,
                            positions=[[.123456789,0],[2,1.987654321],[4,-1]]))
        editors=[canvas,SchematicCanvas(template('F')),LayoutDialog({'edges':[[0,1,2]]})]
        try:
            for editor in editors:
                with self.subTest(editor=type(editor).__name__):
                    current=editor.current_graph if isinstance(editor,GraphCanvas) else editor.current_document
                    def data():
                        value=current();return value.to_dict() if hasattr(value,'to_dict') else value
                    controls=editor.coordinate_controls
                    items=list(editor.vertices.values()) if isinstance(editor.vertices,dict) else editor.vertices
                    before=data();undo=len(getattr(editor,'undo_stack',[]))
                    self.assertFalse(controls.enabled.isChecked())
                    self.assertTrue(all(not v.coordinate_caption.isVisible() for v in items))
                    controls.enabled.setChecked(True)
                    raw=[v.coordinate_caption.text() for v in items]
                    self.assertTrue(all(v.coordinate_caption.isVisible() for v in items))
                    controls.system.setCurrentIndex(1)
                    self.assertEqual(data(),before);self.assertEqual(len(getattr(editor,'undo_stack',[])),undo)
                    if isinstance(editor,SchematicCanvas):code=to_tikz(current())
                    elif isinstance(editor,GraphCanvas):code=document_to_tikz(current())
                    else:code=editor.graph.to_tikz(pos=dict(zip(current()['vertices'],current()['positions'])))
                    for item in items:self.assertIn(item.coordinate_caption.text(),code)
                    if not isinstance(editor,SchematicCanvas):self.assertNotEqual(raw,[v.coordinate_caption.text() for v in items])
                    old=items[0].coordinate_caption.text();items[0].setPos(items[0].pos()+QPointF(35,-21))
                    self.assertNotEqual(items[0].coordinate_caption.text(),old)  # before mouse release
                    controls.scope.setCurrentIndex(1);items[0].coordinate_focus()
                    self.assertTrue(items[0].coordinate_caption.isVisible())
                    self.assertTrue(all(not v.coordinate_caption.isVisible() for v in items[1:]))
                    moved=data();set_language('en')
                    self.assertEqual(controls.enabled.text(),'Show vertex coordinates')
                    self.assertEqual(controls.system.currentData(),'tex');self.assertEqual(data(),moved)
                    set_language('zh');self.assertEqual(controls.enabled.text(),'显示顶点坐标')
                    controls.enabled.setChecked(False)
                    self.assertTrue(all(not v.coordinate_caption.isVisible() for v in items));self.assertEqual(data(),moved)
        finally:
            set_language('zh')
            for editor in editors:editor.close();editor.deleteLater()
            self.app.processEvents()

    def test_real_click_focuses_one_vertex_without_creating_an_undo_entry(self):
        from graph_research.desktop.graph_canvas import GraphCanvas
        from graph_research.graph_input.document import document
        canvas=GraphCanvas();canvas.set_graph(document([0,1],[{'vertices':[0,1]}],positions=[[0,0],[2,1]]))
        canvas.resize(850,650);canvas.show();self.app.processEvents()
        try:
            controls=canvas.coordinate_controls;controls.enabled.setChecked(True);controls.scope.setCurrentIndex(1)
            before=canvas.current_graph().to_dict()
            QTest.mouseClick(canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=canvas.view.mapFromScene(canvas.vertices[1].pos()))
            self.app.processEvents()
            self.assertFalse(canvas.vertices[0].coordinate_caption.isVisible());self.assertTrue(canvas.vertices[1].coordinate_caption.isVisible())
            self.assertEqual(canvas.current_graph().to_dict(),before);self.assertEqual(canvas.undo_stack,[])
        finally:canvas.close();canvas.deleteLater();self.app.processEvents()


if __name__=='__main__':
    unittest.main()
