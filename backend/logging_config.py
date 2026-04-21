"""Structured logging configuration using structlog."""

import logging

import structlog


def configure_logging(debug: bool = False) -> None:
    """Configure structlog for JSON or console output."""
    level = logging.DEBUG if debug else logging.INFO

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer() if debug else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
    )

    logging.basicConfig(format="%(message)s", level=level, force=True)
