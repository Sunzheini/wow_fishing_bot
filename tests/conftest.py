import pytest

import core.screenshot_capture as screenshot_capture_module
from core.screenshot_capture import ScreenshotCapture
from core.controls_interaction import ControlsInteraction
from core.object_detection import ObjectDetection
from core.ocr_recognition import OcrRecognition


def get_objects():
    return {
        'screenshot_capture': ScreenshotCapture(),
        'object_detection': ObjectDetection(),
        'controls_interaction': ControlsInteraction(),
        'ocr_recognition': OcrRecognition()
    }


@pytest.fixture
def objects():
    """
    Provides fresh instances of all core objects for a single test.
    """
    return get_objects()


@pytest.fixture(scope="session", autouse=True)
def isolate_screenshot_directory():
    """
    Redirects ScreenshotCapture to a dedicated "test_screenshots" folder
    for the entire test session, completely separate from the real
    "screenshots" folder used by actual bot runs.

    Without this, test cleanup (which deletes/clears its output
    directory) would operate on the SAME folder a real run saves to,
    and could wipe out real screenshots kept for debugging a live
    failure. Never share this directory with production code.
    """
    original = screenshot_capture_module.screenshots_output_dir_name
    screenshot_capture_module.screenshots_output_dir_name = "test_screenshots"
    yield
    screenshot_capture_module.screenshots_output_dir_name = original


@pytest.fixture(scope="session", autouse=True)
def test_suite_setup():
    """
    This function is automatically called before any test suite runs.
    """
    pass


@pytest.fixture(scope="session", autouse=True)
def test_suite_teardown():
    """
    This function is automatically called after all test suites have run.
    """
    pass
