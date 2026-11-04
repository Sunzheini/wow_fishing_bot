from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from core.screenshot_frame import ScreenshotFrame
from support.app_error_handling import TemplateNotFoundError, handle_errors
from support.app_logging import get_logger
from support.constants import assets_dir_name, templates_dir_name, bobber_template_file_name, \
    bobber_match_threshold, bobber_match_scales, bobber_search_region_x_fraction, \
    bobber_search_region_y_fraction, bobber_motion_check_radius, \
    bobber_motion_min_diff, bobber_color_check_radius, bobber_color_min_saturation, bobber_color_min_value, \
    bobber_color_blue_hue_range, bobber_color_red_hue_ranges, bobber_color_min_blue_pixels, \
    bobber_color_min_red_pixels, bobber_color_fallback_min_blob_area, bobber_color_fallback_max_pair_distance, \
    bobber_color_fallback_search_radius, bobber_fallback_seed_candidates, bobber_fallback_seed_min_distance, \
    splash_region_radius, splash_brightness_threshold, splash_pixel_ratio_threshold

logger = get_logger(__name__)


class ObjectDetection:
    """
    Classic (non-ML) computer-vision detection used by the fishing state
    machine:
      - find_bobber(): locates the bobber via multi-scale template
        matching over the whole frame.
      - detect_splash(): detects a splash via a bright-pixel-ratio
        heuristic in a small region around the known bobber position.
        A rigid template match was tried first but is fundamentally
        unreliable for this: the splash is a randomly-scattered
        particle/foam effect whose exact pixel layout differs every
        time, even though its general brightness/density is a
        consistent and repeatable signal across real gameplay sessions.
    """

    def __init__(self):
        project_root = Path(__file__).parent.parent
        templates_dir = project_root / assets_dir_name / templates_dir_name

        self.bobber_template_gray: Optional[np.ndarray] = self.__load_template_gray(
            templates_dir / bobber_template_file_name
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

    @staticmethod
    def __top_n_match_locations(search_image_gray: np.ndarray, template_gray: np.ndarray,
                                 scales: list[float], n: int,
                                 min_distance: int) -> list[tuple[float, tuple[int, int], tuple[int, int]]]:
        """
        Like __multi_scale_match, but returns up to `n` distinct
        (score, top_left_location, (height, width)) results across all
        scales, sorted best-first, instead of just the single best.

        "Distinct" means mutually separated by at least `min_distance`
        pixels -- otherwise matches from adjacent scales/pixels at
        essentially the same spot would dominate the top-N instead of
        genuinely different candidate locations. This matters because
        the single global-best-scoring location is not always the real
        bobber: an unrelated spot elsewhere can occasionally score
        almost identically, so trying several distinct candidates as
        fallback seeds is far more robust than trusting only the best one.
        """
        all_results = []
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
            all_results.append((max_val, max_loc, (scaled_height, scaled_width)))

        all_results.sort(key=lambda r: r[0], reverse=True)

        selected: list[tuple[float, tuple[int, int], tuple[int, int]]] = []
        for score, loc, shape in all_results:
            if len(selected) >= n:
                break
            is_distinct = all(
                ((loc[0] - other_loc[0]) ** 2 + (loc[1] - other_loc[1]) ** 2) ** 0.5 >= min_distance
                for _, other_loc, _ in selected
            )
            if is_distinct:
                selected.append((score, loc, shape))

        return selected

    @handle_errors()
    def find_bobber(self, frame: ScreenshotFrame) -> Optional[tuple[int, int]]:
        """
        Locates the bobber inside `frame` via multi-scale template
        matching (robust to camera zoom differences between when
        bobber.jpg was captured and the current session). Returns the
        bobber's (x, y) position in absolute screen coordinates, or None
        if no sufficiently confident match is found at any scale and the
        color-blob fallback (see below) also fails.

        The search is restricted to a central bounding box
        (`bobber_search_region_x_fraction` / `_y_fraction`), confirmed
        directly against real gameplay: the bobber only ever lands
        within a fairly constrained central region, never near the
        screen edges/corners (sky/wall/UI elements, the action bar,
        etc. all live outside this box) -- several of which were
        confirmed to otherwise produce persistent false-positive matches.
        """
        full_height, full_width = frame.image.shape[:2]
        x_start, x_end = self.__fraction_bounds(full_width, bobber_search_region_x_fraction)
        y_start, y_end = self.__fraction_bounds(full_height, bobber_search_region_y_fraction)

        if self.bobber_template_gray is None:
            logger.info("Bobber template not loaded; cannot locate the bobber.")
            return None

        frame_gray_full = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY)
        frame_gray = frame_gray_full[y_start:y_end, x_start:x_end]
        template_height, template_width = self.bobber_template_gray.shape[:2]

        if frame_gray.shape[0] < template_height or frame_gray.shape[1] < template_width:
            logger.warning("Search region is smaller than the bobber template; skipping template match.")
            return None

        candidates = self.__top_n_match_locations(
            frame_gray, self.bobber_template_gray, bobber_match_scales,
            bobber_fallback_seed_candidates, bobber_fallback_seed_min_distance
        )
        if not candidates:
            logger.info("Bobber NOT found (no template match candidates at all).")
            return None

        best_val, best_loc, (best_matched_height, best_matched_width) = candidates[0]
        best_local_x = best_loc[0] + best_matched_width // 2 + x_start
        best_local_y = best_loc[1] + best_matched_height // 2 + y_start
        best_screen_x = frame.origin[0] + best_local_x
        best_screen_y = frame.origin[1] + best_local_y

        if best_val >= bobber_match_threshold:
            logger.info("Bobber found at screen (%d, %d), score %.3f (threshold %.3f)",
                        best_screen_x, best_screen_y, best_val, bobber_match_threshold)
            return best_screen_x, best_screen_y

        logger.info(
            "Template match below threshold: best score %.3f < %.3f (best guess was at screen (%d, %d)); "
            "trying color-blob fallback near %d candidate location(s).",
            best_val, bobber_match_threshold, best_screen_x, best_screen_y, len(candidates)
        )

        # The single global-best-scoring location is not always the real
        # bobber -- an unrelated location elsewhere can occasionally
        # score almost identically. Try each distinct candidate as a
        # fallback seed in turn, not just the best one.
        for score, loc, (matched_height, matched_width) in candidates:
            local_x = loc[0] + matched_width // 2 + x_start
            local_y = loc[1] + matched_height // 2 + y_start
            seed_position = (local_x, local_y)

            fallback_position = self.__find_bobber_by_color(frame, x_start, x_end, y_start, y_end, seed_position)
            if fallback_position is not None:
                logger.info("Bobber found via color-blob fallback at screen %s (seed score %.3f).",
                            fallback_position, score)
                return fallback_position

        logger.info("Bobber NOT found (template match and color-blob fallback both failed).")
        return None

    @staticmethod
    def __fraction_bounds(size: int, fraction_range: tuple[float, float]) -> tuple[int, int]:
        """Converts a (low, high) fraction range into (start, end) pixel bounds for a dimension of length `size`."""
        low, high = fraction_range
        return int(size * low), int(size * high)

    @staticmethod
    def __find_bobber_by_color(frame: ScreenshotFrame, x_start: int, x_end: int, y_start: int, y_end: int,
                                seed_position: Optional[tuple[int, int]]) -> Optional[tuple[int, int]]:
        """
        Locates the bobber by looking for a blue-ish blob positioned
        near a red-ish blob (the two feathers), independent of exact
        template shape/size -- far more robust to camera zoom/angle
        changes than grayscale template matching, since hue is much
        more stable than silhouette across those changes.

        If `seed_position` is given (the template match's rough guess,
        in local frame coordinates), the color search is narrowed down
        to just `bobber_color_fallback_search_radius` around it instead
        of the whole central bounding box. This matters a lot in
        practice: real gameplay screenshots contain many small stray
        blue/red specks (water highlights, distant foliage, etc.), and
        scanning the full central region made the nearest-pair heuristic
        prone to latching onto unrelated noise far from the real
        bobber. Falls back to the full central region only if no seed
        is available (template not loaded at all).

        Returns the midpoint between the closest blue/red blob pair (in
        absolute screen coordinates) if one is found within
        `bobber_color_fallback_max_pair_distance`, else None.
        """
        if seed_position is not None:
            seed_x, seed_y = seed_position
            r = bobber_color_fallback_search_radius
            x_start = max(x_start, seed_x - r)
            x_end = min(x_end, seed_x + r)
            y_start = max(y_start, seed_y - r)
            y_end = min(y_end, seed_y + r)

        region_bgr = frame.image[y_start:y_end, x_start:x_end]
        if region_bgr.size == 0:
            return None

        hsv = cv2.cvtColor(region_bgr, cv2.COLOR_BGR2HSV)
        saturation_value_lower = (bobber_color_min_saturation, bobber_color_min_value)

        blue_low, blue_high = bobber_color_blue_hue_range
        blue_mask = cv2.inRange(hsv, (blue_low,) + saturation_value_lower, (blue_high, 255, 255))

        red_mask = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for red_low, red_high in bobber_color_red_hue_ranges:
            red_mask |= cv2.inRange(hsv, (red_low,) + saturation_value_lower, (red_high, 255, 255))

        blue_centroids = ObjectDetection.__blob_centroids(blue_mask)
        red_centroids = ObjectDetection.__blob_centroids(red_mask)

        if not blue_centroids or not red_centroids:
            return None

        best_distance = float("inf")
        best_pair = None
        for bx, by in blue_centroids:
            for rx, ry in red_centroids:
                distance = ((bx - rx) ** 2 + (by - ry) ** 2) ** 0.5
                if distance < best_distance:
                    best_distance = distance
                    best_pair = ((bx, by), (rx, ry))

        if best_pair is None or best_distance > bobber_color_fallback_max_pair_distance:
            return None

        (bx, by), (rx, ry) = best_pair
        local_x = int((bx + rx) / 2) + x_start
        local_y = int((by + ry) / 2) + y_start
        return frame.origin[0] + local_x, frame.origin[1] + local_y

    @staticmethod
    def __blob_centroids(mask: np.ndarray) -> list[tuple[float, float]]:
        """Returns the (x, y) centroid of every connected component in `mask` at least bobber_color_fallback_min_blob_area pixels large."""
        num_labels, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        return [
            (centroids[i][0], centroids[i][1])
            for i in range(1, num_labels)
            if stats[i, cv2.CC_STAT_AREA] >= bobber_color_fallback_min_blob_area
        ]

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

    @handle_errors()
    def has_bobber_feather_colors(self, frame: ScreenshotFrame, position: tuple[int, int]) -> bool:
        """
        Returns True if a small area around `position` contains both a
        blue-ish and a red-ish pixel cluster, matching the bobber's two
        distinctive feather colors.

        Template matching works purely on grayscale and ignores color
        entirely. Plain water never has these saturated colors, so this
        is a strong additional confirmation signal (alongside the motion
        check) to reject false positives. Calibrated directly against
        the real bobber.jpg template (100 blue / 25 red pixels out of
        644 total) vs. a plain water patch (0 of each).
        """
        region = self.__extract_region(frame, position, bobber_color_check_radius)
        if region is None:
            # Can't check -- don't block on an inconclusive check.
            return True

        hsv = cv2.cvtColor(region, cv2.COLOR_BGR2HSV)
        saturation_value_lower = (0, bobber_color_min_saturation, bobber_color_min_value)
        saturation_value_upper = (0, 255, 255)

        blue_low, blue_high = bobber_color_blue_hue_range
        blue_mask = cv2.inRange(
            hsv, (blue_low,) + saturation_value_lower[1:], (blue_high,) + saturation_value_upper[1:]
        )
        blue_count = int(np.count_nonzero(blue_mask))

        red_count = 0
        for red_low, red_high in bobber_color_red_hue_ranges:
            red_mask = cv2.inRange(
                hsv, (red_low,) + saturation_value_lower[1:], (red_high,) + saturation_value_upper[1:]
            )
            red_count += int(np.count_nonzero(red_mask))

        has_colors = blue_count >= bobber_color_min_blue_pixels and red_count >= bobber_color_min_red_pixels

        logger.info(
            "Color check near %s: blue=%d (min %d), red=%d (min %d) -> %s",
            position, blue_count, bobber_color_min_blue_pixels, red_count, bobber_color_min_red_pixels,
            "feather colors present" if has_colors else "MISSING (likely false positive)"
        )
        return has_colors

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
        Detects a splash via a bright-pixel-ratio heuristic in a small
        region around `bobber_position` (absolute screen coordinates).

        Normal water/bobber pixels are rarely above
        `splash_brightness_threshold`, while a real splash's white
        foam/particles push a small but consistent fraction of pixels
        in the region above it. Validated against 3 independent real
        screenshots: ratio was exactly 0.0 on every non-splash frame
        and 0.004-0.009 on every confirmed real splash frame.
        """
        region_gray = self.__extract_region_gray(frame, bobber_position)
        if region_gray is None:
            return False

        bright_pixel_count = int(np.count_nonzero(region_gray > splash_brightness_threshold))
        bright_ratio = bright_pixel_count / region_gray.size if region_gray.size else 0.0

        is_splash = bright_ratio >= splash_pixel_ratio_threshold
        logger.info("Splash check near %s: bright_ratio=%.4f, threshold=%.4f -> %s",
                    bobber_position, bright_ratio, splash_pixel_ratio_threshold,
                    "SPLASH" if is_splash else "no splash")
        return is_splash

    @staticmethod
    def __extract_region_gray(frame: ScreenshotFrame, bobber_position: tuple[int, int]) -> Optional[np.ndarray]:
        """
        Crops a square grayscale region of radius `splash_region_radius`
        around `bobber_position`, converted from absolute screen
        coordinates to frame-local pixel coordinates.
        """
        local_x = bobber_position[0] - frame.origin[0]
        local_y = bobber_position[1] - frame.origin[1]

        height, width = frame.image.shape[:2]
        x_start = max(0, local_x - splash_region_radius)
        x_end = min(width, local_x + splash_region_radius)
        y_start = max(0, local_y - splash_region_radius)
        y_end = min(height, local_y + splash_region_radius)

        if x_start >= x_end or y_start >= y_end:
            logger.warning("Bobber position %s is outside the captured frame; skipping splash check.",
                            bobber_position)
            return None

        region = frame.image[y_start:y_end, x_start:x_end]
        return cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
