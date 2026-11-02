import logging
import shutil
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

import support.app_logging as app_logging_module
from support.app_logging import get_logger
from support.constants import logs_output_dir_name, log_file_name, max_log_file_size_bytes, log_backup_count


@pytest.fixture(autouse=True)
def reset_logging_state():
    """
    Ensures each test configures logging from a clean slate: resets the
    module's "already configured" flag and clears/restores any handlers
    on the root logger, so tests don't leak state into each other.
    """
    app_logging_module._is_configured = False

    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    root_logger.handlers = []

    yield

    for handler in root_logger.handlers:
        handler.close()
    root_logger.handlers = original_handlers
    app_logging_module._is_configured = False


@pytest.fixture(scope="session", autouse=True)
def test_app_logging_teardown():
    """
    Removes the generated logs directory after all tests in this module
    have run. Closes any lingering RotatingFileHandler on the root
    logger first (e.g. one configured at import time by other modules),
    otherwise the log file stays locked and can't be deleted on Windows.
    """
    yield

    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        if isinstance(handler, RotatingFileHandler):
            handler.close()
            root_logger.removeHandler(handler)

    logs_dir = Path(app_logging_module.__file__).parent.parent / logs_output_dir_name
    if logs_dir.exists():
        shutil.rmtree(logs_dir)


def test_get_logger_returns_logger_with_given_name():
    logger = get_logger("my.module")

    assert isinstance(logger, logging.Logger)
    assert logger.name == "my.module"


def test_get_logger_configures_root_logger_with_console_and_file_handlers():
    get_logger(__name__)

    root_logger = logging.getLogger()
    has_console_handler = any(
        type(handler) is logging.StreamHandler for handler in root_logger.handlers
    )
    has_file_handler = any(
        isinstance(handler, RotatingFileHandler) for handler in root_logger.handlers
    )

    assert has_console_handler
    assert has_file_handler


def test_get_logger_only_configures_root_logger_once():
    get_logger(__name__)
    handler_count_after_first_call = len(logging.getLogger().handlers)

    get_logger("some.other.module")
    handler_count_after_second_call = len(logging.getLogger().handlers)

    assert handler_count_after_first_call == handler_count_after_second_call


def test_get_logger_creates_logs_directory():
    get_logger(__name__)

    logs_dir = Path(app_logging_module.__file__).parent.parent / logs_output_dir_name
    assert logs_dir.exists()


def test_rotating_file_handler_uses_configured_constants():
    get_logger(__name__)

    root_logger = logging.getLogger()
    file_handler = next(
        handler for handler in root_logger.handlers if isinstance(handler, RotatingFileHandler)
    )

    assert file_handler.maxBytes == max_log_file_size_bytes
    assert file_handler.backupCount == log_backup_count
    assert Path(file_handler.baseFilename).name == log_file_name


def test_logged_message_is_written_to_log_file():
    logger = get_logger("real_write_test")
    logger.info("hello from test")

    for handler in logging.getLogger().handlers:
        handler.flush()

    logs_dir = Path(app_logging_module.__file__).parent.parent / logs_output_dir_name
    log_file = logs_dir / log_file_name

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "hello from test" in content
