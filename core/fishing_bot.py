from time import monotonic, sleep
from typing import Callable, Optional

from core.controls_interaction import ControlsInteraction
from core.emergency_stop import EmergencyStop
from core.fishing_state import FishingState
from core.object_detection import ObjectDetection
from core.ocr_recognition import OcrRecognition
from core.screenshot_capture import ScreenshotCapture
from support.app_logging import get_logger
from support.constants import max_state_machine_iterations, splash_watch_timeout_seconds, \
    cast_animation_wait_seconds, max_bobber_search_attempts, bobber_search_retry_delay_seconds, \
    wait_time_between_screenshots, start_delay_seconds, bobber_motion_check_delay_seconds, \
    clear_screenshots_before_each_cast as default_clear_screenshots_before_each_cast

logger = get_logger(__name__)

StateChangeCallback = Callable[[FishingState], None]


class FishingBot:
    """
    Encapsulates the fishing state machine, independent of whatever is
    driving it (a simple CLI entrypoint, or a GUI running it on a
    background thread). The GUI needs two things this class provides:
      - an `on_state_change` callback fired every iteration, so it can
        update a visual "current step" indicator;
      - a `request_stop()` method, so a Stop button can halt the loop
        through the same mechanism as the emergency-stop hotkey.
    """

    def __init__(self):
        try:
            self.screenshot_capture = ScreenshotCapture()
            self.object_detection = ObjectDetection()
            self.controls_interaction = ControlsInteraction()
            self.ocr_recognition = OcrRecognition()
            self.emergency_stop = EmergencyStop()
        except Exception:
            logger.exception("Failed to initialize one or more components; aborting.")
            raise

    def request_stop(self) -> None:
        """Requests an immediate stop (e.g. from a GUI Stop button)."""
        self.emergency_stop.request_stop()

    def shutdown(self) -> None:
        """
        Releases OS-level resources (the emergency-stop hotkey hook).

        Does NOT delete saved screenshots on its own -- that's controlled
        separately by clear_screenshots_before_each_cast (opt-in, cleared
        right before each cast while running) and the GUI's explicit
        "Clear Screenshots" button. Deleting them based on *why* the bot
        stopped was tried and repeatedly got in the way of debugging real
        detection failures.
        """
        self.emergency_stop.stop_listening()

    def __wait_before_starting(self) -> bool:
        """
        Counts down from start_delay_seconds to 1, logging one message
        per second (visible in the GUI's log panel), before the fishing
        loop actually begins. Returns False if a stop was requested
        during the countdown, True otherwise.
        """
        for remaining in range(start_delay_seconds, 0, -1):
            if self.emergency_stop.is_stop_requested():
                logger.info("Stop requested during startup countdown; aborting before the first cast.")
                return False
            logger.info("Starting in %d second%s...", remaining, "" if remaining == 1 else "s")
            sleep(1)
        return True

    def run(self, on_state_change: Optional[StateChangeCallback] = None,
            clear_screenshots_before_each_cast: bool = default_clear_screenshots_before_each_cast) -> None:
        """
        Runs the fishing state machine until it reaches STOPPED, hits
        max_state_machine_iterations, or a stop is requested.

        Begins with a start_delay_seconds countdown (logged one message
        per second) before the first cast, giving the user time to
        switch focus into the game window.

        If clear_screenshots_before_each_cast is True, every screenshot
        saved so far is deleted right before each cast (including the
        very first one), keeping disk usage bounded during long runs at
        the cost of only ever having the current cast's screenshots
        available for debugging. Defaults to the clear_screenshots_before_each_cast
        constant (off by default).
        """
        if not self.__wait_before_starting():
            return  # stop was requested during the countdown

        state = FishingState.IDLE
        screenshot_number = 0
        splash_watch_attempts = 0
        splash_watch_start_time = 0.0
        bobber_search_attempts = 0
        iterations = 0
        bobber_position: tuple[int, int] | None = None

        screenshot_capture = self.screenshot_capture
        object_detection = self.object_detection
        controls_interaction = self.controls_interaction
        emergency_stop = self.emergency_stop

        while (
            state != FishingState.STOPPED
            and iterations < max_state_machine_iterations
            and not emergency_stop.is_stop_requested()
        ):
            iterations += 1
            logger.info("State: %s (iteration %d)", state.name, iterations)
            if on_state_change is not None:
                on_state_change(state)

            try:
                if state == FishingState.IDLE:
                    if clear_screenshots_before_each_cast:
                        screenshot_capture.clear_screenshots()
                    controls_interaction.cast_fishing_line()
                    splash_watch_attempts = 0
                    splash_watch_start_time = 0.0
                    bobber_search_attempts = 0
                    bobber_position = None
                    state = FishingState.CASTING

                elif state == FishingState.CASTING:
                    # Wait for the cast animation / bobber to land before looking for it.
                    sleep(cast_animation_wait_seconds)
                    state = FishingState.WAITING_FOR_BOBBER

                elif state == FishingState.WAITING_FOR_BOBBER:
                    screenshot_frame = screenshot_capture.capture_screenshot(screenshot_number)
                    screenshot_number += 1
                    bobber_search_attempts += 1
                    logger.info("Looking for bobber: attempt %d/%d", bobber_search_attempts,
                                max_bobber_search_attempts)

                    candidate_position = object_detection.find_bobber(screenshot_frame)

                    if candidate_position is not None:
                        # Confirm this isn't a static background/UI false
                        # positive by checking for at least a little
                        # natural water motion before committing to it.
                        sleep(bobber_motion_check_delay_seconds)
                        confirm_frame = screenshot_capture.capture_screenshot(screenshot_number)
                        screenshot_number += 1

                        if object_detection.is_bobber_candidate_static(
                            screenshot_frame, confirm_frame, candidate_position
                        ):
                            logger.warning("Rejecting bobber candidate at %s: area is static (likely a "
                                            "false positive, not real water).", candidate_position)
                            candidate_position = None
                        elif not object_detection.has_bobber_feather_colors(screenshot_frame, candidate_position):
                            logger.warning("Rejecting bobber candidate at %s: missing feather colors "
                                            "(likely a false positive).", candidate_position)
                            candidate_position = None

                    bobber_position = candidate_position

                    if bobber_position is not None:
                        state = FishingState.WATCHING_FOR_SPLASH
                    elif bobber_search_attempts >= max_bobber_search_attempts:
                        # No bobber found within the search window -- this can
                        # happen (missed cast, obstructed view, etc.), so
                        # recast rather than stopping the whole bot.
                        state = FishingState.IDLE
                        logger.info("Bobber not found within %d attempts; recasting.",
                                    max_bobber_search_attempts)
                    else:
                        # Stay in WAITING_FOR_BOBBER and retry after a short delay.
                        sleep(bobber_search_retry_delay_seconds)

                elif state == FishingState.WATCHING_FOR_SPLASH:
                    assert bobber_position is not None  # guaranteed by WAITING_FOR_BOBBER
                    if splash_watch_attempts == 0:
                        splash_watch_start_time = monotonic()

                    screenshot_frame = screenshot_capture.capture_screenshot(screenshot_number)
                    screenshot_number += 1
                    splash_watch_attempts += 1
                    elapsed_seconds = monotonic() - splash_watch_start_time
                    logger.info("Watching for splash: attempt %d (%.1fs/%ds elapsed)", splash_watch_attempts,
                                elapsed_seconds, splash_watch_timeout_seconds)

                    splash_detected = object_detection.detect_splash(screenshot_frame, bobber_position)

                    if splash_detected:
                        state = FishingState.REELING
                    elif elapsed_seconds >= splash_watch_timeout_seconds:
                        # No bite within the watch window -- this is normal
                        # (WoW bites can take a while), so recast rather
                        # than stopping the whole bot.
                        state = FishingState.IDLE
                        logger.info("No splash detected within %ds; recasting.", splash_watch_timeout_seconds)
                    else:
                        # Keep watching, pacing captures at wait_time_between_screenshots.
                        sleep(wait_time_between_screenshots)

                elif state == FishingState.REELING:
                    assert bobber_position is not None  # guaranteed by WAITING_FOR_BOBBER
                    controls_interaction.reel_in_bobber(bobber_position)
                    # Shift+right-click reels in and auto-loots in one action, so
                    # there's no separate LOOTING step needed for now.
                    # TODO: re-introduce LOOTING + bag-full check once needed.
                    state = FishingState.IDLE
            except Exception:
                logger.exception("Unexpected error while handling state %s; aborting.", state.name)
                raise

        if on_state_change is not None:
            on_state_change(state)

        if emergency_stop.is_stop_requested():
            logger.warning("Stop requested; halting immediately.")
        elif iterations >= max_state_machine_iterations:
            logger.warning("Reached max_state_machine_iterations (%d) without stopping; forcing stop.",
                            max_state_machine_iterations)

        logger.info("Fishing bot stopped.")
