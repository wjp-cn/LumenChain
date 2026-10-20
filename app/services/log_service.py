import logging, threading
from logging.handlers import RotatingFileHandler

class BatchFilter(logging.Filter):
    def filter(self, record):
        record.run_id = getattr(threading.current_thread(), "launchflow_batch", "系统")
        return True

def setup(root):
    logger = logging.getLogger("LaunchFlow"); logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(root / "logs" / "launchflow.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    handler.addFilter(BatchFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [批次:%(run_id)s] %(message)s")); logger.addHandler(handler)
    return logger
