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


def enable_dpi_awareness() -> None:
    """
    Declares this process as DPI-aware so Win32 input APIs (used by
    pydirectinput for mouse movement/clicks) operate in real physical
    screen pixels -- the same coordinate space mss uses when capturing
    screenshots and that ObjectDetection computes bobber/splash
    positions in.

    Without this, on any display with Windows scaling enabled (e.g.
    125%, 150%), a non-DPI-aware process has its mouse coordinates
    silently rescaled by Windows before being delivered, causing a
    systematic offset between where the bot *thinks* it's clicking
    (the real bobber position, in physical pixels) and where the click
    *actually* lands on screen. This is consistent (not random) and can
    easily be just enough to miss the bobber's small clickable area
    every single time, even though keyboard input (casting) and screen
    capture (detection) are unaffected and keep working correctly.

    Must be called once, as early as possible at process startup,
    before any screenshots are captured or input is sent.
    """
    try:
        # Windows 10 1703+: per-monitor v2 (best accuracy on mixed-DPI setups)
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        logger.debug("DPI awareness enabled (per-monitor v2).")
        return
    except (AttributeError, OSError):
        pass
    try:
        # Windows 8.1+: per-monitor v1
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        logger.debug("DPI awareness enabled (per-monitor v1).")
        return
    except (AttributeError, OSError):
        pass
    try:
        # Windows Vista+: system DPI aware (fallback for older Windows)
        ctypes.windll.user32.SetProcessDPIAware()
        logger.debug("DPI awareness enabled (system-wide fallback).")
    except (AttributeError, OSError):
        logger.warning("Could not enable DPI awareness; mouse clicks may be misaligned on scaled displays.")


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
