import logging
import sys
from datetime import datetime

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
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except FileNotFoundError:
        pass  # logs/ directory might not exist yet

    return logger
