"""stderr logging (the container's json-file driver keeps it); one line per event."""
import logging
import sys
import time


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger("cricstat")
    if root.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    fmt = logging.Formatter("%(asctime)sZ %(levelname)-7s %(name)s: %(message)s",
                            "%Y-%m-%d %H:%M:%S")
    fmt.converter = time.gmtime
    handler.setFormatter(fmt)
    root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger("cricstat.api.%s" % name)
