import os, subprocess, ctypes, json
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Target:
    path: str
    arguments: str = ""
    cwd: str = ""

def resolve(app):
    path = os.path.expandvars(app.path)
    if not Path(path).is_file(): raise FileNotFoundError("程序文件不存在")
    if Path(path).suffix.lower() == ".lnk":
        script = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:LAUNCHFLOW_LINK); @{path=$s.TargetPath;arguments=$s.Arguments;cwd=$s.WorkingDirectory}|ConvertTo-Json -Compress"
        env = os.environ.copy(); env["LAUNCHFLOW_LINK"] = path
        result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], env=env, capture_output=True, timeout=15, creationflags=0x08000000)
        if result.returncode: raise RuntimeError("快捷方式解析失败")
        data = json.loads(result.stdout.decode("utf-8-sig", errors="replace"))
        if not data["path"] or not Path(data["path"]).is_file(): raise FileNotFoundError("快捷方式目标不存在或不是文件")
        return Target(data["path"], app.arguments or data["arguments"], app.working_directory or data["cwd"])
    return Target(path, app.arguments, app.working_directory)

def split_arguments(text):
    if not text.strip(): return []
    if os.name != "nt":
        import shlex
        return shlex.split(text)
    argc = ctypes.c_int()
    fn = ctypes.windll.shell32.CommandLineToArgvW; fn.restype = ctypes.POINTER(ctypes.c_wchar_p)
    args = fn("dummy " + text, ctypes.byref(argc))
    if not args: raise ValueError("启动参数无效")
    try: return [args[i] for i in range(1, argc.value)]
    finally: ctypes.windll.kernel32.LocalFree(args)

def launch(target):
    path = target.path; suffix = Path(path).suffix.lower()
    cwd = target.cwd or str(Path(path).parent)
    if suffix in (".bat", ".cmd"):
        # cmd scripts intentionally use cmd syntax, including user-provided script arguments.
        command = '""' + path + '"' + (" " + target.arguments if target.arguments else "") + '"'
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        return subprocess.Popen('"' + comspec + '" /d /s /c ' + command, executable=comspec, cwd=cwd, shell=False)
    if suffix != ".exe": raise ValueError("仅支持 EXE、LNK、BAT、CMD")
    try: return subprocess.Popen([path, *split_arguments(target.arguments)], cwd=cwd, shell=False)
    except OSError as e:
        if getattr(e, "winerror", None) != 740: raise
        shell = ctypes.windll.shell32.ShellExecuteW
        shell.restype = ctypes.c_void_p
        code = shell(None, "runas", path, target.arguments, cwd, 1)
        if code <= 32: raise PermissionError("Windows 拒绝执行或用户取消 UAC")
        return None  # ShellExecute does not provide a PID; readiness stays independent.
