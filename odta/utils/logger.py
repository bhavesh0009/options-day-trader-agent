import logging
import sys
from datetime import datetime
from pathlib import Path

from odta.constants import IST


def setup_logger(name: str = "odta", log_file: str = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler - create separate log file for each run
    if log_file is None:
        timestamp = datetime.now(IST).strftime("%Y-%m-%d_%H%M%S")
        log_file = f"logs/run_{timestamp}.log"

    try:
        # Ensure logs directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file handler with immediate flushing
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)

        # Force immediate flush after each log (prevents data loss on crash)
        class FlushingFileHandler(logging.FileHandler):
            def emit(self, record):
                super().emit(record)
                self.flush()

        file_handler = FlushingFileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not create file handler for {log_file}: {e}")

    return logger
