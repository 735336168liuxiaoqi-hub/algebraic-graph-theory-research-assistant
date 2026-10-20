"""One graph preparation dialog: text, preview, families, library and native drawing."""
import json
import jsonschema
from html import escape
from pathlib import Path
from PySide6.QtCore import Qt,QTimer
from PySide6.QtGui import QColor,QTextCursor,QTextCharFormat
from PySide6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QSplitter,QTabWidget,
    QLabel,QLineEdit,QPlainTextEdit,QComboBox,QCheckBox,QPushButton,QSpinBox,QListWidget,QListWidgetItem,QFileDialog,QMessageBox,QTextEdit)
from graph_research.graph_input.document import GraphInputError,GraphDocument,document,parse_graph,graph_family,MAX_TEXT
from .graph_canvas import GraphCanvas,choice_help

FORMATS=[('快捷边表','edge_list'),('邻接矩阵','adjacency'),('关联矩阵','incidence'),('图对象JSON','json'),('普通图 graph6','graph6')]
HINTS={
    'edge_list':'无表头，每行一条边，成员用空格或逗号分隔。普通边2点，超边至少2点；可写 {a b c}。带权写 a b | 2；复权写 a b | {"real":0,"imag":1}。纯数字文本标签加双引号，如 "1"。',
    'adjacency':'每行一行矩阵，空格/逗号分隔或使用二维JSON。零表示无边；无向须对称，复权须共轭对称，主对角为0。零权边请用边表。',
    'incidence':'仅用于超图：行=顶点，列=超边，元素为0/1。零行保留孤立点，每列至少2个1；边权请用边表/图JSON。',
    'json':'导入统一图对象JSON，可保留标签、孤立点、方向、权重及坐标；也支持普通图{kind,n,edges}或边表{edges,vertices,weights}。JSON中的内容只是数据。',
    'graph6':'单张无向无权普通图的graph6编码，可包含孤立点。可另填完整顶点列表替换默认0起始标签。'}


class GraphInputDialog(QDialog):
    def __init__(self,library,graph=None,parent=None):
        super().__init__(parent);self.library=library;self.graph=None;self._syncing=False;self._last_tab=0;self.valid=True;self.use_recipe=False;self.schematic_result=None
        self.setWindowTitle('图输入');self.resize(1180,810);self.setMinimumSize(960,650)
        root=QVBoxLayout(self);header=QHBoxLayout();self.name=QLineEdit('未命名图');self.name.setPlaceholderText('图的名称');header.addWidget(self.name,1)
        self.graph_type=QComboBox();self.graph_type.addItem('普通图','graph');self.graph_type.addItem('超图','hypergraph');header.addWidget(self.graph_type)
        choice_help(self.graph_type,{'graph':'每条边恰有两个不同端点，可以选择方向和权重。','hypergraph':'每条超边至少两个不同顶点，允许非一致；当前不支持有向超图。'})
        self.directed=QCheckBox('有向');header.addWidget(self.directed);self.weighted=QCheckBox('带权');header.addWidget(self.weighted);root.addLayout(header)
        splitter=QSplitter();root.addWidget(splitter,1);self.tabs=QTabWidget();splitter.addWidget(self.tabs)
        self._build_input();self._build_family();self._build_library();self.tabs.addTab(QLabel('在右侧画布点击增点、选择成员连边，或切换删除与拖动。\n\n超边通过所有成员顶点的无填充曲线表示；交叉处没有顶点标记就不表示关联。\n\n删除时先点击预览，再次点击同一对象确认。删点会连同关联边一起高亮并删除。点击空白或按 Esc 取消预览；删除后可撤销。'),'鼠标构图')
        right=QWidget();right_layout=QVBoxLayout(right);right_layout.setContentsMargins(8,0,0,0)
        self.summary=QLabel();self.summary.setWordWrap(True);right_layout.addWidget(self.summary)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.canvas=GraphCanvas();self.canvas.changed.connect(self._canvas_changed);self.canvas.error.connect(self._canvas_error);right_layout.addWidget(self.canvas,1);splitter.addWidget(right);splitter.setSizes([400,720])
        self.status=QLabel('输入图后确认右侧预览。');self.status.setWordWrap(True);root.addWidget(self.status)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        actions=QHBoxLayout();self.save=QPushButton('保存到图对象库');self.save.clicked.connect(self.save_graph);actions.addWidget(self.save)
        self.export=QPushButton('导出图JSON');self.export.clicked.connect(self.export_graph);actions.addWidget(self.export);actions.addStretch()
        self.paper=QPushButton('论文示意图');self.paper.setToolTip('用同样的鼠标操作绘制省略超路，保存布局并导出TeX；具体计算须先展开。');self.paper.clicked.connect(self.open_schematic);actions.addWidget(self.paper)
        self.cancel=QPushButton('取消');self.cancel.clicked.connect(self.reject);actions.addWidget(self.cancel)
        self.recipe_button=QPushButton('准备已保存的构图配方');self.recipe_button.clicked.connect(self.prepare_recipe);actions.addWidget(self.recipe_button)
        self.use=QPushButton('使用此图');self.use.setObjectName('primary');self.use.clicked.connect(self.use_graph);actions.addWidget(self.use);root.addLayout(actions)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(280);self.timer.timeout.connect(self.parse_input)
        self.text.textChanged.connect(self.schedule_parse);self.vertices.textChanged.connect(self.schedule_parse);self.format.currentIndexChanged.connect(self._format_changed)
        self.graph_type.currentIndexChanged.connect(self._flags_changed);self.directed.toggled.connect(self._flags_changed);self.weighted.toggled.connect(self._flags_changed)
        self.name.editingFinished.connect(self._name_changed);self.tabs.currentChanged.connect(self._tab_changed)
        self.set_graph(graph or document([],[]),fill_text=graph is not None);self.refresh_library();self.canvas.set_editable(False);self._format_changed()

    def _build_input(self):
        page=QWidget();layout=QVBoxLayout(page);self.format=QComboBox()
        for title,value in FORMATS:self.format.addItem(title,value)
        choice_help(self.format,{key:hint[:220] for key,hint in HINTS.items()})
        layout.addWidget(self.format);self.hint=QLabel();self.hint.setWordWrap(True);self.hint.setObjectName('muted');layout.addWidget(self.hint)
        self.text=QPlainTextEdit();self.text.setPlaceholderText('a b\nb c\nc a');layout.addWidget(self.text,1)
        layout.addWidget(QLabel('完整顶点列表（可留空；填写时须包含所有成员，也可加入孤立点）'))
        self.vertices=QPlainTextEdit();self.vertices.setMaximumHeight(75);self.vertices.setPlaceholderText('a b c isolated');layout.addWidget(self.vertices)
        row=QHBoxLayout();button=QPushButton('导入文件');button.clicked.connect(self.import_file);row.addWidget(button)
        self.example=QPushButton('填入示例');self.example.clicked.connect(self.apply_example);row.addWidget(self.example)
        refresh=QPushButton('更新预览');refresh.clicked.connect(self.parse_input);row.addWidget(refresh);layout.addLayout(row);self.tabs.addTab(page,'快捷输入')

    def _build_family(self):
        page=QWidget();layout=QVBoxLayout(page);form=QFormLayout();self.family=QComboBox()
        for title,value in [('路径 / 松路','path'),('圈 / 松圈','cycle'),('星 / 超星','star'),('完全图','complete'),('无边图','empty')]:self.family.addItem(title,value)
        choice_help(self.family,{'path':'依次连接的普通路径或一致超图松路。','cycle':'闭合的普通圈或一致超图松圈。','star':'一个中心连接所有叶点，或所有超边共享同一个根点。','complete':'普通完全图，每对不同顶点均有一条边。','empty':'普通无边图，保留指定数量的孤立点。'})
        form.addRow('图族',self.family);self.n=QSpinBox();self.n.setRange(1,128);self.n.setValue(5);form.addRow('普通图顶点数',self.n)
        self.m=QSpinBox();self.m.setRange(1,32);self.m.setValue(3);form.addRow('超图边数',self.m)
        self.k=QSpinBox();self.k.setRange(2,8);self.k.setValue(3);form.addRow('超图一致度',self.k);layout.addLayout(form)
        button=QPushButton('生成并预览');button.clicked.connect(self.generate_family);layout.addWidget(button)
        note=QLabel('生成器创建无向无权图。确认后可在画布继续编辑，或使用参数化构图工具组合复杂图族。');note.setWordWrap(True);layout.addWidget(note);layout.addStretch();self.tabs.addTab(page,'图族生成')

    def _build_library(self):
        page=QWidget();layout=QVBoxLayout(page);self.library_list=QListWidget();self.library_list.itemDoubleClicked.connect(lambda _:self.load_selected());layout.addWidget(self.library_list,1)
        row=QHBoxLayout();load=QPushButton('载入选中的图');load.clicked.connect(self.load_selected);row.addWidget(load)
        refresh=QPushButton('刷新');refresh.clicked.connect(self.refresh_library);row.addWidget(refresh);layout.addLayout(row);self.tabs.addTab(page,'图对象库')

    def _format_changed(self,index=None):
        self.hint.setText(HINTS[self.format.currentData()])
        if index is not None:self.schedule_parse()

    def schedule_parse(self):
        if not self._syncing and self.tabs.currentIndex()==0:
            self.valid=False;self._buttons();self.timer.start()

    def _buttons(self):
        enabled=self.valid and self.graph is not None
        self.use.setEnabled(enabled and self.graph.order>0);self.save.setEnabled(enabled);self.export.setEnabled(enabled)
        self.recipe_button.setVisible(bool(self.graph and self.graph.to_dict().get('recipe')));self.recipe_button.setEnabled(enabled)

    def _status(self,text,error=False):
        self.status.setText(text);self.status.setStyleSheet('color:#a94336' if error else 'color:#52716d')

    def set_graph(self,graph,*,fill_text=False,remember=False):
        self._syncing=True
        try:
            self.graph=graph;self.name.setText(graph.name);self.graph_type.setCurrentIndex(self.graph_type.findData(graph.graph_type));self.directed.setChecked(graph.directed);self.weighted.setChecked(graph.weighted)
            self.directed.setEnabled(graph.graph_type=='graph');self.canvas.set_graph(graph,reset_undo=not remember)
            self.summary.setText(graph.summary());self.valid=True;self.text.setExtraSelections([])
            if fill_text:
                def token(v):
                    if isinstance(v,str) and (any(c.isspace() or c in ',|{}[]()"' for c in v) or v.lstrip('-').isdigit()):return json.dumps(v,ensure_ascii=False)
                    return str(v)
                self.format.setCurrentIndex(self.format.findData('edge_list'))
                self.text.setPlainText('\n'.join(' '.join(token(v) for v in edge['vertices'])+(' | '+json.dumps(edge['weight'],ensure_ascii=False) if graph.weighted else '') for edge in graph.edges))
                self.vertices.setPlainText(' '.join(token(v) for v in graph.vertices))
            self._buttons();self._status('结构已更新；确认后点击“使用此图”。')
        finally:self._syncing=False

    def parse_input(self):
        if self._syncing:return
        self.timer.stop()
        try:
            graph=parse_graph(self.text.toPlainText(),self.format.currentData(),self.graph_type.currentData(),self.vertices.toPlainText(),self.directed.isChecked(),self.weighted.isChecked(),self.name.text())
            if self.format.currentData()=='edge_list':
                try:previous=self.canvas.current_graph().to_dict()
                except ValueError:previous=self.canvas.graph.to_dict()
                candidate=graph.to_dict()
                if all(previous[k]==candidate[k] for k in ('graph_type','directed','weighted','vertices','edges')):
                    graph=graph.with_updates(positions=previous['positions'],**({'recipe':previous['recipe']} if previous.get('recipe') else {}),**({'style':previous['style']} if 'style' in previous else {}))
            self.set_graph(graph)
        except (ValueError,TypeError,KeyError) as error:
            self.valid=False;self._buttons();self._status(str(error),True);self.text.setExtraSelections([])
            line=getattr(error,'line',None)
            if line and 0<line<=self.text.document().blockCount():
                selection=QTextEdit.ExtraSelection();cursor=QTextCursor(self.text.document().findBlockByNumber(line-1));cursor.select(QTextCursor.SelectionType.LineUnderCursor)
                selection.cursor=cursor;selection.format=QTextCharFormat();selection.format.setBackground(QColor('#ffe5e1'));self.text.setExtraSelections([selection])

    def _flags_changed(self):
        if self._syncing:return
        self.directed.setEnabled(self.graph_type.currentData()=='graph')
        if self.tabs.currentIndex()==0:self.schedule_parse();return
        try:
            graph=self.canvas.current_graph().with_updates(graph_type=self.graph_type.currentData(),directed=self.directed.isChecked(),weighted=self.weighted.isChecked())
            self.canvas.set_graph(graph,remember=True);self._canvas_changed(graph)
        except ValueError as error:
            self._syncing=True;self.graph_type.setCurrentIndex(self.graph_type.findData(self.graph.graph_type));self.directed.setChecked(self.graph.directed);self.weighted.setChecked(self.graph.weighted);self._syncing=False
            self.directed.setEnabled(self.graph.graph_type=='graph')
            self._status(str(error),True)

    def _canvas_changed(self,graph):
        self.graph=graph
        previous=self._syncing;self._syncing=True
        self.graph_type.setCurrentIndex(self.graph_type.findData(graph.graph_type));self.directed.setChecked(graph.directed);self.weighted.setChecked(graph.weighted);self.directed.setEnabled(graph.graph_type=='graph')
        self._syncing=previous
        if self.tabs.currentIndex()!=0:self.valid=True
        self.summary.setText(graph.summary());self._buttons()
        if self.valid:self._status('画布已更新；变更尚未保存。')

    def _canvas_error(self,message):
        self._status(message,True)
        # Rejected structural operations leave the last valid document intact.
        try:self.canvas.current_graph()
        except ValueError:self.valid=False;self._buttons()

    def _name_changed(self):
        try:
            graph=self.canvas.current_graph().with_updates(name=self.name.text());self.canvas.graph=graph;self._canvas_changed(graph)
        except ValueError as error:self._status(str(error),True);self.valid=False;self._buttons()

    def _tab_changed(self,index):
        self.timer.stop()
        if index==0 and self._last_tab==3:
            try:graph=self.canvas.current_graph()
            except ValueError:graph=self.canvas.graph
            self.set_graph(graph,fill_text=True)
        self._last_tab=index;self.canvas.set_editable(index==3)
        if index==0:self.parse_input()
        elif index==3:
            try:self._canvas_changed(self.canvas.current_graph())
            except ValueError as error:self._canvas_error(str(error))

    def apply_example(self):
        values={'edge_list':'a b\nb c\nc a' if self.graph_type.currentData()=='graph' else 'a b c\nc d e\nb e',
                'adjacency':'0 1 0\n1 0 1\n0 1 0','incidence':'1 0\n1 0\n1 1\n0 1\n0 1','graph6':'Bg',
                'json':json.dumps(document(['a','b','isolated'],[{'vertices':['a','b'],'weight':1}]).to_dict(),ensure_ascii=False,indent=2)}
        self._syncing=True
        if self.format.currentData()=='incidence':self.graph_type.setCurrentIndex(self.graph_type.findData('hypergraph'));self.directed.setChecked(False)
        self.vertices.clear();self.text.setPlainText(values[self.format.currentData()]);self._syncing=False;self.parse_input()

    def generate_family(self):
        try:self.set_graph(graph_family(self.graph_type.currentData(),self.family.currentData(),self.n.value(),self.m.value(),self.k.value()),fill_text=True)
        except ValueError as error:self._status(str(error),True)

    def refresh_library(self):
        self.library_list.clear()
        try:
            for entry in self.library.entries():
                item=QListWidgetItem(('' if entry['valid'] else '⚠ ')+entry['summary']);item.setData(Qt.ItemDataRole.UserRole,entry['id']);item.setToolTip(escape(entry['summary']));self.library_list.addItem(item)
        except (ValueError,OSError) as error:self._status(str(error),True)

    def load_selected(self):
        item=self.library_list.currentItem()
        if item is None:return
        try:self.set_graph(self.library.load(item.data(Qt.ItemDataRole.UserRole)),fill_text=True)
        except (ValueError,OSError) as error:self._status(str(error),True)

    def prepared_graph(self):
        if self.tabs.currentIndex()==0 and self.timer.isActive():self.parse_input()
        if not self.valid:raise GraphInputError('当前输入有错误，请先修正。')
        return self.canvas.current_graph().with_updates(name=self.name.text())

    def use_graph(self):
        try:
            self.graph=self.prepared_graph()
            if not self.graph.order:raise GraphInputError('请先添加至少一个顶点。')
            self.accept()
        except ValueError as error:self._status(str(error),True)

    def open_schematic(self):
        from .schematic import SchematicDialog
        from graph_research.schematics import from_graph
        try:
            scene=from_graph(self.prepared_graph());dialog=SchematicDialog(scene,self)
            dialog.graph_ready.connect(lambda graph:self.set_graph(graph,fill_text=True))
            dialog.diagram_ready.connect(self._use_schematic);dialog.exec();dialog.deleteLater()
        except (ValueError,OSError) as error:self._status(str(error),True)

    def _use_schematic(self,scene):self.schematic_result=scene.to_dict();self.accept()

    def prepare_recipe(self):
        try:
            self.graph=self.prepared_graph()
            if not self.graph.to_dict().get('recipe'):raise GraphInputError('此图未记录构图配方。')
            from graph_research.tools import ToolRegistry
            jsonschema.validate(self.graph.to_dict()['recipe'],ToolRegistry().describe('graph_recipe')['parameters'])
            self.use_recipe=True;self.accept()
        except jsonschema.ValidationError as error:self._status('保存的配方参数无效：'+error.message,True)
        except ValueError as error:self._status(str(error),True)

    def save_graph(self):
        try:
            self.library.save(self.prepared_graph());self.refresh_library();self._status('已保存为图对象库中的独立副本。')
        except (ValueError,OSError) as error:self._status(str(error),True)

    def export_graph(self):
        try:graph=self.prepared_graph()
        except ValueError as error:self._status(str(error),True);return
        path,_=QFileDialog.getSaveFileName(self,'导出完整图对象','研究图.json','图JSON (*.json)')
        if not path:return
        try:self.library.export(graph,path,overwrite=True);self._status('图结构与坐标已导出。')
        except (ValueError,OSError) as error:self._status(str(error),True)

    def load_file(self,path,format):
        file=Path(path)
        with file.open('rb') as stream:raw=stream.read(MAX_TEXT+1)
        if len(raw)>MAX_TEXT:raise GraphInputError('图文件最多1MB。')
        try:text=raw.decode('utf-8-sig')
        except UnicodeDecodeError:raise GraphInputError('请使用UTF-8文本文件。') from None
        graph=parse_graph(text,format,self.graph_type.currentData(),self.vertices.toPlainText(),self.directed.isChecked(),self.weighted.isChecked(),self.name.text())
        self.set_graph(graph,fill_text=True);self.tabs.setCurrentIndex(0);self._status('文件已载入；请确认结构后使用。')

    def import_file(self):
        filters='图JSON (*.json);;快捷边表 (*.txt *.csv);;邻接矩阵 (*.txt *.csv *.json);;关联矩阵 (*.txt *.csv *.json);;graph6 (*.g6 *.graph6 *.txt)'
        path,selected=QFileDialog.getOpenFileName(self,'导入图文件','',filters)
        if not path:return
        format='json' if selected.startswith('图JSON') else 'adjacency' if selected.startswith('邻接') else 'incidence' if selected.startswith('关联') else 'graph6' if selected.startswith('graph6') else 'edge_list'
        try:
            if format=='incidence':self._syncing=True;self.graph_type.setCurrentIndex(self.graph_type.findData('hypergraph'));self.directed.setChecked(False);self._syncing=False
            self.load_file(path,format)
        except (ValueError,TypeError,OSError) as error:self._status(str(error),True)
