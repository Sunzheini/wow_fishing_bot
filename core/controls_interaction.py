import time

import pydirectinput

from support.app_error_handling import handle_errors
from support.app_logging import get_logger
from support.constants import fishing_keybind, key_press_duration, mouse_move_duration, reel_click_button, \
    reel_click_modifier_key

logger = get_logger(__name__)


class ControlsInteraction:
    """
    Sends real keyboard/mouse input to interact with the game.

    Uses pydirectinput (Windows SendInput-based) instead of a plain
    automation library like pyautogui, since many games (including WoW)
    ignore synthetic input that isn't sent via SendInput.
    """

    @handle_errors()
    def cast_fishing_line(self) -> None:
        """Presses the configured fishing keybind to cast the line."""
        logger.info("Casting fishing line (key=%s)", fishing_keybind)
        pydirectinput.keyDown(fishing_keybind)
        time.sleep(key_press_duration)
        pydirectinput.keyUp(fishing_keybind)

    @handle_errors()
    def reel_in_bobber(self, bobber_position: tuple[int, int]) -> None:
        """
        Moves the mouse to `bobber_position` (absolute screen
        coordinates) and shift+right-clicks it -- WoW's auto-loot click,
        which reels in the catch and loots it in a single action.
        """
        x, y = bobber_position
        logger.info("Reeling in (and auto-looting) bobber at (%d, %d)", x, y)
        pydirectinput.moveTo(x, y, duration=mouse_move_duration)
        pydirectinput.keyDown(reel_click_modifier_key)
        try:
            pydirectinput.click(button=reel_click_button)
        finally:
            pydirectinput.keyUp(reel_click_modifier_key)
