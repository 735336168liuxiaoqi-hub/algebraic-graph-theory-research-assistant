"""Native draggable hypergraph layout editor using the existing curve geometry."""
import json
import copy
from pathlib import Path

from PySide6.QtCore import Qt,QPointF,Signal,QTimer
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPen,QBrush
from PySide6.QtWidgets import QVBoxLayout,QHBoxLayout,QGraphicsView,QGraphicsScene,QGraphicsEllipseItem,QGraphicsItem
from .widgets import QDialog,QLabel,QPushButton,QFileDialog,QMessageBox

from graph_research.hypergraphs import Hypergraph
from graph_research.rendering.editor import layout_document,read_layout,validate_layout
from graph_research.rendering.geometry import hyperedge_path,COLORS
from graph_research.runtime.storage import atomic_text


class VertexItem(QGraphicsEllipseItem):
    def __init__(self,label,position,on_change):
        super().__init__(-5,-5,10,10)
        self.changed=on_change
        self.setBrush(QBrush(QColor('#173d3b')));self.setPen(QPen(QColor('white'),1.4));self.setZValue(5)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable|QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(position)
        from PySide6.QtWidgets import QGraphicsSimpleTextItem
        self.caption=QGraphicsSimpleTextItem(str(label),self);self.caption.setPos(8,-19)
        self.caption.setBrush(QBrush(QColor('#233c47')))

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and getattr(self,'coordinate_focus',None):self.coordinate_focus()
        super().mousePressEvent(event)

    def itemChange(self,change,value):
        result=super().itemChange(change,value)
        if change==QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:self.changed()
        return result


class LayoutDialog(QDialog):
    positions_ready=Signal(object)

    def __init__(self,arguments,parent=None):
        super().__init__(parent);self.resize(960,720)
        self.graph=Hypergraph(arguments['edges'],vertices=arguments.get('vertices'))
        self.simple=all(len(edge)==2 for edge in self.graph.Edges)
        self.setWindowTitle('调整布局')
        if self.graph.order()>128 or sum(map(len,self.graph.Edges))>2048:raise ValueError('桌面布局编辑支持至多128个顶点、2048次关联')
        positions=arguments.get('positions');pos=None
        if positions is not None:
            pos={record['vertex']:record['xy'] for record in positions}
            if len(pos)!=len(positions):raise ValueError('顶点坐标不能重复')
        self.document=layout_document(self.graph,pos,seed=arguments.get('seed',42),layout=arguments.get('layout','spring'))
        label=arguments.get('graph_document',{}).get('style',{}).get('graph_label')
        if label is not None:
            from graph_research.graph_input.figure_label import validate
            self.document['style']={'graph_label':validate(label)}
        self.initial_document=copy.deepcopy(self.document)
        self._updating=False;self.vertices=[];self.paths=[]
        root=QVBoxLayout(self);heading=QLabel('拖动顶点调整布局');heading.setObjectName('sectionTitle');root.addWidget(heading)
        if not self.simple:root.addWidget(QLabel('超边成员以曲线经过的标记顶点为准。'))
        self.scene=QGraphicsScene(self);self.view=QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing);self.view.setBackgroundBrush(QBrush(QColor('#ffffff')))
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag);root.addWidget(self.view,1)
        row=QHBoxLayout();root.addLayout(row)
        for title,action in [('适应窗口',self.fit),('恢复初始布局',self.reset),('导入坐标',self.import_positions),('保存坐标',self.save_positions),('用于TikZ导出',self.use_positions)]:
            button=QPushButton(title);button.clicked.connect(action);row.addWidget(button)
        from .coordinate_labels import CoordinateControls
        self.coordinate_controls=CoordinateControls(self);self.coordinate_controls.changed.connect(self.redraw);root.addWidget(self.coordinate_controls)
        from .figure_label import FigureLabelControls
        self.figure_label_controls=FigureLabelControls(self);self.figure_label_controls.applied.connect(self._set_figure_label);root.addWidget(self.figure_label_controls)
        self.build_scene();self.fit()

    def build_scene(self):
        self._updating=True;self.vertices=[];self.paths=[];self.figure_label_controls.reset_item();self.scene.clear()
        self.figure_label_controls.load(self.document.get('style',{}).get('graph_label'))
        for i,_ in enumerate(self.graph.Edges):
            item=self.scene.addPath(QPainterPath(),QPen(QColor('black' if self.simple else COLORS[i%len(COLORS)]),2))
            item.setZValue(1);self.paths.append(item)
        for label,xy in zip(self.document['vertices'],self.document['positions']):
            vertex=VertexItem(label,QPointF(xy[0]*110,-xy[1]*110),self.redraw)
            self.scene.addItem(vertex);self.vertices.append(vertex)
        self._updating=False;self.redraw()

    def redraw(self):
        if self._updating:return
        coordinates={label:[item.pos().x()/110,-item.pos().y()/110] for label,item in zip(self.document['vertices'],self.vertices)}
        curves=[]
        for edge,item in zip(self.graph.Edges,self.paths):
            curve=hyperedge_path([coordinates[v] for v in edge]);path=QPainterPath()
            curves.append(curve)
            vertices=curve.vertices.copy();vertices[:,0]*=110;vertices[:,1]*=-110
            # Matplotlib path codes are shared with the original exported curves.
            index=0
            while index<len(curve.codes):
                code=int(curve.codes[index]);xy=vertices[index]
                if code==1:path.moveTo(float(xy[0]),float(xy[1]));index+=1
                elif code==2:path.lineTo(float(xy[0]),float(xy[1]));index+=1
                elif code==4:
                    p=vertices[index:index+3]
                    path.cubicTo(float(p[0][0]),float(p[0][1]),float(p[1][0]),float(p[1][1]),float(p[2][0]),float(p[2][1]));index+=3
                elif code==79:path.closeSubpath();index+=1
                else:index+=1
            item.setPath(path)
        from graph_research.rendering.tex_coordinates import for_paths
        items=dict(zip(self.document['vertices'],self.vertices))
        self.coordinate_controls.update_items(items,coordinates,lambda:for_paths(coordinates,curves))
        points=list(coordinates.values())+[p for curve in curves for p in curve.vertices]
        self.figure_label_controls.sync(self.scene,self.document.get('style',{}).get('graph_label'),points,scale=110)

    def _set_figure_label(self,value):
        try:
            from graph_research.graph_input.figure_label import validate
            if value is None:self.document.get('style',{}).pop('graph_label',None)
            else:self.document.setdefault('style',{})['graph_label']=validate(value)
            self.figure_label_controls.load(self.document.get('style',{}).get('graph_label'));self.redraw()
        except ValueError as error:
            QMessageBox.warning(self,'标签未应用',str(error));self.redraw()

    def current_document(self):
        data={**self.document,'positions':[[v.pos().x()/110,-v.pos().y()/110] for v in self.vertices]}
        validate_layout(data,self.graph);return data

    def fit(self):
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-45,-45,45,45))
        self.view.fitInView(self.scene.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)

    def showEvent(self,event):
        super().showEvent(event);QTimer.singleShot(0,self.fit)

    def reset(self):
        self.document=copy.deepcopy(self.initial_document);self.build_scene();self.fit()

    def import_positions(self):
        path,_=QFileDialog.getOpenFileName(self,'导入已有布局','','布局JSON (*.json)')
        if not path:return
        try:self.document,_,_=read_layout(path,self.graph);self.build_scene();self.fit()
        except Exception as exc:QMessageBox.warning(self,'坐标未导入',str(exc))

    def save_positions(self):
        path,_=QFileDialog.getSaveFileName(self,'保存布局坐标','超图布局.json','JSON (*.json)')
        if not path:return
        try:
            atomic_text(Path(path),json.dumps(self.current_document(),ensure_ascii=False,indent=2,allow_nan=False),overwrite=True)
        except Exception as exc:QMessageBox.warning(self,'未能保存',str(exc))

    def use_positions(self):
        try:
            data=self.current_document();labels=data['vertices']
            arguments={'vertices':labels,'edges':[[labels[i] for i in edge] for edge in data['edges']],
                       'positions':[{'vertex':v,'xy':xy} for v,xy in zip(labels,data['positions'])]}
            if data.get('style',{}).get('graph_label'):
                from graph_research.graph_input.document import document
                graph=document(labels,[{'vertices':members,'weight':float(w)} for members,w in zip(arguments['edges'],self.graph.weights)],
                               graph_type='graph' if self.simple else 'hypergraph',weighted=any(w!=1 for w in self.graph.weights),
                               positions=data['positions'],style=data['style'])
                arguments['graph_document']=graph.to_dict()
            self.positions_ready.emit(arguments)
            self.accept()
        except Exception as exc:QMessageBox.warning(self,'布局尚不可导出',str(exc))
