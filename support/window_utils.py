"""
Windows-only window utilities (pure ctypes, no extra dependency).

Used to bring the WoW window to the foreground before sending
keyboard/mouse input, since input simulated via SendInput still only
reaches whichever window currently has OS focus -- which won't be WoW
if the user is interacting with this app's own GUI (e.g. on a second
monitor) right before starting the bot.
"""

import ctypes

from support.app_logging import get_logger

logger = get_logger(__name__)

_user32 = ctypes.windll.user32

_EnumWindows = _user32.EnumWindows
_EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
_GetWindowTextLengthW = _user32.GetWindowTextLengthW
_GetWindowTextW = _user32.GetWindowTextW
_IsWindowVisible = _user32.IsWindowVisible
_SetForegroundWindow = _user32.SetForegroundWindow


def _get_window_title(hwnd) -> str:
    length = _GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    _GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def focus_window_by_title_substring(title_substring: str) -> bool:
    """
    Finds the first visible top-level window whose title contains
    `title_substring` (case-insensitive) and brings it to the
    foreground. Returns True if a matching window was found and
    focused, False otherwise.
    """
    found_hwnd = []

    def callback(hwnd, _lparam):
        if _IsWindowVisible(hwnd):
            title = _get_window_title(hwnd)
            if title_substring.lower() in title.lower():
                found_hwnd.append(hwnd)
                return False  # stop enumeration
        return True

    _EnumWindows(_EnumWindowsProc(callback), None)

    if not found_hwnd:
        logger.warning("No window found with title containing '%s'; input may not reach the game.",
                        title_substring)
        return False

    _SetForegroundWindow(found_hwnd[0])
    logger.debug("Focused window matching '%s'.", title_substring)
    return True
