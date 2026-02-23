"""Structured logging configuration — structlog wrapping stdlib.

Call ``setup_logging()`` once during application startup to configure
both structlog and Python's built-in logging module.

- **json** format: machine-readable, suitable for production / log aggregators.
- **console** format: coloured, human-readable, suitable for development.
"""

from __future__ import annotations

import logging
import sys

import structlog


def setup_logging(
    *,
    level: str = "INFO",
    fmt: str = "json",
) -> None:
    """Configure structlog + stdlib logging.

    Parameters
    ----------
    level : str
        Root log level (``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``).
    fmt : str
        Output format — ``"json"`` or ``"console"``.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Shared processors for both structlog and stdlib
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if fmt == "console":
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Formatter that all stdlib handlers share
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(log_level)

    # Silence noisy third-party loggers
    for name in ("uvicorn.access", "httpcore", "httpx"):
        logging.getLogger(name).setLevel(logging.WARNING)
