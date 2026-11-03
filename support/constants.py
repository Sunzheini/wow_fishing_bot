"""
This file contains constants used in the project.
"""

#region Screenshot Capture Constants
screenshots_output_dir_name = "screenshots"
monitor_number_where_the_screenshot_is_taken = 1
screenshot_area = {
    "pixels_from_top": 100,  # 100px from the top
    "pixels_from_left": 100,  # 100px from the left
    "width": 250,
    "height": 250,
}
period_of_screenshotting = 5
wait_time_between_screenshots = 0.2  # 200 milliseconds
#endregion

#region Logging Constants
log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
log_date_format = "%Y-%m-%d %H:%M:%S"
logs_output_dir_name = "logs"
log_file_name = "app.log"
max_log_file_size_bytes = 5 * 1024 * 1024  # 5 MB
log_backup_count = 5  # keep up to 5 rotated log files
#endregion
