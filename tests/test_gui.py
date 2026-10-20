import os, sys, subprocess, time
from pathlib import Path
import pytest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
PySide6=pytest.importorskip('PySide6')
from PySide6.QtWidgets import QApplication, QSystemTrayIcon
from PySide6.QtCore import QTimer
from app.ui.main_window import MainWindow
from app.ui.application_dialog import ApplicationDialog
from app.services.config_service import ConfigService
from app.models.profile import Profile, Application

@pytest.fixture(scope='module')
def qt():return QApplication.instance() or QApplication([])

@pytest.fixture
def window(qt,tmp_path):
    c=ConfigService(tmp_path);c.profiles=[Profile('开发环境',applications=[Application('测试应用','C:/不存在.exe')]),Profile('日常办公')]
    w=MainWindow(c);w.show();qt.processEvents();yield w
    w.cancel()
    if w.thread:w.thread.join(2)
    w.tray.hide();w.deleteLater();qt.processEvents()

def test_window_profile_switch_and_order(window,qt):
    assert window.title.text()=='开发环境';window.profiles.setCurrentRow(1);assert window.title.text()=='日常办公'
    window.profiles.setCurrentRow(0);p=window.selected();p.applications.append(Application('第二项','C:/第二.exe'));window.render();window.apps.setCurrentRow(1);window.move(-1)
    assert ConfigService(window.config.root).profiles[0].applications[0].name=='第二项'
    # Same persistence path as the real QListWidget drop callback.
    item=window.apps.takeItem(0);window.apps.insertItem(1,item);window.reorder()
    assert ConfigService(window.config.root).profiles[0].applications[0].name=='测试应用'

def test_dialog_and_theme(window):
    d=ApplicationDialog(window);d.fields['name'].setText('中文应用');d.fields['path'].setText('C:/中文 空格.exe');d.save();assert d.result()==1
    for theme in ('dark','system','light'):window.config.settings['theme']=theme;window.theme()

def test_background_responsive_and_conflicting_profiles(window,qt):
    from app.core.launcher import Target
    window.scheduler.resolve=lambda a:Target(a.path);window.scheduler.monitor=lambda **k:([],False);window.scheduler.launch=lambda t:None
    p=window.selected();p.applications[0].delay_seconds=2
    window.start(p);window.start(window.config.profiles[1]);assert '当前已有方案' in window.status.text()
    ticks=[];timer=QTimer();timer.timeout.connect(lambda:ticks.append(1));timer.start(10)
    deadline=time.monotonic()+.15
    while time.monotonic()<deadline:qt.processEvents();time.sleep(.005)
    timer.stop();assert len(ticks)>3;window.cancel();window.thread.join(1);qt.processEvents();assert not window.thread.is_alive()

def test_close_tray_restore(window,qt,monkeypatch):
    monkeypatch.setattr(QSystemTrayIcon,'isSystemTrayAvailable',lambda:True)
    window.config.settings['tray_notice']=True;window.config.settings['close_to_tray']=True
    window.close();qt.processEvents();assert not window.isVisible();window.reveal();qt.processEvents();assert window.isVisible()

def test_single_instance_delivery(qt,tmp_path):
    from app.core.single_instance import SingleInstance
    instance=SingleInstance(tmp_path);assert instance.acquire({})
    received=[];instance.request.connect(received.append)
    code='from pathlib import Path;from PySide6.QtCore import QCoreApplication;from app.core.single_instance import SingleInstance;app=QCoreApplication([]);i=SingleInstance(Path(__import__("sys").argv[1]));assert not i.acquire({"profile":"test-profile"})'
    child=subprocess.Popen([sys.executable,'-c',code,str(tmp_path)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    deadline=time.monotonic()+8
    while child.poll() is None and time.monotonic()<deadline:qt.processEvents();time.sleep(.01)
    if child.poll() is None:child.kill()
    out,err=child.communicate();assert child.returncode==0,err.decode(errors='replace');assert received==[{'profile':'test-profile'}]
    instance.server.close();instance.lock.unlock()


def test_logs_dialog(window,qt):
    from PySide6.QtWidgets import QDialog, QTextEdit
    (window.config.root/'logs'/'launchflow.log').write_text('批次 123 测试日志',encoding='utf-8')
    captured=[]
    def inspect():
        modal=QApplication.activeModalWidget();captured.append(modal.findChild(QTextEdit).toPlainText());modal.reject()
    QTimer.singleShot(50,inspect);window.logs();assert '123' in captured[0]

def test_settings_persistence_without_registry_write(window,monkeypatch):
    from app.ui.settings_dialog import SettingsDialog
    from app.core import startup_manager
    writes=[];monkeypatch.setattr(startup_manager,'set_enabled',lambda enabled:writes.append(enabled))
    d=SettingsDialog(window,window.config);d.fields['default_delay'].setValue(7);d.theme.setCurrentIndex(1);d.save()
    restored=ConfigService(window.config.root);assert restored.settings['default_delay']==7 and restored.settings['theme']=='dark';assert not writes

def send_file_drop(widget, urls):
    from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt
    from PySide6.QtGui import QDragEnterEvent, QDragMoveEvent, QDropEvent
    mime=QMimeData();mime.setUrls(urls)
    enter=QDragEnterEvent(QPoint(20,20),Qt.CopyAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(widget.viewport(),enter)
    if not enter.isAccepted():return False
    move=QDragMoveEvent(QPoint(20,20),Qt.CopyAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(widget.viewport(),move)
    assert move.isAccepted()
    drop=QDropEvent(QPointF(20,20),Qt.CopyAction,mime,Qt.LeftButton,Qt.NoModifier)
    QApplication.sendEvent(widget.viewport(),drop)
    return drop.isAccepted()


def test_external_drop_adds_multiple_and_persists_without_launch(window,tmp_path):
    from PySide6.QtCore import QUrl
    paths=[tmp_path/'中文 应用.exe',tmp_path/'桌面 快捷方式.LNK',tmp_path/'可信脚本.cmd']
    for path in paths:path.touch()
    window.config.settings['default_delay']=7
    window.scheduler.launch=lambda target:pytest.fail('dropping a file must never execute it')
    assert send_file_drop(window.apps,[QUrl.fromLocalFile(str(p)) for p in paths])
    restored=ConfigService(window.config.root);apps=restored.profiles[0].applications
    assert len(apps)==4
    assert [a.name for a in apps[-3:]]==[p.stem for p in paths]
    assert all(a.delay_seconds==7 for a in apps[-3:])
    assert apps[-2].working_directory==''
    assert apps[-1].working_directory==str(tmp_path)
    assert window.apps.currentRow()==3 and window.scheduler.active is None
    assert window.windowTitle()=='光启 LumenChain' and window.tray.toolTip()=='光启 LumenChain'


def test_external_drop_duplicates_skipped(window,tmp_path):
    from PySide6.QtCore import QUrl
    path=tmp_path/'应用.exe';path.touch();url=QUrl.fromLocalFile(str(path))
    assert send_file_drop(window.apps,[url,url])
    assert len(window.selected().applications)==2
    assert send_file_drop(window.apps,[url])
    assert len(ConfigService(window.config.root).profiles[0].applications)==2
    assert '重复或无效文件' in window.status.text()


def test_external_drop_rejects_non_programs_and_remote_urls(window,tmp_path):
    from PySide6.QtCore import QUrl
    text=tmp_path/'文本.txt';text.touch()
    assert not send_file_drop(window.apps,[QUrl.fromLocalFile(str(text))])
    assert not send_file_drop(window.apps,[QUrl.fromLocalFile(str(tmp_path))])
    assert not send_file_drop(window.apps,[QUrl('https://example.com/app.exe')])
    assert len(window.selected().applications)==1


def test_external_drop_mixed_files_and_profile_switch(window,tmp_path):
    from PySide6.QtCore import QUrl
    program=tmp_path/'应用.bat';program.touch();text=tmp_path/'文件.txt';text.touch()
    window.profiles.setCurrentRow(1)
    assert send_file_drop(window.apps,[QUrl.fromLocalFile(str(text)),QUrl.fromLocalFile(str(program))])
    assert len(window.config.profiles[0].applications)==1
    assert len(window.config.profiles[1].applications)==1
    assert window.config.profiles[1].applications[0].path==str(program)


def test_drop_without_profile_and_save_failure(window,tmp_path,monkeypatch):
    program=tmp_path/'应用.exe';program.touch()
    original=list(window.selected().applications)
    monkeypatch.setattr(window,'save',lambda:False)
    window.add_dropped_apps([str(program)])
    assert window.selected().applications==original
    window.config.profiles=[];window.refresh()
    asked=[];monkeypatch.setattr(window,'new_profile',lambda:asked.append(True))
    window.add_dropped_apps([str(program)])
    assert asked==[True] and window.selected() is None

def test_compact_drag_preview_and_cancel(window,monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QDrag
    item=window.apps.item(0)
    item.setToolTip('应用名称非常长 '*20+'\nC:/app.exe')
    preview=window.apps.drag_preview(item)
    assert preview.width()/preview.devicePixelRatio()<=280
    assert preview.height()/preview.devicePixelRatio()==38
    assert preview.width()/preview.devicePixelRatio()<window.apps.viewport().width()
    window.apps.setCurrentItem(item)
    captured=[]
    def cancel(drag,*args):
        captured.append((drag.pixmap().size(),drag.hotSpot()))
        return Qt.IgnoreAction
    monkeypatch.setattr(QDrag,'exec',cancel)
    before=[a.id for a in window.selected().applications]
    window.apps.startDrag(Qt.MoveAction)
    assert captured and captured[0][1].x()==20
    assert [a.id for a in window.selected().applications]==before
    assert window.apps._dragged_id is None and window.apps._drop_row is None
    assert not window.apps._scroll_timer.isActive()


def test_precise_internal_reorder_persists_and_keeps_selection(window,qt):
    from PySide6.QtCore import QPointF, Qt
    p=window.selected()
    p.applications.extend([Application('第二项','C:/second.exe'),Application('第三项','C:/third.exe')])
    window.render();qt.processEvents()
    widget=window.apps
    class InternalDrop:
        def __init__(self,position):self.point=QPointF(position);self.accepted=False
        def source(self):return widget
        def position(self):return self.point
        def setDropAction(self,action):assert action==Qt.MoveAction
        def accept(self):self.accepted=True
        def ignore(self):self.accepted=False
    first=widget.item(0);first_id=first.data(Qt.UserRole)
    widget._dragged_id=first_id
    last_rect=widget.visualItemRect(widget.item(2))
    drop=InternalDrop(last_rect.bottomLeft())
    widget.dragMoveEvent(drop)
    assert widget._drop_row==3
    widget.dropEvent(drop)
    assert drop.accepted and widget.currentItem().data(Qt.UserRole)==first_id
    assert [a.name for a in ConfigService(window.config.root).profiles[0].applications]==['第二项','第三项','测试应用']
    widget._dragged_id=first_id
    drop=InternalDrop(widget.visualItemRect(widget.item(0)).topLeft())
    widget.dropEvent(drop)
    assert [a.name for a in ConfigService(window.config.root).profiles[0].applications]==['测试应用','第二项','第三项']
    assert widget._drop_row is None


def test_drag_noop_and_edge_scroll(window,qt):
    from PySide6.QtCore import QPoint, Qt
    p=window.selected();p.applications.extend(Application('应用'+str(i),'C:/app'+str(i)+'.exe') for i in range(25))
    window.render();qt.processEvents();widget=window.apps
    rect=widget.visualItemRect(widget.item(0))
    assert widget.insertion_row(rect.topLeft())==0
    assert widget.insertion_row(rect.bottomLeft())==1
    original=widget.verticalScrollBar().value()
    widget._drag_position=QPoint(20,widget.viewport().height()-2)
    widget._scroll_direction=1;widget.scroll_drag()
    assert widget.verticalScrollBar().value()>original
    widget._drop_row=widget.count()
    widget.viewport().update();qt.processEvents()

def test_row_arrow_clicks_move_correct_application_and_save(window,qt):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    profile=window.selected()
    profile.applications.extend([Application('第二项','C:/second.exe'),Application('第三项','C:/third.exe')])
    window.render();qt.processEvents()
    first_id=profile.applications[0].id;second_id=profile.applications[1].id
    first_up,first_down=window.apps._row_buttons[first_id]
    assert not first_up.isEnabled() and first_down.isEnabled()
    assert not window.apps._row_buttons[profile.applications[-1].id][1].isEnabled()
    # Click an unselected row: its own application must move, not the current selection.
    window.apps.setCurrentRow(0)
    QTest.mouseClick(window.apps._row_buttons[second_id][1],Qt.LeftButton);qt.processEvents()
    assert [a.name for a in ConfigService(window.config.root).profiles[0].applications]==['测试应用','第三项','第二项']
    assert window.apps.currentItem().data(Qt.UserRole)==second_id
    assert not window.apps._row_buttons[second_id][1].isEnabled()
    QTest.mouseClick(window.apps._row_buttons[second_id][0],Qt.LeftButton);qt.processEvents()
    assert [a.name for a in ConfigService(window.config.root).profiles[0].applications]==['测试应用','第二项','第三项']


def test_arrow_buttons_follow_reorder_scroll_resize_and_profile_switch(window,qt):
    from PySide6.QtCore import Qt
    profile=window.selected();profile.applications.extend(Application('应用'+str(i),'C:/app'+str(i)+'.exe') for i in range(20))
    window.render();qt.processEvents()
    identifier=profile.applications[0].id
    item=window.apps.takeItem(0);window.apps.insertItem(2,item);window.reorder();qt.processEvents()
    assert all(button.isEnabled() for button in window.apps._row_buttons[identifier])
    last_id=profile.applications[-1].id
    window.apps.scrollToBottom();qt.processEvents()
    assert window.apps._row_buttons[last_id][0].isVisible()
    assert not window.apps._row_buttons[profile.applications[0].id][0].isVisible()
    window.resize(900,600);qt.processEvents()
    button=window.apps._row_buttons[last_id][1]
    assert button.geometry().right()<window.apps.viewport().width()
    window.profiles.setCurrentRow(1);qt.processEvents()
    assert window.apps._row_buttons=={}


def test_arrow_single_item_disabled_and_save_failure_rolls_back(window,qt,monkeypatch):
    from PySide6.QtCore import Qt
    identifier=window.selected().applications[0].id
    assert not any(button.isEnabled() for button in window.apps._row_buttons[identifier])
    window.selected().applications.append(Application('第二项','C:/second.exe'));window.render();qt.processEvents()
    before=[a.id for a in window.selected().applications]
    monkeypatch.setattr(window,'save',lambda:False)
    window.apps._row_buttons[identifier][1].click();qt.processEvents()
    assert [a.id for a in window.selected().applications]==before
    assert window.apps.item(0).data(Qt.UserRole)==identifier
