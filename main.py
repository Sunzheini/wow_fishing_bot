from core.controls_interaction import ControlsInteraction
from core.fishing_state import FishingState
from core.object_detection import ObjectDetection
from core.ocr_recognition import OcrRecognition
from core.screenshot_capture import ScreenshotCapture
from support.app_logging import get_logger
from support.constants import max_state_machine_iterations, max_splash_watch_attempts, cast_animation_wait_seconds
from time import sleep


logger = get_logger(__name__)


def main():
    # Initialize objects
    screenshot_capture = ScreenshotCapture()
    object_detection = ObjectDetection()
    controls_interaction = ControlsInteraction()
    ocr_recognition = OcrRecognition()

    state = FishingState.IDLE
    screenshot_number = 0
    splash_watch_attempts = 0
    iterations = 0
    bobber_position: tuple[int, int] | None = None

    while state != FishingState.STOPPED and iterations < max_state_machine_iterations:
        iterations += 1
        logger.info("State: %s (iteration %d)", state.name, iterations)

        if state == FishingState.IDLE:
            controls_interaction.cast_fishing_line()
            splash_watch_attempts = 0
            bobber_position = None
            state = FishingState.CASTING

        elif state == FishingState.CASTING:
            # Wait for the cast animation / bobber to land before looking for it.
            sleep(cast_animation_wait_seconds)
            state = FishingState.WAITING_FOR_BOBBER

        elif state == FishingState.WAITING_FOR_BOBBER:
            screenshot_frame = screenshot_capture.capture_screenshot(screenshot_number)
            screenshot_number += 1

            bobber_position = object_detection.find_bobber(screenshot_frame)

            if bobber_position is not None:
                state = FishingState.WATCHING_FOR_SPLASH
            else:
                state = FishingState.STOPPED
                logger.warning("Bobber not found; stopping.")

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

    if iterations >= max_state_machine_iterations:
        logger.warning("Reached max_state_machine_iterations (%d) without stopping; forcing stop.",
                        max_state_machine_iterations)

    logger.info("Fishing bot stopped.")


if __name__ == "__main__":
    main()
