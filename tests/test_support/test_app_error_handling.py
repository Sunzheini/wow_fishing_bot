import logging

import pytest

from support.app_error_handling import AppError, InvalidMonitorError, handle_errors


def test_invalid_monitor_error_is_an_app_error():
    assert issubclass(InvalidMonitorError, AppError)
    assert issubclass(AppError, Exception)


def test_app_error_can_be_raised_and_caught_with_message():
    with pytest.raises(AppError, match="something went wrong"):
        raise AppError("something went wrong")


def test_handle_errors_returns_function_result_when_no_exception():
    @handle_errors()
    def add(a, b):
        return a + b

    assert add(2, 3) == 5


def test_handle_errors_reraises_exception_by_default():
    @handle_errors()
    def boom():
        raise ValueError("boom!")

    with pytest.raises(ValueError, match="boom!"):
        boom()


def test_handle_errors_logs_exception_before_reraising(caplog):
    @handle_errors()
    def boom():
        raise ValueError("boom!")

    with caplog.at_level(logging.ERROR, logger="support.app_error_handling"):
        with pytest.raises(ValueError):
            boom()

    assert any(record.levelname == "ERROR" for record in caplog.records)
    assert any("boom" in record.getMessage() for record in caplog.records)


def test_handle_errors_can_swallow_exception_and_return_default(caplog):
    @handle_errors(reraise=False, default_return="fallback")
    def boom():
        raise RuntimeError("fail")

    with caplog.at_level(logging.ERROR, logger="support.app_error_handling"):
        result = boom()

    assert result == "fallback"
    assert any(record.levelname == "ERROR" for record in caplog.records)


def test_handle_errors_default_return_is_none_when_not_specified():
    @handle_errors(reraise=False)
    def boom():
        raise RuntimeError("fail")

    assert boom() is None


def test_handle_errors_logs_wrapped_function_qualname(caplog):
    @handle_errors(reraise=False)
    def some_descriptive_function_name():
        raise KeyError("x")

    with caplog.at_level(logging.ERROR, logger="support.app_error_handling"):
        some_descriptive_function_name()

    assert any("some_descriptive_function_name" in record.getMessage() for record in caplog.records)


def test_handle_errors_preserves_function_metadata():
    @handle_errors()
    def documented_function():
        """A docstring."""
        return True

    assert documented_function.__name__ == "documented_function"
    assert documented_function.__doc__ == "A docstring."


def test_handle_errors_passes_through_args_and_kwargs():
    @handle_errors()
    def combine(a, b, *, sep="-"):
        return f"{a}{sep}{b}"

    assert combine("x", "y", sep="+") == "x+y"
