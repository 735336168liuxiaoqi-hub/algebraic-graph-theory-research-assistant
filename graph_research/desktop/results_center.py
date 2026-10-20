"""Native result collections, previewed cleanup and a reversible recycle view."""
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject,QThread,Signal,Qt,QUrl,QItemSelectionModel
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QPushButton,QLineEdit,QComboBox,QTableWidget,QTableWidgetItem,
    QHeaderView,QAbstractItemView,QMessageBox,QFileDialog,QFormLayout,QCheckBox,QTreeWidget,QTreeWidgetItem,QDialogButtonBox,QApplication,QLabel)
from graph_research.assistant.result_catalog import ResultCatalog,resolve_bundle
from graph_research.assistant.result_cleanup import ResultCleanup
from graph_research.runtime.storage import read_json,write_json,exclusive_lock
from .app import label

MODES={'offline':'本地工具','api':'科研对话','mcp':'主agent任务'}
CLEANUP_MODES={'temporary':'临时文件','old_auto':'旧自动包','task':'整个任务'}


class ResultEvents(QObject):
    changed=Signal()


RESULT_EVENTS=ResultEvents()


def size_text(value):
    if value<1024:return str(value)+' B'
    if value<1024**2:return f'{value/1024:.1f} KiB'
    if value<1024**3:return f'{value/1024**2:.1f} MiB'
    return f'{value/1024**3:.2f} GiB'


def collect_sources(preferences):
    rows=[]
    for root in preferences.read()['roots']:
        catalog=ResultCatalog(root)
        if catalog.database.is_file():rows.extend(catalog.list_sources())
    return sorted(rows,key=lambda row:row['updated'],reverse=True)


class CenterWorker(QObject):
    done=Signal(object)
    def __init__(self,function):super().__init__();self.function=function
    def run(self):
        try:self.done.emit({'ok':True,'value':self.function()})
        except Exception as error:self.done.emit({'ok':False,'error':str(error)})


class CleanupPreview(QDialog):
    def __init__(self,result,mode,parent=None):
        super().__init__(parent);self.setWindowTitle('清理预览');self.resize(740,500);self.result=result
        layout=QVBoxLayout(self)
        layout.addWidget(label('清理'+CLEANUP_MODES[mode],'title'))
        plans=[plan for group in result for plan in group['preview']['plans']]
        blocked=[item for group in result for item in group['preview']['blocked']]
        total=sum(plan['bytes'] for plan in plans);files=sum(plan['files'] for plan in plans)
        layout.addWidget(label(f'将回收 {len(plans)} 项成果中的 {files} 个文件，合计 {size_text(total)}。'))
        description={'temporary':'保留计算回执、原始结果和科学附件。','old_auto':'只处理未被任务回执引用的旧自动包；手动快照保留。',
            'task':'任务文件移入回收区后不能继续计算；任务编号与已用预算仍保留，重复请求不会重算。'}[mode]
        layout.addWidget(label(description,'muted'))
        tree=QTreeWidget();tree.setHeaderLabels(['范围','体积 / 原因']);layout.addWidget(tree,1)
        for plan in plans:
            item=QTreeWidgetItem([plan['source']['title'],size_text(plan['bytes'])]);tree.addTopLevelItem(item)
            for move in plan['moves']:
                amount=sum(value.get('bytes',0) for value in move['inventory']);child=QTreeWidgetItem([Path(move['source']).name,size_text(amount)])
                child.setToolTip(0,move['source']);item.addChild(child)
        if blocked:
            item=QTreeWidgetItem(['本次保留','']);tree.addTopLevelItem(item);item.setExpanded(True)
            for entry in blocked:item.addChild(QTreeWidgetItem([entry['title'],entry['reason']]))
        tree.header().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        layout.addWidget(label('回收后可撤销；实际释放磁盘空间需要再清空回收区。','muted'))
        buttons=QDialogButtonBox();cancel=buttons.addButton('取消',QDialogButtonBox.ButtonRole.RejectRole);cancel.clicked.connect(self.reject)
        confirm=buttons.addButton('确认回收',QDialogButtonBox.ButtonRole.AcceptRole);confirm.setObjectName('stop');confirm.setEnabled(bool(plans));confirm.clicked.connect(self.accept);layout.addWidget(buttons)


class ResultsCenter(QDialog):
    changed=Signal()
    def __init__(self,workspace,parent=None):
        super().__init__(parent);self.workspace=workspace;self.preferences=workspace.results_preferences;self.thread=None;self.worker=None;self.after=None;self.response=None;self.rows=[]
        self.setWindowTitle('成果中心');screen=QApplication.primaryScreen().availableGeometry();self.resize(min(1060,screen.width()-50),min(760,screen.height()-70))
        self.changed.connect(RESULT_EVENTS.changed.emit)
        outer=QVBoxLayout(self);header=QHBoxLayout();header.addWidget(label('成果中心','title'));header.addStretch()
        self.location=QPushButton('保存位置');self.location.setToolTip('新会话使用新位置；已有成果保留原位置，MCP服务重连后生效。');self.location.clicked.connect(self.choose_directory);header.addWidget(self.location);outer.addLayout(header)
        self.directory_label=label(str(self.preferences.active),'muted');outer.addWidget(self.directory_label)
        row=QHBoxLayout();self.search=QLineEdit();self.search.setPlaceholderText('搜索成果名称、课题或编号');self.search.textChanged.connect(self.render);row.addWidget(self.search,1)
        self.mode=QComboBox();self.mode.addItem('全部来源',None)
        for key,value in MODES.items():self.mode.addItem(value,key)
        self.mode.currentIndexChanged.connect(self.render);row.addWidget(self.mode)
        self.only_pinned=QCheckBox('只看保留');self.only_pinned.toggled.connect(self.render);row.addWidget(self.only_pinned)
        self.refresh_button=QPushButton('刷新');self.refresh_button.clicked.connect(self.refresh);row.addWidget(self.refresh_button);outer.addLayout(row)
        self.table=QTableWidget(0,7);self.table.setHorizontalHeaderLabels(['成果名称','课题','来源','更新时间','包大小','状态','保留'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers);self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
        for i in range(1,7):self.table.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemDoubleClicked.connect(lambda item:self.open_result());self.table.itemSelectionChanged.connect(self.selection_changed);outer.addWidget(self.table,1)
        self.detail=label('计算完成后，成果会自动显示在这里。','muted');outer.addWidget(self.detail)
        self.feedback=label('','muted');outer.addWidget(self.feedback)
        first=QHBoxLayout();self.import_button=QPushButton('导入旧成果');self.import_button.clicked.connect(self.import_legacy);first.addWidget(self.import_button)
        self.recycle_button=QPushButton('回收区');self.recycle_button.clicked.connect(self.open_recycle);first.addWidget(self.recycle_button);first.addStretch()
        self.rename_button=QPushButton('名称与课题');self.rename_button.clicked.connect(self.rename_result);first.addWidget(self.rename_button)
        self.pin_button=QPushButton('标记保留');self.pin_button.clicked.connect(self.toggle_pin);first.addWidget(self.pin_button)
        self.cleanup_button=QPushButton('清理');self.cleanup_button.setObjectName('stop');self.cleanup_button.clicked.connect(self.choose_cleanup);first.addWidget(self.cleanup_button);outer.addLayout(first)
        row=QHBoxLayout();self.close_button=QPushButton('关闭');self.close_button.clicked.connect(self.reject);row.addWidget(self.close_button);row.addStretch()
        self.snapshot_button=QPushButton('保存快照');self.snapshot_button.clicked.connect(self.snapshot);row.addWidget(self.snapshot_button)
        self.versions_button=QPushButton('历史版本');self.versions_button.clicked.connect(self.open_versions);row.addWidget(self.versions_button)
        self.folder_button=QPushButton('所在文件夹');self.folder_button.clicked.connect(self.open_folder);row.addWidget(self.folder_button)
        self.open_button=QPushButton('打开成果');self.open_button.setObjectName('primary');self.open_button.clicked.connect(self.open_result);row.addWidget(self.open_button);outer.addLayout(row)
        self.refresh()

    def start(self,function,after=None,message='正在处理…'):
        if self.thread is not None:return
        self.after=after;self.response=None;self.thread=QThread(self);self.worker=CenterWorker(function);self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run);self.worker.done.connect(self.receive);self.worker.done.connect(self.thread.quit);self.worker.done.connect(self.worker.deleteLater);self.thread.finished.connect(self.worker_finished)
        self.feedback.setText(message);self.controls(False);self.thread.start()

    def receive(self,result):self.response=result

    def worker_finished(self):
        thread=self.thread;self.thread=None;self.worker=None;thread.deleteLater();self.controls(True);result=self.response;after=self.after;self.after=None
        if not result or not result['ok']:self.feedback.setText((result or {}).get('error','操作未完成。'));return
        self.feedback.setText('');
        if after:after(result['value'])

    def controls(self,enabled):
        for widget in (self.location,self.refresh_button,self.import_button,self.recycle_button,self.rename_button,self.pin_button,self.cleanup_button,self.close_button,self.snapshot_button,self.versions_button,self.folder_button,self.open_button):widget.setEnabled(enabled)
        if enabled:self.selection_changed()

    def refresh(self):self.start(lambda:collect_sources(self.preferences),self.loaded,'正在读取成果索引…')

    def loaded(self,rows):self.rows=rows;self.render()

    def render(self,*args):
        selected={(r['results_root'],r['id']) for r in self.selected()};needle=self.search.text().strip().lower();mode=self.mode.currentData()
        rows=[r for r in self.rows if r['state']=='ready' and (not mode or r['mode']==mode) and (not self.only_pinned.isChecked() or r['pinned'])
              and (not needle or needle in (r['title']+' '+r['project']+' '+r['id']).lower())]
        self.table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            bundle=row.get('latest_bundle') or {};availability=bundle.get('availability','missing')
            values=[row['title'],row['project'],MODES.get(row['mode'],row['mode']),datetime.fromtimestamp(row['updated']).strftime('%m-%d %H:%M'),size_text(row['bytes']),
                    '已保存' if availability=='ready' else '文件不可用','是' if row['pinned'] else '']
            for j,value in enumerate(values):
                item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,row);item.setToolTip('成果编号：'+row['id']+'\n'+str(bundle.get('archive','')));self.table.setItem(i,j,item)
            if (row['results_root'],row['id']) in selected:self.table.selectionModel().select(self.table.model().index(i,0),QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Rows)
        self.selection_changed()

    def selected(self):
        return [self.table.item(index.row(),0).data(Qt.ItemDataRole.UserRole) for index in self.table.selectionModel().selectedRows() if self.table.item(index.row(),0)]

    def selection_changed(self):
        if not hasattr(self,'open_button'):return
        rows=self.selected();single=len(rows)==1;busy=self.thread is not None
        for widget in (self.open_button,self.folder_button,self.rename_button,self.snapshot_button,self.versions_button):widget.setEnabled(single and not busy)
        for widget in (self.pin_button,self.cleanup_button):widget.setEnabled(bool(rows) and not busy)
        self.pin_button.setText('取消保留' if rows and all(r['pinned'] for r in rows) else '标记保留')
        if single:
            bundle=rows[0].get('latest_bundle') or {};self.detail.setText(str(bundle.get('archive') or '尚无可用成果包'));self.detail.setToolTip('成果编号：'+rows[0]['id'])
        else:self.detail.setText(f'已选择 {len(rows)} 项成果' if rows else '选择成果可打开、归类、保留或清理。')

    def changed_refresh(self,*args):self.changed.emit();self.refresh()

    def open_result(self):
        rows=self.selected()
        if len(rows)!=1:return
        row=rows[0]
        def verify():
            from graph_research.assistant.results import verify_bundle
            catalog=ResultCatalog(row['results_root']);bundle=catalog.resolve(catalog.source(row['id'])['latest'])
            if bundle.get('availability')!='ready':raise ValueError('成果包当前不可用，可在回收区查看。')
            verify_bundle(bundle['archive'],bundle['sha256']);return bundle['archive']
        self.start(verify,lambda path:QDesktopServices.openUrl(QUrl.fromLocalFile(path)),'正在核验成果包…')

    def open_folder(self):
        rows=self.selected();archive=(rows[0].get('latest_bundle') or {}).get('archive') if len(rows)==1 else None
        directory=Path(archive).parent if archive else Path(rows[0]['results_root']) if rows else self.preferences.active
        if not directory.is_dir():self.feedback.setText('目录已不存在，请刷新成果索引。');return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def open_versions(self):
        rows=self.selected()
        if len(rows)!=1:return
        row=rows[0]
        self.start(lambda:ResultCatalog(row['results_root']).list_versions(row['id']),self.show_versions,'正在读取历史版本…')

    def show_versions(self,rows):
        rows=[row for row in rows if row.get('availability')=='ready']
        dialog=QDialog(self);dialog.setWindowTitle('历史版本');dialog.resize(860,420);layout=QVBoxLayout(dialog)
        layout.addWidget(label('历史版本','title'));layout.addWidget(label('手动快照与被宿主回执引用的版本保留；已替代的普通自动包不在此列。','muted'))
        table=QTableWidget(len(rows),3);table.setHorizontalHeaderLabels(['文件名','类型','版本编号']);table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection);table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i,row in enumerate(rows):
            values=[Path(row['archive']).name,'自动成果' if row['automatic'] else '手动快照',row['artifact_id']]
            for j,value in enumerate(values):item=QTableWidgetItem(value);item.setToolTip(row['archive']);item.setData(Qt.ItemDataRole.UserRole,row);table.setItem(i,j,item)
        table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch);layout.addWidget(table,1)
        buttons=QHBoxLayout();close=QPushButton('关闭');close.clicked.connect(dialog.reject);buttons.addWidget(close);buttons.addStretch();opened=QPushButton('核验并打开');opened.setObjectName('primary');buttons.addWidget(opened);layout.addLayout(buttons)
        def open_selected():
            selected=table.selectionModel().selectedRows()
            if not selected:return
            bundle=table.item(selected[0].row(),0).data(Qt.ItemDataRole.UserRole);dialog.accept()
            def verify():
                from graph_research.assistant.results import verify_bundle
                located=ResultCatalog(bundle['results_root']).resolve(bundle['artifact_id'],expected_sha256=bundle['sha256'])
                if located.get('availability')!='ready':raise ValueError('该版本当前不可用，请刷新。')
                verify_bundle(located['archive'],located['sha256']);return located['archive']
            self.start(verify,lambda path:QDesktopServices.openUrl(QUrl.fromLocalFile(path)),'正在核验历史成果…')
        opened.clicked.connect(open_selected);dialog.exec()

    def choose_directory(self):
        path=QFileDialog.getExistingDirectory(self,'新会话的成果保存位置',str(self.preferences.active))
        if not path:return
        try:self.preferences.select(path);self.directory_label.setText(str(self.preferences.active));self.feedback.setText('新会话使用此目录；已有成果保留原位置。MCP重连后使用新设置。');self.refresh()
        except (OSError,ValueError) as error:self.feedback.setText(str(error))

    def rename_result(self):
        rows=self.selected()
        if len(rows)!=1:return
        row=rows[0];dialog=QDialog(self);dialog.setWindowTitle('成果名称与课题');layout=QVBoxLayout(dialog);form=QFormLayout();name=QLineEdit(row['title']);project=QLineEdit(row['project'])
        name.setMaxLength(26);project.setMaxLength(32);form.addRow('名称',name);form.addRow('课题',project);layout.addLayout(form)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()==QDialog.DialogCode.Accepted:
            title=name.text();topic=project.text();self.start(lambda:ResultCatalog(row['results_root']).rename(row['id'],title,topic),self.changed_refresh,'正在归类成果…')

    def toggle_pin(self):
        rows=self.selected();value=not all(r['pinned'] for r in rows)
        self.start(lambda:[ResultCatalog(r['results_root']).pin(r['id'],value) for r in rows],self.changed_refresh)

    def snapshot(self):
        rows=self.selected()
        if len(rows)!=1:return
        def export():
            from graph_research.assistant.session import ResearchSession
            return ResearchSession(rows[0]['directory']).export_results()
        self.start(export,self.changed_refresh,'正在保存独立快照…')

    def choose_cleanup(self):
        rows=self.selected()
        if not rows:return
        dialog=QDialog(self);dialog.setWindowTitle('清理范围');layout=QVBoxLayout(dialog);choice=QComboBox()
        for key,value in CLEANUP_MODES.items():choice.addItem(value,key)
        layout.addWidget(choice);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=QDialog.DialogCode.Accepted:return
        mode=choice.currentData()
        def preview():
            grouped={}
            for row in rows:grouped.setdefault(row['results_root'],[]).append(row['id'])
            return [{'root':root,'preview':ResultCleanup(ResultCatalog(root)).preview(ids,mode)} for root,ids in grouped.items()]
        self.start(preview,lambda result:self.review_cleanup(result,mode),'正在核对清理范围与可回收空间…')

    def review_cleanup(self,result,mode):
        dialog=CleanupPreview(result,mode,self)
        if dialog.exec()!=QDialog.DialogCode.Accepted:
            for group in result:ResultCleanup(ResultCatalog(group['root'])).discard_previews([p['id'] for p in group['preview']['plans']])
            return
        def apply():
            errors=[];done=0
            for group in result:
                cleaner=ResultCleanup(ResultCatalog(group['root']))
                for plan in group['preview']['plans']:
                    try:cleaner.apply(plan['id']);done+=1
                    except (OSError,ValueError,RuntimeError) as error:errors.append(plan['source']['title']+'：'+str(error))
            return {'done':done,'errors':errors}
        self.start(apply,self.cleaned,'正在移入回收区…')

    def cleaned(self,result):
        self.changed.emit();self.refresh()
        message='已回收'+str(result['done'])+'项，可在回收区撤销。'
        if result['errors']:message+='\n未完成：'+'\n'.join(result['errors'][:3])
        QMessageBox.information(self,'清理结果',message)

    def open_recycle(self):
        def collect():
            rows=[]
            for root in self.preferences.read()['roots']:
                catalog=ResultCatalog(root)
                if catalog.database.exists():rows.extend([{**r,'results_root':root} for r in ResultCleanup(catalog).list_operations()])
            return rows
        self.start(collect,self.show_recycle,'正在读取回收区…')

    def show_recycle(self,rows):
        dialog=QDialog(self);dialog.setWindowTitle('成果回收区');dialog.resize(820,460);layout=QVBoxLayout(dialog)
        layout.addWidget(label('回收区','title'));layout.addWidget(label('恢复不重新计算；永久清理后将无法撤销。','muted'))
        table=QTableWidget(len(rows),5);table.setHorizontalHeaderLabels(['成果','范围','回收时间','体积','状态']);table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for i,row in enumerate(rows):
            values=[row['source']['title'],CLEANUP_MODES[row['mode']],datetime.fromtimestamp(row['created']).strftime('%m-%d %H:%M'),size_text(row['bytes']),'待恢复操作' if row['state']=='moving' else '可恢复']
            for j,value in enumerate(values):item=QTableWidgetItem(value);item.setData(Qt.ItemDataRole.UserRole,row);table.setItem(i,j,item)
        table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch);layout.addWidget(table,1)
        def selected():return [table.item(i.row(),0).data(Qt.ItemDataRole.UserRole) for i in table.selectionModel().selectedRows()]
        row=QHBoxLayout();close=QPushButton('关闭');close.clicked.connect(dialog.reject);row.addWidget(close);row.addStretch()
        restore=QPushButton('恢复所选');row.addWidget(restore);purge=QPushButton('永久清理所选');purge.setObjectName('stop');row.addWidget(purge);layout.addLayout(row)
        def restore_selected():
            values=selected()
            if not values:return
            dialog.accept();self.start(lambda:[ResultCleanup(ResultCatalog(r['results_root'])).restore(r['id']) for r in values],self.changed_refresh,'正在恢复原文件…')
        def purge_selected():
            values=selected()
            if not values:return
            def preview():return [ResultCleanup(ResultCatalog(r['results_root'])).purge_preview(r['id']) for r in values]
            def review(previews):
                text='将永久清理 '+str(sum(p['files'] for p in previews))+' 个文件，释放约 '+size_text(sum(p['bytes'] for p in previews))+'。此操作无法撤销。'
                if QMessageBox.question(self,'永久清理预览',text)!=QMessageBox.StandardButton.Yes:return
                self.start(lambda:[ResultCleanup(ResultCatalog(r['results_root'])).purge(r['id']) for r in values],self.changed_refresh,'正在永久清理回收内容…')
            dialog.accept();self.start(preview,review,'正在核对永久清理范围…')
        restore.clicked.connect(restore_selected);purge.clicked.connect(purge_selected);dialog.exec()

    def import_legacy(self):
        directory=QFileDialog.getExistingDirectory(self,'选择旧会话或旧工作区',str(self.workspace.directory))
        if not directory:return
        def import_all():
            from graph_research.assistant.session import ResearchSession
            root=Path(directory);paths=[]
            if (root/'session.json').is_file():paths.append(root/'session.json')
            paths+=list(root.glob('session_*/session.json'))+list(root.glob('model/session_*/session.json'))+list(root.glob('users/*/tasks/*/session/session.json'))
            if len(paths)>2000:raise ValueError('会话过多，请分批选择旧目录。')
            count=0
            for path in dict.fromkeys(paths):
                document,_=read_json(path,max_bytes=16*1024*1024)
                if document.get('cleared') or not document.get('state'):continue
                with exclusive_lock(path.parent/'.session.lock'):
                    session=ResearchSession(path.parent);catalog=ResultCatalog(session.results_directory or self.preferences.active)
                    imported=catalog.import_legacy(session)
                    self.preferences.remember(catalog.root)
                    if imported:
                        document['exports']['results_root']=str(catalog.root)
                        document['exports']['mode']=session.results_mode
                        latest=document['exports'].get('latest')
                        if latest:document['exports']['latest']=resolve_bundle(latest,source_directory=path.parent,results_root=catalog.root)
                        write_json(path,document,backup=True);count+=len(imported)
            return count
        self.start(import_all,lambda count:self.imported(count),'正在核验和导入旧成果；原文件保留…')

    def imported(self,count):self.changed.emit();self.refresh();QMessageBox.information(self,'导入完成','已登记 '+str(count)+' 个成果包；原文件保留，可再通过清理预览处理旧任务。')

    def reject(self):
        if self.thread is not None:return
        super().reject()

    def closeEvent(self,event):
        if self.thread is not None:event.ignore()
        else:event.accept()
