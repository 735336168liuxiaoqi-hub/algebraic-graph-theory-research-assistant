"""Desktop graph context and presentation dialog; backend contracts stay unchanged."""
import copy
import json

import jsonschema
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QWidget,QScrollArea
from .widgets import QDialog,QComboBox,QLabel,QPushButton,QTabWidget,QMessageBox,QFileDialog

from graph_research.graph_input.document import GraphDocument,document
from graph_research.graph_input.adapters import graph_targets,graph_patch,result_graph,validate_sources
from graph_research.tools.input_guides import input_guide
from .graph_canvas import GraphCanvas
from .graph_text import graph_summary


INTEGRATED={'hypergraph_plot','hypergraph_editor','hypergraph_tikz','graph_tikz','graph_layout','hypergraph_schematic'}
PRODUCERS=INTEGRATED|{'graph_edit','graph_construction','graph_recipe','generate_hypergraph',
    'hypergraph_transform','weighted_graph_spectrum'}


def desktop_groups(groups):
    """Organize only the desktop navigation, retaining extensions by their identity."""
    result=[];combination=[]
    for group in groups:
        tools=[]
        for definition in group['tools']:
            if definition['name']=='combinatorial_plot':combination.append(definition)
            elif definition['name'] not in INTEGRATED:tools.append(definition)
        if tools:result.append({**group,'tools':tools})
    target=next((g for g in result if g['name']=='组合与多项式'),None)
    if combination:
        if target is None:result.append({'name':'组合与多项式','tools':combination})
        else:target['tools'].extend(combination)
    return result


def _ordinary(spec,name):
    from graph_research.graphs import make_graph
    graph=make_graph(spec.get('kind','path'),spec.get('n',5),spec.get('edges'))
    return document(list(graph),[{'vertices':list(e)} for e in graph.edges],name=name)


def _hypergraph(spec,name):
    from graph_research.hypergraphs import Hypergraph
    vertices=spec.get('vertices')
    if 'n' in spec:vertices=list(range(spec['n']))
    graph=Hypergraph(spec['edges'],vertices=vertices,weights=spec.get('weights'))
    records=[{'vertices':list(e),'weight':float(w)} for e,w in zip(graph.hyperedges(),graph.weights)]
    return document(graph.vertices(),records,graph_type='hypergraph',
                    weighted=any(e['weight']!=1 for e in records),name=name)


def _weighted(spec,name):
    return document(list(range(spec['n'])),
        [{'vertices':[e['u'],e['v']],'weight':e.get('weight',1)} for e in spec['edges']],
        directed=spec.get('directed',False),weighted=True,name=name)


def input_graphs(definition,arguments,sources=()):
    """Recover reviewed inputs, preserving roles and verified original labels."""
    jsonschema.validate(arguments,definition['parameters'])
    targets=graph_targets(definition)
    if not targets:return []
    saved=validate_sources(definition,arguments,list(sources)) if sources else []
    restored={('case'+str(s['case_index']) if s['target']=='case' else s['target']):GraphDocument(s['document']) for s in saved}
    name=definition['name'];props=definition['parameters']['properties'];graphs=[]
    if name=='graph_enumeration' and arguments.get('operation')=='degree_realizations':return []
    if name in ('compare_graphs','graph_energy_study'):
        specs=[(role,arguments.get(role,{}),'左侧图' if role=='left' else '右侧图') for role in ('left','right')]
    elif name=='graph_batch_study':
        specs=[('case'+str(i),c['input'],str(i+1)+' · '+c.get('name','批量图')) for i,c in enumerate(arguments.get('cases',[])) if 'input' in c]
    else:specs=[('graph',arguments,'输入图')]
    for role,spec,title in specs:
        if role in restored:graph=restored[role]
        elif name=='graph_energy_study' and not ('weighted' in spec or 'kind' in spec):continue
        elif name=='graph_batch_study':
            kind=arguments['cases'][int(role[4:])].get('graph_type','graph')
            graph=_hypergraph(spec,title) if kind=='hypergraph' else _weighted(spec,title) if kind=='weighted' else _ordinary(spec,title)
        elif name=='graph_energy_study' and 'weighted' in spec:graph=_weighted(spec['weighted'],title)
        elif name=='directed_graph_spectrum':
            graph=document(list(range(spec['n'])),[{'vertices':e} for e in spec['arcs']],directed=True,name=title)
        elif name=='weighted_graph_spectrum':graph=_weighted(spec,title)
        elif name.startswith('hypergraph_') and 'edges' in spec:graph=_hypergraph(spec,title)
        elif {'kind','n','edges'}<=set(props) or name in ('compare_graphs','graph_energy_study'):graph=_ordinary(spec,title)
        else:continue
        if graph.order:graphs.append((title,graph))
    return graphs


def observation_graphs(observation,registry):
    """Result structures take priority; never substitute a transformed graph's input."""
    if not observation.get('ok') or observation.get('tool_status') not in (None,'native_tested'):return []
    name=observation.get('tool')
    result=observation.get('result',{})
    sources=[]
    if observation.get('graph_inputs') and name in ('graph_batch_study','graph_energy_study'):
        sources=validate_sources(registry.describe(name),observation['arguments'],observation['graph_inputs'])
    def restore(graph,target,index=None):
        from graph_research.graph_input.document import same_numbered_structure
        for source in sources:
            if source['target']==target and (index is None or source.get('case_index')==index):
                original=GraphDocument(source['document'])
                if same_numbered_structure(original,graph):return original
        return graph
    if name=='graph_enumeration' and observation.get('arguments',{}).get('operation')=='degree_realizations':
        return [('实现图 '+str(i+1),_ordinary(spec,'实现图 '+str(i+1))) for i,spec in enumerate(result.get('graphs',[]))]
    if name=='graph_batch_study':
        graphs=[]
        for row in result.get('rows',[]):
            if 'construction' in row.get('errors',{}):continue
            if 'graph_document' in row:graphs.append((str(row.get('case',''))+' · '+row.get('name','批量图'),restore(GraphDocument(row['graph_document']),'case',row['case']-1)))
            elif 'resolved_input' in row:
                spec=row['resolved_input'];kind=row.get('input',{}).get('graph_type','graph')
                if 'graph_spec' in spec or 'hypergraph_spec' in spec:
                    graph=result_graph({'tool':'graph_recipe','ok':True,'arguments':row['input'].get('recipe',{}),'result':spec})
                else:graph=_hypergraph(spec,row['name']) if kind=='hypergraph' else _weighted(spec,row['name']) if kind=='weighted' else _ordinary(spec,row['name'])
                graphs.append((str(row.get('case',''))+' · '+row.get('name','批量图'),restore(graph,'case',row['case']-1)))
        return graphs
    if name=='graph_energy_study':
        graphs=[]
        for row in result.get('rows',[]):
            for side,title in [('left','左图'),('right','右图')]:
                if row.get('resolved_'+side):graphs.append((title+' · '+result.get('parameter','t')+'='+str(row['parameter_value']),restore(GraphDocument(row['resolved_'+side]),side)))
        if graphs:return graphs
    if name=='graph_construction':return [('结果图',_ordinary(observation['result']['graph'],'构图结果'))]
    if name in PRODUCERS:return [('结果图',result_graph(observation))]
    return input_graphs(registry.describe(name),observation.get('arguments',{}),observation.get('graph_inputs',[]))


def presentation_call(graph,definition,options=None):
    """Use the normal lossless adapter and leave source graph/form parameters intact."""
    prepared=graph_patch(graph,definition)
    arguments={**prepared['patch'],**copy.deepcopy(options or {})}
    if any(key in prepared['patch'] for key in (options or {})):
        raise ValueError('绘图设置不能覆盖当前图的结构或坐标。')
    jsonschema.validate(arguments,definition['parameters'])
    binding={k:prepared[k] for k in ('target','patch','vertex_mapping')};binding['document']=graph.to_dict()
    return definition['name'],arguments,[binding]


def presentation_title(observation,registry):
    name=observation.get('tool')
    if name not in ('hypergraph_plot','hypergraph_editor'):return None
    try:
        graphs=observation_graphs(observation,registry)
        if graphs and graphs[0][1].graph_type=='graph':return '普通图结构图'
    except (ValueError,KeyError,TypeError,jsonschema.ValidationError):pass
    return None


class GraphActionsDialog(QDialog):
    """One graph-local place to drag, save coordinates, draw and export TikZ."""
    def __init__(self,graphs,registry,parent=None):
        super().__init__(parent);self.registry=registry;self.graphs=list(graphs);self.request=None;self.option_fields={}
        self.setWindowTitle('图形、布局与 LaTeX');self.resize(1000,770)
        root=QVBoxLayout(self);self.choice=QComboBox()
        for title,graph in self.graphs:self.choice.addItem(graph_summary(graph,role=title))
        root.addWidget(self.choice)
        self.tabs=QTabWidget();root.addWidget(self.tabs,1)
        preview=QWidget();layout=QVBoxLayout(preview)
        hint=QLabel('拖动顶点实时调整结构图；滚轮缩放。导出保留此处的顶点位置，原图保持原样。');hint.setWordWrap(True);layout.addWidget(hint)
        self.canvas=GraphCanvas();self.canvas.set_editable(False);layout.addWidget(self.canvas,1)
        self.tabs.addTab(preview,'结构预览与拖动')
        self.plot_name='hypergraph_plot';self.tikz_name=None
        self.choice.currentIndexChanged.connect(self.choose_graph);self.choose_graph(0)
        row=QHBoxLayout();root.addLayout(row)
        self.save_coordinates=QPushButton('保存坐标');self.save_coordinates.clicked.connect(self.save_graph);row.addWidget(self.save_coordinates)
        self.draw_button=QPushButton('生成图片');self.draw_button.clicked.connect(lambda:self.prepare('plot'));row.addWidget(self.draw_button)
        self.tex_button=QPushButton('导出 LaTeX');self.tex_button.clicked.connect(lambda:self.prepare('tex'));row.addWidget(self.tex_button)
        self.auto_button=QPushButton('应用自动布局');self.auto_button.clicked.connect(lambda:self.prepare('layout'));row.addWidget(self.auto_button)
        close=QPushButton('关闭');close.clicked.connect(self.reject);row.addWidget(close)
        self.update_buttons()

    def choose_graph(self,index):
        if index<0:return
        if hasattr(self,'active_index'):
            try:self.graphs[self.active_index]=(self.graphs[self.active_index][0],self.styled_graph())
            except (ValueError,jsonschema.ValidationError) as error:
                self.choice.blockSignals(True);self.choice.setCurrentIndex(self.active_index);self.choice.blockSignals(False)
                QMessageBox.warning(self,'请先修正当前图或样式',str(error));return
        self.active_index=index;graph=self.graphs[index][1];self.canvas.set_graph(graph)
        while self.tabs.count()>1:
            page=self.tabs.widget(1);self.tabs.removeTab(1);page.deleteLater()
        self.option_fields={};self.tikz_name='graph_tikz' if graph.graph_type=='graph' else 'hypergraph_tikz'
        for key,name,title in [('plot',self.plot_name,'图片设置'),('tex',self.tikz_name,'LaTeX 设置'),('layout','graph_layout','自动布局与坐标变换')]:
            if key=='layout' and graph.graph_type!='graph':continue
            definition=self.registry.describe(name);guide=input_guide(definition);guides={f['name']:f for f in guide['fields']}
            page=QWidget();box=QVBoxLayout(page);fields={}
            if key=='layout':
                from .i18n import UiText
                raw_mapping=', '.join(str(i)+' → '+json.dumps(v,ensure_ascii=False) for i,v in enumerate(graph.vertices))
                mapping=QLabel(UiText('以下顶点参数使用编号：'+raw_mapping,'Use these vertex indices: '+raw_mapping))
                mapping.setWordWrap(True);mapping.setTextFormat(Qt.TextFormat.PlainText);box.addWidget(mapping)
            from .app import ParameterField
            for parameter,schema in definition['parameters']['properties'].items():
                if parameter in ('kind','n','edges','positions','graph_document','vertex_labels','edge_labels') or (parameter=='vertices' and key!='layout'):continue
                field=ParameterField(parameter,schema,guides[parameter],parameter in definition['parameters'].get('required',[]),definition)
                fields[parameter]=field;box.addWidget(field)
            box.addStretch();area=QScrollArea();area.setWidgetResizable(True);area.setWidget(page);self.tabs.addTab(area,title);self.option_fields[key]=fields
        if graph.graph_type=='hypergraph':
            page=QWidget();box=QVBoxLayout(page)
            box.addWidget(QLabel('重新布局会替换预览坐标，生成新的图片；也可在结构预览中直接拖动顶点。'))
            self.hyper_layout=QComboBox();self.hyper_layout.addItem('弹簧布局','spring');self.hyper_layout.addItem('环形布局','circular');box.addWidget(self.hyper_layout);box.addStretch();self.tabs.addTab(page,'自动布局')
        self._build_styles(graph)
        if hasattr(self,'draw_button'):self.update_buttons()

    def update_buttons(self):
        graph=self.canvas.current_graph()
        for button,name in [(self.draw_button,self.plot_name),(self.tex_button,self.tikz_name),(self.auto_button,'graph_layout' if graph.graph_type=='graph' else self.plot_name)]:
            try:
                graph_patch(graph,self.registry.describe(name));available=self.registry.describe(name)['availability']['available']
                if not available:raise ValueError('此功能缺少可选依赖，请检查环境。')
                button.setEnabled(True);button.setToolTip('使用当前预览中的图和坐标。')
            except ValueError as error:button.setEnabled(False);button.setToolTip(str(error))
        self.auto_button.setToolTip(self.auto_button.toolTip()+' 自动布局顶点参数按编号填写。')

    def _build_styles(self,graph):
        from graph_research.graph_input.styles import style_schema,DEFAULTS
        from .app import ParameterField
        titles={'vertex_color':'顶点颜色','edge_color':'统一边颜色','edge_colors':'逐边颜色','font_size':'字号（pt）','font_family':'字体类别','vertex_size':'顶点半径（pt）','line_width':'线宽（pt）','line_style':'线型','vertex_labels':'显示顶点标签','edge_labels':'显示边编号','weight_labels':'显示原始权重','vertex_label_offsets':'顶点标签偏移（pt）','edge_label_offsets':'边标签偏移（pt）','vertex_texts':'自定义顶点显示文本','tension':'曲线张力','continuity':'曲线连续性','bias':'曲线偏向'}
        hints={'vertex_label_offsets':'按原始顶点标签填写，例如[{"vertex":0,"xy":[8,12]}]；xy单位pt，向右/向上为正。',
            'edge_label_offsets':'按边顺序从0编号，例如[{"edge_index":0,"xy":[3,8]}]。','vertex_texts':'仅改变显示文本，例如[{"vertex":0,"text":"v_0"}]，不改变顶点身份。',
            'edge_colors':'依照边顺序填写#RRGGBB数组，长度必须等于边数；优先于统一边颜色。'}
        values={'vertex_color':'#173d3b','edge_color':'#263e47','font_size':10,'vertex_size':1.6,'line_width':.9,'vertex_label_offsets':[],'edge_label_offsets':[],'edge_colors':['#263e47']*graph.size,'vertex_texts':[]}
        schema=style_schema()['properties'];definition={'name':'drawing_style','parameters':{'properties':schema}}
        page=QWidget();box=QVBoxLayout(page);self.style_fields={}
        for name,rule in schema.items():
            if name=='graph_label':continue  # Dedicated live controls beside the preview.
            rule=copy.deepcopy(rule);rule['title']=titles[name];rule['description']=hints.get(name,titles[name]+'；样式保存到图JSON，图片和TikZ使用同一设置。')
            if name in DEFAULTS:rule['default']=DEFAULTS[name]
            if 'enum' in rule:
                translations={'sans':'无衬线','serif':'衬线','monospace':'等宽','solid':'实线','dashed':'虚线','dotted':'点线'}
                rule['x-enum-labels']={v:translations[v] for v in rule['enum']};rule['x-enum-descriptions']={v:translations[v]+'；恢复绘图时保留此项。' for v in rule['enum']}
            definition['parameters']['properties'][name]=rule
            guide={'format':rule['description'],'omission':'未勾选时使用默认样式。','input_example':json.dumps(values.get(name,rule.get('default')),ensure_ascii=False)}
            field=ParameterField(name,rule,guide,False,definition);self.style_fields[name]=field;box.addWidget(field)
            if name in graph.to_dict().get('style',{}):field.set_value(graph.to_dict()['style'][name])
        button=QPushButton('应用样式到预览');button.clicked.connect(self.apply_style);box.addWidget(button);box.addStretch()
        area=QScrollArea();area.setWidgetResizable(True);area.setWidget(page);self.tabs.addTab(area,'绘图样式')

    def styled_graph(self):
        style={k:f.read() for k,f in self.style_fields.items() if f.enabled.isChecked()}
        graph=self.canvas.current_graph();label=graph.to_dict().get('style',{}).get('graph_label')
        if label is not None:style['graph_label']=label
        return graph.with_updates(style=style)

    def apply_style(self):
        try:self.canvas.set_graph(self.styled_graph())
        except (ValueError,jsonschema.ValidationError) as error:QMessageBox.warning(self,'样式未应用',str(error))

    def prepare(self,action):
        try:
            graph=self.styled_graph();name=self.plot_name if action=='plot' else self.tikz_name if action=='tex' else 'graph_layout'
            fields=self.option_fields.get(action,{})
            options={k:f.read() for k,f in fields.items() if f.enabled.isChecked()}
            if action=='layout' and graph.graph_type=='hypergraph':
                data=graph.to_dict();data.pop('positions',None);graph=GraphDocument(data);name=self.plot_name
                options={'layout':self.hyper_layout.currentData()}
            self.request=presentation_call(graph,self.registry.describe(name),options);self.accept()
        except jsonschema.ValidationError:
            QMessageBox.warning(self,'请核对绘图设置','参数格式或范围不符合要求，请查看相应参数的说明与示例。')
        except ValueError as error:QMessageBox.warning(self,'图形尚未生成',str(error))

    def save_graph(self):
        path,_=QFileDialog.getSaveFileName(self,'保存含当前坐标的图对象','图与坐标.json','JSON (*.json)')
        if not path:return
        try:
            from graph_research.runtime.storage import atomic_text
            graph=self.styled_graph();atomic_text(path,json.dumps(graph.to_dict(),ensure_ascii=False,indent=2),overwrite=True);self.canvas.set_graph(graph)
        except (ValueError,OSError) as error:QMessageBox.warning(self,'坐标未保存',str(error))
