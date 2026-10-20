import os, sys, subprocess
from pathlib import Path
NAME = "LaunchFlow"
def command():
    args = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(Path(__file__).resolve().parents[2] / "main.py")]
    return subprocess.list2cmdline(args + ["--autostart", "--minimized"])
def current():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key: return winreg.QueryValueEx(key, NAME)[0]
    except FileNotFoundError: return ""
def set_enabled(enabled):
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
        if enabled: winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, command())
        else:
            try: winreg.DeleteValue(key, NAME)
            except FileNotFoundError: pass
