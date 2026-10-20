import os, logging
try:
    import psutil
except ImportError:
    psutil = None

def matching_pids(path="", name=""):
    if psutil is None: raise RuntimeError("请安装 psutil 以检测进程")
    found = []; uncertain = False
    normalized = os.path.normcase(os.path.abspath(path)) if path else ""
    for p in psutil.process_iter():
        try:
            if normalized:
                if p.name().casefold() != os.path.basename(path).casefold(): continue
                exe = p.exe()
                if exe and os.path.normcase(os.path.abspath(exe)) == normalized: found.append(p.pid)
            elif name and p.name().casefold() == name.casefold(): found.append(p.pid)
        except (psutil.AccessDenied, psutil.ZombieProcess): uncertain = True
        except psutil.NoSuchProcess: pass
    if uncertain: logging.getLogger("LaunchFlow").warning("部分进程权限不足，无法完整确认运行状态")
    return found, uncertain
