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
