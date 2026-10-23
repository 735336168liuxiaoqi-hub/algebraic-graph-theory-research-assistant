"""Native paper-figure editor using the existing mouse view and draggable vertices."""
import json
from html import escape
from pathlib import Path

from PySide6.QtCore import Qt,QPointF,QRect,Signal,QTimer
from PySide6.QtGui import QColor,QPainter,QPainterPath,QPainterPathStroker,QPen,QBrush,QRadialGradient,QPixmap,QIcon
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QGraphicsScene,QGraphicsPathItem,QGraphicsEllipseItem,QGraphicsTextItem,QGraphicsItem,QSizePolicy
from .widgets import QDialog,QPushButton,QComboBox,QLineEdit,QLabel,QSpinBox,QDoubleSpinBox,QCheckBox,QFileDialog,QColorDialog

from graph_research.graph_input.document import strict_json,tokens
from graph_research.schematics import SchematicDocument,template,from_graph,compress_path,expand,save
from graph_research.schematics.geometry import primitives
from .graph_canvas import GraphView,choice_help
from .layout import VertexItem
from .i18n import UiText,bind
from .graph_text import graph_summary,schematic_conditions


class SchematicView(GraphView):
    """Keep the paper camera independent of edits and anchor wheel zoom at the cursor."""
    def __init__(self,scene,parent):
        super().__init__(scene,parent)
        self.setTransformationAnchor(self.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(self.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # All accepted coordinates and edge extents fit here. Keeping this fixed
        # prevents Qt from recentering when scene.clear() temporarily removes items.
        scene.setSceneRect(-64000,-64000,128000,128000)

    def wheelEvent(self,event):
        delta=event.angleDelta().y()
        if not delta:event.accept();return
        factor=1.15 if delta>0 else 1/1.15
        if 1e-4<self.transform().m11()*factor<1e4:
            point=event.position().toPoint();anchor=self.mapToScene(point)
            self.scale(factor,factor)
            correction=anchor-self.mapToScene(point)
            self.centerOn(self.mapToScene(self.viewport().rect().center())+correction)
        event.accept()

    def mouseDoubleClickEvent(self,event):
        if self.parent().mode.currentData() in ('edge','path','compress'):
            self.pressed.emit(event);event.accept();return
        super().mouseDoubleClickEvent(event)


class SchematicCanvas(QWidget):
    changed=Signal(object);error=Signal(str)
    def __init__(self,scene=None,parent=None):
        super().__init__(parent);self.document=scene or template('blank');self.vertices={};self.draw_items=[];self.undo_stack=[]
        self._updating=False;self._drag_start=None;self._delete_target=None;self.selected=[];self.selected_edges=set();self.selected_path=None;self.selected_core=None
        self._fit_pending=True;self._last_hit=None
        root=QVBoxLayout(self);root.setContentsMargins(0,0,0,0);row=QHBoxLayout()
        self.mode=QComboBox();self.mode.setMinimumWidth(150)
        for title,key in [('拖动锚点','move'),('点击增点','vertex'),('中心超边','edge'),('省略超路','path'),('压缩已有长路','compress'),('删除','delete')]:self.mode.addItem(title,key)
        choice_help(self.mode,{'move':'拖动端点同步更新图形；拖动空白平移，滚轮以鼠标位置为中心缩放。',
            'vertex':'点击空白处添加锚点；可填写标签，留空自动编号。','edge':'依次选中中心超边的连接顶点，再点“创建中心边”。',
            'path':'先点起点再点终点，按下方路长和花括号参数创建；点已有路段可编辑。',
            'compress':'选择已有具体超边，点击“压缩所选路”；只允许无外部分支的松路。可另选两个端点。',
            'delete':'第一次点击预览关联删除，第二次点击同一对象执行；Esc取消，可撤销。'})
        row.addWidget(self.mode);self.label_input=QLineEdit();self.label_input.setPlaceholderText('新锚点标签（可留空）');self.label_input.setMaximumWidth(180);row.addWidget(self.label_input)
        self.connect_button=QPushButton('创建中心边');self.connect_button.clicked.connect(self.connect_selected);row.addWidget(self.connect_button)
        self.compress_button=QPushButton('压缩所选路');self.compress_button.clicked.connect(self.compress_selected);row.addWidget(self.compress_button);row.addStretch();root.addLayout(row)
        self.settings_panel=QWidget();panel=QVBoxLayout(self.settings_panel);panel.setContentsMargins(0,0,0,0)
        self.context_label=QLabel();self.context_label.setTextFormat(Qt.TextFormat.PlainText);panel.addWidget(self.context_label)
        settings=QHBoxLayout();panel.addLayout(settings)
        self.path_settings=QWidget();path_row=QHBoxLayout(self.path_settings);path_row.setContentsMargins(0,0,0,0)
        path_row.addWidget(QLabel('路长'));self.length_input=QLineEdit('a');self.length_input.setMaximumWidth(75);self.length_input.setToolTip('整数超边数，或a、q+2、n-4等；符号路段只用于示意，先赋值再展开计算。');path_row.addWidget(self.length_input)
        self.brace=QComboBox()
        for text,value in [('花括号左侧','left'),('花括号右侧','right'),('无花括号','none')]:self.brace.addItem(text,value)
        choice_help(self.brace,{'left':'沿起点到终点方向的左侧标注。','right':'沿起点到终点方向的右侧标注。','none':'不显示花括号和路长标签。'});path_row.addWidget(self.brace)
        self.first=QSpinBox();self.last=QSpinBox()
        for title,field,side in [('首端边数',self.first,'起点'),('尾端边数',self.last,'终点')]:
            path_row.addWidget(QLabel(title));field.setRange(0,4);field.setValue(1);field.setMaximumWidth(55)
            field.setToolTip('从'+side+'端展示的完整超边段数；0表示该端不展示完整边，仅保留省略连接。');path_row.addWidget(field)
        path_row.addWidget(QLabel('括号间距(cm)'));self.offset=QDoubleSpinBox();self.offset.setRange(.08,2);self.offset.setSingleStep(.04);self.offset.setValue(.28);self.offset.setMaximumWidth(75);self.offset.setToolTip('花括号与超路之间的距离，单位cm；不调整顶点或超边位置。');path_row.addWidget(self.offset)
        settings.addWidget(self.path_settings)
        self.core_settings=QWidget();core_row=QHBoxLayout(self.core_settings);core_row.setContentsMargins(0,0,0,0);core_row.addWidget(QLabel('边形状'))
        self.shape=QComboBox();self.shape.addItem('椭圆中心边','ellipse');self.shape.addItem('圆形中心边','circle')
        choice_help(self.shape,{'ellipse':'按连接锚点分布绘制椭圆中心超边。','circle':'适合三臂、四臂等径向连接的圆形中心超边。'})
        core_row.addWidget(self.shape);settings.addWidget(self.core_settings)
        self.inner_dots=QCheckBox('显示边内省略点');self.inner_dots.setChecked(True);self.inner_dots.setToolTip('省略单条超边内部未画出的顶点；不代表省略整条边。两连接点时随边方向排列，多连接点时默认居中。');settings.addWidget(self.inner_dots)
        settings.addStretch();self.apply_button=QPushButton('应用到所选边');self.apply_button.clicked.connect(self.apply_settings);settings.addWidget(self.apply_button);root.addWidget(self.settings_panel)
        self._loading_controls=False;self._draft_core={'shape':'ellipse','vertex_ellipsis':False};self._draft_path=self._settings()
        for field in (self.first,self.last,self.offset):field.valueChanged.connect(self._remember_creation_settings)
        for field in (self.brace,self.shape):field.currentIndexChanged.connect(self._remember_creation_settings)
        self.inner_dots.toggled.connect(self._remember_creation_settings);self.length_input.textChanged.connect(self._remember_creation_settings)
        self.scene=QGraphicsScene(self);self.view=SchematicView(self.scene,self);self.view.setRenderHint(QPainter.RenderHint.Antialiasing);self.view.setBackgroundBrush(QBrush(QColor('white')))
        self.view.setMinimumSize(620,370);self.view.pressed.connect(self._pressed);self.view.released.connect(self._released);root.addWidget(self.view,1)
        row=QHBoxLayout();self.fit_button=QPushButton('适应窗口');self.fit_button.setToolTip('主动缩放并居中显示全图；日常编辑保留当前视野。');self.fit_button.clicked.connect(self.fit);row.addWidget(self.fit_button)
        self.undo_button=QPushButton('撤销');self.undo_button.clicked.connect(self.undo);row.addWidget(self.undo_button)
        clear=QPushButton('清除选择');clear.clicked.connect(self.unselect);row.addWidget(clear)
        self.vertex_labels=QCheckBox('顶点标签');self.vertex_labels.toggled.connect(self.redraw);row.addWidget(self.vertex_labels)
        self.selection_text=QLabel();self.selection_text.setWordWrap(True);self.selection_text.setTextFormat(Qt.TextFormat.PlainText);row.addWidget(self.selection_text,1);root.addLayout(row)
        from .coordinate_labels import CoordinateControls
        self.coordinate_controls=CoordinateControls(self);self.coordinate_controls.changed.connect(self.redraw);root.addWidget(self.coordinate_controls)
        from .figure_label import FigureLabelControls
        self.figure_label_controls=FigureLabelControls(self);self.figure_label_controls.applied.connect(self._set_figure_label);root.addWidget(self.figure_label_controls)
        self.mode.currentIndexChanged.connect(self._mode_changed);self.set_document(self.document)

    def current_document(self):
        data=self.document.to_dict()
        for v in data['vertices']:
            if v['id'] in self.vertices:
                p=self.vertices[v['id']].pos();v['xy']=[p.x()/160,-p.y()/160]
        return SchematicDocument(data)

    def set_document(self,scene,*,reset_undo=False,fit_view=True):
        if not isinstance(scene,SchematicDocument):scene=SchematicDocument(scene)
        transform=self.view.transform();center=self.view.mapToScene(self.view.viewport().rect().center())
        self._updating=True;self.vertices={};self.draw_items=[];self.figure_label_controls.reset_item();self.scene.clear();self.document=scene
        self.figure_label_controls.load(scene.to_dict()['style'].get('graph_label'))
        if reset_undo:self.undo_stack=[]
        for v in scene.to_dict()['vertices']:
            item=VertexItem(str(v['id']),QPointF(v['xy'][0]*160,-v['xy'][1]*160),self._dragged)
            item.setData(0,('vertex',v['id']));item.setToolTip(str(v['id']));item.setZValue(6);self.scene.addItem(item);self.vertices[v['id']]=item
        self._updating=False;self._mode_changed()
        if fit_view:
            self._fit_pending=True
            if self.isVisible():self.fit()
        else:
            self.view.setTransform(transform);self.view.centerOn(center)
        self.changed.emit(scene)

    def _publish(self,data):
        candidate=data if isinstance(data,SchematicDocument) else SchematicDocument(data)
        previous=self.current_document()
        if candidate==previous:return
        self.undo_stack.append(previous);self.undo_stack=self.undo_stack[-100:];self.set_document(candidate,fit_view=False)

    def _set_figure_label(self,value):
        try:
            before=self.current_document();data=before.to_dict()
            if value is None:data['style'].pop('graph_label',None)
            else:data['style']['graph_label']=value
            candidate=SchematicDocument(data)
            if candidate!=before:
                self.undo_stack.append(before);self.undo_stack=self.undo_stack[-100:];self.document=candidate
                self.figure_label_controls.load(candidate.to_dict()['style'].get('graph_label'));self.redraw();self.changed.emit(candidate)
        except ValueError as error:self.error.emit(str(error));self.redraw()

    def _mode_changed(self):
        movable=self.mode.currentData()=='move'
        for item in self.vertices.values():item.setFlag(item.GraphicsItemFlag.ItemIsMovable,movable)
        self.view.setDragMode(self.view.DragMode.ScrollHandDrag if movable else self.view.DragMode.NoDrag)
        self.connect_button.setEnabled(self.mode.currentData()=='edge');self.compress_button.setEnabled(self.mode.currentData()=='compress');self.unselect()

    def unselect(self):
        self.selected=[];self.selected_edges=set();self.selected_path=None;self.selected_core=None;self._delete_target=None
        self.coordinate_controls.focused=set()
        self._last_hit=None;self._restore_creation_settings();self.selection_text.setText('');self.redraw();self._sync_controls()

    def _remember_creation_settings(self,*unused):
        if self._loading_controls or self.selected_core is not None or self.selected_path is not None:return
        if self.mode.currentData()=='edge':self._draft_core={'shape':self.shape.currentData(),'vertex_ellipsis':self.inner_dots.isChecked()}
        elif self.mode.currentData()=='path':self._draft_path=self._settings()

    def _load_settings(self,kind,record):
        self._loading_controls=True
        try:
            if kind=='path':
                self.length_input.setText(str(record['length']));self.brace.setCurrentIndex(self.brace.findData(record['brace']))
                self.first.setValue(record['first_edges']);self.last.setValue(record['last_edges']);self.offset.setValue(record['label_offset'])
            else:self.shape.setCurrentIndex(self.shape.findData(record['shape']))
            self.inner_dots.setChecked(record['vertex_ellipsis'])
        finally:self._loading_controls=False

    def _restore_creation_settings(self):
        mode=self.mode.currentData()
        if mode in ('edge','path'):self._load_settings(mode,self._draft_core if mode=='edge' else self._draft_path)

    def _sync_controls(self):
        mode=self.mode.currentData();editing=self.selected_path is not None or self.selected_core is not None
        kind='path' if self.selected_path is not None else 'edge' if self.selected_core is not None else mode
        visible=kind in ('edge','path') and mode not in ('move','vertex','delete','compress')
        self.settings_panel.setVisible(visible);self.path_settings.setVisible(kind=='path');self.core_settings.setVisible(kind=='edge')
        self.label_input.setVisible(mode=='vertex');self.connect_button.setVisible(mode=='edge');self.compress_button.setVisible(mode=='compress')
        self.connect_button.setEnabled(mode=='edge' and not editing and len(self.selected)>=2)
        self.apply_button.setEnabled(editing and visible);self.apply_button.setText(UiText('应用到所选'+('超路' if kind=='path' else '中心边'),'Apply to selected '+('hyperpath' if kind=='path' else 'central edge')))
        if editing:
            index=self.selected_path if kind=='path' else self.selected_core
            self.context_label.setText(UiText(('超路 p' if kind=='path' else '中心边 e')+str(index)+' · 编辑（修改后点击应用）',('Hyperpath p' if kind=='path' else 'Central edge e')+str(index)+' · Edit, then apply'))
        elif kind=='edge':self.context_label.setText(UiText('创建中心边 · 已选'+str(len(self.selected))+'个锚点',f'Create central edge · {len(self.selected)} anchors selected'))
        else:self.context_label.setText(UiText('创建超路 · '+('请选择终点' if self.selected else '先点击起点，再点击终点'),'Create hyperpath · '+('Select the end anchor' if self.selected else 'Select start, then end')))

    def _hit_tag(self,event):
        """Pick visible outlines, with Alt-click to cycle overlapping edges."""
        point=event.position().toPoint();scene_point=self.view.mapToScene(point);candidates=[]
        tolerance=6/max(self.view.transform().m11(),1e-4)
        for item in self.view.items(QRect(point.x()-6,point.y()-6,13,13)):
            if item.data(1)=='coordinate-overlay':continue
            target=item
            while target is not None and target.data(0) is None:target=target.parentItem()
            if target is None:continue
            tag=tuple(target.data(0))
            if tag[0]=='vertex':
                if item.contains(item.mapFromScene(scene_point)):return tag
                continue
            if isinstance(target,QGraphicsPathItem):
                if target.pen().style()==Qt.PenStyle.NoPen:continue
                stroke=QPainterPathStroker();stroke.setWidth(max(tolerance*2,target.pen().widthF()))
                if not stroke.createStroke(target.path()).contains(target.mapFromScene(scene_point)):continue
            elif not item.contains(item.mapFromScene(scene_point)):continue
            if tag not in candidates:candidates.append(tag)
        if not candidates:return None
        current=self._delete_target or (('path',self.selected_path) if self.selected_path is not None else
            ('edge',self.selected_core) if self.selected_core is not None else self._last_hit)
        if current in candidates:
            index=candidates.index(current)
            tag=candidates[(index+1)%len(candidates)] if event.modifiers()&Qt.KeyboardModifier.AltModifier else current
        else:tag=candidates[0]
        self._last_hit=tag;return tag

    def _settings(self):
        text=self.length_input.text().strip();length=int(text) if text.isdigit() else text
        return {'length':length,'brace':self.brace.currentData(),'first_edges':self.first.value(),'last_edges':self.last.value(),
                'label_offset':self.offset.value(),'vertex_ellipsis':self.inner_dots.isChecked()}

    def add_vertex(self,label=None,position=None):
        data=self.current_document().to_dict();used={v['id'] for v in data['vertices']}
        if label is None:
            label=0
            while label in used:label+=1
        data['vertices'].append({'id':label,'xy':position or [len(used)*.5,0]});self._publish(data);return label

    def add_path(self,start,end):
        data=self.current_document().to_dict();data['paths'].append({'start':start,'end':end,**self._settings()});self._publish(data)
        text=self.length_input.text()
        if len(text)==1 and 'a'<=text<'z':self.length_input.setText(chr(ord(text)+1))

    def connect_selected(self):
        try:
            data=self.current_document().to_dict();data['edges'].append({'vertices':self.selected[:],'shape':self.shape.currentData(),'vertex_ellipsis':self.inner_dots.isChecked()});self._publish(data)
        except ValueError as error:self.error.emit(str(error))

    def compress_selected(self):
        try:self._publish(compress_path(self.current_document(),sorted(self.selected_edges),self.selected[:] if len(self.selected)==2 else None))
        except ValueError as error:self.error.emit(str(error))

    def apply_settings(self):
        try:
            data=self.current_document().to_dict()
            if self.selected_path is not None:
                data['paths'][self.selected_path].update(self._settings());data['paths'][self.selected_path].pop('ellipsis',None)
            elif self.selected_core is not None:
                data['edges'][self.selected_core].update(shape=self.shape.currentData(),vertex_ellipsis=self.inner_dots.isChecked())
            else:raise ValueError('先点击已有路段或中心边，再应用参数。')
            self._publish(data)
        except ValueError as error:self.error.emit(str(error))

    def preview_delete(self,tag):
        tag=tuple(tag)
        if self._delete_target==tag:
            data=self.current_document().to_dict();kind,index=tag
            if kind=='vertex':
                data['vertices']=[v for v in data['vertices'] if v['id']!=index]
                data['edges']=[e for e in data['edges'] if index not in e['vertices']]
                data['paths']=[p for p in data['paths'] if index not in (p['start'],p['end'])]
            else:data['edges' if kind=='edge' else 'paths'].pop(index)
            self._publish(data);return
        self._delete_target=tag;self.redraw();self.selection_text.setText('红色对象将被删除；再次点击同一对象确认，Esc取消。')

    def _pressed(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return
        tag=self._hit_tag(event);mode=self.mode.currentData()
        try:
            if tag and tag[0]=='graph_label':self._drag_start=None;return
            if mode=='move':
                self._drag_start=self.current_document()
                if tag is None:self.coordinate_controls.focused=set();self.redraw()
                return
            if mode=='vertex' and tag is None:
                text=tokens(self.label_input.text()) if self.label_input.text().strip() else []
                if len(text)>1:raise ValueError('一次填写一个锚点标签。')
                xy=self.view.mapToScene(event.position().toPoint());self.add_vertex(text[0] if text else None,[xy.x()/160,-xy.y()/160]);self.label_input.clear()
            elif mode=='delete':
                if tag:self.preview_delete(tag)
                else:self.unselect()
            elif tag and tag[0]=='vertex':
                editing=self.selected_path is not None or self.selected_core is not None
                self.selected_path=None;self.selected_core=None
                if editing:self._restore_creation_settings()
                v=tag[1]
                if v in self.selected:self.selected.remove(v)
                else:self.selected.append(v)
                self.selection_text.setText('选中：'+', '.join(map(str,self.selected)));self.redraw();self._sync_controls()
                if mode=='path' and len(self.selected)==2:self.add_path(*self.selected)
            elif tag and tag[0]=='edge' and mode=='compress':
                if tag[1] in self.selected_edges:self.selected_edges.remove(tag[1])
                else:self.selected_edges.add(tag[1])
                self.selection_text.setText('已选超边：'+', '.join(str(i) for i in sorted(self.selected_edges)));self.redraw()
            elif tag and tag[0] in ('path','edge'):
                if (tag[0]=='path' and self.selected_path==tag[1]) or (tag[0]=='edge' and self.selected_core==tag[1]):
                    self.unselect();return
                self.selected=[]
                self.selected_path=tag[1] if tag[0]=='path' else None;self.selected_core=tag[1] if tag[0]=='edge' else None
                record=self.document.to_dict()['paths' if tag[0]=='path' else 'edges'][tag[1]]
                self._load_settings(tag[0],record);self.selection_text.setText('修改参数后应用；再次点击取消。交叠边界可用 Alt+单击切换。');self.redraw();self._sync_controls()
            elif tag is None:self.unselect()
        except (ValueError,IndexError) as error:self.error.emit(str(error))

    def _released(self):
        if self.mode.currentData()!='move':return
        try:
            value=self.current_document()
            if self._drag_start is not None and value!=self._drag_start:self.undo_stack.append(self._drag_start);self.undo_stack=self.undo_stack[-100:]
            self.document=value;self.redraw();self.changed.emit(value)
        except ValueError as error:
            if self._drag_start is not None:self.set_document(self._drag_start,fit_view=False)
            self.error.emit(str(error))
        finally:self._drag_start=None

    def _dragged(self):
        if not self._updating:
            try:self.redraw()
            except ValueError:pass

    def redraw(self):
        if self._updating:return
        from shiboken6 import delete
        for item in self.draw_items:delete(item)
        self.draw_items=[];data=self.current_document().to_dict();pending=self._delete_target
        def affected(tag):
            if tuple(tag)==pending:return True
            if pending and pending[0]=='vertex':
                if tag[0]=='edge':return pending[1] in data['edges'][tag[1]]['vertices']
                if tag[0]=='path':return pending[1] in (data['paths'][tag[1]]['start'],data['paths'][tag[1]]['end'])
            return False
        for v,item in self.vertices.items():
            color=QColor('#d17d20' if v in self.selected else data['style']['vertex_color']);radius=data['style']['vertex_radius']*160
            item.setRect(-radius,-radius,2*radius,2*radius);g=QRadialGradient(-radius*.3,-radius*.3,radius*1.4);g.setColorAt(0,QColor('white'));g.setColorAt(.35,color);g.setColorAt(1,color.darker(150))
            item.setBrush(QBrush(g));item.setPen(QPen(QColor('#d52929' if affected(['vertex',v]) else 'white'),2));item.caption.setVisible(self.vertex_labels.isChecked())
        scene=SchematicDocument(data);drawing=primitives(scene,False)
        for primitive in drawing:
            if primitive.get('role')=='graph_label':continue
            tag=primitive['tag']
            if primitive['kind']=='circle' and primitive['role']=='anchor':continue
            color=QColor('#ce3434' if affected(tag) else '#dc8a20' if tag[0]=='edge' and tag[1] in self.selected_edges or tag[0]=='path' and tag[1]==self.selected_path or tag[0]=='edge' and tag[1]==self.selected_core else data['style']['line_color'])
            if primitive['kind']=='path':
                path=QPainterPath()
                for command in primitive['commands']:
                    values=[v*160*(1 if i%2==0 else -1) for i,v in enumerate(command[1:])]
                    if command[0]=='M':path.moveTo(*values)
                    elif command[0]=='L':path.lineTo(*values)
                    elif command[0]=='C':path.cubicTo(*values)
                    else:path.closeSubpath()
                item=QGraphicsPathItem(path);pen=QPen(color,max(1,primitive['width']*160)*(1.7 if affected(tag) else 1))
                if affected(tag):pen.setStyle(Qt.PenStyle.DashLine)
                if primitive['stroke']=='none':pen=QPen(Qt.PenStyle.NoPen)
                item.setPen(pen)
                if primitive['fill']!='none':item.setBrush(QBrush(QColor(primitive['fill'])))
            elif primitive['kind']=='circle':
                x,y=primitive['xy'];r=primitive['r']*160;item=QGraphicsEllipseItem(-r,-r,2*r,2*r);item.setPos(x*160,-y*160)
                item.setBrush(QBrush(QColor(primitive['color']) if primitive['role']=='junction' else color));item.setPen(QPen(Qt.PenStyle.NoPen))
            else:
                item=QGraphicsTextItem();item.setHtml('<span style="font-family:Times New Roman;font-size:12pt">'+('<i>P</i><sub>'+escape(primitive['text'][2:])+'</sub>')+'</span>')
                item.setDefaultTextColor(color)
                box=item.boundingRect();x,y=primitive['xy'];item.setPos(x*160-box.width()/2,-y*160-box.height()/2)
            item.setZValue(primitive['layer']);item.setData(0,tuple(tag))
            action='再次点击确认删除；Esc取消。' if self.mode.currentData()=='delete' else '点击切换选中；交叠边界用 Alt+单击切换。'
            english_action='Click again to delete; Esc cancels.' if self.mode.currentData()=='delete' else 'Click to toggle selection; Alt+click cycles overlapping boundaries.'
            tip=UiText(('中心边 e' if tag[0]=='edge' else '超路 p')+str(tag[1])+'：'+action,('Central edge e' if tag[0]=='edge' else 'Hyperpath p')+str(tag[1])+': '+english_action)
            bind(item,'tooltip',QGraphicsItem.setToolTip,tip)
            self.scene.addItem(item);self.draw_items.append(item)
        self.undo_button.setEnabled(bool(self.undo_stack))
        from graph_research.schematics.tikz import _tex_coordinates
        scene=SchematicDocument(data);positions={v['id']:v['xy'] for v in data['vertices']}
        self.coordinate_controls.update_items(self.vertices,positions,lambda:_tex_coordinates(scene),self.selected)
        from graph_research.schematics.geometry import bounds
        x0,y0,x1,y1=bounds([p for p in drawing if p.get('role')!='graph_label'])
        self.figure_label_controls.sync(self.scene,data['style'].get('graph_label'),[(x0,y0),(x1,y1)],movable=self.mode.currentData()=='move')

    def undo(self):
        if self._delete_target is not None:self.unselect();return
        if self.undo_stack:self.set_document(self.undo_stack.pop(),fit_view=False)

    def fit(self):
        box=self.scene.itemsBoundingRect().adjusted(-60,-60,60,60)
        if not self.vertices:box.setRect(-400,-260,800,520)
        self.view.fitInView(box,Qt.AspectRatioMode.KeepAspectRatio);self._fit_pending=False
    def showEvent(self,event):
        super().showEvent(event)
        if self._fit_pending:QTimer.singleShot(0,lambda:self.fit() if self._fit_pending else None)


class SchematicDialog(QDialog):
    diagram_ready=Signal(object);graph_ready=Signal(object)
    def __init__(self,scene=None,parent=None):
        super().__init__(parent);self.resize(1220,820);self.setWindowTitle('论文示意图')
        root=QVBoxLayout(self);row=QHBoxLayout();self.templates=QComboBox()
        for title,key in [('空白画布','blank'),('三臂顶点布局','E'),('三臂中心边布局','F'),('四臂中心边布局','H'),('两端分支与内部路','G')]:self.templates.addItem(title,key)
        choice_help(self.templates,{'blank':'从空白画布点击增点、连中心边和省略超路。','E':'一个中心顶点连接三条符号悬挂路。','F':'中心超边的三个不同锚点各连接一条符号路。','H':'中心超边的四个不同锚点各连接一条符号路，k至少为4。','G':'两端中心边各接两条悬挂路；路长只计连接段，不含独立中心边。模板是布局，论文图族须核对定义。'})
        row.addWidget(self.templates);apply=QPushButton('载入模板');apply.clicked.connect(lambda:self.set_document(template(self.templates.currentData())));row.addWidget(apply)
        row.addWidget(QLabel('一致度'));self.rank=QLineEdit();self.rank.setMaximumWidth(65);self.rank.setToolTip('填数值或符号k。已画中心边的不同连接顶点数不能超过k。');row.addWidget(self.rank)
        self.name=QLineEdit();self.name.setPlaceholderText('示意图名称');row.addWidget(self.name,1)
        load=QPushButton('打开示意图');load.clicked.connect(self.load_scene);row.addWidget(load)
        save_button=QPushButton('保存布局');save_button.clicked.connect(lambda:self.export_file('.json'));row.addWidget(save_button);root.addLayout(row)
        style_row=QHBoxLayout();style_row.addWidget(QLabel(UiText('线宽（cm）','Line width (cm)')))
        self.line_width=QDoubleSpinBox();self.line_width.setDecimals(3);self.line_width.setRange(.003,.08);self.line_width.setSingleStep(.002);self.line_width.setMaximumWidth(70);self.line_width.setToolTip('图线宽度，单位cm；保存后TeX和SVG同步使用。');style_row.addWidget(self.line_width)
        self.color_buttons={};self.color_titles={}
        for chinese,english,key in [('线条颜色','Line color','line_color'),('顶点颜色','Vertex color','vertex_color'),('超边填充','Hyperedge fill','edge_fill')]:
            title=UiText(chinese,english);button=QPushButton(title);button.setSizePolicy(QSizePolicy.Policy.Minimum,QSizePolicy.Policy.Fixed)
            button.setObjectName('schematic_color_'+key);button.clicked.connect(lambda checked=False,k=key:self.choose_color(k))
            self.color_buttons[key]=button;self.color_titles[key]=title;style_row.addWidget(button)
        style_row.addStretch();root.addLayout(style_row)
        self.canvas=SchematicCanvas(scene or template('blank'));self.canvas.error.connect(lambda text:self.status.setText(text));self.canvas.changed.connect(self._changed);root.addWidget(self.canvas,1)
        self.status=QLabel();self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText);root.addWidget(self.status)
        row=QHBoxLayout();self.parameters=QLineEdit();self.parameters.setPlaceholderText('展开参数，例如 {"k":3,"a":4}');self.parameters.setMaximumWidth(330);row.addWidget(self.parameters)
        expand_button=QPushButton('展开为具体超图');expand_button.clicked.connect(self.expand_graph);row.addWidget(expand_button);row.addStretch()
        self.standalone=QCheckBox('完整TeX文档');self.standalone.setChecked(True);row.addWidget(self.standalone)
        tex=QPushButton('导出TeX');tex.clicked.connect(lambda:self.export_file('.tex'));row.addWidget(tex)
        svg=QPushButton('导出SVG');svg.clicked.connect(lambda:self.export_file('.svg'));row.addWidget(svg)
        use=QPushButton('用于导出工具');use.clicked.connect(self.use_diagram);row.addWidget(use);close=QPushButton('关闭');close.clicked.connect(self.reject);row.addWidget(close);root.addLayout(row)
        self.rank.editingFinished.connect(self.update_header);self.name.editingFinished.connect(self.update_header);self.set_document(self.canvas.document)
        self.line_width.editingFinished.connect(lambda:self.set_style('line_width',self.line_width.value()))
        for button in self.findChildren(QPushButton):button.setAutoDefault(False)

    def _changed(self,scene):
        data=scene.to_dict();self.rank.setText(str(data['rank']));self.name.setText(data['name'])
        self.line_width.setValue(data['style']['line_width'])
        self.status.setText(schematic_conditions(scene));self._update_colors(data['style'])

    def _update_colors(self,style):
        for key,button in self.color_buttons.items():
            value=style[key];swatch=QPixmap(18,18);swatch.fill(Qt.GlobalColor.transparent)
            painter=QPainter(swatch);painter.setPen(QPen(QColor('#627780'),1));painter.setBrush(QBrush(QColor(value)));painter.drawRect(1,1,15,15);painter.end()
            button.setIcon(QIcon(swatch));title=self.color_titles[key]
            button.setToolTip(UiText(str(title)+'：'+value+'；点击选择颜色。',title.english+': '+value+'; click to choose a color.'))

    def set_document(self,scene):
        self.canvas.set_document(scene,reset_undo=True)
        name=scene.to_dict()['name'];key=name[0] if name[:1] in ('E','F','H','G') else 'blank'
        self.templates.setCurrentIndex(self.templates.findData(key))
    def update_header(self):
        try:
            data=self.canvas.current_document().to_dict();text=self.rank.text().strip();data['rank']=int(text) if text.isdigit() else text;data['name']=self.name.text().strip();self.canvas._publish(data)
        except ValueError as error:self._changed(self.canvas.document);self.status.setText(str(error))

    def export_file(self,suffix):
        path,_=QFileDialog.getSaveFileName(self,'保存论文示意图','论文示意图'+suffix,{' .tex':'TeX (*.tex)'}.get(' '+suffix,'示意图 (*'+suffix+')'))
        if not path:return
        try:
            save(self.canvas.current_document(),path,standalone=self.standalone.isChecked(),vertex_labels=self.canvas.vertex_labels.isChecked(),overwrite=True)
            self.status.setText('已保存：'+path)
        except (ValueError,OSError) as error:self.status.setText(str(error))

    def load_scene(self):
        path,_=QFileDialog.getOpenFileName(self,'打开论文示意图','','示意图JSON (*.json)')
        if not path:return
        try:
            with Path(path).open('rb') as stream:raw=stream.read(256*1024+1)
            if len(raw)>256*1024:raise ValueError('示意图文件最多256KiB。')
            self.set_document(SchematicDocument(strict_json(raw.decode('utf-8-sig'))))
        except (ValueError,OSError) as error:self.status.setText(str(error))

    def expand_graph(self):
        try:
            parameters=strict_json(self.parameters.text()) if self.parameters.text().strip() else {}
            graph=expand(self.canvas.current_document(),parameters);self.graph_ready.emit(graph);self.status.setText(graph_summary(graph,expanded_notice=True))
        except ValueError as error:self.status.setText(str(error))

    def use_diagram(self):self.diagram_ready.emit(self.canvas.current_document());self.accept()

    def set_style(self,key,value):
        try:
            data=self.canvas.current_document().to_dict();data['style'][key]=value;self.canvas._publish(data)
        except ValueError as error:self.status.setText(str(error))

    def choose_color(self,key):
        color=QColorDialog.getColor(QColor(self.canvas.document.to_dict()['style'][key]),self,'选择颜色')
        if color.isValid():self.set_style(key,color.name())
