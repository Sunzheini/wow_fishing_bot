from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from core.screenshot_frame import ScreenshotFrame
from support.app_error_handling import TemplateNotFoundError, handle_errors
from support.app_logging import get_logger
from support.constants import assets_dir_name, templates_dir_name, bobber_template_file_name, \
    bobber_match_threshold, splash_template_file_name, splash_match_threshold, splash_search_radius

logger = get_logger(__name__)


class ObjectDetection:
    """
    Classic (non-ML) computer-vision detection used by the fishing state
    machine:
      - find_bobber(): locates the bobber via template matching over the
        whole frame.
      - detect_splash(): locates the splash via template matching
        restricted to a small window around the known bobber position.
    """

    def __init__(self):
        project_root = Path(__file__).parent.parent
        templates_dir = project_root / assets_dir_name / templates_dir_name

        self.bobber_template_gray: Optional[np.ndarray] = self.__load_template_gray(
            templates_dir / bobber_template_file_name
        )
        self.splash_template_gray: Optional[np.ndarray] = self.__load_template_gray(
            templates_dir / splash_template_file_name
        )

    @staticmethod
    def __load_template_gray(template_path: Path) -> Optional[np.ndarray]:
        """
        Loads a template image as grayscale. Returns None (and logs a
        warning) if the file doesn't exist yet, so the bot can still run
        before a real template image is supplied.
        """
        if not template_path.exists():
            logger.warning(
                "Template not found at %s; detection using it will always return a negative "
                "result until a template image is placed there.", template_path
            )
            return None

        template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            raise TemplateNotFoundError(f"Failed to load template image at {template_path}")

        return template

    @handle_errors()
    def find_bobber(self, frame: ScreenshotFrame) -> Optional[tuple[int, int]]:
        """
        Locates the bobber inside `frame` via template matching.
        Returns the bobber's (x, y) position in absolute screen
        coordinates, or None if no sufficiently confident match is found.
        """
        if self.bobber_template_gray is None:
            return None

        frame_gray = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY)
        template_height, template_width = self.bobber_template_gray.shape[:2]

        if frame_gray.shape[0] < template_height or frame_gray.shape[1] < template_width:
            logger.warning("Frame is smaller than the bobber template; skipping match.")
            return None

        result = cv2.matchTemplate(frame_gray, self.bobber_template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val < bobber_match_threshold:
            logger.debug("Bobber not found (best match score %.3f < %.3f)", max_val, bobber_match_threshold)
            return None

        local_x = max_loc[0] + template_width // 2
        local_y = max_loc[1] + template_height // 2

        screen_x = frame.origin[0] + local_x
        screen_y = frame.origin[1] + local_y

        logger.debug("Bobber found at screen (%d, %d), score %.3f", screen_x, screen_y, max_val)
        return screen_x, screen_y

    @handle_errors()
    def detect_splash(self, frame: ScreenshotFrame, bobber_position: tuple[int, int]) -> bool:
        """
        Detects a splash via template matching, restricted to a small
        search window (radius `splash_search_radius`) around
        `bobber_position` (absolute screen coordinates). This is both
        faster and more reliable than a full-frame search, since the
        splash always occurs near the bobber.
        """
        if self.splash_template_gray is None:
            return False

        window_gray = self.__extract_search_window_gray(frame, bobber_position)
        if window_gray is None:
            return False

        template_height, template_width = self.splash_template_gray.shape[:2]
        if window_gray.shape[0] < template_height or window_gray.shape[1] < template_width:
            logger.warning("Splash search window is smaller than the splash template; skipping match.")
            return False

        result = cv2.matchTemplate(window_gray, self.splash_template_gray, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        is_splash = max_val >= splash_match_threshold
        logger.debug("Splash check near %s: score=%.3f -> %s", bobber_position, max_val, is_splash)
        return is_splash

    @staticmethod
    def __extract_search_window_gray(frame: ScreenshotFrame, bobber_position: tuple[int, int]) -> Optional[np.ndarray]:
        """
        Crops a square grayscale search window of radius
        `splash_search_radius` around `bobber_position`, converted from
        absolute screen coordinates to frame-local pixel coordinates.
        """
        local_x = bobber_position[0] - frame.origin[0]
        local_y = bobber_position[1] - frame.origin[1]

        height, width = frame.image.shape[:2]
        x_start = max(0, local_x - splash_search_radius)
        x_end = min(width, local_x + splash_search_radius)
        y_start = max(0, local_y - splash_search_radius)
        y_end = min(height, local_y + splash_search_radius)

        if x_start >= x_end or y_start >= y_end:
            logger.warning("Bobber position %s is outside the captured frame; skipping splash check.",
                            bobber_position)
            return None

        window = frame.image[y_start:y_end, x_start:x_end]
        return cv2.cvtColor(window, cv2.COLOR_BGR2GRAY)
