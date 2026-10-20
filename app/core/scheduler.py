import copy, threading, time, logging
from app.core.launcher import resolve, launch
from app.core.process_monitor import matching_pids
from app.core.readiness_checker import check

class Cancelled(Exception): pass
class Scheduler:
    def __init__(self, emit=lambda *args: None, resolver=resolve, launcher=launch, monitor=matching_pids, checker=check):
        def report(kind, identifier, text):
            if kind == "state": logging.getLogger("LaunchFlow").info("应用 %s 状态：%s", identifier, text)
            emit(kind, identifier, text)
        self.emit = report; self.resolve = resolver; self.launch = launcher; self.monitor = monitor; self.check = checker
        self.lock = threading.Lock(); self.cancelled = threading.Event(); self.active = None
    def reserve(self, profile):
        with self.lock:
            if self.active is not None: return None
            snapshot = copy.deepcopy(profile); snapshot.validate(); self.active = snapshot; self.cancelled.clear(); return snapshot
    def cancel(self): self.cancelled.set()
    def wait(self, seconds):
        end = time.monotonic() + seconds
        while True:
            if self.cancelled.is_set(): raise Cancelled()
            remaining = end - time.monotonic()
            if remaining <= 0: return
            self.emit("countdown", "", f"等待剩余 {remaining:.1f} 秒")
            if self.cancelled.wait(min(0.25, remaining)): raise Cancelled()
    def run(self, profile):
        start = time.monotonic(); threading.current_thread().launchflow_batch = profile.id + ":" + str(time.time_ns()); counts = dict(started=0, skipped=0, failed=0, cancelled=0)
        apps = [a for a in profile.applications if a.enabled]
        log = logging.getLogger("LaunchFlow"); log.info("批次 %s 方案 %s %s", start, profile.id, profile.name)
        try:
            for i, a in enumerate(apps):
                if self.cancelled.is_set(): counts["cancelled"] += len(apps)-i; break
                accepted = False
                try:
                    attempts = a.retry_count + 1 if a.failure_action == "retry" else 1
                    for attempt in range(attempts):
                        try:
                            self.emit("state", a.id, "检测中")
                            target = self.resolve(a)
                            running = False
                            if a.skip_if_running:
                                pids, uncertain = self.monitor(path=target.path)
                                if not pids and uncertain and a.process_name: pids, _ = self.monitor(name=a.process_name)
                                if not pids and uncertain and not a.process_name: raise PermissionError("目标进程路径无法读取，不能安全确认是否已运行；可配置降级进程名")
                                running = bool(pids)
                            if running:
                                self.emit("state", a.id, "已运行，跳过启动")
                            elif not accepted:
                                self.emit("state", a.id, "启动中"); self.launch(target); accepted = True; counts["started"] += 1
                                self.emit("state", a.id, "启动命令已接受")
                            if a.launch_strategy == "delay" and not running: self.wait(a.delay_seconds)
                            if a.launch_strategy == "ready":
                                deadline = time.monotonic() + a.readiness["timeout"]
                                self.emit("state", a.id, "等待独立就绪条件")
                                while True:
                                    if self.cancelled.is_set(): raise Cancelled()
                                    if self.check(a, target): break
                                    if time.monotonic() >= deadline: raise TimeoutError(a.readiness["kind"] + " 就绪检测超时")
                                    self.wait(min(a.readiness["interval"], max(0, deadline-time.monotonic())))
                                self.emit("state", a.id, {"process":"进程已出现", "window":"窗口已出现", "tcp":"指定服务就绪"}[a.readiness["kind"]])
                            if running and not accepted: counts["skipped"] += 1
                            break
                        except Cancelled: raise
                        except Exception as e:
                            log.exception("应用 %s 第 %s 次失败", a.name, attempt+1)
                            if attempt + 1 == attempts: raise
                            self.emit("state", a.id, f"失败，等待重试：{e}"); self.wait(a.retry_interval)
                    log.info("应用 %s 处理完成", a.name)
                except Cancelled:
                    counts["cancelled"] += len(apps)-i; self.emit("state", a.id, "已取消"); break
                except Exception as e:
                    counts["failed"] += 1; self.emit("state", a.id, "失败：" + str(e))
                    if a.failure_action == "stop":
                        counts["cancelled"] += len(apps)-i-1; break
                self.emit("progress", str(i+1), str(len(apps)))
        finally:
            with self.lock: self.active = None
            summary = f"流程结束：共 {len(apps)} 项；命令已提交 {counts['started']}，已跳过 {counts['skipped']}，失败 {counts['failed']}，未完成 {counts['cancelled']}；耗时 {time.monotonic()-start:.1f} 秒（提交与失败可能重叠）"
            log.info(summary); self.emit("finished", "", summary)
        return counts
