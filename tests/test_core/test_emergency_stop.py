from unittest.mock import MagicMock

import pytest

import core.emergency_stop as emergency_stop_module
from core.emergency_stop import EmergencyStop
from support.constants import emergency_stop_hotkey


@pytest.fixture(autouse=True)
def mock_keyboard(monkeypatch):
    """
    Replaces the `keyboard` module with a MagicMock for every test in
    this module, so no real global keyboard hook is ever installed
    during tests.
    """
    mock = MagicMock()
    monkeypatch.setattr(emergency_stop_module, "keyboard", mock)
    return mock


def test_init_registers_the_configured_hotkey(mock_keyboard):
    """__init__ must register a hotkey callback for emergency_stop_hotkey."""
    EmergencyStop()

    assert mock_keyboard.add_hotkey.call_count == 1
    registered_hotkey, callback = mock_keyboard.add_hotkey.call_args[0]
    assert registered_hotkey == emergency_stop_hotkey
    assert callable(callback)


def test_is_stop_requested_is_false_initially(mock_keyboard):
    """Before the hotkey is pressed, is_stop_requested() must be False."""
    emergency_stop = EmergencyStop()
    assert emergency_stop.is_stop_requested() is False


def test_pressing_hotkey_sets_stop_requested(mock_keyboard):
    """
    Simulates the hotkey being pressed by invoking the callback that was
    registered with keyboard.add_hotkey, and checks the flag flips to True.
    """
    emergency_stop = EmergencyStop()

    _, callback = mock_keyboard.add_hotkey.call_args[0]
    callback()

    assert emergency_stop.is_stop_requested() is True


def test_reset_clears_the_stop_flag(mock_keyboard):
    """reset() must clear a previously-requested stop."""
    emergency_stop = EmergencyStop()
    _, callback = mock_keyboard.add_hotkey.call_args[0]
    callback()
    assert emergency_stop.is_stop_requested() is True

    emergency_stop.reset()

    assert emergency_stop.is_stop_requested() is False


def test_stop_listening_removes_the_hotkey(mock_keyboard):
    """stop_listening() must unregister the configured hotkey."""
    emergency_stop = EmergencyStop()

    emergency_stop.stop_listening()

    mock_keyboard.remove_hotkey.assert_called_once_with(emergency_stop_hotkey)


def test_stop_listening_does_not_raise_if_hotkey_already_removed(mock_keyboard):
    """
    If the hotkey was already removed (or never successfully registered),
    stop_listening() must not raise.
    """
    mock_keyboard.remove_hotkey.side_effect = KeyError("not found")
    emergency_stop = EmergencyStop()

    emergency_stop.stop_listening()  # should not raise
