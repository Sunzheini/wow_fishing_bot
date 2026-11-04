import time
import tkinter as tk
import uuid

from support.window_utils import focus_window_by_title_substring


def test_returns_false_when_no_window_matches():
    """
    An extremely unlikely title substring should never match any real
    window on the system, so the function must return False (and log a
    warning) instead of raising.
    """
    unique_title = f"definitely-no-such-window-{uuid.uuid4()}"
    assert focus_window_by_title_substring(unique_title) is False


def test_finds_and_focuses_a_real_window_with_matching_title():
    """
    Creates a real, visible Tk window with a unique title and verifies
    focus_window_by_title_substring() finds it and reports success.
    """
    unique_title = f"wow-fishing-bot-test-window-{uuid.uuid4()}"
    root = tk.Tk()
    root.title(unique_title)
    root.geometry("100x50+0+0")
    root.update()  # ensure the window is actually realized/visible to the OS
    time.sleep(0.1)  # give the window manager a moment to register it

    try:
        found = focus_window_by_title_substring(unique_title)
        assert found is True
    finally:
        root.destroy()


def test_match_is_case_insensitive():
    """Title matching must be case-insensitive."""
    unique_title = f"CaseSensitiveTitle-{uuid.uuid4()}"
    root = tk.Tk()
    root.title(unique_title)
    root.geometry("100x50+0+0")
    root.update()
    time.sleep(0.1)

    try:
        found = focus_window_by_title_substring(unique_title.lower())
        assert found is True
    finally:
        root.destroy()


def test_does_not_find_a_destroyed_window():
    """After the window is destroyed, it must no longer be found."""
    unique_title = f"wow-fishing-bot-destroyed-window-{uuid.uuid4()}"
    root = tk.Tk()
    root.title(unique_title)
    root.geometry("100x50+0+0")
    root.update()
    time.sleep(0.1)
    root.destroy()

    assert focus_window_by_title_substring(unique_title) is False
