from core.screenshot_capture import ScreenshotCapture
from core.object_detection import ObjectDetection
from core.controls_interaction import ControlsInteraction
from core.ocr_recognition import OcrRecognition


def main():
    # Initialize objects
    screenshot_capture = ScreenshotCapture()
    object_detection = ObjectDetection()
    controls_interaction = ControlsInteraction()
    ocr_recognition = OcrRecognition()

    # Capture screenshots
    screenshot_capture.capture_screenshots()


if __name__ == "__main__":
    main()
