from unittest.mock import MagicMock

import pytest

import core.fishing_bot as fishing_bot_module
from core.fishing_bot import FishingBot
from core.fishing_state import FishingState
from core.screenshot_frame import ScreenshotFrame
from support.constants import start_delay_seconds


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    """Avoids real delays from every sleep() call inside FishingBot.run()."""
    mock = MagicMock()
    monkeypatch.setattr(fishing_bot_module, "sleep", mock)
    return mock


@pytest.fixture
def mocks(monkeypatch):
    """
    Replaces every class FishingBot() instantiates with a MagicMock
    instance, so no real screenshots, input, OCR, or global hotkeys are
    involved.
    """
    screenshot_capture = MagicMock()
    object_detection = MagicMock()
    controls_interaction = MagicMock()
    ocr_recognition = MagicMock()
    emergency_stop = MagicMock()

    monkeypatch.setattr(fishing_bot_module, "ScreenshotCapture", MagicMock(return_value=screenshot_capture))
    monkeypatch.setattr(fishing_bot_module, "ObjectDetection", MagicMock(return_value=object_detection))
    monkeypatch.setattr(fishing_bot_module, "ControlsInteraction", MagicMock(return_value=controls_interaction))
    monkeypatch.setattr(fishing_bot_module, "OcrRecognition", MagicMock(return_value=ocr_recognition))
    monkeypatch.setattr(fishing_bot_module, "EmergencyStop", MagicMock(return_value=emergency_stop))

    # Default: stop never requested, unless a test overrides it.
    emergency_stop.is_stop_requested.return_value = False

    # Default: any found bobber candidate passes the motion check (real
    # water, not a static false positive), unless a test overrides it.
    object_detection.is_bobber_candidate_static.return_value = False

    # capture_screenshot just needs to return some ScreenshotFrame; content doesn't matter
    # since object_detection is fully mocked too.
    screenshot_capture.capture_screenshot.return_value = ScreenshotFrame(
        image=MagicMock(), timestamp=0.0, origin=(0, 0)
    )

    return {
        "screenshot_capture": screenshot_capture,
        "object_detection": object_detection,
        "controls_interaction": controls_interaction,
        "ocr_recognition": ocr_recognition,
        "emergency_stop": emergency_stop,
    }


def test_happy_path_casts_finds_bobber_detects_splash_and_reels_in(mocks):
    """
    Full happy-path cycle: IDLE -> CASTING -> WAITING_FOR_BOBBER ->
    WATCHING_FOR_SPLASH (2 misses then a hit) -> REELING -> back to IDLE,
    then the stop flag fires to end the test deterministically.
    """
    bobber_position = (111, 222)
    mocks["object_detection"].find_bobber.return_value = bobber_position
    mocks["object_detection"].detect_splash.side_effect = [False, False, True]

    # The startup countdown consumes start_delay_seconds is_stop_requested()
    # checks first (sleep is mocked, so it runs instantly), then one full
    # cycle (7 iterations: IDLE, CASTING, WAITING_FOR_BOBBER,
    # WATCHING_FOR_SPLASH x3, REELING), then request stop so the loop
    # doesn't start a second cycle.
    mocks["emergency_stop"].is_stop_requested.side_effect = [False] * (start_delay_seconds + 7) + [True] * 100

    state_changes = []
    FishingBot().run(on_state_change=state_changes.append)

    mocks["controls_interaction"].cast_fishing_line.assert_called_once()
    assert mocks["object_detection"].find_bobber.call_count == 1
    assert mocks["object_detection"].detect_splash.call_count == 3
    mocks["controls_interaction"].reel_in_bobber.assert_called_once_with(bobber_position)
    assert state_changes[0] == FishingState.IDLE
    assert FishingState.REELING in state_changes


def test_stops_after_max_bobber_search_attempts_when_bobber_never_found(mocks, monkeypatch):
    """
    If find_bobber() always returns None, the state machine must give up
    after max_bobber_search_attempts attempts and never reel in.
    """
    monkeypatch.setattr(fishing_bot_module, "max_bobber_search_attempts", 3)
    mocks["object_detection"].find_bobber.return_value = None

    FishingBot().run()

    assert mocks["object_detection"].find_bobber.call_count == 3
    mocks["controls_interaction"].reel_in_bobber.assert_not_called()


def test_rejects_static_bobber_candidate_and_keeps_searching(mocks, monkeypatch):
    """
    If find_bobber() returns a candidate but is_bobber_candidate_static()
    says that area is frozen (a likely false positive, e.g. a static
    background/UI element), the state machine must reject it and keep
    searching rather than committing to it.
    """
    monkeypatch.setattr(fishing_bot_module, "max_bobber_search_attempts", 3)
    mocks["object_detection"].find_bobber.return_value = (123, 456)
    mocks["object_detection"].is_bobber_candidate_static.return_value = True

    FishingBot().run()

    assert mocks["object_detection"].find_bobber.call_count == 3
    assert mocks["object_detection"].is_bobber_candidate_static.call_count == 3
    mocks["controls_interaction"].reel_in_bobber.assert_not_called()


def test_accepts_bobber_candidate_once_motion_confirms_real_water(mocks):
    """
    If is_bobber_candidate_static() says the area is moving (real
    water), the candidate must be accepted and the state machine must
    proceed to WATCHING_FOR_SPLASH.
    """
    bobber_position = (123, 456)
    mocks["object_detection"].find_bobber.return_value = bobber_position
    mocks["object_detection"].is_bobber_candidate_static.return_value = False
    mocks["object_detection"].detect_splash.return_value = True  # reel in immediately

    # 5 main-loop iterations for one full cycle (IDLE, CASTING,
    # WAITING_FOR_BOBBER, WATCHING_FOR_SPLASH, REELING), plus
    # start_delay_seconds countdown checks before that. Stop right after
    # so the loop doesn't start a second cycle.
    mocks["emergency_stop"].is_stop_requested.side_effect = [False] * (start_delay_seconds + 5) + [True] * 100

    FishingBot().run()

    mocks["object_detection"].find_bobber.assert_called_once()
    mocks["controls_interaction"].reel_in_bobber.assert_called_once_with(bobber_position)


def test_recasts_after_max_splash_watch_attempts_when_splash_never_detected(mocks, monkeypatch):
    """
    If detect_splash() always returns False, the state machine must give
    up watching after max_splash_watch_attempts attempts and recast
    (go back to IDLE -> CASTING) rather than stopping entirely.
    """
    monkeypatch.setattr(fishing_bot_module, "max_splash_watch_attempts", 4)
    mocks["object_detection"].find_bobber.return_value = (1, 2)
    mocks["object_detection"].detect_splash.return_value = False

    # 8 iterations for one full "no bite" cycle + the start of a recast:
    # IDLE, CASTING, WAITING_FOR_BOBBER, WATCHING_FOR_SPLASH x4 (gives up,
    # back to IDLE), IDLE (recast). Plus the startup countdown's checks.
    # Stop right after to keep the test fast.
    mocks["emergency_stop"].is_stop_requested.side_effect = [False] * (start_delay_seconds + 8) + [True] * 100

    FishingBot().run()

    assert mocks["object_detection"].detect_splash.call_count == 4
    mocks["controls_interaction"].reel_in_bobber.assert_not_called()
    # Recast actually happened: cast_fishing_line called once for the
    # original cast, and again for the recast.
    assert mocks["controls_interaction"].cast_fishing_line.call_count == 2


def test_stop_requested_halts_immediately_regardless_of_state(mocks):
    """
    If is_stop_requested() is already True, the loop must exit on its
    very first check, performing no actions at all.
    """
    mocks["emergency_stop"].is_stop_requested.return_value = True

    FishingBot().run()

    mocks["controls_interaction"].cast_fishing_line.assert_not_called()
    mocks["object_detection"].find_bobber.assert_not_called()


def test_run_counts_down_start_delay_seconds_before_the_first_cast(mocks, mock_sleep, caplog):
    """
    run() must sleep once per second for start_delay_seconds seconds
    before doing anything else, and log each remaining second (so it's
    visible in the GUI's log panel).
    """
    mocks["object_detection"].find_bobber.return_value = None  # stop quickly after countdown

    import logging
    with caplog.at_level(logging.INFO, logger="core.fishing_bot"):
        FishingBot().run()

    # sleep(1) called once per countdown second.
    assert mock_sleep.call_args_list.count(((1,),)) >= start_delay_seconds

    countdown_messages = [r.message for r in caplog.records if "Starting in" in r.message]
    assert len(countdown_messages) == start_delay_seconds
    assert countdown_messages[0] == f"Starting in {start_delay_seconds} seconds..."
    assert countdown_messages[-1] == "Starting in 1 second..."


def test_run_aborts_during_countdown_if_stop_requested(mocks):
    """
    If a stop is requested partway through the countdown, run() must
    abort immediately without casting at all.
    """
    # True on the 3rd countdown check; everything after is irrelevant.
    mocks["emergency_stop"].is_stop_requested.side_effect = [False, False, True] + [True] * 100

    FishingBot().run()

    mocks["controls_interaction"].cast_fishing_line.assert_not_called()
    mocks["object_detection"].find_bobber.assert_not_called()


def test_request_stop_delegates_to_emergency_stop(mocks):
    """FishingBot.request_stop() must delegate to EmergencyStop.request_stop()."""
    bot = FishingBot()
    bot.request_stop()
    mocks["emergency_stop"].request_stop.assert_called_once()


def test_shutdown_releases_hotkey_and_never_touches_screenshots(mocks):
    """
    FishingBot.shutdown() must release the hotkey hook but NEVER delete
    screenshots automatically, regardless of why the bot stopped --
    screenshots are a debugging aid that should only ever be cleared by
    an explicit user action (e.g. the GUI's "Clear Screenshots" button).
    """
    for stop_requested in (True, False):
        mocks["emergency_stop"].is_stop_requested.return_value = stop_requested
        mocks["emergency_stop"].reset_mock()
        mocks["screenshot_capture"].reset_mock()

        bot = FishingBot()
        bot.shutdown()

        mocks["emergency_stop"].stop_listening.assert_called_once()
        mocks["screenshot_capture"].clear_screenshots.assert_not_called()


def test_run_raises_if_state_handling_fails(mocks):
    """
    An unexpected exception inside the loop must propagate out of run(),
    after being logged (verified separately via caplog if desired).
    """
    mocks["controls_interaction"].cast_fishing_line.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        FishingBot().run()


def test_stops_after_max_state_machine_iterations_as_last_resort(mocks, monkeypatch):
    """
    Even if nothing ever reaches FishingState.STOPPED or requests a
    stop, the hard iteration cap must still end the loop.
    """
    monkeypatch.setattr(fishing_bot_module, "max_state_machine_iterations", 5)
    monkeypatch.setattr(fishing_bot_module, "max_bobber_search_attempts", 1_000_000)
    mocks["object_detection"].find_bobber.return_value = None

    FishingBot().run()

    # 5 iterations total; state stays in WAITING_FOR_BOBBER after CASTING+IDLE.
    assert mocks["object_detection"].find_bobber.call_count <= 5
