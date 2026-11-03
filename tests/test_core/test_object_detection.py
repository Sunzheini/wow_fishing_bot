from pathlib import Path

import cv2
import pytest

import core.object_detection as object_detection_module
from core.object_detection import ObjectDetection
from core.screenshot_frame import ScreenshotFrame
from support.app_error_handling import TemplateNotFoundError
from support.constants import assets_dir_name, templates_dir_name

ASSETS_DIR = Path(object_detection_module.__file__).parent.parent / assets_dir_name / templates_dir_name

KNOWN_BOBBER_POSITION = (1015, 299)  # confirmed via find_bobber() on the real fixture screenshot


def load_frame(filename: str) -> ScreenshotFrame:
    """Loads one of the real fixture screenshots as a ScreenshotFrame with origin (0, 0)."""
    image = cv2.imread(str(ASSETS_DIR / filename))
    assert image is not None, f"Failed to load fixture image: {filename}"
    return ScreenshotFrame(image=image, timestamp=0.0, origin=(0, 0))


def test_templates_are_loaded_on_init(objects):
    """
    Both the bobber and splash templates must load successfully from the
    real asset files, since they're present in assets/templates/.
    """
    object_detection = objects['object_detection']

    assert object_detection.bobber_template_gray is not None
    assert object_detection.splash_template_gray is not None


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

    assert object_detection.detect_splash(frame, KNOWN_BOBBER_POSITION) is True


def test_detect_splash_returns_false_when_template_missing(objects, monkeypatch):
    """
    If the splash template failed to load (None), detect_splash() must
    return False instead of raising.
    """
    object_detection = objects['object_detection']
    monkeypatch.setattr(object_detection, "splash_template_gray", None)

    frame = load_frame("screenshot_with_bobber_with_splash.jpg")
    assert object_detection.detect_splash(frame, KNOWN_BOBBER_POSITION) is False


def test_detect_splash_returns_false_for_out_of_bounds_bobber_position(objects):
    """
    A bobber_position far outside the frame bounds must be handled
    gracefully (no crash), returning False.
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

