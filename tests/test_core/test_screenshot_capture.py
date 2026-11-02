import re
import shutil
from pathlib import Path

import cv2
import pytest
from mss import MSS

import core.screenshot_capture as screenshot_capture_module
from core.screenshot_capture import ScreenshotCapture
from support.constants import screenshots_output_dir_name, period_of_screenshotting, screenshot_area, \
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


def test_capture_screenshots_creates_real_screenshot_files(objects):
    """
    Real (unmocked) test: actually grabs the screen via mss and makes
    sure the produced PNG files exist on disk with the expected count
    and dimensions, matching the real values from support.constants.
    """
    screenshot_capture = objects['screenshot_capture']
    screenshot_capture.capture_screenshots()

    created_files = sorted(screenshot_capture.output_dir.glob("*.png"))
    assert len(created_files) == period_of_screenshotting

    expected_width = screenshot_area["width"]
    expected_height = screenshot_area["height"]

    for file_path in created_files:
        image = cv2.imread(str(file_path))
        assert image is not None
        height, width = image.shape[:2]
        assert width == expected_width
        assert height == expected_height


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


def test_filenames_match_expected_pattern_and_monitor_offsets(objects):
    """
    Checks that every produced filename follows the documented pattern
    and encodes the correct monitor offsets (mon["top"] + pixels_from_top,
    mon["left"] + pixels_from_left) and dimensions from screenshot_area.
    """
    with MSS() as sct:
        mon = sct.monitors[monitor_number_where_the_screenshot_is_taken]

    expected_top = mon["top"] + screenshot_area["pixels_from_top"]
    expected_left = mon["left"] + screenshot_area["pixels_from_left"]
    expected_width = screenshot_area["width"]
    expected_height = screenshot_area["height"]

    screenshot_capture = objects['screenshot_capture']
    screenshot_capture.capture_screenshots()

    created_files = sorted(screenshot_capture.output_dir.glob("*.png"))
    assert len(created_files) == period_of_screenshotting

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
        assert 0 <= index < period_of_screenshotting
        seen_indices.add(index)

    assert seen_indices == set(range(period_of_screenshotting))


def test_capture_screenshots_with_zero_period_creates_no_files(objects, monkeypatch):
    """
    Edge case: if period_of_screenshotting is 0, capture_screenshots()
    should run without error and produce no files.
    """
    monkeypatch.setattr(screenshot_capture_module, "period_of_screenshotting", 0)

    screenshot_capture = objects['screenshot_capture']
    screenshot_capture.capture_screenshots()

    created_files = list(screenshot_capture.output_dir.glob("*.png"))
    assert created_files == []


@pytest.fixture(scope="session", autouse=True)
def screenshot_capture_teardown():
    """
    This function is automatically called after all test suites have run.
    """
    yield # All tests have run at this point, so we can perform any necessary cleanup here.

    output_dir = Path(screenshot_capture_module.__file__).parent.parent / screenshots_output_dir_name
    if output_dir.exists():
        shutil.rmtree(output_dir)
