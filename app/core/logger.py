"""Structured JSON logging for observability."""

import logging
import sys

from pythonjsonlogger import jsonlogger


def setup_logger(name: str = "propman", level: int = logging.INFO) -> logging.Logger:
    """Create a structured JSON logger.

    All log entries output as single-line JSON, making them easy to parse
    by log aggregation tools (e.g. Loki, ELK, CloudWatch).
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


logger = setup_logger()
