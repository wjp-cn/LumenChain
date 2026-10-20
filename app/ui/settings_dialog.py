from PySide6.QtWidgets import *
from app.core import startup_manager
import copy

class SettingsDialog(QDialog):
    def __init__(self,parent,config):
        super().__init__(parent); self.setWindowTitle("设置"); self.config=config; self.resize(480,560)
        layout=QVBoxLayout(self); scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();form=QFormLayout(body);scroll.setWidget(body);layout.addWidget(scroll); self.fields={}
        for key,label in (("startup","开机启动编排器"),("auto_run","开机自动执行方案"),("close_to_tray","关闭窗口时最小化到托盘"),("default_skip","默认跳过已运行软件")):
            w=QCheckBox(label); w.setChecked(config.settings[key]); self.fields[key]=w; form.addRow(w)
        self.profile=QComboBox(); self.profile.addItem("请选择方案","")
        for p in config.profiles: self.profile.addItem(p.name,p.id)
        self.profile.setCurrentIndex(max(0,self.profile.findData(config.settings["default_profile"]))); form.addRow("默认 / 开机方案",self.profile)
        for key,label,lo,hi in (("startup_delay","开机延迟秒数",0,3600),("default_delay","默认启动间隔秒数",0,3600),("default_timeout","默认就绪超时秒数",1,3600),("default_retry","默认重试次数",0,3)):
            w=QSpinBox(); w.setRange(lo,hi); w.setValue(config.settings[key]); self.fields[key]=w; form.addRow(label,w)
        self.failure=QComboBox(); self.failure.addItems(["跳过并继续","停止整个队列","重试后继续"]); self.failure.setCurrentIndex(["continue","stop","retry"].index(config.settings["default_failure"])); form.addRow("默认失败处理",self.failure)
        self.theme=QComboBox(); self.theme.addItems(["浅色","深色","跟随系统"]); self.theme.setCurrentIndex(["light","dark","system"].index(config.settings["theme"])); form.addRow("外观",self.theme)
        label=QLabel("启动编排器 LaunchFlow 1.0.0\n一次编排，一键启动。\nPython（PSF 许可） / PySide6（LGPLv3） / psutil（BSD）\n开源许可见随附 THIRD_PARTY_NOTICES.md。"); label.setWordWrap(True); layout.addWidget(label)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.button(QDialogButtonBox.Save).setText("保存"); buttons.button(QDialogButtonBox.Cancel).setText("取消"); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
    def save(self):
        old=copy.deepcopy(self.config.settings); new=copy.deepcopy(old)
        for k,w in self.fields.items(): new[k]=w.isChecked() if isinstance(w,QCheckBox) else w.value()
        new["default_profile"]=self.profile.currentData(); new["theme"]=["light","dark","system"][self.theme.currentIndex()]; new["default_failure"]=["continue","stop","retry"][self.failure.currentIndex()]
        if new["auto_run"] and (not new["startup"] or not new["default_profile"]): QMessageBox.warning(self,"设置无效","自动执行需开启开机启动并选择方案"); return
        try:
            if new["startup"] != old["startup"] or (new["startup"] and startup_manager.current()!=startup_manager.command()): startup_manager.set_enabled(new["startup"])
            self.config.settings=new; self.config.save()
        except Exception as e:
            self.config.settings=old
            QMessageBox.warning(self,"保存失败",str(e)); return
        self.accept()
