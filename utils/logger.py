"""
utils/logger.py — Centralized logging with Qt signal emission
"""

import logging
import sys
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal


class _QtLogHandler(logging.Handler, QObject):
    """Forwards log records to a Qt signal."""
    log_emitted = pyqtSignal(str, str)   # level, message

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record: logging.LogRecord):
        msg = self.format(record)
        self.log_emitted.emit(record.levelname, msg)


# ── Singleton Qt handler (attached once) ─────────────────────────────────────
_qt_handler: Optional[_QtLogHandler] = None


def get_qt_handler() -> _QtLogHandler:
    global _qt_handler
    if _qt_handler is None:
        _qt_handler = _QtLogHandler()
        _qt_handler.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                              datefmt="%H:%M:%S"))
    return _qt_handler


def get_logger(name: str = "spaque") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        # Console
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(
            logging.Formatter("%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
                              datefmt="%H:%M:%S"))
        logger.addHandler(console)
        # Qt handler
        logger.addHandler(get_qt_handler())
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
    return logger
