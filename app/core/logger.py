"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
from typing import Any

from app.core.config import get_settings


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        return json.dumps(payload)


def setup_logging() -> None:
    settings = get_settings()
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_format.lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
            )
        )

    root_logger.addHandler(handler)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
