from unittest.mock import MagicMock

import pytest

import main as main_module


def test_main_runs_bot_and_always_calls_shutdown(monkeypatch):
    """main() must instantiate FishingBot, call run(), and always call
    shutdown() afterward, even if run() raises."""
    mock_bot = MagicMock()
    monkeypatch.setattr(main_module, "FishingBot", MagicMock(return_value=mock_bot))

    main_module.main()

    mock_bot.run.assert_called_once_with()
    mock_bot.shutdown.assert_called_once()


def test_main_calls_shutdown_even_if_run_raises(monkeypatch):
    """shutdown() must still be called if run() raises an exception."""
    mock_bot = MagicMock()
    mock_bot.run.side_effect = RuntimeError("boom")
    monkeypatch.setattr(main_module, "FishingBot", MagicMock(return_value=mock_bot))

    with pytest.raises(RuntimeError):
        main_module.main()

    mock_bot.shutdown.assert_called_once()
