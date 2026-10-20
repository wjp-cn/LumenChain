from dataclasses import dataclass, field, asdict
from uuid import uuid4
from datetime import datetime
import copy, math

def uid(): return str(uuid4())
def now(): return datetime.now().isoformat(timespec="seconds")
@dataclass
class Application:
    name: str
    path: str
    id: str = field(default_factory=uid)
    arguments: str = ""
    working_directory: str = ""
    enabled: bool = True
    skip_if_running: bool = True
    launch_strategy: str = "delay"
    delay_seconds: float = 3
    failure_action: str = "continue"
    retry_count: int = 0
    retry_interval: float = 1
    process_name: str = ""
    readiness: dict = field(default_factory=lambda: dict(kind="process", value="", host="127.0.0.1", port=2375, timeout=60, interval=0.5, associate=False))
    def validate(self):
        for key in ("id", "name", "path", "arguments", "working_directory", "process_name"):
            if not isinstance(getattr(self,key),str): raise ValueError("应用文本字段格式无效")
        if not self.id or not isinstance(self.enabled,bool) or not isinstance(self.skip_if_running,bool): raise ValueError("应用 ID 或开关无效")
        for key in ("delay_seconds", "retry_interval", "retry_count"):
            if not isinstance(getattr(self,key),(int,float)) or not math.isfinite(getattr(self,key)): raise ValueError("时间或重试次数格式无效")
        if not isinstance(self.retry_count,int): raise ValueError("重试次数必须为整数")
        if not self.name.strip() or not self.path.strip(): raise ValueError("名称和程序路径不能为空")
        if self.launch_strategy not in ("immediate", "delay", "ready"): raise ValueError("启动策略无效")
        if self.failure_action not in ("continue", "stop", "retry"): raise ValueError("失败策略无效")
        if not 0 <= self.delay_seconds <= 3600 or not 0 <= self.retry_count <= 3 or not 0 <= self.retry_interval <= 3600: raise ValueError("等待时间或重试次数超出范围")
        r = self.readiness
        if not isinstance(r,dict): raise ValueError("就绪配置无效")
        for key in ("value", "host"):
            if not isinstance(r.get(key),str): raise ValueError("就绪文本字段无效")
        for key in ("timeout","interval","port"):
            if not isinstance(r.get(key),(int,float)) or not math.isfinite(r[key]): raise ValueError("就绪检测数值无效")
        if not isinstance(r["port"],int): raise ValueError("端口必须为整数")
        if r.get("kind") not in ("process", "window", "tcp"): raise ValueError("就绪类型无效")
        if not 0.1 <= r.get("interval", 0) <= 60 or not 0.1 <= r.get("timeout", 0) <= 3600: raise ValueError("就绪检测时间无效")
        if not 1 <= r.get("port", 0) <= 65535: raise ValueError("端口无效")
        if self.launch_strategy == "ready" and r["kind"] == "window" and not r.get("value", "").strip(): raise ValueError("请输入窗口标题关键字")
@dataclass
class Profile:
    name: str
    description: str = ""
    id: str = field(default_factory=uid)
    applications: list = field(default_factory=list)
    created_at: str = field(default_factory=now)
    modified_at: str = field(default_factory=now)
    def validate(self):
        if not all(isinstance(v,str) for v in (self.id,self.name,self.description,self.created_at,self.modified_at)) or not self.id: raise ValueError("方案字段格式无效")
        if not self.name.strip(): raise ValueError("方案名称不能为空")
        ids = [a.id for a in self.applications]
        if len(ids) != len(set(ids)): raise ValueError("应用 ID 重复")
        for a in self.applications: a.validate()
    def clone(self):
        p = copy.deepcopy(self); p.id = uid(); p.name += " 副本"; p.created_at = p.modified_at = now()
        for a in p.applications: a.id = uid()
        return p
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, data):
        data = copy.deepcopy(data)
        apps = data.pop("applications", [])
        for a in apps:
            if isinstance(a.get("arguments"), list):
                import subprocess
                a["arguments"] = subprocess.list2cmdline(a["arguments"])
            if a.get("readiness") is None: a.pop("readiness", None)
        p = cls(**data, applications=[Application(**a) for a in apps]); p.validate(); return p
