from core.controls_interaction import ControlsInteraction
from core.emergency_stop import EmergencyStop
from core.fishing_state import FishingState
from core.object_detection import ObjectDetection
from core.ocr_recognition import OcrRecognition
from core.screenshot_capture import ScreenshotCapture
from support.app_logging import get_logger
from support.constants import max_state_machine_iterations, max_splash_watch_attempts, cast_animation_wait_seconds, \
    max_bobber_search_attempts, bobber_search_retry_delay_seconds
from time import sleep


logger = get_logger(__name__)


def main():
    # Initialize objects
    try:
        screenshot_capture = ScreenshotCapture()
        object_detection = ObjectDetection()
        controls_interaction = ControlsInteraction()
        ocr_recognition = OcrRecognition()
        emergency_stop = EmergencyStop()
    except Exception:
        logger.exception("Failed to initialize one or more components; aborting.")
        raise

    state = FishingState.IDLE
    screenshot_number = 0
    splash_watch_attempts = 0
    bobber_search_attempts = 0
    iterations = 0
    bobber_position: tuple[int, int] | None = None

    try:
        while (
            state != FishingState.STOPPED
            and iterations < max_state_machine_iterations
            and not emergency_stop.is_stop_requested()
        ):
            iterations += 1
            logger.info("State: %s (iteration %d)", state.name, iterations)

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
                        logger.warning("Bobber not found within %d attempts; stopping.", max_bobber_search_attempts)
                    else:
                        # Stay in WAITING_FOR_BOBBER and retry after a short delay.
                        sleep(bobber_search_retry_delay_seconds)

                elif state == FishingState.WATCHING_FOR_SPLASH:
                    assert bobber_position is not None  # guaranteed by WAITING_FOR_BOBBER before reaching this state
                    screenshot_frame = screenshot_capture.capture_screenshot(screenshot_number)
                    screenshot_number += 1
                    splash_watch_attempts += 1

                    splash_detected = object_detection.detect_splash(screenshot_frame, bobber_position)

                    if splash_detected:
                        state = FishingState.REELING
                    elif splash_watch_attempts >= max_splash_watch_attempts:
                        state = FishingState.STOPPED
                        logger.warning("Splash not detected within %d attempts; stopping.", max_splash_watch_attempts)
                    # else: stay in WATCHING_FOR_SPLASH and keep watching

                elif state == FishingState.REELING:
                    assert bobber_position is not None  # guaranteed by WAITING_FOR_BOBBER before reaching this state
                    controls_interaction.reel_in_bobber(bobber_position)
                    # Shift+right-click reels in and auto-loots in one action, so
                    # there's no separate LOOTING step needed for now.
                    # TODO: re-introduce LOOTING + bag-full check once needed.
                    state = FishingState.IDLE
            except Exception:
                logger.exception("Unexpected error while handling state %s; aborting.", state.name)
                raise

        if emergency_stop.is_stop_requested():
            logger.warning("Emergency stop requested; halting immediately.")
        elif iterations >= max_state_machine_iterations:
            logger.warning("Reached max_state_machine_iterations (%d) without stopping; forcing stop.",
                            max_state_machine_iterations)

        logger.info("Fishing bot stopped.")
    finally:
        emergency_stop.stop_listening()


if __name__ == "__main__":
    main()
