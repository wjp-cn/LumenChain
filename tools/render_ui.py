import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import os
os.environ['QT_QPA_PLATFORM']='windows'
from PySide6.QtWidgets import QApplication
from app.services.config_service import ConfigService
from app.ui.main_window import MainWindow
import tempfile
app=QApplication([])
with tempfile.TemporaryDirectory() as directory:
    c=ConfigService(directory);w=MainWindow(c);w.show();app.processEvents();w.grab().save('docs/empty-state.png');w.tray.hide();w.hide()
