from pathlib import Path

import cv2
import pytest

import core.object_detection as object_detection_module
from core.object_detection import ObjectDetection
from core.screenshot_frame import ScreenshotFrame
from support.app_error_handling import TemplateNotFoundError
from support.constants import assets_dir_name, templates_dir_name

ASSETS_DIR = Path(object_detection_module.__file__).parent.parent / assets_dir_name / templates_dir_name

KNOWN_BOBBER_POSITION = (901, 425)  # confirmed via find_bobber() on the real fixture screenshot
# The splash fixture is from a different real cast/session than the
# no-splash fixture above, so the bobber was at a different position.
SPLASH_BOBBER_POSITION = (940, 375)


def load_frame(filename: str) -> ScreenshotFrame:
    """Loads one of the real fixture screenshots as a ScreenshotFrame with origin (0, 0)."""
    image = cv2.imread(str(ASSETS_DIR / filename))
    assert image is not None, f"Failed to load fixture image: {filename}"
    return ScreenshotFrame(image=image, timestamp=0.0, origin=(0, 0))


def test_templates_are_loaded_on_init(objects):
    """
    The bobber template must load successfully from the real asset
    file, since it's present in assets/templates/. (Splash detection no
    longer uses a template -- see detect_splash tests below.)
    """
    object_detection = objects['object_detection']

    assert object_detection.bobber_template_gray is not None


def test_load_template_gray_returns_none_for_missing_file():
    """
    A missing template file should log a warning and return None,
    instead of raising, so the bot can still start without real assets.
    """
    missing_path = ASSETS_DIR / "does_not_exist.jpg"
    assert not missing_path.exists()

    result = ObjectDetection._ObjectDetection__load_template_gray(missing_path)
    assert result is None


def test_load_template_gray_raises_for_corrupt_file(tmp_path):
    """
    An existing but unreadable/corrupt image file should raise
    TemplateNotFoundError instead of silently returning None.
    """
    corrupt_file = tmp_path / "corrupt.jpg"
    corrupt_file.write_bytes(b"not a real image")

    with pytest.raises(TemplateNotFoundError):
        ObjectDetection._ObjectDetection__load_template_gray(corrupt_file)


def test_find_bobber_returns_none_when_no_bobber_present(objects):
    """
    find_bobber() must return None on a screenshot where no bobber is
    visible at all.
    """
    object_detection = objects['object_detection']
    frame = load_frame("screenshot_no_bobber.jpg")

    assert object_detection.find_bobber(frame) is None


def test_find_bobber_finds_bobber_when_present(objects):
    """
    find_bobber() must locate the bobber on a screenshot where it's
    floating on the water (no splash yet), returning a position close
    to the known real location.
    """
    object_detection = objects['object_detection']
    frame = load_frame("screenshot_with_bobber_no_splash.jpg")

    position = object_detection.find_bobber(frame)

    assert position is not None
    x, y = position
    expected_x, expected_y = KNOWN_BOBBER_POSITION
    assert abs(x - expected_x) <= 5
    assert abs(y - expected_y) <= 5


def test_find_bobber_respects_frame_origin_offset(objects):
    """
    find_bobber() must add frame.origin to the locally-matched position,
    so a non-zero origin (e.g. from a cropped capture) is handled correctly.
    """
    object_detection = objects['object_detection']
    image = cv2.imread(str(ASSETS_DIR / "screenshot_with_bobber_no_splash.jpg"))
    offset_origin = (100, 50)
    frame = ScreenshotFrame(image=image, timestamp=0.0, origin=offset_origin)

    position = object_detection.find_bobber(frame)

    assert position is not None
    x, y = position
    expected_x = KNOWN_BOBBER_POSITION[0] + offset_origin[0]
    expected_y = KNOWN_BOBBER_POSITION[1] + offset_origin[1]
    assert abs(x - expected_x) <= 5
    assert abs(y - expected_y) <= 5


def test_find_bobber_returns_none_when_template_missing(objects, monkeypatch):
    """
    If the bobber template failed to load (None), find_bobber() must
    return None instead of raising.
    """
    object_detection = objects['object_detection']
    monkeypatch.setattr(object_detection, "bobber_template_gray", None)

    frame = load_frame("screenshot_with_bobber_no_splash.jpg")
    assert object_detection.find_bobber(frame) is None


def test_find_bobber_returns_none_when_frame_smaller_than_template(objects):
    """
    A frame smaller than the template in either dimension must be
    handled gracefully, returning None instead of raising from
    cv2.matchTemplate.
    """
    object_detection = objects['object_detection']
    tiny_image = cv2.imread(str(ASSETS_DIR / "bobber.jpg"))[:5, :5]
    frame = ScreenshotFrame(image=tiny_image, timestamp=0.0, origin=(0, 0))

    assert object_detection.find_bobber(frame) is None


def test_detect_splash_false_when_no_splash_present(objects):
    """
    detect_splash() must return False for a frame where the bobber is
    floating but hasn't splashed yet.
    """
    object_detection = objects['object_detection']
    frame = load_frame("screenshot_with_bobber_no_splash.jpg")

    assert object_detection.detect_splash(frame, KNOWN_BOBBER_POSITION) is False


def test_detect_splash_true_when_splash_present(objects):
    """
    detect_splash() must return True for a frame where the bobber has
    just splashed.
    """
    object_detection = objects['object_detection']
    frame = load_frame("screenshot_with_bobber_with_splash.jpg")

    assert object_detection.detect_splash(frame, SPLASH_BOBBER_POSITION) is True


def test_detect_splash_returns_false_when_region_out_of_frame(objects):
    """
    If the splash region computed around bobber_position doesn't
    overlap the frame at all, detect_splash() must return False
    instead of raising.
    """
    object_detection = objects['object_detection']
    frame = load_frame("screenshot_with_bobber_with_splash.jpg")
    out_of_bounds_position = (-10_000, -10_000)

    assert object_detection.detect_splash(frame, out_of_bounds_position) is False


# ----- Multi-scale matching --------------------------------------------------

def test_find_bobber_still_finds_bobber_when_template_is_scaled_down(objects, monkeypatch):
    """
    If the real bobber appears SMALLER on screen than the stored
    template (e.g. the player zoomed out since the template was
    captured), find_bobber() must still locate it by trying smaller
    scaled-down versions of the template.
    """
    object_detection = objects['object_detection']

    # Shrink the real fixture screenshot itself to 70% size, simulating
    # the bobber appearing smaller (more "zoomed out") than the template.
    original = cv2.imread(str(ASSETS_DIR / "screenshot_with_bobber_no_splash.jpg"))
    shrunk = cv2.resize(original, (int(original.shape[1] * 0.7), int(original.shape[0] * 0.7)))
    frame = ScreenshotFrame(image=shrunk, timestamp=0.0, origin=(0, 0))

    position = object_detection.find_bobber(frame)

    assert position is not None
    expected_x = int(KNOWN_BOBBER_POSITION[0] * 0.7)
    expected_y = int(KNOWN_BOBBER_POSITION[1] * 0.7)
    assert abs(position[0] - expected_x) <= 10
    assert abs(position[1] - expected_y) <= 10


def test_multi_scale_match_prefers_the_best_scoring_scale(objects):
    """
    __multi_scale_match must return the highest score found across all
    configured scales, not just whatever the first scale happens to produce.
    """
    object_detection = objects['object_detection']
    frame = load_frame("screenshot_with_bobber_no_splash.jpg")
    frame_gray = cv2.cvtColor(frame.image, cv2.COLOR_BGR2GRAY)

    best_score, best_loc, best_shape = ObjectDetection._ObjectDetection__multi_scale_match(
        frame_gray, object_detection.bobber_template_gray, [0.5, 1.0, 1.5]
    )

    # Manually compute the score at scale=1.0 (no resizing) and confirm
    # the multi-scale result is at least as good (it found the real
    # bobber, cropped at native scale, so 1.0 should already be near-perfect).
    import cv2 as cv2_local
    result = cv2_local.matchTemplate(frame_gray, object_detection.bobber_template_gray, cv2_local.TM_CCOEFF_NORMED)
    _, single_scale_score, _, _ = cv2_local.minMaxLoc(result)

    assert best_score >= single_scale_score - 1e-6
    assert best_score > 0.9  # this fixture was cropped from this exact screenshot


# ----- Color-blob fallback -----------------------------------------------------

def test_find_bobber_uses_color_fallback_when_template_score_is_low(objects, monkeypatch):
    """
    If the template match score is below threshold, find_bobber() must
    still locate the bobber via the color-blob fallback (seeded by the
    template's best guess), rather than giving up immediately.
    """
    object_detection = objects['object_detection']
    frame = load_frame("screenshot_with_bobber_no_splash.jpg")

    # Force the template match to "fail" (as if captured at a very
    # different zoom level), so only the color-blob fallback can succeed.
    monkeypatch.setattr(object_detection_module, "bobber_match_threshold", 1.01)

    position = object_detection.find_bobber(frame)

    assert position is not None
    expected_x, expected_y = KNOWN_BOBBER_POSITION
    # The color-blob fallback is less precise than a good template
    # match, so allow a more generous tolerance.
    assert abs(position[0] - expected_x) <= 30
    assert abs(position[1] - expected_y) <= 30


def test_find_bobber_returns_none_without_seed_when_template_missing(objects, monkeypatch):
    """
    The color-blob fallback requires a template-based seed location to
    search near it (scanning the whole central region without one is
    too noisy in practice). If no template is loaded at all, find_bobber()
    must return None rather than attempting an unseeded color scan.
    """
    object_detection = objects['object_detection']
    monkeypatch.setattr(object_detection, "bobber_template_gray", None)

    frame = load_frame("screenshot_with_bobber_no_splash.jpg")
    assert object_detection.find_bobber(frame) is None


# ----- Bobber motion confirmation --------------------------------------------

def test_is_bobber_candidate_static_true_for_identical_frames(objects):
    """
    If the area around the candidate position is pixel-identical between
    two frames, it must be flagged as static (a likely false positive on
    a background/UI element, since real water always has some ripple).
    """
    object_detection = objects['object_detection']
    image = cv2.imread(str(ASSETS_DIR / "screenshot_with_bobber_no_splash.jpg"))

    frame_a = ScreenshotFrame(image=image, timestamp=0.0, origin=(0, 0))
    frame_b = ScreenshotFrame(image=image.copy(), timestamp=0.1, origin=(0, 0))

    assert object_detection.is_bobber_candidate_static(frame_a, frame_b, KNOWN_BOBBER_POSITION) is True


def test_is_bobber_candidate_static_false_when_region_changes(objects):
    """
    If the area around the candidate position visibly changes between
    the two frames (simulated here by brightening it), it must NOT be
    flagged as static.
    """
    object_detection = objects['object_detection']
    image_a = cv2.imread(str(ASSETS_DIR / "screenshot_with_bobber_no_splash.jpg"))
    image_b = image_a.copy()

    x, y = KNOWN_BOBBER_POSITION
    # Brighten a patch around the candidate position to simulate motion/ripple.
    image_b[y - 20:y + 20, x - 20:x + 20] = cv2.add(image_b[y - 20:y + 20, x - 20:x + 20], 100)

    frame_a = ScreenshotFrame(image=image_a, timestamp=0.0, origin=(0, 0))
    frame_b = ScreenshotFrame(image=image_b, timestamp=0.1, origin=(0, 0))

    assert object_detection.is_bobber_candidate_static(frame_a, frame_b, KNOWN_BOBBER_POSITION) is False


def test_is_bobber_candidate_static_false_when_region_out_of_bounds(objects):
    """
    An inconclusive comparison (position outside the frame) must not be
    treated as "static" -- it shouldn't block a legitimate candidate
    just because the check itself couldn't run.
    """
    object_detection = objects['object_detection']
    frame = load_frame("screenshot_with_bobber_no_splash.jpg")
    out_of_bounds_position = (-10_000, -10_000)

    assert object_detection.is_bobber_candidate_static(frame, frame, out_of_bounds_position) is False


# ----- Bobber feather color confirmation --------------------------------------

def test_has_bobber_feather_colors_true_at_the_real_bobber_position(objects):
    """
    The real bobber position must have both the blue and red feather
    colors detected nearby.
    """
    object_detection = objects['object_detection']
    frame = load_frame("screenshot_with_bobber_no_splash.jpg")

    assert object_detection.has_bobber_feather_colors(frame, KNOWN_BOBBER_POSITION) is True


def test_has_bobber_feather_colors_false_on_plain_water(objects):
    """
    A position over plain water (no bobber at all) must not have the
    feather colors detected -- real water lacks the saturated blue/red
    hues entirely.
    """
    object_detection = objects['object_detection']
    frame = load_frame("screenshot_no_bobber.jpg")

    # Same coordinates as the (now patched-over) bobber position in the
    # synthetic no-bobber fixture.
    assert object_detection.has_bobber_feather_colors(frame, KNOWN_BOBBER_POSITION) is False


def test_has_bobber_feather_colors_true_when_region_out_of_bounds(objects):
    """
    An inconclusive check (position outside the frame) must not block a
    legitimate candidate just because the check itself couldn't run.
    """
    object_detection = objects['object_detection']
    frame = load_frame("screenshot_with_bobber_no_splash.jpg")
    out_of_bounds_position = (-10_000, -10_000)

    assert object_detection.has_bobber_feather_colors(frame, out_of_bounds_position) is True


