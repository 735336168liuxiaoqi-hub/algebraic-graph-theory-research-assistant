"""Symbolic semantics, graph preservation, common geometry and real mouse workflows."""
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import networkx as nx

from graph_research.graph_input.document import document,GraphDocument
from graph_research.graph_input.adapters import result_graph
from graph_research.schematics import SchematicDocument,template,from_graph,compress_path,expand,to_tikz,to_svg,save
from graph_research.schematics.geometry import primitives
from graph_research.tools import ToolRegistry


def path_graph(m=5,k=3):
    edges=[list(range(i*(k-1),i*(k-1)+k)) for i in range(m)];vertices=list(range(m*(k-1)+1))
    return document(vertices,[{'vertices':e} for e in edges],graph_type='hypergraph')


def incidence(graph):
    g=nx.Graph()
    for v in graph.vertices:g.add_node(('v',v),kind='v')
    for i,e in enumerate(graph.edges):
        g.add_node(('e',i),kind='e')
        for v in e['vertices']:g.add_edge(('e',i),('v',v))
    return g


class SchematicTests(unittest.TestCase):
    def test_whole_figure_label_survives_scene_roundtrip_and_expansion(self):
        from graph_research.graph_input.figure_label import validate
        data=template('E').to_dict();data['style']['graph_label']={'text':'H_k 图(a)','position':'above','offset':[.1,0]}
        scene=SchematicDocument(data);before=scene.to_dict();plain=template('E')
        without_label=[p for p in primitives(scene) if p.get('role')!='graph_label']
        self.assertEqual(without_label,primitives(plain))
        labels=[p for p in primitives(scene) if p.get('role')=='graph_label'];self.assertEqual(len(labels),1)
        self.assertEqual(labels[0]['text'],'Hₖ 图(a)');self.assertIn(r'H\textsubscript{k} 图(a)',to_tikz(scene))
        self.assertIn('ctex',to_tikz(scene,standalone=True));root=ET.fromstring(to_svg(scene))
        self.assertTrue(any('H' in ''.join(t.itertext()) and '图(a)' in ''.join(t.itertext()) for t in root.findall('{http://www.w3.org/2000/svg}text')))
        graph_text=next(t for t in root.findall('{http://www.w3.org/2000/svg}text') if '图(a)' in ''.join(t.itertext()))
        sub=graph_text.find('{http://www.w3.org/2000/svg}tspan')
        self.assertAlmostEqual(float(sub.attrib['font-size']),float(graph_text.attrib['font-size'])*.7)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'figure.json';save(scene,path);restored=SchematicDocument(json.loads(path.read_text(encoding='utf-8')))
            self.assertEqual(restored.to_dict(),before);self.assertEqual(to_tikz(restored),to_tikz(scene))
        graph=expand(scene,{'k':3,'a':1,'b':1,'c':1})
        self.assertEqual(graph.to_dict()['style']['graph_label'],validate(data['style']['graph_label']))
        self.assertEqual(from_graph(graph).to_dict()['style']['graph_label'],graph.to_dict()['style']['graph_label'])
        self.assertEqual(scene.to_dict(),before)

    def test_tex_coordinates_are_short_and_do_not_change_scene_or_svg(self):
        import re
        from graph_research.schematics.tikz import _tex_coordinates as tex_coordinates
        for name in ('E','F','H','G'):
            scene=template(name);data=scene.to_dict();data['vertices'][0]['xy']=[.123456789,-.987654321]
            scene=SchematicDocument(data);before=scene.to_dict();svg=to_svg(scene)
            code=to_tikz(scene);coords=tex_coordinates(scene)
            self.assertEqual(coords.places,4)
            for x,y in re.findall(r'\((-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)\)',code):
                self.assertTrue(all(len(v.split('.')[-1])<=4 for v in (x,y) if '.' in v))
            self.assertEqual(scene.to_dict(),before);self.assertEqual(to_svg(scene),svg)
            self.assertIn(coords.point(data['vertices'][0]['xy']),code)

    def test_templates_exports_and_explicit_instantiation(self):
        for name in ('E','F','H','G'):
            scene=template(name);code=to_tikz(scene,standalone=True);svg=to_svg(scene)
            self.assertIn('\\begin{tikzpicture}',code);self.assertIn('\\end{document}',code)
            self.assertNotIn('tkz-euclide',code);ET.fromstring(svg)
            graph=expand(scene,{'k':4,'a':3,'b':3,'c':3,'d':3,'q':2})
            self.assertTrue(graph.uniform);self.assertTrue(all(len(e['vertices'])==4 for e in graph.edges))
        self.assertEqual(expand(template('E'),{'k':3,'a':1,'b':2,'c':3}).size,6)
        with self.assertRaises(ValueError):expand(template('H'),{'k':3,'a':1,'b':1,'c':1,'d':1})
        with self.assertRaises(ValueError):expand(template('E'))

    def test_rejects_commands_invalid_parameters_aliasing_and_schematic_graph_confusion(self):
        raw=template('E').to_dict()
        for value in ['__import__("os")','a*2',r'\input{secret}',-1,True]:
            data=json.loads(json.dumps(raw));data['paths'][0]['length']=value
            with self.assertRaises(ValueError):SchematicDocument(data)
        for params in ({'k':3,'a':0,'b':2,'c':3},{'k':3,'a':True,'b':2,'c':3},{'k':128,'a':128,'b':128,'c':128}):
            with self.assertRaises(ValueError):expand(template('E'),params)
        with self.assertRaises(ValueError):GraphDocument(raw)
        with self.assertRaises(ValueError):result_graph({'ok':True,'tool':'hypergraph_schematic','arguments':{'operation':'export'},'result':{'diagram':raw}})
        data=template('E').to_dict();data['vertices'][0]['xy'][0]=20
        self.assertNotEqual(data,template('E').to_dict())

    def test_compression_preserves_source_and_expands_isomorphic_graph(self):
        for rank in (2,3,4):
            graph=path_graph(k=rank);identity=graph.sha256;scene=from_graph(graph);compressed=compress_path(scene,[4,2,0,1,3])
            self.assertEqual(graph.sha256,identity);self.assertEqual(scene.to_dict()['source_graph'],graph.to_dict())
            self.assertEqual(len(compressed.to_dict()['vertices']),2);self.assertEqual(compressed.to_dict()['paths'][0]['length'],5)
            expanded=expand(compressed)
            self.assertEqual((expanded.order,expanded.size),(graph.order,graph.size))
            self.assertTrue(nx.is_isomorphic(incidence(graph),incidence(expanded),node_match=lambda a,b:a['kind']==b['kind']))
            self.assertEqual(compressed.to_dict()['source_graph'],graph.to_dict())

    def test_compression_rejects_branching_multi_intersections_and_external_connections(self):
        for edges in ([[0,1,2],[0,3,4],[0,5,6]],[[0,1,2],[1,2,3],[3,4,5]],
                      [[0,1,2],[2,3,4],[4,5,6],[3,7,8]]):
            ids=list(dict.fromkeys(v for e in edges for v in e));scene=from_graph(document(ids,[{'vertices':e} for e in edges],graph_type='hypergraph'))
            before=scene.to_dict()
            with self.assertRaises(ValueError):compress_path(scene,[0,1,2])
            self.assertEqual(scene.to_dict(),before)

    def test_math_labels_and_vertex_text_escape_without_mutating_original_export(self):
        scene=template('G');self.assertIn('$P_{q+2}$',to_tikz(scene))
        data=template('blank').to_dict();data['vertices']=[{'id':r'点_甲\input{x}%','xy':[0,0]}]
        text=to_tikz(SchematicDocument(data),standalone=True,vertex_labels=True)
        self.assertNotIn(r'\input{x}',text);self.assertIn(r'\textbackslash{}input\{x\}',text);self.assertIn('ctex',text)
        from graph_research.hypergraphs import Hypergraph
        self.assertIn('% Members are ON each unfilled curve',Hypergraph([[0,1,2]]).to_tikz())

    def test_same_shared_geometry_updates_brace_label_and_exports_roundtrip(self):
        scene=template('E');before=primitives(scene);data=scene.to_dict();data['vertices'][1]['xy']=[1,3]
        moved=SchematicDocument(data);after=primitives(moved)
        self.assertNotEqual(before,after)
        before_label=next(p for p in before if p['kind']=='label');after_label=next(p for p in after if p['kind']=='label')
        self.assertNotEqual(before_label['xy'],after_label['xy'])
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);save(moved,root/'layout.json');loaded=SchematicDocument(json.loads((root/'layout.json').read_text(encoding='utf-8')))
            self.assertEqual(to_tikz(loaded),to_tikz(moved));self.assertEqual(to_svg(loaded),to_svg(moved))
            save(moved,root/'figure.tex')
            with self.assertRaises(FileExistsError):save(moved,root/'figure.tex')

    def test_styles_are_shared_and_cannot_inject_tex_or_svg(self):
        data=template('E').to_dict();data['style']={'line_color':'#234567','vertex_color':'#347856','edge_fill':'#ddebfa','line_width':.03}
        scene=SchematicDocument(data);self.assertIn('{234567}',to_tikz(scene));self.assertIn('stroke="#234567"',to_svg(scene))
        self.assertAlmostEqual(primitives(scene)[0]['width'],.03)
        data['style']['line_color']='red;\\input{x}'
        with self.assertRaises(ValueError):SchematicDocument(data)

    def test_all_fills_precede_outlines_in_svg_and_tex_for_mixed_edges_and_paths(self):
        scene=template('G');items=primitives(scene)
        fills=[i for i,p in enumerate(items) if p['kind']=='path' and p['fill']!='none']
        outlines=[i for i,p in enumerate(items) if p['kind']=='path' and p['stroke']!='none']
        self.assertTrue(fills);self.assertLess(max(fills),min(outlines))
        self.assertTrue(all(items[i]['stroke']=='none' for i in fills))
        svg=ET.fromstring(to_svg(scene));paths=svg.findall('{http://www.w3.org/2000/svg}path')
        painted=[i for i,p in enumerate(paths) if p.attrib['fill']!='none']
        stroked=[i for i,p in enumerate(paths) if p.attrib['stroke']!='none']
        self.assertLess(max(painted),min(stroked))
        code=to_tikz(scene);self.assertLess(code.rfind(r'\path[draw=none,fill=grsfill]'),code.find(r'\draw['))

    def test_center_edge_dots_follow_two_anchors_and_multiple_anchors_stay_centered(self):
        for shape in ('ellipse','circle'):
            for a,b in (([0,0],[2,0]),([1,-1],[1,2]),([-2,-1],[1,3]),([0,0],[.0001,.0001])):
                scene=SchematicDocument({'vertices':[{'id':'u','xy':a},{'id':'v','xy':b}],
                                         'edges':[{'vertices':['u','v'],'shape':shape,'vertex_ellipsis':True}]})
                dots=[p for p in primitives(scene) if p.get('role')=='dot'];self.assertEqual(len(dots),3)
                center=[(a[i]+b[i])/2 for i in (0,1)];dx,dy=b[0]-a[0],b[1]-a[1]
                for dot in dots:
                    x,y=dot['xy'];self.assertAlmostEqual((x-center[0])*dy-(y-center[1])*dx,0)
                    self.assertLess(math.dist(dot['xy'],center)+dot['r'],math.dist(a,b)/2+.12)
                for i in (0,1):self.assertAlmostEqual(sum(p['xy'][i] for p in dots)/3,center[i])
        points=[[0,0],[0,2],[0,3]]
        scene=SchematicDocument({'vertices':[{'id':i,'xy':p} for i,p in enumerate(points)],
                                  'edges':[{'vertices':[0,1,2],'vertex_ellipsis':True}]})
        dots=[p for p in primitives(scene) if p.get('role')=='dot']
        self.assertTrue(all(abs(p['xy'][1]-5/3)<1e-12 for p in dots))
        self.assertLess(dots[0]['xy'][0],dots[1]['xy'][0]);self.assertLess(dots[1]['xy'][0],dots[2]['xy'][0])

    def test_registered_tool_export_expand_and_numerical_binding_boundary(self):
        registry=ToolRegistry();data=template('E').to_dict()
        with tempfile.TemporaryDirectory() as directory,patch('graph_research.tools.schematic.Path.cwd',return_value=Path(directory)):
            result=registry.call('hypergraph_schematic',{'diagram':data})
            self.assertEqual(len(result['files']),4);self.assertTrue(all(Path(p).is_file() for p in result['files'].values()))
        result=registry.call('hypergraph_schematic',{'diagram':data,'operation':'expand','parameters':{'k':3,'a':1,'b':2,'c':3}})
        graph=result_graph({'ok':True,'tool':'hypergraph_schematic','arguments':{'operation':'expand'},'result':result})
        self.assertEqual(graph.size,6)
        spectrum=registry.call('hypergraph_spectrum',{'edges':result['hypergraph_spec']['edges'],'alpha':.3})
        self.assertTrue(spectrum['verification']['passed'])
        isolated=template('E').to_dict();isolated['vertices'].append({'id':'isolated','xy':[4,4]})
        result=registry.call('hypergraph_schematic',{'diagram':isolated,'operation':'expand','parameters':{'k':3,'a':1,'b':1,'c':1}})
        self.assertIsNone(result['spectral_input']);self.assertIn('isolated',result['graph_document']['vertices'])

    @unittest.skipUnless(os.name=='nt','Windows protected worker')
    def test_protected_export_has_all_artifacts_and_cannot_write_core(self):
        from graph_research.runtime.runner import run_tool
        from graph_research.runtime.integrity import CORE
        with tempfile.TemporaryDirectory() as directory:
            data=template('E').to_dict();data['style']['graph_label']={'text':'H_k'}
            root=Path(directory);result=run_tool('hypergraph_schematic',{'diagram':data},root/'tools',directory=root/'tasks')
            self.assertTrue(all(Path(p).is_file() for p in result['files'].values()))
            self.assertIn(r'H\textsubscript{k}',Path(result['files']['tex']).read_text(encoding='utf-8'))
        with self.assertRaises(PermissionError):save(template('E'),CORE/'accidental-schematic.tex')

    @unittest.skipUnless(os.name=='nt','Windows protected task workflow')
    def test_host_workflow_exports_expands_and_binds_spectral_input_without_models(self):
        from graph_research.assistant import create_subagent,SubagentLimits
        scene=template('E').to_dict()
        with tempfile.TemporaryDirectory() as directory:
            parent,_=create_subagent(directory,user_id='paper',limits=SubagentLimits(max_tool_calls=3,max_model_calls=0))
            response=parent.submit({'version':1,'request_id':'paper-workflow','objective':'导出并明确展开后计算',
                'execution':{'mode':'tools','steps':[
                    {'id':'figure','tool':'hypergraph_schematic','arguments':{'diagram':scene}},
                    {'id':'concrete','tool':'hypergraph_schematic','arguments':{'diagram':scene,'operation':'expand','parameters':{'k':3,'a':1,'b':2,'c':3}}},
                    {'id':'spectrum','tool':'hypergraph_spectrum','arguments':{'alpha':.3},'bindings':{'edges':{'step':'concrete','path':['spectral_input','edges']}}}]},
                'constraints':{'max_tool_calls':3,'max_model_calls':0,'allow_extensions':False}})
            self.assertEqual(response['status'],'completed');self.assertEqual(response['budget']['used'],{'tool_calls':3,'model_calls':0})
            self.assertTrue(response['results'][-1]['data']['verification']['passed'])


os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
try:
    from PySide6.QtCore import Qt,QPoint,QPointF,QEvent
    from PySide6.QtGui import QWheelEvent,QMouseEvent,QImage,QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from graph_research.desktop.schematic import SchematicDialog
    QT=True
except ImportError:QT=False


@unittest.skipUnless(QT,'Optional native desktop unavailable')
class SchematicMouseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):self.widget=SchematicDialog();self.widget.show();self.app.processEvents();self.canvas=self.widget.canvas
    def tearDown(self):self.widget.close();self.widget.deleteLater();self.app.processEvents()
    def mode(self,name):self.canvas.mode.setCurrentIndex(self.canvas.mode.findData(name));self.app.processEvents()
    def click(self,xy):QTest.mouseClick(self.canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=self.canvas.view.mapFromScene(QPointF(*xy)));self.app.processEvents()

    def test_real_clicks_add_symbolic_path_drag_refresh_delete_preview_and_undo(self):
        self.mode('vertex');self.click([-200,0]);self.click([200,0]);self.assertEqual(len(self.canvas.document.to_dict()['vertices']),2)
        labels=list(self.canvas.vertices);self.mode('path')
        self.click([self.canvas.vertices[labels[0]].pos().x(),self.canvas.vertices[labels[0]].pos().y()]);self.click([self.canvas.vertices[labels[1]].pos().x(),self.canvas.vertices[labels[1]].pos().y()])
        self.assertEqual(len(self.canvas.document.to_dict()['paths']),1)
        self.mode('move');old=to_tikz(self.canvas.current_document());self.canvas.vertices[labels[1]].setPos(self.canvas.vertices[labels[1]].pos()+QPointF(50,-50));self.canvas._released()
        self.assertNotEqual(to_tikz(self.canvas.current_document()),old)
        self.mode('delete');point=self.canvas.vertices[labels[0]].pos();unchanged=to_tikz(self.canvas.current_document());self.click([point.x(),point.y()]);self.assertEqual(len(self.canvas.document.to_dict()['paths']),1)
        self.assertEqual(to_tikz(self.canvas.current_document()),unchanged)
        self.click([point.x(),point.y()]);self.assertEqual(len(self.canvas.document.to_dict()['paths']),0)
        self.canvas.undo();self.assertEqual(len(self.canvas.document.to_dict()['paths']),1)

    def test_expand_requires_explicit_parameters_and_emits_concrete_graph_only(self):
        self.widget.set_document(template('E'));values=[];self.widget.graph_ready.connect(values.append)
        self.widget.expand_graph();self.assertFalse(values)
        self.widget.parameters.setText('{"k":3,"a":1,"b":2,"c":3}');self.widget.expand_graph();self.assertEqual(values[0].size,6)
        self.widget.canvas._publish(self.widget.canvas.current_document());self.assertFalse(self.widget.canvas.undo_button.isEnabled())
        self.widget.set_style('line_width',.03);self.assertTrue(self.widget.canvas.undo_button.isEnabled())

    def test_dialog_rank_validation_and_compression_from_existing_canvas(self):
        self.widget.set_document(template('H'));self.widget.rank.setText('3');self.widget.update_header();self.assertEqual(self.widget.canvas.document.to_dict()['rank'],'k')
        self.widget.set_document(from_graph(path_graph()));self.canvas.selected_edges=set(range(5));self.canvas.compress_selected()
        self.assertEqual(len(self.canvas.document.to_dict()['paths']),1)

    def test_graph_input_handoff_does_not_replace_concrete_graph_with_symbolic_data(self):
        from graph_research.desktop.graph_input import GraphInputDialog
        from graph_research.graph_input.storage import GraphLibrary
        with tempfile.TemporaryDirectory() as directory:
            dialog=GraphInputDialog(GraphLibrary(Path(directory)/'library'),path_graph())
            before=dialog.graph.to_dict()
            def choose(editor):editor.diagram_ready.emit(template('E'));return editor.DialogCode.Accepted
            with patch.object(SchematicDialog,'exec',choose):dialog.open_schematic()
            self.assertIsNotNone(dialog.schematic_result);self.assertEqual(dialog.graph.to_dict(),before)
            dialog.close();dialog.deleteLater();self.app.processEvents()

    def test_file_dialog_import_is_bounded_and_preserves_last_valid_layout(self):
        import io
        before=self.canvas.document.to_dict()
        class LimitedStream(io.BytesIO):
            def read(self,size=-1):
                if not 0<size<=256*1024+1:raise AssertionError('Import must not read unbounded data')
                return super().read(size)
        with patch('graph_research.desktop.schematic.QFileDialog.getOpenFileName',return_value=('oversized.json','')):
            with patch.object(Path,'open',return_value=LimitedStream(b' '*(256*1024+2))):self.widget.load_scene()
        self.assertIn('256KiB',self.widget.status.text());self.assertEqual(self.canvas.document.to_dict(),before)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scene.json';save(template('H'),path)
            with patch('graph_research.desktop.schematic.QFileDialog.getOpenFileName',return_value=(str(path),'')):self.widget.load_scene()
            self.assertEqual(self.canvas.document.to_dict(),template('H').to_dict())

    def test_click_add_edit_undo_and_reshow_keep_camera_and_screen_position(self):
        self.mode('vertex');view=self.canvas.view;scale=view.transform().m11()
        for delta in (QPoint(-140,-60),QPoint(170,75),QPoint(40,-95)):
            point=view.viewport().rect().center()+delta;expected=view.mapToScene(point)
            QTest.mouseClick(view.viewport(),Qt.MouseButton.LeftButton,pos=point);self.app.processEvents()
            vertex=list(self.canvas.vertices.values())[-1]
            self.assertLess((vertex.pos()-expected).manhattanLength(),1e-8)
            self.assertLess((view.mapFromScene(vertex.pos())-point).manhattanLength(),3)
            self.assertAlmostEqual(view.transform().m11(),scale)
        center=view.mapToScene(view.viewport().rect().center())
        self.canvas.undo();self.app.processEvents()
        self.assertAlmostEqual(view.transform().m11(),scale)
        self.assertLess((view.mapToScene(view.viewport().rect().center())-center).manhattanLength()*scale,3)
        self.widget.hide();self.widget.show();self.app.processEvents()
        self.assertAlmostEqual(view.transform().m11(),scale)
        self.canvas.fit();self.assertNotAlmostEqual(view.transform().m11(),scale)

    def test_wheel_zoom_keeps_cursor_world_anchor_and_resize_keeps_scale(self):
        self.widget.set_document(template('E'));self.app.processEvents();view=self.canvas.view
        point=view.viewport().rect().center()+QPoint(110,40);before=view.mapToScene(point);scale=view.transform().m11()
        event=QWheelEvent(QPointF(point),QPointF(view.viewport().mapToGlobal(point)),QPoint(),QPoint(0,120),
                          Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False)
        self.app.sendEvent(view.viewport(),event);self.app.processEvents()
        self.assertAlmostEqual(view.transform().m11(),scale*1.15)
        self.assertLess((view.mapToScene(point)-before).manhattanLength()*view.transform().m11(),3)
        self.widget.resize(self.widget.width()+90,self.widget.height()+50);self.app.processEvents()
        self.assertAlmostEqual(view.transform().m11(),scale*1.15)

    def test_edge_and_path_toggle_selection_without_editing_or_undo(self):
        for scene,kind in ((from_graph(path_graph(m=1)),'edge'),(template('E'),'path')):
            self.widget.set_document(scene);self.app.processEvents();self.mode('edge' if kind=='edge' else 'path')
            primitive=next(p for p in primitives(scene) if p['kind']=='path' and p['tag']==[kind,0])
            command=primitive['commands'][1];x,y=command[-2:];xy=[x*160,-y*160]
            before=self.canvas.current_document();self.click(xy)
            self.assertEqual(self.canvas.selected_core if kind=='edge' else self.canvas.selected_path,0)
            self.click(xy)
            self.assertIsNone(self.canvas.selected_core if kind=='edge' else self.canvas.selected_path)
            self.assertEqual(self.canvas.current_document(),before);self.assertFalse(self.canvas.undo_stack)

    def test_edge_delete_still_requires_two_clicks_and_compression_is_multiselect(self):
        scene=from_graph(path_graph());self.widget.set_document(scene);self.app.processEvents();self.mode('compress')
        def outline(index):
            p=next(p for p in primitives(scene) if p['kind']=='path' and p['tag']==['edge',index])
            x,y=p['commands'][1][-2:];return [x*160,-y*160]
        self.click(outline(0));self.click(outline(1));self.assertEqual(self.canvas.selected_edges,{0,1})
        self.click(outline(0));self.assertEqual(self.canvas.selected_edges,{1})
        self.mode('delete');self.click(outline(0));self.assertEqual(len(self.canvas.document.to_dict()['edges']),5)
        self.click(outline(0));self.assertEqual(len(self.canvas.document.to_dict()['edges']),4)

    def test_context_parameters_creation_settings_and_explicit_apply(self):
        self.assertFalse(self.canvas.settings_panel.isVisible());self.mode('edge')
        self.assertTrue(self.canvas.core_settings.isVisible());self.assertFalse(self.canvas.path_settings.isVisible())
        self.assertFalse(self.canvas.apply_button.isEnabled());self.assertFalse(self.canvas.connect_button.isEnabled())
        self.canvas.inner_dots.setChecked(True);self.canvas.shape.setCurrentIndex(self.canvas.shape.findData('circle'))
        self.mode('vertex');self.assertFalse(self.canvas.settings_panel.isVisible())
        self.canvas.add_vertex('u',[-1,0]);self.canvas.add_vertex('v',[1,0]);self.mode('edge')
        self.assertTrue(self.canvas.inner_dots.isChecked());self.assertEqual(self.canvas.shape.currentData(),'circle')
        self.click([-160,0]);self.click([160,0]);self.assertTrue(self.canvas.connect_button.isEnabled())
        self.canvas.connect_button.click();self.app.processEvents()
        edge=self.canvas.document.to_dict()['edges'][0]
        self.assertTrue(edge['vertex_ellipsis']);self.assertEqual(edge['shape'],'circle')
        p=next(p for p in primitives(self.canvas.document) if p['kind']=='path' and p['tag']==['edge',0])
        x,y=p['commands'][1][-2:];self.click([x*160,-y*160])
        self.assertTrue(self.canvas.apply_button.isEnabled());self.assertIn('e0',self.canvas.context_label.text())
        before=self.canvas.document;self.canvas.inner_dots.setChecked(False);self.assertEqual(self.canvas.document,before)
        self.canvas.apply_button.click();self.app.processEvents()
        self.assertFalse(self.canvas.document.to_dict()['edges'][0]['vertex_ellipsis'])
        self.assertTrue(self.canvas.inner_dots.isChecked())  # unchanged creation draft
        self.assertFalse(self.canvas.apply_button.isEnabled())
        self.mode('path');self.assertTrue(self.canvas.path_settings.isVisible());self.assertFalse(self.canvas.core_settings.isVisible())
        self.assertIn('单条超边',self.canvas.inner_dots.toolTip())
        for field in (self.canvas.first,self.canvas.last,self.canvas.offset):self.assertTrue(field.toolTip())

    def test_overlapping_edges_allow_alt_cycle_and_click_again_to_cancel(self):
        scene=SchematicDocument({'vertices':[{'id':i,'xy':p} for i,p in enumerate([[-1,0],[1,0],[0,-1],[0,1]])],
            'edges':[{'vertices':[0,1],'shape':'circle'},{'vertices':[2,3],'shape':'circle'}]})
        self.widget.set_document(scene);self.app.processEvents();self.mode('edge');self.click([0,-1.12*160])
        first=self.canvas.selected_core;self.assertIn(first,(0,1))
        point=self.canvas.view.mapFromScene(QPointF(0,-1.12*160))
        QTest.mouseClick(self.canvas.view.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.AltModifier,pos=point);self.app.processEvents()
        self.assertEqual(self.canvas.selected_core,1-first)
        self.click([0,-1.12*160]);self.assertIsNone(self.canvas.selected_core)
        self.mode('vertex');self.click([0,0]);self.assertEqual(len(self.canvas.document.to_dict()['vertices']),5)

    def test_fast_second_click_cancels_edit_selection(self):
        scene=SchematicDocument({'vertices':[{'id':0,'xy':[-1,0]},{'id':1,'xy':[1,0]}],
                                  'edges':[{'vertices':[0,1],'shape':'circle'}]})
        self.widget.set_document(scene);self.app.processEvents();self.mode('edge');self.click([0,-1.12*160])
        self.assertEqual(self.canvas.selected_core,0)
        point=self.canvas.view.mapFromScene(QPointF(0,-1.12*160))
        QTest.mouseDClick(self.canvas.view.viewport(),Qt.MouseButton.LeftButton,pos=point);self.app.processEvents()
        self.assertIsNone(self.canvas.selected_core);self.assertFalse(self.canvas.undo_stack)

    def test_real_drag_updates_dot_direction_and_one_undo_roundtrips(self):
        scene=SchematicDocument({'vertices':[{'id':'u','xy':[0,0]},{'id':'v','xy':[0,2]}],
                                  'edges':[{'vertices':['u','v'],'vertex_ellipsis':True}]})
        self.widget.set_document(scene);self.app.processEvents();self.mode('move');view=self.canvas.view
        before=to_tikz(scene);scale=view.transform().m11();start=view.mapFromScene(self.canvas.vertices['v'].pos());end=start+QPoint(80,30)
        QTest.mousePress(view.viewport(),Qt.MouseButton.LeftButton,pos=start)
        move=QMouseEvent(QEvent.Type.MouseMove,QPointF(end),QPointF(view.viewport().mapToGlobal(end)),
                         Qt.MouseButton.NoButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(view.viewport(),move);QTest.mouseRelease(view.viewport(),Qt.MouseButton.LeftButton,pos=end);self.app.processEvents()
        after=self.canvas.current_document();self.assertNotEqual(to_tikz(after),before);self.assertEqual(len(self.canvas.undo_stack),1)
        self.assertAlmostEqual(view.transform().m11(),scale)
        dots=[p['xy'] for p in primitives(after) if p.get('role')=='dot'];self.assertNotAlmostEqual(dots[0][0],dots[2][0])
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'scene.json';save(after,path);loaded=SchematicDocument(json.loads(path.read_text(encoding='utf-8')))
            self.assertEqual(to_tikz(loaded),to_tikz(after));self.assertEqual(to_svg(loaded),to_svg(after))
        self.canvas.undo();self.assertEqual(self.canvas.current_document().to_dict(),scene.to_dict());self.assertAlmostEqual(view.transform().m11(),scale)

    def test_intersecting_center_edge_boundary_survives_later_fill_in_native_and_svg(self):
        data={'vertices':[{'id':i,'xy':p} for i,p in enumerate([[-1,0],[1,0],[0,-1],[0,1]])],
              'edges':[{'vertices':[0,1]},{'vertices':[2,3],'shape':'circle'}]}
        for edges in (data['edges'],list(reversed(data['edges']))):
            scene=SchematicDocument({**data,'edges':edges});self.widget.set_document(scene);self.app.processEvents()
            # The top of the small horizontal ellipse lies inside the large
            # circle. It disappeared when the later circle painted its fill.
            target=QPointF(0,-.1224*160);point=self.canvas.view.mapFromScene(target)
            image=self.canvas.view.viewport().grab().toImage()
            colors=[image.pixelColor(point+QPoint(dx,dy)).red() for dx in range(-2,3) for dy in range(-2,3)]
            self.assertLess(min(colors),80)
            svg=to_svg(scene);renderer=QSvgRenderer(svg.encode());size=renderer.defaultSize()
            image=QImage(size,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.white);painter=QPainter(image);renderer.render(painter);painter.end()
            box=renderer.viewBoxF();x=round((0-box.x())*size.width()/box.width());y=round((-.1224*120-box.y())*size.height()/box.height())
            self.assertLess(min(image.pixelColor(x+dx,y+dy).red() for dx in range(-2,3) for dy in range(-2,3)),80)


if __name__=='__main__':unittest.main()
