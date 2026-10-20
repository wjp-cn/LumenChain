import json, copy, threading, os
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon
from PySide6.QtWidgets import *
from app.models.profile import Application, Profile, now
from app.core.scheduler import Scheduler
from app.ui.application_dialog import ApplicationDialog
from app.ui.settings_dialog import SettingsDialog

class Bridge(QObject):
    event=Signal(str,str,str)
class ApplicationList(QListWidget):
    reordered=Signal()
    filesDropped=Signal(list)

    @staticmethod
    def local_applications(mime):
        if not mime.hasUrls():
            return []
        return [url.toLocalFile() for url in mime.urls()
                if url.isLocalFile() and Path(url.toLocalFile()).is_file()
                and Path(url.toLocalFile()).suffix.lower() in (".exe", ".lnk", ".bat", ".cmd")]

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls():
            if self.local_applications(event.mimeData()):
                event.setDropAction(Qt.CopyAction)
                event.accept()
            else:
                event.ignore()
            return
        super().dragEnterEvent(event)

    def dragMoveEvent(self,event):
        if event.mimeData().hasUrls():
            if self.local_applications(event.mimeData()):
                event.setDropAction(Qt.CopyAction)
                event.accept()
            else:
                event.ignore()
            return
        super().dragMoveEvent(event)

    def dropEvent(self,event):
        if event.mimeData().hasUrls():
            paths=self.local_applications(event.mimeData())
            if paths:
                event.setDropAction(Qt.CopyAction)
                event.accept()
                self.filesDropped.emit(paths)
            else:
                event.ignore()
            return
        super().dropEvent(event)
        if event.isAccepted():
            self.reordered.emit()

class MainWindow(QMainWindow):
    def __init__(self,config):
        super().__init__(); self.config=config; self.setWindowTitle("光启 LumenChain"); self.resize(1080,720); self.setMinimumSize(850,560)
        self.bridge=Bridge(); self.bridge.event.connect(self.on_scheduler_event); self.scheduler=Scheduler(self.bridge.event.emit); self.thread=None; self.exiting=False; self.pending=False; self.pending_token=0
        self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        root=QWidget(); self.setCentralWidget(root); outer=QHBoxLayout(root)
        sidebar=QVBoxLayout(); outer.addLayout(sidebar,1); sidebar.addWidget(QLabel("光启 LumenChain\n一次编排，一键启动。")); self.profiles=QListWidget(); sidebar.addWidget(self.profiles)
        self.profiles.currentRowChanged.connect(self.render)
        for label,fn in (("＋ 新建方案",self.new_profile),("设置",self.settings)):
            b=QPushButton(label); b.clicked.connect(fn); sidebar.addWidget(b)
        work=QVBoxLayout(); outer.addLayout(work,4); self.title=QLabel(); self.title.setObjectName("title"); work.addWidget(self.title); self.description=QLabel(); work.addWidget(self.description)
        row=QHBoxLayout(); work.addLayout(row)
        for label,fn in (("添加软件",self.add_app),("方案操作",self.profile_menu),("数据管理",self.data_menu)):
            b=QPushButton(label); b.clicked.connect(fn); row.addWidget(b)
        self.apps=ApplicationList(); self.apps.setDragDropMode(QAbstractItemView.DragDrop); self.apps.setDefaultDropAction(Qt.MoveAction); self.apps.setDropIndicatorShown(True); self.apps.filesDropped.connect(self.add_dropped_apps); self.apps.reordered.connect(self.reorder); self.apps.itemDoubleClicked.connect(lambda _:self.edit_app()); self.apps.setContextMenuPolicy(Qt.CustomContextMenu); self.apps.customContextMenuRequested.connect(self.app_menu); work.addWidget(self.apps)
        self.apps.setToolTip("将桌面或资源管理器中的 EXE、LNK、BAT、CMD 拖入此处添加；列表内拖动可调整顺序。")
        self.status=QLabel("创建方案并添加软件，即可一键启动。"); self.status.setWordWrap(True); work.addWidget(self.status); self.progress=QProgressBar(); self.progress.setRange(0,1); self.progress.setValue(0); work.addWidget(self.progress)
        buttons=QHBoxLayout(); work.addLayout(buttons)
        for label,fn in (("一键启动",lambda:self.start(self.selected())),("停止启动",self.cancel),("查看日志",self.logs)):
            b=QPushButton(label); b.clicked.connect(fn); buttons.addWidget(b)
        self.tray=QSystemTrayIcon(self.windowIcon(),self); self.tray.activated.connect(lambda reason:self.reveal() if reason in (QSystemTrayIcon.DoubleClick,QSystemTrayIcon.Trigger) else None)
        self.tray.setToolTip("光启 LumenChain"); self.tray.show(); self.refresh(); self.theme()
        QApplication.styleHints().colorSchemeChanged.connect(lambda _:self.theme())
    def selected(self):
        row=self.profiles.currentRow(); return self.config.profiles[row] if 0<=row<len(self.config.profiles) else None
    def save(self):
        try: self.config.save(); return True
        except Exception as e: QMessageBox.warning(self,"保存失败",str(e)); return False
    def refresh(self,selected=None):
        selected=selected or (self.selected().id if self.selected() else None)
        self.profiles.blockSignals(True); self.profiles.clear()
        for p in self.config.profiles: self.profiles.addItem(p.name)
        index=next((i for i,p in enumerate(self.config.profiles) if p.id==selected),0)
        self.profiles.setCurrentRow(index); self.profiles.blockSignals(False); self.render(); self.tray_menu()
    def render(self,*_):
        p=self.selected(); self.apps.clear()
        self.title.setText(p.name if p else "还没有启动方案")
        self.description.setText((p.description + f" · {len(p.applications)} 个软件 · 拖入应用添加 / ≡ 拖拽排序 / 右键操作") if p else "创建启动方案，或将应用快捷方式拖入下方列表开始添加。")
        if p:
            for a in p.applications:
                strategy={"immediate":"立即继续","delay":f"延迟 {a.delay_seconds:g} 秒","ready":"等待就绪 · "+a.readiness["kind"]}[a.launch_strategy]
                text=f"≡  {a.name}     {'已启用' if a.enabled else '已禁用'}\n      {strategy}" + (" · 路径无效" if not Path(os.path.expandvars(a.path)).is_file() else "")
                item=QListWidgetItem(text); item.setData(Qt.UserRole,a.id); item.setToolTip(a.name+"\n"+a.path)
                from PySide6.QtCore import QFileInfo
                item.setIcon(QFileIconProvider().icon(QFileInfo(a.path))); self.apps.addItem(item)
            if not p.applications: self.description.setText("将应用图标拖入下方列表，或点击“添加软件”；支持 EXE、LNK、BAT、CMD。")
    def new_profile(self):
        name,ok=QInputDialog.getText(self,"新建方案","方案名称")
        if ok and name.strip():
            p=Profile(name.strip()); self.config.profiles.append(p); self.save(); self.refresh(p.id)
    def profile_menu(self):
        p=self.selected()
        if not p:return
        menu=QMenu(self)
        for text,fn in (("修改名称和描述",self.rename),("复制方案",self.clone),("设为默认方案",self.set_default),("删除方案",self.delete_profile)):
            menu.addAction(text,fn)
        menu.exec(self.cursor().pos())
    def rename(self):
        p=self.selected(); name,ok=QInputDialog.getText(self,"重命名方案","名称",text=p.name)
        if ok and name.strip():
            desc,ok=QInputDialog.getText(self,"方案描述","描述",text=p.description)
            if ok:p.name=name.strip(); p.description=desc; p.modified_at=now(); self.save(); self.refresh(p.id)
    def clone(self):
        p=self.selected().clone(); self.config.profiles.append(p); self.save(); self.refresh(p.id)
    def set_default(self): self.config.settings["default_profile"]=self.selected().id; self.save()
    def confirm(self,text): return QMessageBox.question(self,"请确认",text,QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes
    def delete_profile(self):
        p=self.selected()
        if self.confirm("删除方案“"+p.name+"”？"):
            self.config.profiles.remove(p)
            if self.config.settings["default_profile"]==p.id:self.config.settings["default_profile"]=""; self.config.settings["auto_run"]=False
            self.save(); self.refresh()
    def add_app(self):
        p=self.selected()
        if not p:self.new_profile(); p=self.selected()
        if not p:return
        dialog=ApplicationDialog(self,settings=self.config.settings)
        if dialog.exec():
            p.applications.append(dialog.application); p.modified_at=now(); self.save(); self.render(); self.apps.setCurrentRow(self.apps.count()-1); self.apps.scrollToBottom(); self.apps.currentItem().setBackground(__import__("PySide6.QtGui",fromlist=["QColor"]).QColor("#d4e5ff")); QTimer.singleShot(1600,self.render)

    def add_dropped_apps(self,paths):
        profile=self.selected()
        if profile is None:
            self.new_profile()
            profile=self.selected()
        if profile is None:
            return
        settings=self.config.settings
        existing={os.path.normcase(os.path.realpath(os.path.expandvars(a.path))) for a in profile.applications}
        added=[]
        skipped=0
        for filename in paths:
            path=Path(filename)
            normalized=os.path.normcase(os.path.realpath(filename))
            if not path.is_file() or path.suffix.lower() not in (".exe", ".lnk", ".bat", ".cmd") or normalized in existing:
                skipped+=1
                continue
            application=Application(
                path.stem, str(path),
                working_directory="" if path.suffix.lower()==".lnk" else str(path.parent),
                delay_seconds=settings["default_delay"],
                skip_if_running=settings["default_skip"],
                failure_action=settings["default_failure"],
                retry_count=settings["default_retry"],
            )
            application.readiness["timeout"]=settings["default_timeout"]
            application.validate()
            added.append(application)
            existing.add(normalized)
        if added:
            previous_modified=profile.modified_at
            profile.applications.extend(added)
            profile.modified_at=now()
            if not self.save():
                del profile.applications[-len(added):]
                profile.modified_at=previous_modified
                return
            self.render()
            self.apps.setCurrentRow(self.apps.count()-1)
            self.apps.scrollToBottom()
        message=f"已添加 {len(added)} 个应用"
        if skipped:
            message+=f"，跳过 {skipped} 个重复或无效文件"
        message+="；双击条目可编辑参数和启动策略。"
        if any(Path(a.path).suffix.lower() in (".bat", ".cmd") for a in added):
            message+=" BAT/CMD 会执行脚本，请仅启动可信文件。"
        if self.scheduler.active is not None:
            message+=" 当前启动使用原有快照，新增项下次生效。"
        self.status.setText(message)
    def app(self):
        p=self.selected(); row=self.apps.currentRow()
        return p.applications[row] if p and 0<=row<len(p.applications) else None
    def edit_app(self):
        a=self.app()
        if not a:return
        d=ApplicationDialog(self,a)
        if d.exec():self.selected().applications[self.apps.currentRow()]=d.application; self.save(); self.render()
    def app_menu(self,pos):
        item=self.apps.itemAt(pos)
        if not item:return
        self.apps.setCurrentItem(item); menu=QMenu(self)
        for label,fn in (("编辑配置",self.edit_app),("单独启动",self.single),("上移",lambda:self.move(-1)),("下移",lambda:self.move(1)),("启用 / 禁用",self.toggle),("删除",self.delete_app)):
            menu.addAction(label,fn)
        menu.exec(self.apps.mapToGlobal(pos))
    def single(self):
        a=self.app()
        if a:
            if not a.enabled:self.status.setText("此软件已禁用，请先启用。");return
            self.start(Profile("单独启动："+a.name,applications=[a]))
    def move(self,delta):
        p=self.selected(); i=self.apps.currentRow(); j=i+delta
        if 0<=j<len(p.applications):p.applications[i],p.applications[j]=p.applications[j],p.applications[i]; self.save(); self.render(); self.apps.setCurrentRow(j)
    def reorder(self):
        p=self.selected()
        if p:
            lookup={a.id:a for a in p.applications}; p.applications=[lookup[self.apps.item(i).data(Qt.UserRole)] for i in range(self.apps.count())]; p.modified_at=now(); self.save()
    def toggle(self):
        a=self.app()
        if a:a.enabled=not a.enabled;self.save();self.render()
    def delete_app(self):
        a=self.app()
        if a and self.confirm("删除软件“"+a.name+"”？"):self.selected().applications.remove(a);self.save();self.render()
    def start(self,profile,scheduled=False):
        if not profile:self.status.setText("请先选择有效方案。");self.reveal();return
        if self.pending and not scheduled:self.status.setText("开机方案已在倒计时，点击停止启动可取消。");self.reveal();return
        if self.thread and self.thread.is_alive():self.status.setText("当前已有方案正在启动，请查看当前进度。");self.reveal();return
        snapshot=self.scheduler.reserve(profile)
        if snapshot is None:self.status.setText("当前已有方案正在启动。");self.reveal();return
        self.progress.setRange(0,max(1,sum(a.enabled for a in snapshot.applications)));self.progress.setValue(0)
        self.status.setText("正在启动："+snapshot.name+"；编辑仅在下次启动生效。")
        self.thread=threading.Thread(target=self.scheduler.run,args=(snapshot,),daemon=False);self.thread.start()
    def cancel(self):self.pending=False;self.pending_token+=1;self.scheduler.cancel();self.status.setText("已请求停止；已启动的软件保持运行。")
    def on_scheduler_event(self,kind,identifier,text):
        if kind in ("countdown","finished"):self.status.setText(text)
        elif kind=="state":
            self.status.setText(text)
            for i in range(self.apps.count()):
                item=self.apps.item(i)
                if item.data(Qt.UserRole)==identifier:
                    a=next((a for a in self.selected().applications if a.id==identifier),None)
                    if a:item.setText(f"≡  {a.name}\n      {text}")
        elif kind=="progress":self.progress.setRange(0,max(1,int(text)));self.progress.setValue(int(identifier))
        if kind=="finished" and self.exiting:self.wait_exit()
    def tray_menu(self):
        menu=QMenu();menu.addAction("打开主界面",self.reveal);menu.addSeparator()
        for p in self.config.profiles:menu.addAction("启动："+p.name,lambda checked=False,pid=p.id:self.start(next((p for p in self.config.profiles if p.id==pid),None)))
        menu.addSeparator();menu.addAction("退出",self.quit);self.tray.setContextMenu(menu);self.traymenu=menu
    def reveal(self):self.showNormal();self.raise_();self.activateWindow()
    def quit(self):
        self.exiting=True;self.pending=False;self.scheduler.cancel();self.hide();self.wait_exit()
    def wait_exit(self):
        if self.thread and self.thread.is_alive():QTimer.singleShot(100,self.wait_exit)
        else:self.tray.hide();QApplication.quit()
    def closeEvent(self,event):
        event.ignore()
        if self.config.settings["close_to_tray"] and QSystemTrayIcon.isSystemTrayAvailable():
            if not self.config.settings["tray_notice"]:
                QMessageBox.information(self,"仍在托盘运行","关闭窗口后程序仍在系统托盘运行。点击托盘图标恢复窗口，托盘菜单中可退出。");self.config.settings["tray_notice"]=True;self.save()
            self.hide()
        else:self.quit()
    def changeEvent(self,event):
        from PySide6.QtCore import QEvent
        if event.type()==QEvent.WindowStateChange and self.isMinimized() and QSystemTrayIcon.isSystemTrayAvailable():QTimer.singleShot(0,self.hide)
        super().changeEvent(event)
    def settings(self):
        if SettingsDialog(self,self.config).exec():self.theme()
    def theme(self):
        from PySide6.QtCore import Qt
        dark=self.config.settings["theme"]=="dark" or (self.config.settings["theme"]=="system" and QApplication.styleHints().colorScheme()==Qt.ColorScheme.Dark)
        bg,card,fg,border=("#191c22","#252a33","#eef2f9","#414955") if dark else ("#f3f5f9","#ffffff","#202b3b","#dce2ec")
        self.setStyleSheet(f"QWidget {{font-family:'Microsoft YaHei','Segoe UI';font-size:13px;color:{fg};}} QMainWindow,QDialog {{background:{bg};}} QListWidget,QLineEdit,QSpinBox,QDoubleSpinBox,QComboBox,QTextEdit {{background:{card};border:1px solid {border};border-radius:7px;padding:7px;}} QListWidget::item {{padding:12px;border-bottom:1px solid {border};}} QListWidget::item:selected {{background:#d4e5ff;color:#132e52;}} QPushButton {{background:#246bce;color:white;border:0;border-radius:6px;padding:9px 15px;}} QPushButton:hover {{background:#3980e5;}} QLabel#title {{font-size:25px;font-weight:600;}} QProgressBar {{border:1px solid {border};border-radius:5px;text-align:center;}} QProgressBar::chunk {{background:#357bda;}}")
    def data_menu(self):
        m=QMenu(self)
        for text,fn in (("导入方案",self.import_data),("导出方案",self.export_data),("打开配置目录",lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config.root)))),("打开日志目录",lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.config.root/"logs"))))):m.addAction(text,fn)
        m.exec(self.cursor().pos())
    def export_data(self):
        path,_=QFileDialog.getSaveFileName(self,"导出方案","LaunchFlow-profiles.json","JSON (*.json)")
        if path:
            try:Path(path).write_text(json.dumps(dict(schema_version=1,profiles=[p.to_dict() for p in self.config.profiles]),ensure_ascii=False,indent=2),encoding="utf-8")
            except OSError as e:QMessageBox.warning(self,"导出失败",str(e))
    def import_data(self):
        path,_=QFileDialog.getOpenFileName(self,"导入方案","","JSON (*.json)")
        if not path:return
        try:
            incoming=self.config.parse(json.loads(Path(path).read_text(encoding="utf-8")))
            preview="\n".join(f"{p.name}：{len(p.applications)} 个软件" for p in incoming)
            mode,ok=QInputDialog.getItem(self,"导入预览",preview+"\n导入不会执行程序或修改开机设置。",["新增方案（生成新 ID）","覆盖同 ID 方案"],0,False)
            if not ok:return
            if mode.startswith("覆盖") and not self.confirm("确定覆盖同 ID 方案？"):return
            for p in incoming:
                if mode.startswith("新增"):
                    name=p.name;p=p.clone();p.name=name;self.config.profiles.append(p)
                else:
                    i=next((i for i,q in enumerate(self.config.profiles) if q.id==p.id),None)
                    if i is None:self.config.profiles.append(p)
                    else:self.config.profiles[i]=p
            self.save();self.refresh()
        except Exception as e:QMessageBox.warning(self,"导入失败",str(e))
    def logs(self):
        d=QDialog(self);d.setWindowTitle("运行日志");d.resize(850,550);l=QVBoxLayout(d);search=QLineEdit();search.setPlaceholderText("输入方案名、批次或关键字过滤");l.addWidget(search);text=QTextEdit();text.setReadOnly(True);l.addWidget(text)
        def read():
            lines=[]
            for p in sorted((self.config.root/"logs").glob("*.log*"),key=lambda p:p.stat().st_mtime):lines.extend(p.read_text(encoding="utf-8",errors="replace").splitlines())
            return "\n".join(line for line in lines if search.text().casefold() in line.casefold())
        def refresh():text.setPlainText(read())
        def export():
            path,_=QFileDialog.getSaveFileName(d,"导出日志","launchflow.log")
            if path:Path(path).write_text(text.toPlainText(),encoding="utf-8")
        def clear():
            if self.confirm("清空历史日志？"):
                import logging
                for handler in logging.getLogger("LaunchFlow").handlers:
                    handler.acquire()
                    try:
                        handler.close()
                        for p in (self.config.root/"logs").glob("*.log*"):p.unlink(missing_ok=True)
                    finally:handler.release()
                refresh()
        row=QHBoxLayout();l.addLayout(row)
        for title,fn in (("刷新",refresh),("复制",lambda:QApplication.clipboard().setText(text.toPlainText())),("导出",export),("清空历史",clear)):
            b=QPushButton(title);b.clicked.connect(fn);row.addWidget(b)
        search.textChanged.connect(refresh);refresh();d.exec()
