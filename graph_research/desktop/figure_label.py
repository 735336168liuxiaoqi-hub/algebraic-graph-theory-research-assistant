"""Whole-figure label controls and a draggable, exportable canvas label."""
import copy

from PySide6.QtCore import Qt,QPointF,Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QHBoxLayout,QGraphicsTextItem,QGraphicsItem
from .widgets import QLabel,QLineEdit,QComboBox,QSpinBox,QPushButton
from .i18n import UiText,bind
from graph_research.graph_input import figure_label as label_api


class FigureLabelItem(QGraphicsTextItem):
    def __init__(self,owner):
        super().__init__();self.owner=owner;self._start=None
        self.setData(0,('graph_label',0));self.setZValue(15)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.document().setDocumentMargin(0)
        bind(self,'tooltip',QGraphicsItem.setToolTip,UiText('拖动调整整张图的标签位置；清空标签后应用可移除。',
                                                          'Drag to reposition the figure label; clear the text and apply to remove it.'))

    def mousePressEvent(self,event):
        self._start=self.pos();super().mousePressEvent(event)

    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        if self._start is not None:
            delta=self.pos()-self._start;self._start=None
            if abs(delta.x())+abs(delta.y())>1e-9:self.owner.move_label(delta)


class FigureLabelControls(QWidget):
    applied=Signal(object)

    def __init__(self,parent=None):
        super().__init__(parent);self.item=None;self.record=None;self._span=1.;self._scale=160.
        row=QHBoxLayout(self);row.setContentsMargins(0,0,0,0)
        row.addWidget(QLabel(UiText('图标签','Figure label')))
        self.text=QLineEdit();self.text.setPlaceholderText(UiText('例如 G_1、H_k、图(a)；留空可移除','e.g. G_1, H_k, (a); leave empty to remove'))
        self.text.setMaxLength(128);self.text.setToolTip(UiText('整张图的可见标签；支持G_1、H_k、G_{n+1}及Unicode上下标。文本不会作为TeX命令执行。',
                                                               'Visible label for the whole figure. Supports G_1, H_k, G_{n+1} and Unicode subscripts/superscripts. Text is never executed as TeX.'))
        row.addWidget(self.text,1)
        self.position=QComboBox();self.position.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.position.addItem(UiText('图下方','Below graph'),'below');self.position.addItem(UiText('图上方','Above graph'),'above')
        for index,zh,en in [(0,'放在整张图的下方；可继续拖动微调。','Place below the figure; drag for fine adjustment.'),
                            (1,'放在整张图的上方；可继续拖动微调。','Place above the figure; drag for fine adjustment.')]:
            self.position.setItemData(index,UiText(zh,en),Qt.ItemDataRole.ToolTipRole)
        row.addWidget(self.position)
        self.font_size=QSpinBox();self.font_size.setRange(6,36);self.font_size.setValue(12)
        self.font_size.setSuffix(' pt');self.font_size.setToolTip(UiText('图标签字号，不改变顶点或边的标签字号。',
                                                                      'Figure label font size; vertex/edge label sizes remain unchanged.'))
        row.addWidget(self.font_size)
        self.apply_button=QPushButton(UiText('应用标签','Apply label'));self.apply_button.clicked.connect(self.apply);row.addWidget(self.apply_button)

    def load(self,value):
        self.record=label_api.validate(value) if value is not None else None
        record=self.record or label_api.DEFAULTS
        self.text.setText(record['text']);self.position.setCurrentIndex(self.position.findData(record['position']));self.font_size.setValue(round(record['font_size']))

    def apply(self):
        if not self.text.text().strip():self.applied.emit(None);return
        value=copy.deepcopy(self.record or label_api.DEFAULTS)
        if self.position.currentData()!=value['position']:value['offset']=[0.,0.]
        value.update(text=self.text.text(),position=self.position.currentData(),font_size=self.font_size.value())
        self.applied.emit(label_api.validate(value))

    def reset_item(self):self.item=None

    def sync(self,scene,value,points,*,scale=160,movable=True):
        if value is None or not value.get('text','').strip():
            if self.item is not None:self.item.hide()
            return
        value=label_api.validate(value);point,span=label_api.layout(points,value);self._span=span;self._scale=scale
        if self.item is None:self.item=FigureLabelItem(self);scene.addItem(self.item)
        self.item.setHtml('<span style="font-family:Cambria,Microsoft YaHei;font-size:'+str(value['font_size'])+'pt">'+label_api.html_text(value['text'])+'</span>')
        self.item.setDefaultTextColor(QColor(value['color']))
        box=self.item.boundingRect();self.item.setPos(point[0]*scale-box.width()/2,-point[1]*scale-box.height()/2)
        self.item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,movable);self.item.setAcceptedMouseButtons(Qt.MouseButton.LeftButton if movable else Qt.MouseButton.NoButton)
        self.item.show()

    def move_label(self,delta):
        if self.record is None:return
        value=copy.deepcopy(self.record)
        value['offset']=[value['offset'][0]+delta.x()/self._scale/self._span,
                         value['offset'][1]-delta.y()/self._scale/self._span]
        # Canvas validation reports a failed move and restores its previous label.
        self.applied.emit(value)
