from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from core.screenshot_frame import ScreenshotFrame
from support.app_error_handling import TemplateNotFoundError, handle_errors
from support.app_logging import get_logger
from support.constants import assets_dir_name, templates_dir_name, bobber_template_file_name, \
    bobber_match_threshold, bobber_match_scales, splash_template_file_name, splash_match_threshold, \
    splash_search_radius, splash_match_scales, bobber_motion_check_radius, bobber_motion_min_diff

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
            logger.error("Failed to load template image at %s (file exists but could not be decoded)",
                         template_path)
            raise TemplateNotFoundError(f"Failed to load template image at {template_path}")

        return template

    @staticmethod
    def __multi_scale_match(search_image_gray: np.ndarray, template_gray: np.ndarray,
                             scales: list[float]) -> tuple[float, tuple[int, int], tuple[int, int]]:
        """
        Runs cv2.matchTemplate at several scaled versions of
        `template_gray` against `search_image_gray`, returning the best
        (score, top_left_location, (template_height, template_width))
        found across all scales. This makes matching robust to the
        template having been captured at a different camera zoom level
        than the current one.
        """
        best_score = -1.0
        best_loc = (0, 0)
        best_shape = template_gray.shape[:2]

        search_height, search_width = search_image_gray.shape[:2]
        original_height, original_width = template_gray.shape[:2]

        for scale in scales:
            scaled_height = max(1, int(original_height * scale))
            scaled_width = max(1, int(original_width * scale))
            if scaled_height >= search_height or scaled_width >= search_width:
                continue

            resized_template = cv2.resize(template_gray, (scaled_width, scaled_height))
            result = cv2.matchTemplate(search_image_gray, resized_template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_score:
                best_score = max_val
                best_loc = max_loc
                best_shape = (scaled_height, scaled_width)

        return best_score, best_loc, best_shape

    @handle_errors()
    def find_bobber(self, frame: ScreenshotFrame) -> Optional[tuple[int, int]]:
        """
        Locates the bobber inside `frame` via multi-scale template
        matching (robust to camera zoom differences between when
        bobber.jpg was captured and the current session). Returns the
        bobber's (x, y) position in absolute screen coordinates, or None
        if no sufficiently confident match is found at any scale.
        """
        if self.bobber_template_gray is None:
            return None

        frame_gray = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY)
        template_height, template_width = self.bobber_template_gray.shape[:2]

        if frame_gray.shape[0] < template_height or frame_gray.shape[1] < template_width:
            logger.warning("Frame is smaller than the bobber template; skipping match.")
            return None

        max_val, max_loc, (matched_height, matched_width) = self.__multi_scale_match(
            frame_gray, self.bobber_template_gray, bobber_match_scales
        )

        local_x = max_loc[0] + matched_width // 2
        local_y = max_loc[1] + matched_height // 2
        screen_x = frame.origin[0] + local_x
        screen_y = frame.origin[1] + local_y

        if max_val < bobber_match_threshold:
            logger.info(
                "Bobber NOT found: best score %.3f < threshold %.3f (best guess was at screen (%d, %d))",
                max_val, bobber_match_threshold, screen_x, screen_y
            )
            return None

        logger.info("Bobber found at screen (%d, %d), score %.3f (threshold %.3f)",
                    screen_x, screen_y, max_val, bobber_match_threshold)
        return screen_x, screen_y

    @handle_errors()
    def is_bobber_candidate_static(self, frame_a: ScreenshotFrame, frame_b: ScreenshotFrame,
                                    position: tuple[int, int]) -> bool:
        """
        Returns True if the small area around `position` is suspiciously
        frozen (near pixel-identical) between `frame_a` and `frame_b`.

        Template matching can occasionally lock onto a static background
        or UI element that happens to resemble the bobber template --
        real water (with a real bobber floating on it) always has at
        least subtle ripple motion, so a completely static match is a
        strong signal of a false positive.
        """
        region_a = self.__extract_region(frame_a, position, bobber_motion_check_radius)
        region_b = self.__extract_region(frame_b, position, bobber_motion_check_radius)
        if region_a is None or region_b is None or region_a.shape != region_b.shape:
            # Can't compare -- don't block on an inconclusive check.
            return False

        diff = cv2.absdiff(region_a, region_b)
        max_diff = int(diff.sum(axis=2).max())
        is_static = max_diff < bobber_motion_min_diff

        logger.info("Motion check near %s: max pixel diff=%d (min required=%d) -> %s",
                    position, max_diff, bobber_motion_min_diff, "STATIC (likely false positive)" if is_static
                    else "moving (real water)")
        return is_static

    @staticmethod
    def __extract_region(frame: ScreenshotFrame, position: tuple[int, int], radius: int) -> Optional[np.ndarray]:
        """Crops a square BGR region of the given radius around `position` (absolute screen coordinates)."""
        local_x = position[0] - frame.origin[0]
        local_y = position[1] - frame.origin[1]

        height, width = frame.image.shape[:2]
        x_start = max(0, local_x - radius)
        x_end = min(width, local_x + radius)
        y_start = max(0, local_y - radius)
        y_end = min(height, local_y + radius)

        if x_start >= x_end or y_start >= y_end:
            return None

        return frame.image[y_start:y_end, x_start:x_end]

    @handle_errors()
    def detect_splash(self, frame: ScreenshotFrame, bobber_position: tuple[int, int]) -> bool:
        """
        Detects a splash via multi-scale template matching, restricted
        to a small search window (radius `splash_search_radius`) around
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

        max_val, _, _ = self.__multi_scale_match(window_gray, self.splash_template_gray, splash_match_scales)

        is_splash = max_val >= splash_match_threshold
        logger.info("Splash check near %s: score=%.3f, threshold=%.3f -> %s",
                    bobber_position, max_val, splash_match_threshold, "SPLASH" if is_splash else "no splash")
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
