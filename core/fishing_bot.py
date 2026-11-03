from time import sleep
from typing import Callable, Optional

from core.controls_interaction import ControlsInteraction
from core.emergency_stop import EmergencyStop
from core.fishing_state import FishingState
from core.object_detection import ObjectDetection
from core.ocr_recognition import OcrRecognition
from core.screenshot_capture import ScreenshotCapture
from support.app_logging import get_logger
from support.constants import max_state_machine_iterations, max_splash_watch_attempts, cast_animation_wait_seconds, \
    max_bobber_search_attempts, bobber_search_retry_delay_seconds, wait_time_between_screenshots, start_delay_seconds

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
        Releases OS-level resources (the emergency-stop hotkey hook) and
        clears saved screenshots, since they're only useful as a
        debugging aid during a run.
        """
        self.emergency_stop.stop_listening()
        self.screenshot_capture.clear_screenshots()

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

    def run(self, on_state_change: Optional[StateChangeCallback] = None) -> None:
        """
        Runs the fishing state machine until it reaches STOPPED, hits
        max_state_machine_iterations, or a stop is requested.

        Begins with a start_delay_seconds countdown (logged one message
        per second) before the first cast, giving the user time to
        switch focus into the game window.
        """
        if not self.__wait_before_starting():
            return  # stop was requested during the countdown

        state = FishingState.IDLE
        screenshot_number = 0
        splash_watch_attempts = 0
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
                    controls_interaction.cast_fishing_line()
                    splash_watch_attempts = 0
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

                    bobber_position = object_detection.find_bobber(screenshot_frame)

                    if bobber_position is not None:
                        state = FishingState.WATCHING_FOR_SPLASH
                    elif bobber_search_attempts >= max_bobber_search_attempts:
                        state = FishingState.STOPPED
                        logger.warning("Bobber not found within %d attempts; stopping.",
                                        max_bobber_search_attempts)
                    else:
                        # Stay in WAITING_FOR_BOBBER and retry after a short delay.
                        sleep(bobber_search_retry_delay_seconds)

                elif state == FishingState.WATCHING_FOR_SPLASH:
                    assert bobber_position is not None  # guaranteed by WAITING_FOR_BOBBER
                    screenshot_frame = screenshot_capture.capture_screenshot(screenshot_number)
                    screenshot_number += 1
                    splash_watch_attempts += 1

                    splash_detected = object_detection.detect_splash(screenshot_frame, bobber_position)

                    if splash_detected:
                        state = FishingState.REELING
                    elif splash_watch_attempts >= max_splash_watch_attempts:
                        # No bite within the watch window -- this is normal
                        # (WoW bites can take a while), so recast rather
                        # than stopping the whole bot.
                        state = FishingState.IDLE
                        logger.info("No splash detected within %d attempts (~%.1fs); recasting.",
                                    max_splash_watch_attempts,
                                    max_splash_watch_attempts * wait_time_between_screenshots)
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
