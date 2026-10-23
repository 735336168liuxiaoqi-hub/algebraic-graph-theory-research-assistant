"""Optional live coordinate overlays; no drawing/document state is changed."""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QFont
from PySide6.QtWidgets import QWidget, QHBoxLayout, QGraphicsSimpleTextItem, QGraphicsItem

from .widgets import QCheckBox, QComboBox
from .i18n import UiText
from graph_research.rendering.tex_coordinates import TexCoordinates


class CoordinateControls(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.focused = set()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.enabled = QCheckBox(UiText('显示顶点坐标', 'Show vertex coordinates'))
        self.enabled.setToolTip(UiText('只在编辑画布显示；拖动时实时更新，不写入图片、TeX标签或布局文件。',
                                      'Live editor overlay only; excluded from images, TeX labels and saved layouts.'))
        self.system = QComboBox()
        self.system.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.system.addItem(UiText('原始坐标', 'Original coordinates'), 'original')
        self.system.addItem(UiText('TeX 导出坐标', 'TeX export coordinates'), 'tex')
        self.system.setToolTip(UiText('原始坐标是保存的逻辑坐标；TeX坐标包含当前导出的平移、缩放及精度处理，单位cm。',
                                     'Original: saved logical positions. TeX: exported positions after translation, scaling and precision formatting, in cm.'))
        self.system.setItemData(0,UiText('保存的逻辑坐标，显示时缩短数字，不修改完整保存值。',
                                        'Saved logical coordinates; only displayed numbers are shortened.'),Qt.ItemDataRole.ToolTipRole)
        self.system.setItemData(1,UiText('与当前默认TeX导出一致的坐标，单位cm。',
                                        'Positions matching the current default TeX export, in cm.'),Qt.ItemDataRole.ToolTipRole)
        self.scope = QComboBox()
        self.scope.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.scope.addItem(UiText('全部顶点', 'All vertices'), 'all')
        self.scope.addItem(UiText('仅选中顶点', 'Selected vertices only'), 'selected')
        self.scope.setToolTip(UiText('仅显示正在选择或最近点击、拖动的顶点，减少遮挡。',
                                    'Show selected or most recently clicked/dragged vertices to reduce clutter.'))
        self.scope.setItemData(0,UiText('显示当前图中全部顶点的坐标。','Show coordinates for all vertices.'),Qt.ItemDataRole.ToolTipRole)
        self.scope.setItemData(1,UiText('显示已选顶点或最近点击、拖动的顶点。',
                                       'Show selected or most recently clicked/dragged vertices.'),Qt.ItemDataRole.ToolTipRole)
        for widget in (self.enabled, self.system, self.scope):row.addWidget(widget)
        row.addStretch()
        self.enabled.toggled.connect(self._changed)
        self.system.currentIndexChanged.connect(self._changed)
        self.scope.currentIndexChanged.connect(self._changed)
        self._changed()

    def _changed(self, *unused):
        self.system.setEnabled(self.enabled.isChecked())
        self.scope.setEnabled(self.enabled.isChecked())
        self.changed.emit()

    def focus(self, key):
        self.focused = {key}
        self.changed.emit()

    def update_items(self, items, positions, formatter, selected=()):
        enabled = self.enabled.isChecked()
        chosen = set(selected) | self.focused
        coords = None
        if enabled:
            coords = formatter() if self.system.currentData() == 'tex' else TexCoordinates(vertices=positions.values())
        for key, vertex in items.items():
            if not hasattr(vertex, 'coordinate_caption'):
                caption = QGraphicsSimpleTextItem(vertex)
                caption.setData(1, 'coordinate-overlay')
                caption.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                caption.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
                caption.setBrush(QBrush(QColor('#557078')))
                caption.setFont(QFont('Consolas', 9))
                caption.setPos(10, 10)
                caption.setZValue(20)
                vertex.coordinate_caption = caption
            vertex.coordinate_focus = lambda k=key: self.focus(k)
            caption = vertex.coordinate_caption
            visible = enabled and (self.scope.currentData() == 'all' or key in chosen)
            caption.setVisible(visible)
            if visible:caption.setText(coords.point(positions[key]))
