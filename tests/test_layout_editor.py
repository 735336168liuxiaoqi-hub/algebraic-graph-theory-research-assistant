"""Coordinate round trips, topology validation and safe offline generation."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import shutil
import subprocess
from unittest.mock import patch

import numpy as np

from graph_research import Hypergraph
from graph_research.layout_editor import layout_document, validate_layout
from graph_research.registry import ToolRegistry
from graph_research.plotting import hyperedge_path


class LayoutEditorTests(unittest.TestCase):
    def test_roundtrip_mixed_labels_isolates_weights_and_reordered_graph(self):
        h=Hypergraph([[1,'1','a'],['a','b']],vertices=[1,'1','a','b','isolated'],weights=[2,3])
        pos={v:(i,i*i) for i,v in enumerate(h.Vertices)}
        h.set_pos(pos)
        with tempfile.TemporaryDirectory() as temporary:
            path=h.save_pos(Path(temporary)/'layout.json')
            rebuilt=Hypergraph.from_layout(path)
            self.assertEqual(rebuilt.get_pos(),pos)
            self.assertEqual(rebuilt.weights.tolist(),[2,3])
            reordered=Hypergraph([['b','a'],['a','1',1]],vertices=list(reversed(h.Vertices)))
            reordered.load_pos(path)
            self.assertEqual(reordered.get_pos(),pos)

    def test_bad_topology_and_coordinates_leave_current_layout_untouched(self):
        h=Hypergraph([[0,1,2]])
        h.set_pos({0:(0,0),1:(1,0),2:(0,1)})
        original=h.get_pos()
        data=layout_document(h)
        bad=[]
        for value in (float('nan'),float('inf'),True,'0',1e10):
            d=copy.deepcopy(data);d['positions'][0][0]=value;bad.append(d)
        d=copy.deepcopy(data);d['positions'][1]=d['positions'][0];bad.append(d)
        d=copy.deepcopy(data);d['edges']=[[0,1]];bad.append(d)
        d=copy.deepcopy(data);d['vertices']=[0,1,3];bad.append(d)
        for d in bad:
            with self.assertRaises(ValueError):validate_layout(d,h)
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'wrong.json'
            path.write_text(json.dumps(bad[-1]),encoding='utf-8')
            with self.assertRaises(ValueError):h.load_pos(path)
        self.assertEqual(h.get_pos(),original)

    def test_empty_graph_and_unicode_labels(self):
        for h in (Hypergraph(),Hypergraph(vertices=['孤立点']),Hypergraph([['点甲','点乙']])):
            data=layout_document(h)
            rebuilt,_=validate_layout(data,h)
            self.assertEqual(rebuilt.vertices(),h.vertices())
        with self.assertRaises(ValueError):layout_document(Hypergraph([[1,2**54]]))

    def test_offline_editor_escapes_script_labels_and_embeds_exact_positions(self):
        label='</script><img src=x onerror=alert(1)>'
        h=Hypergraph([[label,'乙']])
        pos={label:(0,0),'乙':(1,1)}
        with tempfile.TemporaryDirectory() as temporary:
            with patch('webbrowser.open') as browser:
                path=h.edit_layout(Path(temporary)/'editor.html',pos=pos)
                browser.assert_not_called()
            text=path.read_text(encoding='utf-8')
            self.assertNotIn(label,text)
            encoded=text.split('<script type="application/json" id="layout-data">')[1].split('</script>')[0]
            data=json.loads(encoded)
            self.assertEqual(data['vertices'],h.vertices())
            self.assertEqual(data['positions'],[list(pos[v]) for v in h.Vertices])
            self.assertNotIn('__LAYOUT_JSON__',text)
            self.assertNotIn('https://',text)

    def test_registry_editor_generates_an_offline_file(self):
        with tempfile.TemporaryDirectory() as temporary,patch('graph_research.layout_editor.Path.cwd',return_value=Path(temporary)):
            result=ToolRegistry().call('hypergraph_editor',{'edges':[[0,1],[1,2,3]],'vertices':[0,1,2,3,4]})
            self.assertFalse(result['uniform'])
            self.assertTrue(Path(result['editor']).is_file())
            self.assertEqual(result['order'],5)

    @unittest.skipUnless(shutil.which('node'),'Node is only needed for cross-language development verification')
    def test_browser_curve_matches_python_static_export(self):
        source=(Path(__file__).resolve().parents[1]/'graph_research/assets/hypergraph_editor.html').read_text(encoding='utf-8')
        function=source[source.index('function geometry(ids)'):source.index('function pathData(g)')]
        samples=[[[0,0],[1,2]],[[0,0],[2,0],[0,2]],
                 [[1,1],[0,0],[2,-1],[3,2]],[[0,0],[1,0],[2,0]]]
        script="const samples=JSON.parse(require('fs').readFileSync(0,'utf8'));let positions;"+function+";process.stdout.write(JSON.stringify(samples.map(p=>{positions=p;return geometry(p.map((_,i)=>i));})));"
        output=subprocess.run([shutil.which('node'),'-e',script],input=json.dumps(samples),text=True,capture_output=True,check=True)
        for points,geometry in zip(samples,json.loads(output.stdout)):
            vertices=geometry['points'] if len(points)==2 else [geometry['points'][0]]+[p for segment in geometry['segments'] for p in segment[1:]]+[geometry['points'][0]]
            np.testing.assert_allclose(vertices,hyperedge_path(points).vertices,atol=1e-12)


if __name__=='__main__':
    unittest.main()
