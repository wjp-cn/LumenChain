import ctypes, json, os, subprocess, tempfile, time, sys
from pathlib import Path
from ctypes import wintypes
exe=Path(sys.argv[1] if len(sys.argv)>1 else 'dist/LaunchFlow/LaunchFlow.exe').resolve()
user=ctypes.windll.user32
user.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
user.GetWindowThreadProcessId.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.DWORD)]
user.IsWindowVisible.argtypes=[wintypes.HWND]
callback=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
user.EnumWindows.argtypes=[callback,wintypes.LPARAM]
def windows(pid):
    import psutil
    try: pids={pid, *(child.pid for child in psutil.Process(pid).children(recursive=True))}
    except psutil.NoSuchProcess: pids={pid}
    found=[]
    @callback
    def visit(hwnd,_):
        p=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(p))
        if p.value in pids:
            title=ctypes.create_unicode_buffer(1024);user.GetWindowTextW(hwnd,title,len(title))
            if 'LaunchFlow' in title.value:found.append((hwnd,bool(user.IsWindowVisible(hwnd))))
        return True
    user.EnumWindows(visit,0);return found
with tempfile.TemporaryDirectory() as root:
    env=os.environ.copy();env['APPDATA']=root;env['QT_QPA_PLATFORM']='windows'
    started=time.monotonic()
    first=subprocess.Popen([str(exe),'--autostart','--minimized','--smoke-test','--smoke-timeout','20000'],env=env,cwd=root)
    try:
        deadline=time.monotonic()+15
        log=Path(root)/"LaunchFlow/logs/launchflow.log"
        while (not log.exists() or not log.read_text(encoding="utf-8")) and time.monotonic()<deadline and first.poll() is None:time.sleep(.05)
        assert first.poll() is None, "first instance exited early"
        hidden=windows(first.pid);assert not any(visible for _,visible in hidden),hidden
        second=subprocess.run([str(exe)],env=env,cwd=root,timeout=25)
        assert second.returncode==0
        deadline=time.monotonic()+2
        while not any(visible for _,visible in windows(first.pid)) and time.monotonic()<deadline:time.sleep(.05)
        assert any(visible for _,visible in windows(first.pid)),'second instance did not restore window'
        assert first.wait(timeout=30)==0
        log=Path(root)/'LaunchFlow/logs/launchflow.log';assert log.exists()
        assert 'ERROR' not in log.read_text(encoding='utf-8')
        result=dict(exe=str(exe),hidden_start=True,second_instance_restore=True,clean_exit=True,external_working_directory=True,elapsed=round(time.monotonic()-started,2))
        Path('docs/package-smoke-'+('onefile' if exe.parent.name=='dist' else 'onedir')+'.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
    finally:
        if first.poll() is None:first.terminate();first.wait(timeout=5)
