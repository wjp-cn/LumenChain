import socket, ctypes, os
from app.core.process_monitor import matching_pids

def check(app, target):
    r = app.readiness; kind = r["kind"]
    if kind == "process":
        return bool(matching_pids(name=r["value"])[0] if r["value"] else matching_pids(path=target.path)[0])
    if kind == "tcp":
        try:
            with socket.create_connection((r["host"], int(r["port"])), timeout=min(0.5, r["interval"])): return True
        except OSError: return False
    if os.name != "nt": raise RuntimeError("窗口检测仅支持 Windows")
    pids = set(matching_pids(path=target.path)[0]) if r.get("associate") else None
    matched = []
    callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user = ctypes.windll.user32
    user.IsWindowVisible.argtypes = [ctypes.c_void_p]
    user.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    user.EnumWindows.argtypes = [callback, ctypes.c_void_p]
    @callback
    def visit(hwnd, _):
        if not user.IsWindowVisible(hwnd): return True
        buf = ctypes.create_unicode_buffer(2048); user.GetWindowTextW(hwnd, buf, len(buf))
        pid = ctypes.c_ulong(); user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if r["value"].casefold() in buf.value.casefold() and (pids is None or pid.value in pids): matched.append(hwnd)
        return True
    user.EnumWindows(visit, 0)
    return bool(matched)
