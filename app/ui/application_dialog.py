from PySide6.QtWidgets import *
from app.models.profile import Application
import copy
from pathlib import Path

class ApplicationDialog(QDialog):
    def __init__(self, parent, application=None, settings=None):
        super().__init__(parent); self.setWindowTitle("编辑软件" if application else "添加应用程序"); self.resize(570, 650)
        settings = settings or {}
        self.application = copy.deepcopy(application) if application else Application("", "", delay_seconds=settings.get("default_delay",3), skip_if_running=settings.get("default_skip",True), failure_action=settings.get("default_failure","continue"), retry_count=settings.get("default_retry",0))
        if not application: self.application.readiness["timeout"] = settings.get("default_timeout",60)
        a = self.application; layout = QVBoxLayout(self); scroll = QScrollArea(); scroll.setWidgetResizable(True); body = QWidget(); form = QFormLayout(body); scroll.setWidget(body); layout.addWidget(scroll)
        self.fields = {}
        for key, label in (("name","软件名称"),("path","程序路径"),("arguments","启动参数"),("working_directory","工作目录"),("process_name","降级匹配进程名")):
            edit = QLineEdit(getattr(a,key)); self.fields[key] = edit
            if key in ("path", "working_directory"):
                row = QHBoxLayout(); row.addWidget(edit); b=QPushButton("浏览"); row.addWidget(b)
                b.clicked.connect(lambda checked=False,k=key:self.browse(k)); form.addRow(label,row)
            else: form.addRow(label,edit)
        self.enabled=QCheckBox("启用此软件"); self.enabled.setChecked(a.enabled); form.addRow(self.enabled)
        self.skip=QCheckBox("如果已经运行则跳过启动（仍检查就绪条件）"); self.skip.setChecked(a.skip_if_running); form.addRow(self.skip)
        self.strategy=QComboBox(); self.strategy.addItems(["立即启动下一个","启动后延迟","等待软件就绪"]); self.strategy.setCurrentIndex(["immediate","delay","ready"].index(a.launch_strategy)); form.addRow("等待策略",self.strategy)
        self.delay=self.spin(0,3600,a.delay_seconds); form.addRow("延迟秒数",self.delay)
        self.kind=QComboBox(); self.kind.addItems(["指定进程","窗口标题","TCP 连接"]); self.kind.setCurrentIndex(["process","window","tcp"].index(a.readiness["kind"])); form.addRow("就绪检测",self.kind)
        self.value=QLineEdit(a.readiness["value"]); self.value.setPlaceholderText("进程名留空则匹配目标路径；窗口必须填关键字"); form.addRow("进程名 / 标题关键字",self.value)
        self.associate=QCheckBox("窗口必须属于目标可执行文件"); self.associate.setChecked(a.readiness.get("associate",False)); form.addRow(self.associate)
        self.host=QLineEdit(a.readiness["host"]); form.addRow("TCP 主机",self.host)
        self.port=self.spin(1,65535,a.readiness["port"],True); form.addRow("TCP 端口",self.port)
        self.timeout=self.spin(.1,3600,a.readiness["timeout"]); form.addRow("最大等待秒数",self.timeout)
        self.interval=self.spin(.1,60,a.readiness["interval"]); form.addRow("检测间隔秒数",self.interval)
        self.failure=QComboBox(); self.failure.addItems(["跳过并继续","停止整个队列","重试后继续"]); self.failure.setCurrentIndex(["continue","stop","retry"].index(a.failure_action)); form.addRow("失败 / 超时处理",self.failure)
        self.retry=self.spin(0,3,a.retry_count,True); form.addRow("重试次数",self.retry)
        self.retry_delay=self.spin(0,3600,a.retry_interval); form.addRow("重试间隔秒数",self.retry_delay)
        note=QLabel("BAT/CMD 使用命令解释器执行，参数中的命令符号也会执行。仅添加可信脚本。TCP 可连接仅表示端口可用。")
        note.setWordWrap(True); layout.addWidget(note)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.button(QDialogButtonBox.Save).setText("保存"); buttons.button(QDialogButtonBox.Cancel).setText("取消")
        buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
    def spin(self,lo,hi,value,integer=False):
        w=QSpinBox() if integer else QDoubleSpinBox(); w.setRange(lo,hi); w.setValue(value); return w
    def browse(self,key):
        path=QFileDialog.getExistingDirectory(self,"选择工作目录") if key=="working_directory" else QFileDialog.getOpenFileName(self,"选择程序","","程序 (*.exe *.lnk *.bat *.cmd)")[0]
        if path:
            self.fields[key].setText(path)
            if key=="path" and not self.fields["name"].text(): self.fields["name"].setText(Path(path).stem); self.fields["working_directory"].setText("" if Path(path).suffix.lower()==".lnk" else str(Path(path).parent))
    def save(self):
        a=self.application
        for key,w in self.fields.items(): setattr(a,key,w.text())
        a.enabled=self.enabled.isChecked(); a.skip_if_running=self.skip.isChecked(); a.launch_strategy=["immediate","delay","ready"][self.strategy.currentIndex()]; a.delay_seconds=self.delay.value()
        a.failure_action=["continue","stop","retry"][self.failure.currentIndex()]; a.retry_count=self.retry.value(); a.retry_interval=self.retry_delay.value()
        a.readiness=dict(kind=["process","window","tcp"][self.kind.currentIndex()],value=self.value.text(),host=self.host.text(),port=self.port.value(),timeout=self.timeout.value(),interval=self.interval.value(),associate=self.associate.isChecked())
        try: a.validate()
        except (ValueError,TypeError) as e: QMessageBox.warning(self,"配置无效",str(e)); return
        self.accept()
