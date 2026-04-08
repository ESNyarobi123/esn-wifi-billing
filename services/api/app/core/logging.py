import logging
import sys
from typing import Any

_LOG_FMT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        root.setLevel(getattr(logging, level.upper(), logging.INFO))
        return
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format=_LOG_FMT, stream=sys.stdout)


def log_extra(logger: logging.Logger, level: int, msg: str, **kwargs: Any) -> None:
    """Attach structured context (router_id=..., task=...) to a single log line."""
    if kwargs:
        suffix = " ".join(f"{k}={v!r}" for k, v in kwargs.items())
        msg = f"{msg} | {suffix}"
    logger.log(level, msg)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
