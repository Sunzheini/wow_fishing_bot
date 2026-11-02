"""
Centralized logging configuration for the project.

Usage (in any module):
    from support.app_logging import get_logger

    logger = get_logger(__name__)
    logger.info("Something happened")
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from support.constants import log_format, log_date_format, logs_output_dir_name, log_file_name, \
    max_log_file_size_bytes, log_backup_count

_is_configured = False


def _configure_root_logger(level: int = logging.INFO) -> None:
    """
    Configures the root logger with a console handler and a rotating
    file handler (logs/app.log, rotates at 5MB). Safe to call multiple
    times; only configures once.
    """
    global _is_configured
    if _is_configured:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(log_format, datefmt=log_date_format)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    project_root = Path(__file__).parent.parent
    logs_dir = project_root / logs_output_dir_name
    logs_dir.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        logs_dir / log_file_name,
        maxBytes=max_log_file_size_bytes,
        backupCount=log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    _is_configured = True


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Returns a logger configured consistently for the whole project.
    Call once per module with `get_logger(__name__)`.
    """
    _configure_root_logger(level)
    return logging.getLogger(name)
