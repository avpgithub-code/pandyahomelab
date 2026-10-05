"""Human-readable logging: one file per UTC day in CRICSTAT_LOG_DIR, plus stderr.

stdout is reserved for the single-line JSON run summary, so logs never go there.
"""
import logging
import os
import sys
import time

LOGGER_NAME = "cricstat"
_FORMAT = "%(asctime)sZ %(levelname)-7s %(name)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _formatter():
    fmt = logging.Formatter(_FORMAT, _DATEFMT)
    fmt.converter = time.gmtime
    return fmt


def setup_logging(log_dir, level="INFO", quiet=False):
    """Attach the dated file handler and the stderr handler. Returns the log file path."""
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, "ingest-%s.log" % time.strftime("%Y%m%d", time.gmtime()))
    root = logging.getLogger(LOGGER_NAME)
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()
    root.setLevel(level)
    root.propagate = False

    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(_formatter())
    root.addHandler(file_handler)

    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(_formatter())
    stream.setLevel(logging.WARNING if quiet else level)
    root.addHandler(stream)
    return path


def get_logger(name: str) -> logging.Logger:
    """Child logger under the cricstat namespace."""
    return logging.getLogger("%s.%s" % (LOGGER_NAME, name))
