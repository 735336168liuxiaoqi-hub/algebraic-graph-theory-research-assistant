"""Editable native graph canvas; shared unfilled hyperedge curves and visible weights."""
import math
from PySide6.QtCore import Qt,QPointF,Signal,QTimer
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen,QBrush,QPolygonF
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGraphicsView,QGraphicsScene,QGraphicsPathItem,QGraphicsPolygonItem,QGraphicsSimpleTextItem
from .widgets import QPushButton,QComboBox,QLineEdit,QLabel
from graph_research.graph_input.document import document,GraphDocument,GraphInputError,tokens,strict_json,weight_parts,display_label
from graph_research.rendering.geometry import hyperedge_path,vertex_positions,COLORS
from .layout import VertexItem
from .i18n import UiText
from .graph_text import quantity


def _positions(graph):
    data=graph.to_dict()
    if 'positions' in data:return data['positions']
    from graph_research.hypergraphs import Hypergraph
    # Opposite arcs share geometry for layout only; both arcs remain in the document and drawing.
    members=[];seen=set()
    for edge in graph.edges:
        key=frozenset(edge['vertices'])
        if key not in seen:members.append(edge['vertices']);seen.add(key)
    h=Hypergraph(members,vertices=list(graph.vertices));pos=vertex_positions(h,seed=42,iterations=60)
    return [[float(pos[v][0]),float(pos[v][1])] for v in graph.vertices]


_caption=display_label


def choice_help(combo,hints):
    for i in range(combo.count()):combo.setItemData(i,hints[combo.itemData(i)],Qt.ItemDataRole.ToolTipRole)
    combo.view().setMouseTracking(True)
    combo.currentIndexChanged.connect(lambda i:combo.setToolTip(combo.itemData(i,Qt.ItemDataRole.ToolTipRole) or ''))
    combo.setToolTip(combo.currentData(Qt.ItemDataRole.ToolTipRole) or '')


class GraphView(QGraphicsView):
    pressed=Signal(object);released=Signal()
    def mousePressEvent(self,event):
        self.pressed.emit(event)
        if self.parent().mode.currentData()!='move':event.accept();return
        super().mousePressEvent(event)
    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event);self.released.emit()
    def mouseDoubleClickEvent(self,event):
        if self.parent().mode.currentData()=='delete':
            self.pressed.emit(event);event.accept();return
        super().mouseDoubleClickEvent(event)
    def wheelEvent(self,event):
        factor=1.15 if event.angleDelta().y()>0 else 1/1.15
        if 1e-9<self.transform().m11()*factor<1e6:self.scale(factor,factor)
        event.accept()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_Escape:
            self.parent().unselect();event.accept();return
        super().keyPressEvent(event)


class GraphCanvas(QWidget):
    changed=Signal(object);error=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self.graph=document([],[]);self.vertices=[];self.paths=[];self.selected=[];self.undo_stack=[];self._updating=False;self._drag_start=None;self._delete_target=None
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0)
        self.controls=QWidget();row=QHBoxLayout(self.controls);row.setContentsMargins(0,0,0,0)
        self.mode=QComboBox()
        for title,key in [('拖动顶点','move'),('点击增点','vertex'),('选择连边','edge'),('删除点/边','delete')]:self.mode.addItem(title,key)
        self.mode.setToolTip('增点：点击空白处；连边：普通图依次点两个顶点，超图选好成员后点击创建边；删除顶点会删除所有关联边。')
        choice_help(self.mode,{'move':'拖动顶点并实时更新曲线，保留结构；滚轮缩放。','vertex':'点击空白处添加顶点，可指定标签或自动编号。','edge':'选择成员创建普通边或超边，超边选好后点击创建边。','delete':'首次点击高亮待删除对象，删点时同时高亮关联边；再次点击同一对象确认。点击空白或按Esc取消，可撤销删除。'})
        self.mode.currentIndexChanged.connect(self._mode_changed);row.addWidget(self.mode)
        self.label_input=QLineEdit();self.label_input.setPlaceholderText('新顶点标签（可留空）');self.label_input.setMaximumWidth(155);row.addWidget(self.label_input)
        self.weight_input=QLineEdit('1');self.weight_input.setMaximumWidth(115);self.weight_input.setToolTip('创建边的权重：有限数，或{"real":0,"imag":1}；须启用带权。');row.addWidget(self.weight_input)
        self.connect_button=QPushButton('创建边');self.connect_button.clicked.connect(self.connect_selected);row.addWidget(self.connect_button);root.addWidget(self.controls)
        self.scene=QGraphicsScene(self);self.view=GraphView(self.scene,self);self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QBrush(QColor('white')));self.view.setMinimumSize(350,320);self.view.pressed.connect(self._pressed);self.view.released.connect(self._released)
        root.addWidget(self.view,1)
        bottom=QHBoxLayout();self.fit_button=QPushButton('适应窗口');self.fit_button.clicked.connect(self.fit);bottom.addWidget(self.fit_button)
        self.undo_button=QPushButton('撤销');self.undo_button.clicked.connect(self.undo);bottom.addWidget(self.undo_button)
        self.clear_selection=QPushButton('清除选点');self.clear_selection.clicked.connect(self.unselect);bottom.addWidget(self.clear_selection)
        self.selection_text=QLabel('');self.selection_text.setWordWrap(True);bottom.addWidget(self.selection_text,1);root.addLayout(bottom)
        self.selection_text.setTextFormat(Qt.TextFormat.PlainText)
        from .coordinate_labels import CoordinateControls
        self.coordinate_controls=CoordinateControls(self);self.coordinate_controls.changed.connect(self.redraw);root.addWidget(self.coordinate_controls)
        from .figure_label import FigureLabelControls
        self.figure_label_controls=FigureLabelControls(self);self.figure_label_controls.applied.connect(self._set_figure_label);root.addWidget(self.figure_label_controls)
        self.set_graph(self.graph)

    def set_editable(self,editable):
        self.controls.setVisible(editable);self.undo_button.setVisible(editable);self.clear_selection.setVisible(editable)
        self.mode.setCurrentIndex(0);self.unselect()

    def set_graph(self,graph,*,remember=False,reset_undo=False):
        if remember:self._remember()
        if reset_undo:self.undo_stack=[]
        self.graph=graph;self._updating=True;self.selected=[];self._delete_target=None;self.vertices=[];self.paths=[];self.figure_label_controls.reset_item();self.scene.clear()
        self.figure_label_controls.load(graph.to_dict().get('style',{}).get('graph_label'))
        positions=_positions(graph);self.graph=graph.with_updates(positions=positions)
        for i,_ in enumerate(graph.edges):
            item=QGraphicsPathItem();item.setPen(QPen(QColor(COLORS[i%len(COLORS)] if graph.graph_type=='hypergraph' else '#263e47'),2))
            item.setData(0,('edge',i));item.setZValue(1);self.scene.addItem(item);self.paths.append(item)
        for label,xy in zip(graph.vertices,positions):
            vertex=VertexItem(_caption(label),QPointF(xy[0]*160,-xy[1]*160),self._dragged)
            vertex.setData(0,('vertex',label));vertex.setZValue(5);self.scene.addItem(vertex);self.vertices.append(vertex)
        self._updating=False;self.redraw();self._mode_changed();self.fit();self.undo_button.setEnabled(bool(self.undo_stack))

    def current_graph(self):
        return self.graph.with_updates(positions=[[v.pos().x()/160,-v.pos().y()/160] for v in self.vertices])

    def _set_figure_label(self,value):
        try:
            before=self.current_graph();style=before.to_dict().get('style',{})
            if value is None:style.pop('graph_label',None)
            else:style['graph_label']=value
            candidate=before.with_updates(style=style)
            if candidate!=before:
                self._remember();self.graph=candidate;self.figure_label_controls.load(style.get('graph_label'));self.redraw();self.changed.emit(candidate)
        except ValueError as error:self.error.emit(str(error));self.redraw()

    def _remember(self):
        self.undo_stack.append(self.current_graph());self.undo_stack=self.undo_stack[-100:];self.undo_button.setEnabled(True)

    def _publish(self,graph):
        data=graph.to_dict();data.pop('recipe',None);graph=GraphDocument(data)
        self.set_graph(graph,remember=True);self.changed.emit(self.current_graph())

    def _edited(self,data):
        if 'style' in data:
            from graph_research.graph_input.styles import reconcile_style
            data['style']=reconcile_style(data['style'],self.graph.edges,data['vertices'],data['edges'],data['directed'])
        return GraphDocument(data)

    def _mode_changed(self):
        for vertex in self.vertices:vertex.setFlag(vertex.GraphicsItemFlag.ItemIsMovable,self.mode.currentData()=='move')
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if self.mode.currentData()=='move' else QGraphicsView.DragMode.NoDrag)
        self.clear_selection.setText('取消预览' if self.mode.currentData()=='delete' else '清除选点')
        self.unselect()

    def unselect(self):
        self.selected=[];self._delete_target=None;self.coordinate_controls.focused=set();self.redraw()
        self.selection_text.setText('')

    def preview_delete(self,tag):
        """Preview only; confirm by clicking the same original object again."""
        if self._delete_target==tag:
            if tag[0]=='vertex':self.remove_vertex(tag[1])
            else:self.remove_edge(tag[1])
            return
        self.selected=[];self._delete_target=tag;self.redraw()
        if tag[0]=='vertex':
            count=sum(tag[1] in edge['vertices'] for edge in self.graph.edges)
            chinese='将删除顶点 '+_caption(tag[1])+' 及 '+str(count)+' 条关联边。再次点击该顶点确认。'
            english='Delete vertex '+_caption(tag[1])+' and '+quantity(count,'incident hyperedge' if self.graph.graph_type=='hypergraph' else 'incident edge')+'. Click this vertex again to confirm.'
        else:
            chinese='将删除边 e'+str(tag[1])+'，保留其顶点。再次点击该边确认。'
            english='Delete '+('hyperedge' if self.graph.graph_type=='hypergraph' else 'edge')+' e'+str(tag[1])+', retaining its vertices. Click the edge again to confirm.'
        self.selection_text.setText(UiText(chinese+' 点击空白或按 Esc 取消。',english+' Click empty space or press Esc to cancel.'))

    def toggle_vertex(self,label):
        if label in self.selected:self.selected.remove(label)
        else:self.selected.append(label)
        for value,item in zip(self.graph.vertices,self.vertices):item.setBrush(QBrush(QColor('#df8d25' if value in self.selected else '#173d3b')))
        self._coordinate_labels()
        labels=', '.join(_caption(v) for v in self.selected);self.selection_text.setText(UiText('选中：'+labels,'Selected: '+labels))

    def add_vertex(self,label=None,position=None):
        data=self.current_graph().to_dict();used=set(data['vertices'])
        if label is None:
            label=0
            while label in used:label+=1
        if position is None:
            position=[len(used)*.5,0]
            while position in data['positions']:position=[position[0]+.5,0]
        data['vertices'].append(label);data['positions'].append(position);self._publish(self._edited(data));return label

    def add_edge(self,members,weight=1):
        data=self.current_graph().to_dict();data['edges'].append({'vertices':list(members),'weight':weight});self._publish(self._edited(data))

    def remove_vertex(self,label):
        data=self.current_graph().to_dict();index=data['vertices'].index(label);data['vertices'].pop(index);data['positions'].pop(index)
        data['edges']=[edge for edge in data['edges'] if label not in edge['vertices']];self._publish(self._edited(data))

    def remove_edge(self,index):
        data=self.current_graph().to_dict();data['edges'].pop(index);self._publish(self._edited(data))

    def connect_selected(self):
        try:
            self.add_edge(self.selected,strict_json(self.weight_input.text()));self.unselect()
        except (ValueError,IndexError) as error:self.error.emit(str(error))

    def undo(self):
        if self._delete_target is not None:self.unselect();return
        if not self.undo_stack:return
        graph=self.undo_stack.pop();self.set_graph(graph);self.changed.emit(self.current_graph())

    def _pressed(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        item=next((item for item in self.view.items(event.position().toPoint()) if item.data(1)!='coordinate-overlay'),None)
        while item is not None and item.data(0) is None:item=item.parentItem()
        tag=item.data(0) if item is not None else None;mode=self.mode.currentData()
        try:
            if tag and tag[0]=='graph_label':self._drag_start=None;return
            if mode=='move':
                self._drag_start=self.current_graph()
                if tag is None:self.coordinate_controls.focused=set();self._coordinate_labels()
                return
            if mode=='vertex' and tag is None:
                text=self.label_input.text().strip();labels=tokens(text) if text else []
                if len(labels)>1:raise GraphInputError('一次填写一个新顶点标签；含空格的标签使用双引号。')
                point=self.view.mapToScene(event.position().toPoint());self.add_vertex(labels[0] if labels else None,[point.x()/160,-point.y()/160])
                self.label_input.clear()
            elif mode=='edge' and tag and tag[0]=='vertex':
                self.toggle_vertex(tag[1])
                if self.graph.graph_type=='graph' and len(self.selected)==2:self.connect_selected()
            elif mode=='delete':
                if tag:self.preview_delete(tag)
                else:self.unselect()
        except (ValueError,IndexError) as error:self.error.emit(str(error))

    def _released(self):
        if self.mode.currentData()!='move':return
        try:
            graph=self.current_graph()
            previous=self._drag_start or self.graph
            if graph!=previous:self.undo_stack.append(previous);self.undo_stack=self.undo_stack[-100:];self.undo_button.setEnabled(True)
            self.graph=graph;self.changed.emit(graph)
        except ValueError as error:self.error.emit(str(error))
        finally:self._drag_start=None

    def _dragged(self):
        if not self._updating:self.redraw()

    def redraw(self):
        data=self.graph.to_dict();coordinates={v:[item.pos().x(),item.pos().y()] for v,item in zip(data['vertices'],self.vertices)}
        from graph_research.graph_input.styles import resolved_style
        from graph_research.rendering.presentation import geometry,arrow_triangle,edge_color,edge_text
        from PySide6.QtGui import QFont
        import numpy as np
        style=resolved_style(self.graph);texts={r['vertex']:r['text'] for r in style.get('vertex_texts',[])}
        offsets={r['vertex']:r['xy'] for r in style.get('vertex_label_offsets',[])};edge_offsets={r['edge_index']:r['xy'] for r in style.get('edge_label_offsets',[])}
        font=QFont({'sans':'Microsoft YaHei','serif':'SimSun','monospace':'Consolas'}[style['font_family']]);font.setPointSizeF(style['font_size'])
        from matplotlib.path import Path as Curve
        math_coordinates={v:np.array([xy[0]/160,-xy[1]/160]) for v,xy in coordinates.items()}
        paths=[Curve(p.vertices*np.array([160,-160]),p.codes) for p in geometry(self.graph,math_coordinates)]
        span=float(np.ptp(np.array(list(coordinates.values())),axis=0).max()) if coordinates else 160.;span=span or 160.
        pending=self._delete_target
        affected={i for i,edge in enumerate(data['edges']) if pending is not None and (pending==('edge',i) or pending[0]=='vertex' and pending[1] in edge['vertices'])}
        for value,vertex in zip(data['vertices'],self.vertices):
            deleting=pending==('vertex',value)
            vertex.setBrush(QBrush(QColor('#c33d35' if deleting else '#df8d25' if value in self.selected else style['vertex_color'])))
            radius=style['vertex_size']*3;vertex.setRect(-radius,-radius,2*radius,2*radius)
            vertex.caption.setText(texts.get(value,_caption(value)));vertex.caption.setFont(font);vertex.caption.setVisible(style['vertex_labels'])
            offset=offsets.get(value,[6,14]);vertex.caption.setPos(offset[0]*1.33,-offset[1]*1.33)
            vertex.setPen(QPen(QColor('#c33d35' if deleting else 'white'),2.5 if deleting else 1.4))
            vertex.caption.setBrush(QBrush(QColor('#c33d35' if deleting else '#233c47')))
        for index,(edge,item) in enumerate(zip(data['edges'],self.paths)):
            color='#c33d35' if index in affected else edge_color(self.graph,index,style)
            line_style={'solid':Qt.PenStyle.SolidLine,'dashed':Qt.PenStyle.DashLine,'dotted':Qt.PenStyle.DotLine}[style['line_style']]
            item.setPen(QPen(QColor(color),3.5 if index in affected else style['line_width']*2,Qt.PenStyle.DashLine if index in affected else line_style))
            from shiboken6 import delete
            for child in item.childItems():delete(child)
            path=QPainterPath();curve=paths[index];i=0
            while i<len(curve.codes):
                code=int(curve.codes[i]);xy=curve.vertices[i]
                if code==1:path.moveTo(float(xy[0]),float(xy[1]));i+=1
                elif code==2:path.lineTo(float(xy[0]),float(xy[1]));i+=1
                elif code==4:
                    p=curve.vertices[i:i+3];path.cubicTo(*[float(v) for row in p for v in row]);i+=3
                elif code==79:path.closeSubpath();i+=1
                else:i+=1
            item.setPath(path)
            if data['directed']:
                points=arrow_triangle(curve,span)
                if points is not None:
                    triangle=QPolygonF([QPointF(float(x),float(y)) for x,y in points]);arrow=QGraphicsPolygonItem(triangle,item);arrow.setBrush(QBrush(item.pen().color()));arrow.setPen(QPen(Qt.PenStyle.NoPen))
            text=edge_text(self.graph,index,style)
            if text:
                caption=QGraphicsSimpleTextItem(text,item);caption.setFont(font);caption.setBrush(QBrush(item.pen().color()));xy=edge_offsets.get(index,[3,4]);caption.setPos(path.pointAtPercent(.5)+QPointF(xy[0]*1.33,-xy[1]*1.33-12));caption.setZValue(3)
        self._coordinate_labels()
        points=list(math_coordinates.values())+[p/[160,-160] for curve in paths for p in curve.vertices]
        self.figure_label_controls.sync(self.scene,style.get('graph_label'),points,movable=self.mode.currentData()=='move')

    def _coordinate_labels(self):
        from graph_research.rendering.tex_coordinates import for_paths
        from graph_research.rendering.presentation import geometry
        import numpy as np
        items=dict(zip(self.graph.vertices,self.vertices))
        positions={v:np.array([item.pos().x()/160,-item.pos().y()/160]) for v,item in items.items()}
        self.coordinate_controls.update_items(items,positions,lambda:for_paths(positions,geometry(self.graph,positions)),self.selected)

    def fit(self):
        bounds=self.scene.itemsBoundingRect().adjusted(-55,-55,55,55)
        if not self.vertices:bounds.setRect(-250,-200,500,400)
        self.scene.setSceneRect(bounds);self.view.fitInView(bounds,Qt.AspectRatioMode.KeepAspectRatio)

    def showEvent(self,event):super().showEvent(event);QTimer.singleShot(0,self.fit)
