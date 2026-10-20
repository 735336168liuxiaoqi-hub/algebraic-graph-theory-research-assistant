"""LaTeX export geometry, label escaping and ordinary-graph support."""
import json
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
        np.testing.assert_allclose(actual,expected,atol=1e-12)
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


if __name__=='__main__':
    unittest.main()
