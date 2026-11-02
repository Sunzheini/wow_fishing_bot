from pathlib import Path

from mss import MSS
import mss.tools
from time import sleep

from support.constants import monitor_number_where_the_screenshot_is_taken, period_of_screenshotting, \
    wait_time_between_screenshots, screenshot_area, screenshots_output_dir_name


class ScreenshotCapture:
    def __init__(self):
        # Choose where screenshots are saved; created automatically if it doesn't exist
        project_root = Path(__file__).parent.parent
        self.output_dir = project_root / screenshots_output_dir_name
        self.output_dir.mkdir(exist_ok=True)

    @staticmethod
    def __get_information_of_monitor(monitor_number=monitor_number_where_the_screenshot_is_taken):
        with MSS() as sct:
            mon = sct.monitors[monitor_number]
            print(mon)
            return mon

    def capture_screenshots(self):
        with MSS() as sct:
            # Get information of monitor
            mon = self.__get_information_of_monitor(monitor_number_where_the_screenshot_is_taken)

            for takt in range(period_of_screenshotting):
                # Capture a part of the screen (e.g., top-left corner)
                monitor = {
                    "top": mon["top"] + screenshot_area["pixels_from_top"],  # 100px from the top
                    "left": mon["left"] + screenshot_area["pixels_from_left"],  # 100px from the left
                    "width": screenshot_area["width"],
                    "height": screenshot_area["height"],
                    "mon": monitor_number_where_the_screenshot_is_taken,
                }

                # Include the iteration index so each screenshot gets a unique filename
                filename = "sct-mon{mon}_{top}x{left}_{width}x{height}_{takt}.png".format(
                    takt=takt, **monitor
                )
                output = self.output_dir / filename

                # Grab the data
                sct_img = sct.grab(monitor)

                # Save to the picture file
                mss.tools.to_png(sct_img.rgb, sct_img.size, output=str(output))
                print(output)

                # Wait before taking the next screenshot
                sleep(wait_time_between_screenshots)
