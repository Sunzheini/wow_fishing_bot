"""
Tkinter frontend for the fishing bot.

Uses only the standard library (tkinter) so it can be frozen into a
single .exe with PyInstaller without extra GUI dependencies.
"""

import queue
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from core.fishing_bot import FishingBot
from core.fishing_state import FishingState
from core.screenshot_capture import ScreenshotCapture
from support.app_logging import get_logger
from support.constants import gui_window_title, gui_window_size, gui_poll_interval_ms, \
    gui_step_color_active, gui_step_color_stopped, gui_step_color_inactive, gui_log_font

logger = get_logger(__name__)

# Order in which the state "steps" are stacked top to bottom in the UI.
FISHING_STEPS_DISPLAY_ORDER = [
    FishingState.IDLE,
    FishingState.CASTING,
    FishingState.WAITING_FOR_BOBBER,
    FishingState.WATCHING_FOR_SPLASH,
    FishingState.REELING,
    FishingState.LOOTING,
    FishingState.STOPPED,
]

STEP_DISPLAY_NAMES = {
    FishingState.IDLE: "Idle",
    FishingState.CASTING: "Casting",
    FishingState.WAITING_FOR_BOBBER: "Waiting for bobber",
    FishingState.WATCHING_FOR_SPLASH: "Watching for splash",
    FishingState.REELING: "Reeling in",
    FishingState.LOOTING: "Looting",
    FishingState.STOPPED: "Stopped",
}


class _QueueLogHandler:
    """A minimal logging.Handler that pushes formatted records into a queue."""

    def __init__(self, log_queue: "queue.Queue[str]"):
        import logging
        self._queue = log_queue

        class _Handler(logging.Handler):
            def emit(_self, record: logging.LogRecord) -> None:
                try:
                    log_queue.put_nowait(_self.format(record))
                except queue.Full:
                    pass

        self.handler = _Handler()
        self.handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s",
                                                      datefmt="%H:%M:%S"))


class FishingBotApp:
    """Main application window: stacked state steps, Start/Stop controls, and a live log panel."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(gui_window_title)
        self.root.geometry(gui_window_size)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.bot: FishingBot | None = None
        self.bot_thread: threading.Thread | None = None
        self.state_queue: "queue.Queue[FishingState]" = queue.Queue()
        self.log_queue: "queue.Queue[str]" = queue.Queue()

        self._attach_log_queue_handler()
        self._build_widgets()
        self._poll_queues()

    # ----- UI construction -------------------------------------------------

    def _build_widgets(self) -> None:
        container = ttk.Frame(self.root, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Fishing Steps", font=("Segoe UI", 11, "bold")).pack(anchor="w")

        steps_frame = ttk.Frame(container)
        steps_frame.pack(fill=tk.X, pady=(5, 10))

        self.step_labels: dict[FishingState, tk.Label] = {}
        for step in FISHING_STEPS_DISPLAY_ORDER:
            label = tk.Label(
                steps_frame,
                text=STEP_DISPLAY_NAMES[step],
                anchor="w",
                padx=8,
                pady=6,
                bg=gui_step_color_inactive,
                relief=tk.RIDGE,
            )
            label.pack(fill=tk.X, pady=2)
            self.step_labels[step] = label

        buttons_frame = ttk.Frame(container)
        buttons_frame.pack(fill=tk.X, pady=(0, 10))

        self.start_button = ttk.Button(buttons_frame, text="Start", command=self._on_start_clicked)
        self.start_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        self.stop_button = ttk.Button(buttons_frame, text="Stop", command=self._on_stop_clicked, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, expand=True, fill=tk.X)

        self.status_label = ttk.Label(container, text="Status: idle", font=("Segoe UI", 9, "italic"))
        self.status_label.pack(anchor="w", pady=(0, 5))

        ttk.Label(container, text="Log", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.log_text = ScrolledText(container, height=12, state=tk.DISABLED, wrap=tk.WORD, font=gui_log_font)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self.clear_log_button = ttk.Button(container, text="Clear Log", command=self._on_clear_log_clicked)
        self.clear_log_button.pack(anchor="e", pady=(5, 0))

        self.clear_screenshots_button = ttk.Button(
            container, text="Clear Screenshots", command=self._on_clear_screenshots_clicked
        )
        self.clear_screenshots_button.pack(anchor="e", pady=(5, 0))

    def _attach_log_queue_handler(self) -> None:
        import logging
        queue_handler = _QueueLogHandler(self.log_queue)
        logging.getLogger().addHandler(queue_handler.handler)

    # ----- Button handlers ---------------------------------------------------

    def _on_start_clicked(self) -> None:
        if self.bot_thread is not None and self.bot_thread.is_alive():
            return  # already running

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_label.config(text="Status: running")
        self._reset_step_highlights()

        self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self.bot_thread.start()

    def _on_stop_clicked(self) -> None:
        if self.bot is not None:
            self.bot.request_stop()
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: stopping...")

    def _on_clear_log_clicked(self) -> None:
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _on_clear_screenshots_clicked(self) -> None:
        """
        Manually deletes saved screenshots. This is the ONLY way
        screenshots ever get deleted -- never automatically -- since
        they're the main debugging aid for detection failures.
        """
        ScreenshotCapture().clear_screenshots()

    def _on_close(self) -> None:
        if self.bot is not None:
            self.bot.request_stop()
        if self.bot_thread is not None and self.bot_thread.is_alive():
            self.bot_thread.join(timeout=3)
        if self.bot is not None:
            self.bot.shutdown()
        self.root.destroy()

    # ----- Background thread --------------------------------------------------

    def _run_bot(self) -> None:
        try:
            self.bot = FishingBot()
            self.bot.run(on_state_change=self.state_queue.put)
        except Exception:
            logger.exception("Fishing bot crashed.")
        finally:
            if self.bot is not None:
                self.bot.shutdown()
            self.root.after(0, self._on_bot_finished)

    def _on_bot_finished(self) -> None:
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="Status: stopped")

    # ----- Polling (runs on the main/UI thread) --------------------------------

    def _poll_queues(self) -> None:
        self._drain_state_queue()
        self._drain_log_queue()
        self.root.after(gui_poll_interval_ms, self._poll_queues)

    def _drain_state_queue(self) -> None:
        latest_state = None
        try:
            while True:
                latest_state = self.state_queue.get_nowait()
        except queue.Empty:
            pass
        if latest_state is not None:
            self._highlight_step(latest_state)

    def _drain_log_queue(self) -> None:
        lines = []
        try:
            while True:
                lines.append(self.log_queue.get_nowait())
        except queue.Empty:
            pass
        if lines:
            self.log_text.config(state=tk.NORMAL)
            for line in lines:
                self.log_text.insert(tk.END, line + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)

    def _reset_step_highlights(self) -> None:
        for label in self.step_labels.values():
            label.config(bg=gui_step_color_inactive)

    def _highlight_step(self, state: FishingState) -> None:
        self._reset_step_highlights()
        color = gui_step_color_stopped if state == FishingState.STOPPED else gui_step_color_active
        self.step_labels[state].config(bg=color)


def main() -> None:
    root = tk.Tk()
    FishingBotApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
