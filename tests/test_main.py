from unittest.mock import MagicMock

import pytest

import main as main_module
from core.fishing_state import FishingState
from core.screenshot_frame import ScreenshotFrame


@pytest.fixture(autouse=True)
def mock_sleep(monkeypatch):
    """Avoids real delays from every sleep() call inside main()."""
    mock = MagicMock()
    monkeypatch.setattr(main_module, "sleep", mock)
    return mock


@pytest.fixture
def mocks(monkeypatch):
    """
    Replaces every class main() instantiates with a MagicMock instance,
    so no real screenshots, input, OCR, or global hotkeys are involved.
    """
    screenshot_capture = MagicMock()
    object_detection = MagicMock()
    controls_interaction = MagicMock()
    ocr_recognition = MagicMock()
    emergency_stop = MagicMock()

    monkeypatch.setattr(main_module, "ScreenshotCapture", MagicMock(return_value=screenshot_capture))
    monkeypatch.setattr(main_module, "ObjectDetection", MagicMock(return_value=object_detection))
    monkeypatch.setattr(main_module, "ControlsInteraction", MagicMock(return_value=controls_interaction))
    monkeypatch.setattr(main_module, "OcrRecognition", MagicMock(return_value=ocr_recognition))
    monkeypatch.setattr(main_module, "EmergencyStop", MagicMock(return_value=emergency_stop))

    # Default: emergency stop never triggered, unless a test overrides it.
    emergency_stop.is_stop_requested.return_value = False

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


def test_happy_path_casts_finds_bobber_detects_splash_and_reels_in(mocks, monkeypatch):
    """
    Full happy-path cycle: IDLE -> CASTING -> WAITING_FOR_BOBBER ->
    WATCHING_FOR_SPLASH (2 misses then a hit) -> REELING -> back to IDLE,
    then the emergency stop fires to end the test deterministically.
    """
    bobber_position = (111, 222)
    mocks["object_detection"].find_bobber.return_value = bobber_position
    mocks["object_detection"].detect_splash.side_effect = [False, False, True]

    # Allow exactly one full cycle (7 iterations: IDLE, CASTING,
    # WAITING_FOR_BOBBER, WATCHING_FOR_SPLASH x3, REELING), then request
    # stop so the loop doesn't start a second cycle.
    mocks["emergency_stop"].is_stop_requested.side_effect = [False] * 7 + [True] * 100

    main_module.main()

    mocks["controls_interaction"].cast_fishing_line.assert_called_once()
    assert mocks["object_detection"].find_bobber.call_count == 1
    assert mocks["object_detection"].detect_splash.call_count == 3
    mocks["controls_interaction"].reel_in_bobber.assert_called_once_with(bobber_position)
    mocks["emergency_stop"].stop_listening.assert_called_once()


def test_stops_after_max_bobber_search_attempts_when_bobber_never_found(mocks, monkeypatch):
    """
    If find_bobber() always returns None, the state machine must give up
    after max_bobber_search_attempts attempts and never reel in.
    """
    monkeypatch.setattr(main_module, "max_bobber_search_attempts", 3)
    mocks["object_detection"].find_bobber.return_value = None

    main_module.main()

    assert mocks["object_detection"].find_bobber.call_count == 3
    mocks["controls_interaction"].reel_in_bobber.assert_not_called()
    mocks["emergency_stop"].stop_listening.assert_called_once()


def test_stops_after_max_splash_watch_attempts_when_splash_never_detected(mocks, monkeypatch):
    """
    If detect_splash() always returns False, the state machine must give
    up after max_splash_watch_attempts attempts and never reel in.
    """
    monkeypatch.setattr(main_module, "max_splash_watch_attempts", 4)
    mocks["object_detection"].find_bobber.return_value = (1, 2)
    mocks["object_detection"].detect_splash.return_value = False

    main_module.main()

    assert mocks["object_detection"].detect_splash.call_count == 4
    mocks["controls_interaction"].reel_in_bobber.assert_not_called()


def test_emergency_stop_halts_immediately_regardless_of_state(mocks, monkeypatch):
    """
    If is_stop_requested() becomes True right away, the loop must exit
    on its very first check, performing no actions at all.
    """
    mocks["emergency_stop"].is_stop_requested.return_value = True

    main_module.main()

    mocks["controls_interaction"].cast_fishing_line.assert_not_called()
    mocks["object_detection"].find_bobber.assert_not_called()
    mocks["emergency_stop"].stop_listening.assert_called_once()


def test_stop_listening_is_called_even_if_an_exception_occurs(mocks):
    """
    stop_listening() must be called (via finally) even if something
    inside the loop raises unexpectedly.
    """
    mocks["controls_interaction"].cast_fishing_line.side_effect = RuntimeError("boom")

    with pytest.raises(RuntimeError):
        main_module.main()

    mocks["emergency_stop"].stop_listening.assert_called_once()


def test_stops_after_max_state_machine_iterations_as_last_resort(mocks, monkeypatch):
    """
    Even if nothing ever reaches FishingState.STOPPED or requests an
    emergency stop, the hard iteration cap must still end the loop.
    """
    monkeypatch.setattr(main_module, "max_state_machine_iterations", 5)
    # Keep find_bobber/detect_splash always failing softly so the state
    # machine just keeps retrying without ever setting STOPPED itself...
    # but with a large bobber/splash attempt budget so the iteration cap
    # is what actually ends the loop first.
    monkeypatch.setattr(main_module, "max_bobber_search_attempts", 1_000_000)
    mocks["object_detection"].find_bobber.return_value = None

    main_module.main()

    # 5 iterations total; state stays in WAITING_FOR_BOBBER after CASTING+IDLE.
    assert mocks["object_detection"].find_bobber.call_count <= 5
