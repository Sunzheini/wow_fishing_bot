import re
import shutil
from pathlib import Path

import cv2
import pytest
from mss import MSS

import core.screenshot_capture as screenshot_capture_module
from core.screenshot_capture import ScreenshotCapture
from core.screenshot_frame import ScreenshotFrame
from support.app_error_handling import InvalidMonitorError
from support.constants import screenshots_output_dir_name, screenshot_area, \
    monitor_number_where_the_screenshot_is_taken


FILENAME_PATTERN = re.compile(
    r"^sct-mon(?P<mon>\d+)_(?P<top>\d+)x(?P<left>\d+)_(?P<width>\d+)x(?P<height>\d+)_(?P<index>\d+)\.png$"
)


@pytest.fixture(scope="session", autouse=True)
def screenshot_capture_setup():
    """
    This function is automatically called before any test suite runs.
    """
    pass


@pytest.fixture(autouse=True)
def clear_png_files_before_each_test():
    """
    Ensures each test starts with an empty output directory by removing
    any leftover PNG files before it runs.
    """
    output_dir = Path(screenshot_capture_module.__file__).parent.parent / screenshots_output_dir_name
    if output_dir.exists():
        for png_file in output_dir.glob("*.png"):
            png_file.unlink()


def test_output_dir_is_created(objects):
    """
    Test that the output directory for screenshots is created
    correctly by the __init__ method of ScreenshotCapture.
    """
    screenshot_capture = objects['screenshot_capture']

    expected_dir = Path(screenshot_capture_module.__file__).parent.parent / screenshots_output_dir_name
    assert screenshot_capture.output_dir == expected_dir
    assert screenshot_capture.output_dir.exists()


def test_capture_screenshot_creates_real_screenshot_file(objects, monkeypatch):
    """
    Real (unmocked) test: actually grabs the screen via mss and makes
    sure the produced PNG file exists on disk with the expected
    dimensions, matching the real values from support.constants.
    """
    monkeypatch.setattr(screenshot_capture_module, "capture_full_screen", False)

    screenshot_capture = objects['screenshot_capture']
    screenshot_capture.capture_screenshot(0)

    created_files = sorted(screenshot_capture.output_dir.glob("*.png"))
    assert len(created_files) == 1

    expected_width = screenshot_area["width"]
    expected_height = screenshot_area["height"]

    image = cv2.imread(str(created_files[0]))
    assert image is not None
    height, width = image.shape[:2]
    assert width == expected_width
    assert height == expected_height


def test_capture_screenshot_returns_screenshot_frame(objects, monkeypatch):
    """
    capture_screenshot() must return a ScreenshotFrame whose image matches
    the configured dimensions and whose origin matches the monitor offset.
    """
    monkeypatch.setattr(screenshot_capture_module, "capture_full_screen", False)

    with MSS() as sct:
        mon = sct.monitors[monitor_number_where_the_screenshot_is_taken]

    expected_top = mon["top"] + screenshot_area["pixels_from_top"]
    expected_left = mon["left"] + screenshot_area["pixels_from_left"]

    screenshot_capture = objects['screenshot_capture']
    frame = screenshot_capture.capture_screenshot(0)

    assert isinstance(frame, ScreenshotFrame)
    assert frame.origin == (expected_left, expected_top)
    assert frame.image.shape[0] == screenshot_area["height"]
    assert frame.image.shape[1] == screenshot_area["width"]
    assert frame.image.shape[2] == 3  # BGR, no alpha channel
    assert isinstance(frame.timestamp, float)


def test_multiple_consecutive_captures_keep_all_files_and_frames(objects, monkeypatch):
    """
    Calling capture_screenshot() several times in a row must:
      - keep every previously saved file on disk (no overwrites/deletions),
      - create exactly one new file per call,
      - return a valid ScreenshotFrame for each call.
    """
    monkeypatch.setattr(screenshot_capture_module, "capture_full_screen", False)

    screenshot_capture = objects['screenshot_capture']
    num_screenshots = 4
    frames = []

    for screenshot_number in range(num_screenshots):
        frame = screenshot_capture.capture_screenshot(screenshot_number)
        frames.append(frame)

        # After each call, exactly screenshot_number + 1 files should exist.
        existing_files = sorted(screenshot_capture.output_dir.glob("*.png"))
        assert len(existing_files) == screenshot_number + 1

    # All frames returned are proper ScreenshotFrame instances with image data.
    assert len(frames) == num_screenshots
    for frame in frames:
        assert isinstance(frame, ScreenshotFrame)
        assert frame.image.shape[0] == screenshot_area["height"]
        assert frame.image.shape[1] == screenshot_area["width"]

    # Final state: one distinct, readable file per call, all still present.
    final_files = sorted(screenshot_capture.output_dir.glob("*.png"))
    assert len(final_files) == num_screenshots
    for file_path in final_files:
        image = cv2.imread(str(file_path))
        assert image is not None


def test_get_information_of_monitor_matches_real_mss_monitors():
    """
    Sanity check (real, unmocked): the private helper must return the
    exact same monitor info mss itself reports for the configured
    monitor index.
    """
    with MSS() as sct:
        expected_mon = sct.monitors[monitor_number_where_the_screenshot_is_taken]
        actual_mon = ScreenshotCapture._ScreenshotCapture__get_information_of_monitor(
            sct, monitor_number_where_the_screenshot_is_taken
        )

    assert actual_mon == expected_mon


def test_get_information_of_monitor_raises_for_invalid_monitor_number():
    """
    An out-of-range monitor number must raise InvalidMonitorError
    instead of letting a raw IndexError leak out.
    """
    with MSS() as sct:
        invalid_monitor_number = len(sct.monitors) + 10
        with pytest.raises(InvalidMonitorError):
            ScreenshotCapture._ScreenshotCapture__get_information_of_monitor(
                sct, invalid_monitor_number
            )


def test_capture_screenshot_propagates_invalid_monitor_error(objects, monkeypatch):
    """
    capture_screenshot() is decorated with handle_errors(), whose default
    behavior is to log and re-raise. An invalid configured monitor number
    should surface as InvalidMonitorError to the caller.
    """
    monkeypatch.setattr(
        screenshot_capture_module, "monitor_number_where_the_screenshot_is_taken", 999
    )

    screenshot_capture = objects['screenshot_capture']
    with pytest.raises(InvalidMonitorError):
        screenshot_capture.capture_screenshot(0)


def test_filenames_match_expected_pattern_and_monitor_offsets(objects, monkeypatch):
    """
    Checks that every produced filename follows the documented pattern
    and encodes the correct monitor offsets (mon["top"] + pixels_from_top,
    mon["left"] + pixels_from_left) and dimensions from screenshot_area.
    """
    monkeypatch.setattr(screenshot_capture_module, "capture_full_screen", False)

    with MSS() as sct:
        mon = sct.monitors[monitor_number_where_the_screenshot_is_taken]

    expected_top = mon["top"] + screenshot_area["pixels_from_top"]
    expected_left = mon["left"] + screenshot_area["pixels_from_left"]
    expected_width = screenshot_area["width"]
    expected_height = screenshot_area["height"]

    screenshot_capture = objects['screenshot_capture']
    num_screenshots = 3
    for screenshot_number in range(num_screenshots):
        screenshot_capture.capture_screenshot(screenshot_number)

    created_files = sorted(screenshot_capture.output_dir.glob("*.png"))
    assert len(created_files) == num_screenshots

    seen_indices = set()
    for file_path in created_files:
        match = FILENAME_PATTERN.match(file_path.name)
        assert match, f"Unexpected filename format: {file_path.name}"

        assert int(match.group("mon")) == monitor_number_where_the_screenshot_is_taken
        assert int(match.group("top")) == expected_top
        assert int(match.group("left")) == expected_left
        assert int(match.group("width")) == expected_width
        assert int(match.group("height")) == expected_height

        index = int(match.group("index"))
        assert 0 <= index < num_screenshots
        seen_indices.add(index)

    assert seen_indices == set(range(num_screenshots))


def test_capture_screenshot_full_screen_matches_monitor_dimensions(objects):
    """
    When capture_full_screen is True (the default), the captured frame
    must cover the entire configured monitor, not the cropped
    screenshot_area, regardless of screenshot_area's values.
    """
    with MSS() as sct:
        mon = sct.monitors[monitor_number_where_the_screenshot_is_taken]

    screenshot_capture = objects['screenshot_capture']
    frame = screenshot_capture.capture_screenshot(0)

    assert frame.origin == (mon["left"], mon["top"])
    assert frame.image.shape[0] == mon["height"]
    assert frame.image.shape[1] == mon["width"]


def test_clear_screenshots_removes_all_png_files(objects):
    """
    clear_screenshots() must delete every PNG file previously saved by
    capture_screenshot(), leaving the output directory empty (but intact).
    """
    screenshot_capture = objects['screenshot_capture']
    for screenshot_number in range(3):
        screenshot_capture.capture_screenshot(screenshot_number)

    assert len(list(screenshot_capture.output_dir.glob("*.png"))) == 3

    screenshot_capture.clear_screenshots()

    assert list(screenshot_capture.output_dir.glob("*.png")) == []
    assert screenshot_capture.output_dir.exists()  # the directory itself remains


def test_clear_screenshots_does_not_raise_when_directory_already_empty(objects):
    """clear_screenshots() on an already-empty directory must not raise."""
    screenshot_capture = objects['screenshot_capture']
    assert list(screenshot_capture.output_dir.glob("*.png")) == []

    screenshot_capture.clear_screenshots()  # should not raise


@pytest.fixture(scope="session", autouse=True)
def screenshot_capture_teardown():
    """
    This function is automatically called after all test suites have run.
    """
    yield # All tests have run at this point, so we can perform any necessary cleanup here.

    output_dir = Path(screenshot_capture_module.__file__).parent.parent / screenshots_output_dir_name
    if output_dir.exists():
        shutil.rmtree(output_dir)
