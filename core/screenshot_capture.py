from pathlib import Path
from time import time

import cv2
import mss.tools
import numpy as np
from mss import MSS
from mss.base import MSSBase

from core.screenshot_frame import ScreenshotFrame
from support.app_error_handling import InvalidMonitorError, handle_errors
from support.app_logging import get_logger
from support.constants import monitor_number_where_the_screenshot_is_taken, \
    screenshot_area, screenshots_output_dir_name, capture_full_screen


logger = get_logger(__name__)


class ScreenshotCapture:
    def __init__(self):
        # Choose where screenshots are saved; created automatically if it doesn't exist
        project_root = Path(__file__).parent.parent
        self.output_dir = project_root / screenshots_output_dir_name
        self.output_dir.mkdir(exist_ok=True)

    @staticmethod
    def __get_information_of_monitor(
        sct: MSSBase, monitor_number: int = monitor_number_where_the_screenshot_is_taken
    ) -> dict:
        """
        Returns mss's monitor info dict (top/left/width/height/...) for
        the given monitor index, reusing an already-open MSS session.
        """
        try:
            mon = sct.monitors[monitor_number]
        except IndexError as error:
            raise InvalidMonitorError(
                f"Invalid monitor_number {monitor_number}; "
                f"available monitors: 0..{len(sct.monitors) - 1}"
            ) from error

        logger.debug("Monitor %s info: %s", monitor_number, mon)
        return mon

    @handle_errors()
    def capture_screenshot(self, screenshot_number: int) -> ScreenshotFrame:
        with MSS() as sct:
            # Get information of the configured monitor (single session,
            # reused for every grab below).
            mon = self.__get_information_of_monitor(sct, monitor_number_where_the_screenshot_is_taken)

            # Capture either the entire monitor, or a cropped region
            # offset from the monitor's top-left corner by the
            # configured pixel amounts, depending on capture_full_screen.
            if capture_full_screen:
                region = {
                    "top": mon["top"],
                    "left": mon["left"],
                    "width": mon["width"],
                    "height": mon["height"],
                }
            else:
                region = {
                    "top": mon["top"] + screenshot_area["pixels_from_top"],
                    "left": mon["left"] + screenshot_area["pixels_from_left"],
                    "width": screenshot_area["width"],
                    "height": screenshot_area["height"],
                }

            # Include the iteration index so each screenshot gets a unique filename
            filename = "sct-mon{mon}_{top}x{left}_{width}x{height}_{screenshot_number}.png".format(
                mon=monitor_number_where_the_screenshot_is_taken, screenshot_number=screenshot_number, **region
            )
            output = self.output_dir / filename

            # Grab the data
            sct_img = sct.grab(region)

            # Save to the picture file
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(output))
            logger.info("Saved screenshot: %s", output)

            # yield the single screenshot
            return ScreenshotFrame(
                image=cv2.cvtColor(np.array(sct_img), cv2.COLOR_BGRA2BGR),
                timestamp=time(),
                origin=(region["left"], region["top"])
            )
