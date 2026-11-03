"""
Centralized error handling utilities for the project.

Usage (in any module):
    from support.app_error_handling import AppError, handle_errors

    class MyInvalidThingError(AppError):
        pass

    @handle_errors()
    def do_something():
        ...
"""

import functools
from typing import Callable, TypeVar

from support.app_logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class AppError(Exception):
    """Base exception class for all application-specific errors."""
    pass


class InvalidMonitorError(AppError):
    """Raised when an invalid monitor number/index is requested."""
    pass


class TemplateNotFoundError(AppError):
    """Raised when a required template image can't be loaded from disk."""
    pass


def handle_errors(reraise: bool = True, default_return: T = None) -> Callable:
    """
    Decorator that logs any exception raised inside the wrapped function
    with full traceback, and either re-raises it (default) or swallows
    it and returns `default_return` instead.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as error:
                logger.exception("Error in %s: %s", func.__qualname__, error)
                if reraise:
                    raise
                return default_return
        return wrapper
    return decorator
