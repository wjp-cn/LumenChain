import os, subprocess, sys
from pathlib import Path
import pytest
from app.core.launcher import resolve, launch, Target
from app.models.profile import Application
pytestmark=pytest.mark.skipif(os.name!='nt',reason='需要真实 Windows')

def test_real_cmd_unicode_spaces(tmp_path):
    script=tmp_path/'测试 脚本.cmd';out=tmp_path/'结果 文件.txt'
    script.write_text('@echo off\r\n> "%~1" echo success\r\n',encoding='utf-8')
    proc=launch(Target(str(script),'"'+str(out)+'"'));assert proc.wait(timeout=5)==0
    assert out.read_text().strip()=='success'

def test_shortcut_resolution(tmp_path):
    link=tmp_path/'中文 快捷方式.lnk'
    env=os.environ.copy();env['LF_TEST_LINK']=str(link);env['LF_TEST_EXE']=sys.executable
    code='$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LF_TEST_LINK);$s.TargetPath=$env:LF_TEST_EXE;$s.Arguments="--version";$s.Save()'
    subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',code],env=env,check=True,capture_output=True,timeout=15)
    t=resolve(Application('快捷方式',str(link)));assert Path(t.path)==Path(sys.executable);assert t.arguments=='--version'

def test_real_process_detection():
    pytest.importorskip('psutil')
    from app.core.process_monitor import matching_pids
    import psutil
    pids,_=matching_pids(path=psutil.Process().exe());assert os.getpid() in pids

def test_startup_command_only():
    from app.core.startup_manager import command
    text=command();assert '--autostart' in text and '--minimized' in text
    # Registry writes require the explicit settings toggle; this test does not modify user startup.

def test_actual_window_title_readiness(tmp_path):
    pytest.importorskip('PySide6')
    from app.core.readiness_checker import check
    title='LaunchFlowTestWindow-'+str(os.getpid())
    code='from PySide6.QtWidgets import QApplication,QWidget;from PySide6.QtCore import QTimer;import sys;app=QApplication([]);w=QWidget();w.setWindowTitle(sys.argv[1]);w.show();QTimer.singleShot(5000,app.quit);app.exec()'
    env=os.environ.copy();env['QT_QPA_PLATFORM']='windows'
    child=subprocess.Popen([sys.executable,'-c',code,title],env=env)
    try:
        import time
        a=Application('窗口测试',sys.executable);a.readiness.update(kind='window',value=title)
        deadline=time.monotonic()+4;found=False
        while time.monotonic()<deadline:
            if check(a,Target(sys.executable)):found=True;break
            time.sleep(.05)
        assert found
        assert child.wait(timeout=8)==0
    finally:
        if child.poll() is None:child.terminate();child.wait(timeout=5)
