from unittest.mock import MagicMock, call

import pytest

import core.controls_interaction as controls_interaction_module
from support.constants import fishing_keybind, key_press_duration, mouse_move_duration, \
    reel_click_button, reel_click_modifier_key, reel_modifier_press_delay, reel_click_hold_duration, \
    reel_modifier_release_delay, reel_click_spray_offsets, reel_click_spray_delay, park_mouse_position, \
    wow_window_title_substring


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


@pytest.fixture(autouse=True)
def mock_focus_window(monkeypatch):
    """
    Replaces the real window-focusing call with a MagicMock, so tests
    never actually enumerate/focus windows on the real desktop.
    """
    mock = MagicMock(return_value=True)
    monkeypatch.setattr(controls_interaction_module, "focus_window_by_title_substring", mock)
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


def test_reel_in_bobber_sprays_clicks_around_the_detected_position(objects, mock_pydirectinput, mock_sleep):
    """
    reel_in_bobber() must hold the modifier key once, then try every
    configured nearby offset point (moveTo -> press+release the mouse
    button, with timed delays), finally releasing the modifier key only
    after all spray points have been attempted. This greatly increases
    the odds of landing on WoW's tiny fishing bobber hitbox.
    """
    controls_interaction = objects['controls_interaction']
    position = (123, 456)

    controls_interaction.reel_in_bobber(position)

    expected_spray_moves = [
        call(123 + dx, 456 + dy, duration=mouse_move_duration) for dx, dy in reel_click_spray_offsets
    ]
    # moveTo is also called once more at the end to park the mouse.
    assert mock_pydirectinput.moveTo.call_args_list[:-1] == expected_spray_moves

    mock_pydirectinput.keyDown.assert_called_once_with(reel_click_modifier_key)
    assert mock_pydirectinput.mouseDown.call_count == len(reel_click_spray_offsets)
    assert mock_pydirectinput.mouseUp.call_count == len(reel_click_spray_offsets)
    mock_pydirectinput.mouseDown.assert_called_with(button=reel_click_button)
    mock_pydirectinput.mouseUp.assert_called_with(button=reel_click_button)
    mock_pydirectinput.keyUp.assert_called_once_with(reel_click_modifier_key)

    # keyDown(shift) happens before the first click, keyUp(shift) happens
    # before the final park-mouse moveTo.
    mock_calls = mock_pydirectinput.mock_calls
    assert mock_calls.index(call.keyDown(reel_click_modifier_key)) < \
           mock_calls.index(call.mouseDown(button=reel_click_button))
    assert mock_calls.index(call.keyUp(reel_click_modifier_key)) < mock_calls.index(mock_calls[-1])

    mock_sleep.assert_any_call(reel_modifier_press_delay)
    mock_sleep.assert_any_call(reel_click_hold_duration)
    mock_sleep.assert_any_call(reel_modifier_release_delay)
    mock_sleep.assert_any_call(reel_click_spray_delay)


def test_reel_in_bobber_parks_mouse_after_looting(objects, mock_pydirectinput):
    """
    After successfully looting, reel_in_bobber() must move the mouse to
    the configured park position (out of the way of the water/capture
    area), as the very last action.
    """
    controls_interaction = objects['controls_interaction']

    controls_interaction.reel_in_bobber((123, 456))

    park_x, park_y = park_mouse_position
    mock_pydirectinput.moveTo.assert_called_with(park_x, park_y, duration=mouse_move_duration)
    assert mock_pydirectinput.mock_calls[-1] == call.moveTo(park_x, park_y, duration=mouse_move_duration)


def test_reel_in_bobber_does_not_park_mouse_if_click_fails(objects, mock_pydirectinput):
    """
    If the click sequence fails partway through, the mouse must not be
    parked afterward (the exception propagates before reaching that step).
    """
    controls_interaction = objects['controls_interaction']
    mock_pydirectinput.mouseDown.side_effect = RuntimeError("simulated click failure")

    with pytest.raises(RuntimeError):
        controls_interaction.reel_in_bobber((10, 20))

    park_x, park_y = park_mouse_position
    for call_args in mock_pydirectinput.moveTo.call_args_list:
        assert call_args != call(park_x, park_y, duration=mouse_move_duration)


def test_reel_in_bobber_releases_modifier_key_even_if_click_fails(objects, mock_pydirectinput):
    """
    If pydirectinput.mouseDown() raises, the modifier key must still be
    released afterward (no stuck Shift key), even though the exception
    then propagates (handle_errors default is reraise=True).
    """
    controls_interaction = objects['controls_interaction']
    mock_pydirectinput.mouseDown.side_effect = RuntimeError("simulated click failure")

    with pytest.raises(RuntimeError):
        controls_interaction.reel_in_bobber((10, 20))

    mock_pydirectinput.keyUp.assert_called_once_with(reel_click_modifier_key)


def test_cast_fishing_line_focuses_wow_window_before_pressing_key(objects, mock_focus_window):
    """
    cast_fishing_line() must bring the WoW window to the foreground
    before sending the key press, so input reliably reaches the game
    even if this app's own GUI currently has OS focus.
    """
    controls_interaction = objects['controls_interaction']

    controls_interaction.cast_fishing_line()

    mock_focus_window.assert_called_once_with(wow_window_title_substring)


def test_reel_in_bobber_focuses_wow_window_before_clicking(objects, mock_focus_window):
    """
    reel_in_bobber() must bring the WoW window to the foreground before
    moving the mouse and clicking.
    """
    controls_interaction = objects['controls_interaction']

    controls_interaction.reel_in_bobber((10, 20))

    mock_focus_window.assert_called_once_with(wow_window_title_substring)


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
