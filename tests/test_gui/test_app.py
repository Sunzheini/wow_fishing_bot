import logging
import tkinter as tk

import pytest

import gui.app as gui_app_module
from core.fishing_state import FishingState
from gui.app import FishingBotApp, FISHING_STEPS_DISPLAY_ORDER
from support.constants import gui_step_color_active, gui_step_color_stopped, gui_step_color_inactive


class FakeFishingBot:
    """A lightweight stand-in for core.fishing_bot.FishingBot used in GUI tests."""

    instances = []

    def __init__(self):
        self.request_stop_called = False
        self.shutdown_called = False
        self.run_called_with_callback = None
        FakeFishingBot.instances.append(self)

    def run(self, on_state_change=None):
        self.run_called_with_callback = on_state_change
        if on_state_change is not None:
            on_state_change(FishingState.IDLE)
            on_state_change(FishingState.CASTING)

    def request_stop(self):
        self.request_stop_called = True

    def shutdown(self):
        self.shutdown_called = True


@pytest.fixture(autouse=True)
def reset_fake_bot_instances():
    FakeFishingBot.instances.clear()
    yield
    FakeFishingBot.instances.clear()


@pytest.fixture
def root():
    tk_root = tk.Tk()
    yield tk_root
    try:
        tk_root.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def app(root):
    root_logger = logging.getLogger()
    handlers_before = list(root_logger.handlers)

    application = FishingBotApp(root)

    yield application

    # Remove any logging handler this app instance attached, so it
    # doesn't leak into other tests.
    for handler in list(root_logger.handlers):
        if handler not in handlers_before:
            root_logger.removeHandler(handler)


def run_mainloop_briefly(app: FishingBotApp, duration_ms: int = 500) -> None:
    """
    Runs the real Tk mainloop for a short, bounded time.

    Needed because Tkinter only allows a background thread to call
    root.after() safely while mainloop() is actively running in the main
    thread; without this, FishingBotApp._run_bot()'s root.after(0, ...)
    call raises "main thread is not in main loop".
    """
    app.root.after(duration_ms, app.root.quit)
    app.root.mainloop()


# ----- Initial state -----------------------------------------------------

def test_initial_ui_state(app):
    assert str(app.start_button["state"]) == "normal"
    assert str(app.stop_button["state"]) == "disabled"
    assert app.status_label["text"] == "Status: idle"
    for label in app.step_labels.values():
        assert label["bg"] == gui_step_color_inactive


def test_all_fishing_states_have_a_step_label(app):
    assert set(app.step_labels.keys()) == set(FISHING_STEPS_DISPLAY_ORDER)
    assert len(FISHING_STEPS_DISPLAY_ORDER) == len(FishingState)


# ----- Step highlighting ---------------------------------------------------

def test_highlight_step_colors_only_the_given_step(app):
    app._highlight_step(FishingState.CASTING)

    assert app.step_labels[FishingState.CASTING]["bg"] == gui_step_color_active
    for state, label in app.step_labels.items():
        if state != FishingState.CASTING:
            assert label["bg"] == gui_step_color_inactive


def test_highlight_step_uses_stopped_color_for_stopped_state(app):
    app._highlight_step(FishingState.STOPPED)

    assert app.step_labels[FishingState.STOPPED]["bg"] == gui_step_color_stopped


def test_highlight_step_switches_highlight_between_calls(app):
    app._highlight_step(FishingState.IDLE)
    app._highlight_step(FishingState.REELING)

    assert app.step_labels[FishingState.IDLE]["bg"] == gui_step_color_inactive
    assert app.step_labels[FishingState.REELING]["bg"] == gui_step_color_active


def test_reset_step_highlights_clears_all_steps(app):
    app._highlight_step(FishingState.WATCHING_FOR_SPLASH)

    app._reset_step_highlights()

    for label in app.step_labels.values():
        assert label["bg"] == gui_step_color_inactive


# ----- Queue draining -------------------------------------------------------

def test_drain_state_queue_highlights_the_latest_state_only(app):
    app.state_queue.put(FishingState.IDLE)
    app.state_queue.put(FishingState.CASTING)
    app.state_queue.put(FishingState.WAITING_FOR_BOBBER)

    app._drain_state_queue()

    assert app.step_labels[FishingState.WAITING_FOR_BOBBER]["bg"] == gui_step_color_active
    assert app.step_labels[FishingState.IDLE]["bg"] == gui_step_color_inactive
    assert app.step_labels[FishingState.CASTING]["bg"] == gui_step_color_inactive
    assert app.state_queue.empty()


def test_drain_state_queue_does_nothing_when_empty(app):
    app._highlight_step(FishingState.REELING)

    app._drain_state_queue()  # queue is empty; must not reset the highlight

    assert app.step_labels[FishingState.REELING]["bg"] == gui_step_color_active


def test_drain_log_queue_appends_lines_to_log_widget(app):
    app.log_queue.put("first log line")
    app.log_queue.put("second log line")

    app._drain_log_queue()

    content = app.log_text.get("1.0", tk.END)
    assert "first log line" in content
    assert "second log line" in content
    assert app.log_queue.empty()


def test_drain_log_queue_leaves_widget_disabled_afterward(app):
    app.log_queue.put("some line")

    app._drain_log_queue()

    assert str(app.log_text["state"]) == "disabled"


def test_clear_log_button_empties_the_log_widget(app):
    app.log_queue.put("some line that should disappear")
    app._drain_log_queue()
    assert "some line that should disappear" in app.log_text.get("1.0", tk.END)

    app._on_clear_log_clicked()

    assert app.log_text.get("1.0", tk.END).strip() == ""


def test_clear_log_leaves_widget_disabled_afterward(app):
    app._on_clear_log_clicked()
    assert str(app.log_text["state"]) == "disabled"


def test_clear_log_does_not_affect_future_log_lines(app):
    app._on_clear_log_clicked()

    app.log_queue.put("a brand new line")
    app._drain_log_queue()

    assert "a brand new line" in app.log_text.get("1.0", tk.END)


# ----- Start/Stop button behavior -------------------------------------------

def test_on_start_clicked_disables_start_and_enables_stop(app, monkeypatch):
    monkeypatch.setattr(gui_app_module, "FishingBot", FakeFishingBot)

    app._on_start_clicked()

    assert str(app.start_button["state"]) == "disabled"
    assert str(app.stop_button["state"]) == "normal"
    assert app.status_label["text"] == "Status: running"

    run_mainloop_briefly(app)  # let the background thread finish and call root.after(0, ...)


def test_on_start_clicked_runs_bot_and_eventually_resets_buttons(app, monkeypatch):
    monkeypatch.setattr(gui_app_module, "FishingBot", FakeFishingBot)

    app._on_start_clicked()
    run_mainloop_briefly(app)

    assert str(app.start_button["state"]) == "normal"
    assert str(app.stop_button["state"]) == "disabled"
    assert app.status_label["text"] == "Status: stopped"

    assert len(FakeFishingBot.instances) == 1
    fake_bot = FakeFishingBot.instances[0]
    assert fake_bot.shutdown_called is True


def test_on_start_clicked_ignores_second_click_while_already_running(app, monkeypatch):
    class SlowFakeBot(FakeFishingBot):
        def run(self, on_state_change=None):
            import time
            time.sleep(0.3)

    monkeypatch.setattr(gui_app_module, "FishingBot", SlowFakeBot)

    app._on_start_clicked()
    first_thread = app.bot_thread

    app._on_start_clicked()  # should be a no-op since first_thread is still alive

    assert app.bot_thread is first_thread
    assert len(SlowFakeBot.instances) == 1

    run_mainloop_briefly(app, duration_ms=600)


def test_on_stop_clicked_requests_stop_on_the_bot(app):
    fake_bot = FakeFishingBot()
    app.bot = fake_bot

    app._on_stop_clicked()

    assert fake_bot.request_stop_called is True
    assert str(app.stop_button["state"]) == "disabled"
    assert app.status_label["text"] == "Status: stopping..."


def test_on_stop_clicked_does_not_raise_when_no_bot_running(app):
    app.bot = None
    app._on_stop_clicked()  # should not raise
    assert str(app.stop_button["state"]) == "disabled"


def test_state_changes_from_bot_run_reach_the_state_queue(app, monkeypatch):
    monkeypatch.setattr(gui_app_module, "FishingBot", FakeFishingBot)

    app._on_start_clicked()
    run_mainloop_briefly(app)

    # FakeFishingBot.run() pushed IDLE then CASTING via on_state_change.
    app._drain_state_queue()
    assert app.step_labels[FishingState.CASTING]["bg"] == gui_step_color_active


# ----- Window close ----------------------------------------------------------

def test_on_close_requests_stop_and_shuts_down_running_bot(app):
    fake_bot = FakeFishingBot()
    app.bot = fake_bot
    app.bot_thread = None  # simulate "not running" thread so join() is skipped

    app._on_close()

    assert fake_bot.request_stop_called is True
    assert fake_bot.shutdown_called is True


def test_on_close_does_not_raise_when_bot_never_started(app):
    app.bot = None
    app.bot_thread = None

    app._on_close()  # should not raise
