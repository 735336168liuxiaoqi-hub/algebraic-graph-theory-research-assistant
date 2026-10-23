"""Q01—Q08: graph identity, scientific labels, saved styles and protected exports."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import networkx as nx
import numpy as np

from graph_research.graph_input.document import GraphDocument,document,parse_graph
from graph_research.graph_input.adapters import graph_patch,result_graph
from graph_research.rendering.presentation import document_to_tikz,plot_document,geometry,coordinates
from graph_research.tools.registry import ToolRegistry
from graph_research.workflows.batch import graph_batch_study
from graph_research.workflows.energy import graph_energy_study
from graph_research import graphs,Hypergraph

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')


class WholeFigureLabelTests(unittest.TestCase):
    def test_label_validation_and_simple_subscripts_are_literal_and_bounded(self):
        from graph_research.graph_input import figure_label as api
        self.assertEqual(api.display_text('G_1 H_k G_{n+1}'),'G₁ Hₖ Gₙ₊₁')
        self.assertEqual(api.tex_text('G₁ H_k'),r'G\textsubscript{1} H\textsubscript{k}')
        self.assertNotIn('<img',api.html_text('<img src=x>'))
        self.assertNotIn(r'\input{secret}',api.tex_text(r'G_1 \input{secret} $%'))
        for invalid in ({'text':'x\ny'},{'text':'x','position':'free'},{'text':'x','font_size':True},
                        {'text':'x','offset':[float('nan'),0]},{'text':'x','offset':[6,0]},
                        {'text':'x','color':'red;bad'},{'text':'x','raw_tex':True}):
            with self.subTest(value=invalid),self.assertRaises(ValueError):api.validate(invalid)

    def test_graph_label_exports_without_changing_structure_coordinates_or_scale(self):
        import re
        for kind,directed,weighted,edges in [('graph',False,False,[{'vertices':[0,1]}]),
                                           ('graph',True,True,[{'vertices':[0,1],'weight':-2}]),
                                           ('hypergraph',False,True,[{'vertices':[0,1,2],'weight':2}])]:
            original=document([0,1,2],edges,graph_type=kind,directed=directed,weighted=weighted,
                              positions=[[0,0],[2,1],[3,-1]])
            label={'text':'H_k 图(a)','position':'below','offset':[.1,-.08],'font_size':14,'color':'#112233'}
            labelled=original.with_updates(style={'graph_label':label});before=labelled.to_dict()
            code=document_to_tikz(labelled,standalone=True);unlabelled=document_to_tikz(original)
            self.assertIn(r'H\textsubscript{k} 图(a)',code);self.assertIn(r'\usepackage[UTF8]{ctex}',code)
            pattern=r'\\coordinate .*?;'
            self.assertEqual(re.findall(pattern,code),re.findall(pattern,unlabelled))
            figure=plot_document(labelled);annotations=[t for t in figure.axes[0].texts if t.get_gid()=='graph-label']
            self.assertEqual(len(annotations),1);self.assertEqual(annotations[0].get_text(),'Hₖ 图(a)')
            self.assertEqual(figure.graph_document['style']['graph_label'],label)
            for a,b in zip(geometry(original,coordinates(original)),figure.hypergraph_paths):np.testing.assert_array_equal(a.vertices,b.vertices)
            self.assertEqual(labelled.to_dict(),before)
            self.assertEqual(labelled.edges,original.edges);self.assertEqual(labelled.vertices,original.vertices)
            self.assertEqual(parse_graph(labelled._serialized,'json').to_dict(),before)
            for ext in ('png','svg','pdf'):
                with tempfile.TemporaryDirectory() as folder:
                    path=Path(folder)/('label.'+ext);figure.savefig(path,bbox_inches='tight');self.assertGreater(path.stat().st_size,100)

    def test_empty_label_is_backward_compatible_and_renumbering_keeps_whole_label(self):
        from graph_research.graph_input.styles import remap_style,reconcile_style
        label={'text':'G_1'};style={'graph_label':label}
        self.assertEqual(remap_style(style,['a','b'],[0,1]),style)
        self.assertEqual(reconcile_style(style,[{'vertices':['a','b']}],['a'],[]),style)
        graph=document([0,1],[{'vertices':[0,1]}],positions=[[0,0],[1,0]])
        self.assertEqual(document_to_tikz(graph.with_updates(style={'graph_label':{'text':''}})),document_to_tikz(graph))


class GraphOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.registry=ToolRegistry()

    def sample(self):
        return document([1,'1','孤立点'],[{'vertices':[1,'1'],'weight':-2},{'vertices':['1',1],'weight':{'real':0,'imag':3}}],directed=True,weighted=True,
            positions=[[0,0],[1,0],[0,1]],style={'font_size':13,'line_style':'dashed','edge_color':'#882244','vertex_texts':[{'vertex':1,'text':'点_甲'}],
                'vertex_label_offsets':[{'vertex':1,'xy':[12,17]}],'edge_label_offsets':[{'edge_index':1,'xy':[-8,9]}]})

    def test_direct_python_exports_retain_weights_and_direction(self):
        graph=nx.DiGraph();graph.add_edge('a','b',weight=-2);graph.add_edge('b','a',weight=3j);graph.add_node('isolate')
        tex=graphs.to_tikz(graph,standalone=True)
        self.assertIn('directed: true',tex);self.assertIn('{-2}',tex);self.assertIn('{3i}',tex);self.assertIn('{isolate}',tex)
        self.assertEqual(tex.count(r'\fill[edgecolor'),2);self.assertIn('.. controls',tex)
        weighted=Hypergraph([[0,1,2]],weights=[7]);plain=Hypergraph([[0,1,2]])
        self.assertNotEqual(weighted.to_tikz(),plain.to_tikz());self.assertIn('{7}',weighted.to_tikz())
        figure=weighted.plot();self.assertIn('7',[t.get_text() for t in figure.axes[0].texts])

    def test_images_and_tikz_use_same_labels_curves_styles_and_never_evaluate_text(self):
        graph=self.sample();before=graph.to_dict();figure=plot_document(graph);tex=document_to_tikz(graph,standalone=True)
        labels=[t.get_text() for t in figure.axes[0].texts]
        self.assertTrue({'-2','3i','点_甲','孤立点'}<=set(labels));self.assertIn(r'点\_甲',tex);self.assertIn(r'\usepackage[UTF8]{ctex}',tex)
        self.assertIn('13',tex);self.assertIn('dashed',tex);self.assertIn('882244',tex)
        paths=geometry(graph,coordinates(graph));self.assertFalse(np.array_equal(paths[0].vertices,paths[1].vertices[::-1]))
        for actual,expected in zip(figure.hypergraph_paths,paths):np.testing.assert_allclose(actual.vertices,expected.vertices)
        self.assertEqual(graph.to_dict(),before)

    def test_style_roundtrip_rejects_unsafe_unknown_and_out_of_graph_settings(self):
        graph=self.sample();restored=parse_graph(json.dumps(graph.to_dict(),ensure_ascii=False),'json')
        self.assertEqual(restored.to_dict(),graph.to_dict())
        self.assertNotIn('style',document([0,1],[{'vertices':[0,1]}]).to_dict())
        for style in ({'line_width':float('nan')},{'edge_color':r'\input{bad}'},{'raw_tex':'bad'},
                      {'vertex_label_offsets':[{'vertex':'missing','xy':[0,0]}]}, {'edge_label_offsets':[{'edge_index':8,'xy':[0,0]}]}):
            with self.subTest(style=style),self.assertRaises(ValueError):graph.with_updates(style=style)

    def test_numeric_and_string_vertex_labels_are_distinct_without_changing_identity(self):
        graph=document([1,'1','01'],[{'vertices':[1,'1']}],positions=[[0,0],[1,0],[0,1]])
        before=graph.to_dict();figure=plot_document(graph);labels=[text.get_text() for text in figure.axes[0].texts]
        self.assertEqual(labels,['1','"1"','"01"'])
        tex=document_to_tikz(graph)
        self.assertIn('{1};',tex);self.assertIn('{"1"};',tex);self.assertIn('{"01"};',tex)
        custom=graph.with_updates(style={'vertex_texts':[{'vertex':'1','text':'chosen'}]})
        self.assertIn('{chosen};',document_to_tikz(custom))
        self.assertEqual(graph.to_dict(),before)
        from graph_research.rendering.tikz import hypergraph_to_tikz
        from graph_research.rendering.plotting import HyperGraphPlot
        h=Hypergraph([[1,'1']],vertices=[1,'1','01'])
        self.assertIn('{"1"};',hypergraph_to_tikz(h))
        self.assertIn('"1"',[text.get_text() for text in HyperGraphPlot(h).plot().axes[0].texts])

    def test_style_errors_include_safe_correction_rule_without_actual_input(self):
        from graph_research.errors import FieldValidationError
        from graph_research.runtime.observability import error_details
        graph=self.sample()
        for key,value in [('font_size',99),('line_style','PRIVATE_INPUT'),('vertex_color','PRIVATE_INPUT')]:
            with self.subTest(key=key),self.assertRaises(FieldValidationError) as caught:graph.with_updates(style={key:value})
            detail=error_details(caught.exception)
            self.assertEqual(detail['field_path'],['style',key]);self.assertIn('validation',detail)
            self.assertNotIn('PRIVATE_INPUT',json.dumps(detail))

    def test_tool_names_do_not_infer_graph_type_from_binary_edges(self):
        with tempfile.TemporaryDirectory() as directory,patch('pathlib.Path.cwd',return_value=Path(directory)):
            for name,kind,stem in [('graph_tikz','graph','graph'),('hypergraph_tikz','hypergraph','hypergraph')]:
                graph=document(['a','b','i'],[{'vertices':['a','b'],'weight':2}],graph_type=kind,weighted=True)
                args=graph_patch(graph,self.registry.describe(name))['patch'];result=self.registry.call(name,args)
                self.assertEqual(Path(result['files']['standalone']).name,stem+'.tex');self.assertEqual(Path(result['files']['fragment']).name,stem+'-tikz.tex')
                self.assertEqual(result['graph_document']['graph_type'],kind);self.assertIn('{2}',Path(result['files']['standalone']).read_text(encoding='utf-8'))
                restored=result_graph({'ok':True,'tool':name,'arguments':args,'result':result})
                self.assertEqual(restored.vertices,graph.vertices);self.assertEqual(restored.edges,graph.edges)

    def test_directed_complex_graph_layout_changes_only_coordinates(self):
        graph=self.sample();args=graph_patch(graph,self.registry.describe('graph_layout'))['patch']
        with tempfile.TemporaryDirectory() as directory,patch('pathlib.Path.cwd',return_value=Path(directory)):
            result=self.registry.call('graph_layout',{**args,'operation':'transform','angle':90})
            restored=GraphDocument(result['graph_document'])
            for key in ('vertices','edges','style','directed','weighted','graph_type'):self.assertEqual(restored.to_dict()[key],graph.to_dict()[key])
            np.testing.assert_allclose(restored.to_dict()['positions'],[[0,0],[0,1],[-1,0]],atol=1e-14)
            self.assertTrue({'png','svg','pdf','coordinates'}<=result['files'].keys())
            self.assertIn('无向无权支撑结构',result['interpretation'])

    def test_mixed_batch_includes_directed_weighted_and_nonuniform_graphs(self):
        cases=[{'name':'directed','graph_type':'weighted','input':{'n':3,'directed':True,'edges':[{'u':0,'v':1,'weight':2},{'u':1,'v':0,'weight':-3}]}},
               {'name':'nonuniform','graph_type':'hypergraph','input':{'edges':[[0,1],[1,2,3]],'vertices':[0,1,2,3,4],'weights':[2,4]}},
               {'name':'recipe','recipe':{'graph_type':'graph','base':{'kind':'path','n':3},'steps':[]}}]
        with tempfile.TemporaryDirectory() as directory,patch('pathlib.Path.cwd',return_value=Path(directory)):
            result=graph_batch_study(cases,['structure'],plot=True)
            self.assertEqual(result['status'],'complete',result);self.assertTrue({'png','svg','pdf'}<=result['files'].keys())
            from graph_research.desktop.graph_actions import observation_graphs
            choices=observation_graphs({'ok':True,'tool':'graph_batch_study','arguments':{'cases':cases},'result':result},self.registry)
            self.assertEqual(len(choices),3);self.assertTrue(choices[0][1].directed);self.assertEqual(choices[1][1].order,5)

    def test_enumeration_and_parameterized_recipe_results_have_real_graphs(self):
        from graph_research.desktop.graph_actions import observation_graphs
        args={'operation':'degree_realizations','degrees':[2,2,2,2]};value=self.registry.call('graph_enumeration',args)
        choices=observation_graphs({'ok':True,'tool':'graph_enumeration','arguments':args,'result':value},self.registry)
        self.assertEqual(len(choices),value['count']);self.assertEqual(choices[0][1].order,4)
        recipe={'graph_type':'graph','base':{'kind':'path','n':'t'},'steps':[]}
        value=graph_energy_study({'recipe':recipe},{'kind':'path','n':3},values=[2,3])
        choices=observation_graphs({'ok':True,'tool':'graph_energy_study','arguments':{'left':{'recipe':recipe},'right':{'kind':'path','n':3}},'result':value},self.registry)
        self.assertEqual([g.order for _,g in choices],[2,3,3,3]);self.assertEqual(value['status'],'certified_finite_domain')
        copied={'graph_type':'graph','base':{'kind':'path','n':2},'steps':[{'operation':'disjoint_copies','copies':2}]}
        value=graph_energy_study({'recipe':copied},{'kind':'path','n':3},values=[1])
        self.assertEqual(GraphDocument(value['rows'][0]['resolved_left']).order,4)

    def test_chat_manual_export_keeps_pending_state_and_charges_only_tool_attempts(self):
        from graph_research.assistant.session import ResearchSession
        from graph_research.assistant import verify_bundle
        from graph_research.desktop.graph_actions import presentation_call
        from tests.test_feature_workflow import ScriptedModel
        with tempfile.TemporaryDirectory() as directory:
            session=ResearchSession(Path(directory)/'chat',results_mode='api')
            session.ask('先澄清图的顶点数',ScriptedModel([{'action':'clarify','questions':['几个点？']}]))
            before=copy.deepcopy(session.state);usage=session.workflow_usage()
            name,args,bindings=presentation_call(self.sample(),self.registry.describe('graph_tikz'))
            with patch('httpx.Client',side_effect=AssertionError('Manual export must not contact a model')):observation=session.present_graph(name,args,graph_inputs=bindings)
            self.assertTrue(observation['ok'],observation)
            for key in ('status','answer','question','conversation','assessment_id','plan','decision'):self.assertEqual(session.state.get(key),before.get(key))
            self.assertEqual(session.workflow_usage()['model_calls'],usage['model_calls']);self.assertEqual(session.workflow_usage()['tool_calls'],usage['tool_calls']+1)
            self.assertTrue(verify_bundle(session.result_bundle['archive'],session.result_bundle['sha256'])['ok'])
            with self.assertRaises(ValueError):session.present_graph('graph_invariants',{'n':3})

    def test_native_style_and_structural_edits_preserve_correct_edge_identity(self):
        from PySide6.QtWidgets import QApplication
        from graph_research.desktop.graph_canvas import GraphCanvas
        app=QApplication.instance() or QApplication([]);canvas=GraphCanvas();source=self.sample();canvas.set_graph(source)
        paths=geometry(source,coordinates(source));qpath=canvas.paths[0].path()
        for i,xy in enumerate(paths[0].vertices):
            element=qpath.elementAt(i);np.testing.assert_allclose([element.x,element.y],xy*np.array([160,-160]))
        canvas.remove_edge(0);style=canvas.current_graph().to_dict()['style']
        self.assertEqual(style['edge_label_offsets'][0]['edge_index'],0)
        canvas.remove_vertex(1);self.assertEqual(canvas.current_graph().to_dict()['style']['vertex_label_offsets'],[])
        canvas.close();canvas.deleteLater();app.processEvents()

    def test_cli_default_filenames_and_explicit_output_are_consistent(self):
        from contextlib import chdir,redirect_stdout
        from io import StringIO
        import sys
        from graph_research.cli import _main
        with tempfile.TemporaryDirectory() as directory,chdir(directory),redirect_stdout(StringIO()):
            source=Path('input.json');source.write_text(json.dumps({'vertices':[0,1,2],'edges':[[0,1]]}),encoding='utf-8')
            for flags,name in [(['--simple-graph'],'graph.tex'),(['--simple-graph','--fragment'],'graph-tikz.tex'),([], 'hypergraph.tex'),(['--fragment'],'hypergraph-tikz.tex')]:
                with patch.object(sys,'argv',['graph-research','latex',str(source),*flags]):self.assertEqual(_main(),0)
                self.assertTrue((Path('outputs')/name).is_file())
            with patch.object(sys,'argv',['graph-research','latex',str(source),'--simple-graph','--output','my-figure.tex']):self.assertEqual(_main(),0)
            self.assertTrue(Path('my-figure.tex').is_file())

    def test_manual_export_budget_and_pre_start_cancel_do_not_reset_chat(self):
        from graph_research.assistant.session import ResearchSession
        from threading import Event
        from graph_research.desktop.graph_actions import presentation_call
        with tempfile.TemporaryDirectory() as directory:
            session=ResearchSession(Path(directory)/'chat',results_mode='api');session.set_workflow_budget({'max_tool_calls':1})
            name,args,bindings=presentation_call(self.sample(),self.registry.describe('graph_tikz'))
            cancelled=Event();cancelled.set()
            result=session.present_graph(name,args,graph_inputs=bindings,cancel_event=cancelled)
            self.assertFalse(result['ok']);self.assertEqual(session.workflow_usage()['tool_calls'],0)
            result=session.present_graph(name,args,graph_inputs=bindings);self.assertTrue(result['ok'],result)
            status=session.state['status'];result=session.present_graph(name,{**args,'vertex_labels':False},graph_inputs=bindings)
            self.assertFalse(result['ok']);self.assertEqual(session.workflow_usage()['tool_calls'],1);self.assertEqual(session.workflow_usage()['model_calls'],0);self.assertEqual(session.state['status'],status)

    def test_style_editor_save_and_import_preserve_custom_offsets_and_font(self):
        from PySide6.QtWidgets import QApplication
        from graph_research.desktop.graph_actions import GraphActionsDialog
        app=QApplication.instance() or QApplication([]);dialog=GraphActionsDialog([('图',self.sample())],self.registry)
        try:
            dialog.style_fields['font_size'].set_value(18);dialog.apply_style()
            with tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'drawing.json'
                with patch('graph_research.desktop.graph_actions.QFileDialog.getSaveFileName',return_value=(str(path),'')):dialog.save_graph()
                restored=parse_graph(path.read_text(encoding='utf-8'),'json')
                self.assertEqual(restored.to_dict()['style']['font_size'],18)
                self.assertEqual(restored.to_dict()['style']['vertex_label_offsets'],self.sample().to_dict()['style']['vertex_label_offsets'])
                self.assertEqual(restored.edges,self.sample().edges);self.assertTrue(restored.directed)
        finally:dialog.close();dialog.deleteLater();app.processEvents()

    def test_batch_and_energy_preserve_source_labels_styles_and_zero_weight_edges(self):
        from graph_research.desktop.graph_actions import observation_graphs
        from graph_research.graph_input.adapters import validate_bindings,validate_sources
        original=document([1,'1','isolate'],[{'vertices':[1,'1'],'weight':0}],weighted=True,positions=[[0,0],[1,0],[0,1]],style={'font_size':17})
        definition=self.registry.describe('graph_batch_study');prepared=graph_patch(original,definition,'case')
        args={**prepared['patch'],'calculations':['structure'],'plot':True}
        binding={k:prepared[k] for k in ('target','patch','vertex_mapping','case_index')};binding['document']=original.to_dict()
        sources=validate_bindings(definition,args,[binding])
        with tempfile.TemporaryDirectory() as directory,patch('pathlib.Path.cwd',return_value=Path(directory)):
            value=graph_batch_study(**args)
            graph=observation_graphs({'ok':True,'tool':'graph_batch_study','arguments':args,'graph_inputs':sources,'result':value},self.registry)[0][1]
            self.assertEqual(graph.to_dict(),original.to_dict());self.assertEqual(value['rows'][0]['graph_document'],original.to_dict())
        energy=self.registry.describe('graph_energy_study');prepared=graph_patch(original,energy,'left')
        args={**prepared['patch'],'right':{'kind':'path','n':3}}
        binding={k:prepared[k] for k in ('target','patch','vertex_mapping')};binding['document']=original.to_dict()
        sources=validate_bindings(energy,args,[binding]);value=graph_energy_study(**args)
        choices=observation_graphs({'ok':True,'tool':'graph_energy_study','arguments':args,'graph_inputs':sources,'result':value},self.registry)
        self.assertEqual(choices[0][1].to_dict(),original.to_dict());self.assertEqual(value['rows'][0]['resolved_left']['edges'][0]['weight'],0)
        legacy=document(['a','b'],[{'vertices':['a','b']}]);definition=self.registry.describe('graph_tikz')
        source={'document':legacy.to_dict(),'target':'graph','vertex_mapping':[]}
        validate_sources(definition,{'vertices':['a','b'],'edges':[['a','b']]},[source])
        bad={'document':original.to_dict(),'target':'graph','vertex_mapping':[]}
        with self.assertRaises(ValueError):validate_sources(definition,{'vertices':list(original.vertices),'edges':[[1,'1']]},[bad])


if __name__=='__main__':unittest.main()
