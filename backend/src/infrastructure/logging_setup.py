"""Configuración central de logging para LARIA (infraestructura)."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Formato NDJSON apto para agregadores; sin secretos."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra_fields") and isinstance(record.extra_fields, dict):
            payload.update(record.extra_fields)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    """Idempotente: configura el root logger una sola vez."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.handlers.clear()
    numeric = getattr(logging, (level or "INFO").upper(), logging.INFO)
    root.setLevel(numeric)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric)
    if (fmt or "text").lower() == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
    root.addHandler(handler)

    # Ruido de librerías
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    _CONFIGURED = True
    logging.getLogger("laria").info(
        "logging configured level=%s format=%s", level, fmt
    )


def reset_logging_for_tests() -> None:
    """Solo tests: permite reconfigurar."""
    global _CONFIGURED
    _CONFIGURED = False
    root = logging.getLogger()
    root.handlers.clear()


def log_event(logger: logging.Logger, level: int, message: str, **fields) -> None:
    """Emite un log con campos estructurados opcionales."""
    record = logger.makeRecord(
        logger.name,
        level,
        "(laria)",
        0,
        message,
        args=(),
        exc_info=None,
    )
    record.extra_fields = fields
    logger.handle(record)
