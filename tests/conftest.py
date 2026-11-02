import pytest

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
