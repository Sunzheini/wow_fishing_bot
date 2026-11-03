from unittest.mock import MagicMock, call

import pytest

import core.controls_interaction as controls_interaction_module
from support.constants import fishing_keybind, key_press_duration, mouse_move_duration, \
    reel_click_button, reel_click_modifier_key


@pytest.fixture(autouse=True)
def mock_pydirectinput(monkeypatch):
    """
    Replaces pydirectinput with a MagicMock for every test in this module,
    so no real keyboard/mouse input is ever sent during tests.
    """
    mock = MagicMock()
    monkeypatch.setattr(controls_interaction_module, "pydirectinput", mock)
    return mock


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    """Avoids real delays from time.sleep() during tests."""
    mock = MagicMock()
    monkeypatch.setattr(controls_interaction_module.time, "sleep", mock)
    return mock


def test_cast_fishing_line_presses_and_releases_the_configured_key(objects, mock_pydirectinput, mock_sleep):
    """
    cast_fishing_line() must press down the configured fishing keybind,
    hold it for key_press_duration, then release it -- in that order.
    """
    controls_interaction = objects['controls_interaction']

    controls_interaction.cast_fishing_line()

    mock_pydirectinput.keyDown.assert_called_once_with(fishing_keybind)
    mock_sleep.assert_called_once_with(key_press_duration)
    mock_pydirectinput.keyUp.assert_called_once_with(fishing_keybind)

    # Verify strict ordering: keyDown -> sleep -> keyUp
    assert mock_pydirectinput.mock_calls.index(call.keyDown(fishing_keybind)) < \
           mock_pydirectinput.mock_calls.index(call.keyUp(fishing_keybind))


def test_reel_in_bobber_moves_mouse_then_shift_right_clicks(objects, mock_pydirectinput):
    """
    reel_in_bobber() must move the mouse to the given position, hold the
    modifier key (shift), right-click, then release the modifier key --
    all in the correct order.
    """
    controls_interaction = objects['controls_interaction']
    position = (123, 456)

    controls_interaction.reel_in_bobber(position)

    mock_pydirectinput.moveTo.assert_called_once_with(123, 456, duration=mouse_move_duration)
    mock_pydirectinput.keyDown.assert_called_once_with(reel_click_modifier_key)
    mock_pydirectinput.click.assert_called_once_with(button=reel_click_button)
    mock_pydirectinput.keyUp.assert_called_once_with(reel_click_modifier_key)

    call_order = [c[0] for c in mock_pydirectinput.method_calls]
    assert call_order == ["moveTo", "keyDown", "click", "keyUp"]


def test_reel_in_bobber_releases_modifier_key_even_if_click_fails(objects, mock_pydirectinput):
    """
    If pydirectinput.click() raises, the modifier key must still be
    released afterward (no stuck Shift key), even though the exception
    then propagates (handle_errors default is reraise=True).
    """
    controls_interaction = objects['controls_interaction']
    mock_pydirectinput.click.side_effect = RuntimeError("simulated click failure")

    with pytest.raises(RuntimeError):
        controls_interaction.reel_in_bobber((10, 20))

    mock_pydirectinput.keyUp.assert_called_once_with(reel_click_modifier_key)


def test_cast_fishing_line_propagates_errors_via_handle_errors(objects, mock_pydirectinput):
    """
    Any underlying pydirectinput failure should propagate out of
    cast_fishing_line() (handle_errors default reraise=True), rather
    than being silently swallowed.
    """
    controls_interaction = objects['controls_interaction']
    mock_pydirectinput.keyDown.side_effect = OSError("simulated input failure")

    with pytest.raises(OSError):
        controls_interaction.cast_fishing_line()
