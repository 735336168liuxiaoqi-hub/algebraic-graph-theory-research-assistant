"""Localized Qt presentation widgets. Editable data, JSON and answers stay raw."""
from PySide6 import QtWidgets as W
from PySide6.QtCore import Qt
from .i18n import tr,bind,unbind,forget


class WidgetMixin:
    def setWindowTitle(self,value):return bind(self,'title',W.QWidget.setWindowTitle,value)
    def setToolTip(self,value):return bind(self,'tooltip',W.QWidget.setToolTip,value)
    def setRawToolTip(self,value):
        forget(self,'tooltip');return W.QWidget.setToolTip(self,value)
    def setStatusTip(self,value):return bind(self,'status_tip',W.QWidget.setStatusTip,value)


class QLabel(WidgetMixin,W.QLabel):
    def __init__(self,*args,**kwargs):
        source=args[0] if args and isinstance(args[0],str) else None
        super().__init__(*args,**kwargs)
        if source is not None:self.setText(source)
    def setText(self,value):
        if self.property('i18n_raw'):return self.setRawText(value)
        return bind(self,'text',W.QLabel.setText,value)
    def setRawText(self,value):
        forget(self,'text');return W.QLabel.setText(self,value)


class QPushButton(WidgetMixin,W.QPushButton):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        source=next((a for a in args if isinstance(a,str)),None)
        if source is not None:self.setText(source)
    def setText(self,value):return bind(self,'text',W.QPushButton.setText,value)


class QCheckBox(WidgetMixin,W.QCheckBox):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if args and isinstance(args[0],str):self.setText(args[0])
    def setText(self,value):return bind(self,'text',W.QCheckBox.setText,value)


class QToolButton(WidgetMixin,W.QToolButton):
    def setText(self,value):return bind(self,'text',W.QToolButton.setText,value)


class QLineEdit(WidgetMixin,W.QLineEdit):
    def setPlaceholderText(self,value):return bind(self,'placeholder',W.QLineEdit.setPlaceholderText,value)


class QPlainTextEdit(WidgetMixin,W.QPlainTextEdit):
    def setPlaceholderText(self,value):return bind(self,'placeholder',W.QPlainTextEdit.setPlaceholderText,value)
    def setLocalizedRenderer(self,renderer):
        from .i18n import listen
        first=not hasattr(self,'_localized_renderer');self._localized_renderer=renderer
        if first:listen(self._render_localized)
        self._render_localized()
    def _render_localized(self):W.QPlainTextEdit.setPlainText(self,self._localized_renderer())


class QComboBox(WidgetMixin,W.QComboBox):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.currentIndexChanged.connect(self._current_tip)
    def _current_tip(self,index):
        from .i18n import _bindings
        source=_bindings.get(self,{}).get(('item_tip',index))
        if source:self.setToolTip(source[1])
    def addItem(self,*args,**kwargs):
        index=self.count();result=super().addItem(*args,**kwargs)
        if not self.property('i18n_raw'):
            source=next((a for a in args if isinstance(a,str)),None)
            if source is not None:bind(self,('item',index),W.QComboBox.setItemText,source,index)
        return result
    def addItems(self,texts):
        for text in texts:self.addItem(text)
    def addRawItem(self,*args,**kwargs):return W.QComboBox.addItem(self,*args,**kwargs)
    def setToolTip(self,value):
        from .i18n import _bindings
        source=_bindings.get(self,{}).get(('item_tip',self.currentIndex()))
        if source and value==tr(source[1]):value=source[1]
        return bind(self,'tooltip',W.QWidget.setToolTip,value)
    def setItemText(self,index,text):
        if self.property('i18n_raw'):return super().setItemText(index,text)
        return bind(self,('item',index),W.QComboBox.setItemText,text,index)
    def setItemData(self,index,value,role=Qt.ItemDataRole.UserRole):
        if role==Qt.ItemDataRole.ToolTipRole:
            result=bind(self,('item_tip',index),_combo_tooltip,value,index)
            if index==self.currentIndex():self.setToolTip(value)
            return result
        return super().setItemData(index,value,role)
    def clear(self):
        unbind(self,'item');unbind(self,'item_tip');return super().clear()


def _combo_tooltip(obj,index,value):W.QComboBox.setItemData(obj,index,value,Qt.ItemDataRole.ToolTipRole)


class QTabWidget(WidgetMixin,W.QTabWidget):
    def removeTab(self,index):
        child=self.widget(index);forget(self,('tab',child));forget(self,('tab_tip',child))
        return super().removeTab(index)
    def addTab(self,*args):
        index=super().addTab(*args);self.setTabText(index,args[-1]);return index
    def insertTab(self,index,*args):
        # Tab insertion/removal changes positions; rebind labels by child widget.
        result=super().insertTab(index,*args);self.setTabText(result,args[-1]);return result
    def setTabText(self,index,text):return bind(self,('tab',self.widget(index)),_tab_text,text,self.widget(index))
    def setTabToolTip(self,index,text):return bind(self,('tab_tip',self.widget(index)),_tab_tip,text,self.widget(index))


def _tab_text(obj,widget,text):
    index=obj.indexOf(widget)
    if index>=0:W.QTabWidget.setTabText(obj,index,text)
def _tab_tip(obj,widget,text):
    index=obj.indexOf(widget)
    if index>=0:W.QTabWidget.setTabToolTip(obj,index,text)


class QMenu(WidgetMixin,W.QMenu):
    def addAction(self,*args,**kwargs):
        action=super().addAction(*args,**kwargs)
        source=next((a for a in args if isinstance(a,str)),None)
        if source is not None:
            from PySide6.QtGui import QAction
            bind(action,'text',QAction.setText,source)
        return action


class QMenuBar(WidgetMixin,W.QMenuBar):
    def addMenu(self,*args):
        if len(args)==1 and isinstance(args[0],str):
            menu=QMenu(self);bind(menu,'menu_title',W.QMenu.setTitle,args[0]);super().addMenu(menu);return menu
        return super().addMenu(*args)


class QStatusBar(WidgetMixin,W.QStatusBar):
    def showMessage(self,text,timeout=0):
        return bind(self,'status_message',_status_message,text,timeout)
    def clearMessage(self):
        forget(self,'status_message');return super().clearMessage()


def _status_message(obj,timeout,text):W.QStatusBar.showMessage(obj,text,timeout)


class QMainWindow(WidgetMixin,W.QMainWindow):
    def menuBar(self):
        if not hasattr(self,'_localized_menu'):
            self._localized_menu=QMenuBar(self);self.setMenuBar(self._localized_menu)
        return self._localized_menu
    def statusBar(self):
        if not hasattr(self,'_localized_status'):
            self._localized_status=QStatusBar(self);self.setStatusBar(self._localized_status)
        return self._localized_status


class QDialog(WidgetMixin,W.QDialog):pass


class QTreeWidgetItem(W.QTreeWidgetItem):
    def __init__(self,*args,**kwargs):
        self._raw_text=kwargs.pop('raw',False)
        super().__init__(*args,**kwargs)
        texts=next((a for a in args if isinstance(a,(list,tuple))),None)
        if texts:
            for col,text in enumerate(texts):self.setText(col,text)
    def setText(self,column,text):
        if self._raw_text:return W.QTreeWidgetItem.setText(self,column,text)
        return bind(self,('text',column),W.QTreeWidgetItem.setText,text,column)
    def setToolTip(self,column,text):return bind(self,('tip',column),W.QTreeWidgetItem.setToolTip,text,column)


class QListWidgetItem(W.QListWidgetItem):
    def __init__(self,*args,**kwargs):
        self._raw_text=kwargs.pop('raw',False)
        super().__init__(*args,**kwargs)
        source=next((a for a in args if isinstance(a,str)),None)
        if source is not None:self.setText(source)
    def setText(self,value):
        if self._raw_text:return W.QListWidgetItem.setText(self,value)
        return bind(self,'text',W.QListWidgetItem.setText,value)
    def setToolTip(self,value):return bind(self,'tip',W.QListWidgetItem.setToolTip,value)


class QTreeWidget(WidgetMixin,W.QTreeWidget):
    def setHeaderLabels(self,values):return bind(self,'headers',W.QTreeWidget.setHeaderLabels,values)


class QTableWidget(WidgetMixin,W.QTableWidget):
    def setHorizontalHeaderLabels(self,values):return bind(self,'headers',W.QTableWidget.setHorizontalHeaderLabels,values)


class QTableWidgetItem(W.QTableWidgetItem):
    """Data cells are raw by default; only explicitly marked UI cells translate."""
    def __init__(self,*args,**kwargs):
        self._ui=kwargs.pop('ui',False);super().__init__(*args,**kwargs)
        if self._ui and args and isinstance(args[0],str):self.setText(args[0])
    def setText(self,value):
        if self._ui:return bind(self,'text',W.QTableWidgetItem.setText,value)
        return W.QTableWidgetItem.setText(self,value)


class QFormLayout(W.QFormLayout):
    def addRow(self,*args):
        if args and isinstance(args[0],str):args=(QLabel(args[0]),*args[1:])
        return super().addRow(*args)


class QSpinBox(WidgetMixin,W.QSpinBox):
    def setSpecialValueText(self,value):return bind(self,'special',W.QSpinBox.setSpecialValueText,value)


class QDoubleSpinBox(WidgetMixin,W.QDoubleSpinBox):
    def setSpecialValueText(self,value):return bind(self,'special',W.QDoubleSpinBox.setSpecialValueText,value)


class QMessageBox(W.QMessageBox):
    @staticmethod
    def information(parent,title,text,*args,**kwargs):return W.QMessageBox.information(parent,tr(title),tr(text),*args,**kwargs)
    @staticmethod
    def warning(parent,title,text,*args,**kwargs):return W.QMessageBox.warning(parent,tr(title),tr(text),*args,**kwargs)
    @staticmethod
    def critical(parent,title,text,*args,**kwargs):return W.QMessageBox.critical(parent,tr(title),tr(text),*args,**kwargs)
    @staticmethod
    def question(parent,title,text,*args,**kwargs):return W.QMessageBox.question(parent,tr(title),tr(text),*args,**kwargs)


class QFileDialog(W.QFileDialog):
    @staticmethod
    def getOpenFileName(parent=None,caption='',directory='',filter='',*args,**kwargs):return W.QFileDialog.getOpenFileName(parent,tr(caption),directory,tr(filter),*args,**kwargs)
    @staticmethod
    def getSaveFileName(parent=None,caption='',directory='',filter='',*args,**kwargs):return W.QFileDialog.getSaveFileName(parent,tr(caption),directory,tr(filter),*args,**kwargs)
    @staticmethod
    def getExistingDirectory(parent=None,caption='',directory='',*args,**kwargs):return W.QFileDialog.getExistingDirectory(parent,tr(caption),directory,*args,**kwargs)


class QInputDialog(W.QInputDialog):
    @staticmethod
    def getText(parent,title,label,*args,**kwargs):return W.QInputDialog.getText(parent,tr(title),tr(label),*args,**kwargs)


class QColorDialog(W.QColorDialog):
    @staticmethod
    def getColor(*args,**kwargs):
        if len(args)>=3:args=(*args[:2],tr(args[2]),*args[3:])
        return W.QColorDialog.getColor(*args,**kwargs)


def language_menu(window):
    from PySide6.QtGui import QActionGroup
    from .i18n import language,set_language
    menu=window.menuBar().addMenu('语言 / Language');group=QActionGroup(window);group.setExclusive(True)
    actions={}
    for code,title in [('zh','简体中文'),('en','English')]:
        action=menu.addAction(title);action.setCheckable(True);action.setChecked(language()==code);group.addAction(action)
        def select(checked,code=code):
            if checked:
                try:set_language(code,persist=True)
                except OSError as error:
                    for name,entry in actions.items():entry.setChecked(name==language())
                    QMessageBox.warning(window,'语言设置未保存',str(error))
        action.triggered.connect(select);actions[code]=action
    window._language_actions=actions;window._language_group=group
    return menu


class QtLanguageController:
    """Also translate Qt's standard buttons when its bundled catalog is available."""
    def __init__(self,application):
        from PySide6.QtCore import QTranslator
        from .i18n import listen
        self.application=application;self.translator=QTranslator(application)
        listen(self.update);self.update()
    def update(self):
        from PySide6.QtCore import QLibraryInfo
        from .i18n import language
        self.application.removeTranslator(self.translator)
        if language()=='zh' and self.translator.load('qtbase_zh_CN',QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)):
            self.application.installTranslator(self.translator)
