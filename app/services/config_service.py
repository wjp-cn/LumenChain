import json, os, shutil
from pathlib import Path
from app.models.profile import Profile

DEFAULTS = dict(theme="light", close_to_tray=True, startup=False, auto_run=False, default_profile="", startup_delay=10, default_delay=3, default_skip=True, default_timeout=60, default_failure="continue", default_retry=0, tray_notice=False)
class ConfigService:
    def __init__(self, root=None):
        self.root = Path(root or Path(os.environ.get("APPDATA", str(Path.home()))) / "LaunchFlow")
        self.root.mkdir(parents=True, exist_ok=True)
        for d in ("logs", "backups"): (self.root / d).mkdir(exist_ok=True)
        self.warnings = []
        self.settings = DEFAULTS | self.load("config.json", {"schema_version":1, "settings":{}}).get("settings", {})
        self.validate_settings(self.settings)
        self.profiles = self.parse(self.load("profiles.json", {"schema_version":1, "profiles":[]}))
    @staticmethod
    def validate_settings(settings):
        for key in ("startup","auto_run","close_to_tray","default_skip","tray_notice"):
            if key in settings and not isinstance(settings[key],bool): raise ValueError("设置开关格式无效")
        for key in ("startup_delay","default_delay","default_timeout","default_retry"):
            if key in settings and (not isinstance(settings[key],int) or not 0 <= settings[key] <= (3 if key=="default_retry" else 3600)): raise ValueError("默认时间或重试次数无效")
        if settings.get("theme","light") not in ("light","dark","system"): raise ValueError("主题无效")
        if settings.get("default_failure","continue") not in ("continue","stop","retry"): raise ValueError("默认失败处理无效")
        if not isinstance(settings.get("default_profile",""),str): raise ValueError("默认方案 ID 无效")
    @staticmethod
    def parse(data):
        if data.get("schema_version", 1) != 1: raise ValueError("不支持的配置版本")
        profiles = [Profile.from_dict(p) for p in data["profiles"]]
        if len({p.id for p in profiles}) != len(profiles): raise ValueError("方案 ID 重复")
        return profiles
    def load(self, name, default):
        path = self.root / name
        if not path.exists(): return default
        for candidate in (path, self.root / "backups" / name):
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if data.get("schema_version", 1) != 1: raise ValueError("不支持的版本")
                if name == "profiles.json": self.parse(data)
                elif not isinstance(data.get("settings"), dict): raise ValueError("设置格式无效")
                else: self.validate_settings(data["settings"])
                if candidate != path: self.warnings.append(f"{name} 已从备份恢复")
                return data
            except (ValueError, TypeError, KeyError, OSError) as e: self.warnings.append(f"{candidate.name} 读取失败：{e}")
        raise ValueError(f"{name} 及备份损坏，请保留原文件并手动恢复")
    def write(self, name, data):
        path = self.root / name; tmp = path.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2); f.flush(); os.fsync(f.fileno())
            if path.exists():
                try:
                    old = json.loads(path.read_text(encoding="utf-8"))
                    if name == "profiles.json": self.parse(old)
                    shutil.copy2(path, self.root / "backups" / name)
                except (ValueError, TypeError, KeyError): pass
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    def save(self):
        self.validate_settings(self.settings)
        for p in self.profiles: p.validate()
        self.write("profiles.json", {"schema_version":1, "profiles":[p.to_dict() for p in self.profiles]})
        self.write("config.json", {"schema_version":1, "settings":self.settings})
