from PySide6.QtCore import Qt, QFileInfo
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QToolButton, QDialogButtonBox, QMessageBox, QFileIconProvider,
)


class BatchApplicationDialog(QDialog):
    def __init__(self,parent,profile,remove_callback):
        super().__init__(parent)
        self.profile=profile
        self.remove_callback=remove_callback
        self.setWindowTitle("批量管理 · "+profile.name)
        self.resize(560,480)
        layout=QVBoxLayout(self)
        hint=QLabel("勾选要从当前方案移除的程序。不会卸载软件或关闭已运行的程序。")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        selection=QHBoxLayout(); layout.addLayout(selection)
        self.select_all=QToolButton(); self.select_all.setText("全选")
        self.clear_selection=QToolButton(); self.clear_selection.setText("取消全选")
        self.select_all.clicked.connect(lambda:self.check_all(True))
        self.clear_selection.clicked.connect(lambda:self.check_all(False))
        selection.addWidget(self.select_all); selection.addWidget(self.clear_selection)
        selection.addStretch(); self.count=QLabel(); selection.addWidget(self.count)
        self.list=QListWidget(); self.list.itemChanged.connect(self.update_count)
        layout.addWidget(self.list)
        self.result_label=QLabel(); self.result_label.setWordWrap(True); layout.addWidget(self.result_label)
        footer=QHBoxLayout(); layout.addLayout(footer)
        self.remove_button=QPushButton("移除选中项")
        self.remove_button.setStyleSheet("QPushButton {background:#b94646;color:white;} QPushButton:hover {background:#a03434;} QPushButton:disabled {background:#e3e7ed;color:#8792a2;}")
        self.remove_button.clicked.connect(self.remove_selected)
        footer.addWidget(self.remove_button); footer.addStretch()
        buttons=QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText("关闭")
        buttons.rejected.connect(self.reject); footer.addWidget(buttons)
        self.populate()

    def populate(self):
        self.list.blockSignals(True); self.list.clear()
        icons=QFileIconProvider()
        for application in self.profile.applications:
            item=QListWidgetItem(icons.icon(QFileInfo(application.path)),application.name)
            item.setData(Qt.UserRole,application.id)
            item.setToolTip(application.name+"\n"+application.path)
            item.setFlags(item.flags()|Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list.addItem(item)
        self.list.blockSignals(False)
        self.update_count()

    def checked_ids(self):
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())
                if self.list.item(i).checkState()==Qt.Checked]

    def check_all(self,checked):
        self.list.blockSignals(True)
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.list.blockSignals(False)
        self.update_count()

    def update_count(self,*_):
        count=len(self.checked_ids())
        self.count.setText(f"已选择 {count} / {self.list.count()} 项")
        self.remove_button.setText(f"移除选中项（{count}）" if count else "移除选中项")
        self.remove_button.setEnabled(count>0)
        self.select_all.setEnabled(self.list.count()>0)
        self.clear_selection.setEnabled(count>0)

    def confirm_removal(self,count):
        return QMessageBox.question(self,"确认批量移除",f"从方案“{self.profile.name}”移除选中的 {count} 个程序？\n仅删除方案中的条目，不会删除程序文件、卸载软件或关闭进程。",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)==QMessageBox.Yes

    def remove_selected(self):
        identifiers=self.checked_ids()
        if not identifiers or not self.confirm_removal(len(identifiers)):
            return
        if self.remove_callback(self.profile.id,identifiers):
            self.populate()
            self.result_label.setText(f"已从当前方案移除 {len(identifiers)} 项。")
        else:
            self.result_label.setText("未能保存移除操作，条目已保留，请重试。")
