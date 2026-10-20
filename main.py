import argparse, sys, logging
from app.services.config_service import ConfigService
from app.services.log_service import setup

def main():
    parser=argparse.ArgumentParser(description="光启 LumenChain")
    parser.add_argument("--autostart",action="store_true");parser.add_argument("--profile");parser.add_argument("--minimized",action="store_true");parser.add_argument("--smoke-test",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--smoke-timeout",type=int,default=5000,help=argparse.SUPPRESS)
    args=parser.parse_args()
    from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
    from PySide6.QtCore import QTimer, QTranslator, QLibraryInfo, QLocale
    app=QApplication(sys.argv);app.setApplicationName("LaunchFlow");app.setApplicationDisplayName("光启 LumenChain");app.setQuitOnLastWindowClosed(False)
    translator=QTranslator(app)
    QLocale.setDefault(QLocale("zh_CN"))
    translator.load("qtbase_zh_CN",QLibraryInfo.path(QLibraryInfo.TranslationsPath))
    app.installTranslator(translator)
    try:
        config=ConfigService();logger=setup(config.root)
        def exception_hook(kind,value,tb):
            logger.error("未处理异常",exc_info=(kind,value,tb));QMessageBox.critical(None,"发生错误",str(value))
        sys.excepthook=exception_hook
        from app.core.single_instance import SingleInstance
        instance=SingleInstance(config.root)
        if not instance.acquire(vars(args)):return 0
        from app.ui.main_window import MainWindow
        window=MainWindow(config)
        def handle(request,initial=False):
            if not initial:window.reveal()
            profile_id=request.get("profile")
            autostart=request.get("autostart",False)
            if autostart and config.settings["startup"] and config.settings["auto_run"]:profile_id=profile_id or config.settings["default_profile"]
            if profile_id:
                profile=next((p for p in config.profiles if p.id==profile_id),None)
                if not profile:window.status.setText("指定方案不存在，请在设置中重新选择。");window.reveal();return
                if autostart:
                    if window.pending or window.scheduler.active is not None:window.status.setText("当前已有方案正在启动或等待启动。");window.reveal();return
                    window.pending=True;window.sync_launch_controls();window.status.setText(f"开机方案将在 {config.settings['startup_delay']} 秒后启动，点击“取消倒计时”可取消。")
                    window.pending_token+=1
                    token=window.pending_token
                    def execute():
                        if window.pending and token==window.pending_token:
                            window.pending=False
                            window.sync_launch_controls()
                            current=next((p for p in config.profiles if p.id==profile_id),None)
                            window.start(current,scheduled=True)
                    QTimer.singleShot(config.settings["startup_delay"]*1000,execute)
                else:window.start(profile)
            if initial and (not request.get("minimized") or not QSystemTrayIcon.isSystemTrayAvailable()):window.reveal()
        instance.request.connect(handle)
        QTimer.singleShot(0,lambda:handle(vars(args),True))
        if config.warnings:QTimer.singleShot(100,lambda:QMessageBox.warning(window,"配置恢复提示","\n".join(config.warnings)))
        if config.settings["startup"]:
            from app.core import startup_manager
            if startup_manager.current()!=startup_manager.command():
                QTimer.singleShot(200,lambda:QMessageBox.warning(window,"开机启动路径已变化","请打开设置并保存，以修复当前 EXE 的开机启动路径。"))
        if args.smoke_test:QTimer.singleShot(max(1000,args.smoke_timeout),window.quit)
        logger.info("启动编排器已启动")
        return app.exec()
    except Exception as e:
        logging.getLogger("LaunchFlow").exception("初始化失败");QMessageBox.critical(None,"启动失败",str(e));return 1
if __name__=="__main__":sys.exit(main())
