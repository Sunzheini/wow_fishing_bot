import time

import pydirectinput

from support.app_error_handling import handle_errors
from support.app_logging import get_logger
from support.constants import fishing_keybind, key_press_duration, mouse_move_duration, reel_click_button, \
    reel_click_modifier_key, reel_modifier_press_delay, reel_click_hold_duration, reel_modifier_release_delay, \
    reel_click_spray_offsets, reel_click_spray_delay, park_mouse_after_reel, park_mouse_position, \
    wow_window_title_substring
from support.window_utils import focus_window_by_title_substring

logger = get_logger(__name__)


class ControlsInteraction:
    """
    Sends real keyboard/mouse input to interact with the game.

    Uses pydirectinput (Windows SendInput-based) instead of a plain
    automation library like pyautogui, since many games (including WoW)
    ignore synthetic input that isn't sent via SendInput.

    Before every action, the WoW window is brought to the foreground:
    input simulated via SendInput still only reaches whichever window
    currently holds OS focus, which won't be WoW if the user was just
    interacting with this app's own GUI (e.g. on a second monitor).
    """

    @handle_errors()
    def cast_fishing_line(self) -> None:
        """Presses the configured fishing keybind to cast the line."""
        focus_window_by_title_substring(wow_window_title_substring)
        logger.info("Casting fishing line (key=%s)", fishing_keybind)
        pydirectinput.keyDown(fishing_keybind)
        time.sleep(key_press_duration)
        pydirectinput.keyUp(fishing_keybind)

    @handle_errors()
    def reel_in_bobber(self, bobber_position: tuple[int, int]) -> None:
        """
        Shift+right-clicks `bobber_position` (absolute screen
        coordinates) -- WoW's auto-loot click, which reels in the catch
        and loots it in a single action.

        WoW's clickable hitbox for the fishing bobber is notoriously
        tiny, while `bobber_position` is only the center of a visual
        template match and can be a few pixels off from the real
        interactable point. Instead of a single click, this tries
        several nearby points in a small cross/grid pattern
        (`reel_click_spray_offsets`) around the detected position --
        any click that misses just lands harmlessly on water, but this
        greatly increases the odds that at least one click actually
        lands on the bobber.

        The modifier key is held for a short delay before, during, and
        after each click (instead of an instant click()) because some
        games poll modifier key state and can otherwise miss a
        just-pressed Shift.

        After looting, the mouse is parked out of the way (see
        `park_mouse_after_reel` / `park_mouse_position`) so the cursor
        doesn't linger over the water, keeping it clear of the capture
        area for the next screenshot.
        """
        focus_window_by_title_substring(wow_window_title_substring)
        x, y = bobber_position
        logger.info("Reeling in (and auto-looting) bobber at (%d, %d), trying %d nearby click points",
                    x, y, len(reel_click_spray_offsets))

        pydirectinput.keyDown(reel_click_modifier_key)
        try:
            for offset_index, (dx, dy) in enumerate(reel_click_spray_offsets):
                target_x, target_y = x + dx, y + dy
                pydirectinput.moveTo(target_x, target_y, duration=mouse_move_duration)
                time.sleep(reel_modifier_press_delay)
                pydirectinput.mouseDown(button=reel_click_button)
                time.sleep(reel_click_hold_duration)
                pydirectinput.mouseUp(button=reel_click_button)
                time.sleep(reel_modifier_release_delay)

                if offset_index < len(reel_click_spray_offsets) - 1:
                    time.sleep(reel_click_spray_delay)
        finally:
            pydirectinput.keyUp(reel_click_modifier_key)

        if park_mouse_after_reel:
            park_x, park_y = park_mouse_position
            logger.debug("Parking mouse at (%d, %d) after looting.", park_x, park_y)
            pydirectinput.moveTo(park_x, park_y, duration=mouse_move_duration)

