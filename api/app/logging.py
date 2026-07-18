import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import structlog
from concurrent_log_handler import ConcurrentRotatingFileHandler

from api.app.config import Settings

EventProcessor = Callable[[Any, str, dict[str, Any]], dict[str, Any]]


def _add_service(service: str) -> EventProcessor:
    def add_service(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
        event_dict.setdefault("service", service)
        return event_dict

    return add_service


def _handlers(settings: Settings, formatter: logging.Formatter) -> list[logging.Handler]:
    terminal = logging.StreamHandler(sys.stdout)
    terminal.setFormatter(formatter)
    handlers: list[logging.Handler] = [terminal]

    if settings.log_file:
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = ConcurrentRotatingFileHandler(
            log_path,
            maxBytes=settings.log_max_bytes,
            backupCount=settings.log_backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    return handlers


def configure_logging(settings: Settings, service: str) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    shared_processors: list[EventProcessor] = [
        structlog.contextvars.merge_contextvars,
        _add_service(service),
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )
    logging.basicConfig(
        handlers=_handlers(settings, formatter),
        level=level,
        force=True,
    )
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "arq"):
        named_logger = logging.getLogger(logger_name)
        named_logger.handlers.clear()
        named_logger.propagate = True
    for logger_name in ("httpx", "httpcore", "deepgram", "urllib3"):
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
