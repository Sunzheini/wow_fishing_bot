"""
This file contains constants used in the project.
"""

#region Screenshot Capture Constants
screenshots_output_dir_name = "screenshots"
monitor_number_where_the_screenshot_is_taken = 1
capture_full_screen = True  # if True, ignore screenshot_area and capture the entire monitor
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

#region Fishing State Machine Constants
max_state_machine_iterations = 100  # safety cap to avoid infinite loops
max_splash_watch_attempts = 25  # how many WATCHING_FOR_SPLASH attempts before giving up
cast_animation_wait_seconds = 1.5  # time to wait for the cast animation to finish before looking for the bobber
max_bobber_search_attempts = 10  # how many WAITING_FOR_BOBBER attempts before giving up
bobber_search_retry_delay_seconds = 0.5  # delay between WAITING_FOR_BOBBER retries
emergency_stop_hotkey = "esc"  # global hotkey that immediately stops the bot
#endregion

#region Object Detection Constants
assets_dir_name = "assets"
templates_dir_name = "templates"
bobber_template_file_name = "bobber.jpg"  # cropped reference image of the bobber icon/float
bobber_match_threshold = 0.8  # cv2.matchTemplate TM_CCOEFF_NORMED score required to accept a match

splash_template_file_name = "splash.jpg"  # cropped reference image of the splash/foam effect
splash_match_threshold = 0.7  # cv2.matchTemplate TM_CCOEFF_NORMED score required to accept a splash match
splash_search_radius = 80  # pixels around the bobber position to search for the splash template
#endregion

#region Controls Interaction Constants
fishing_keybind = "1"  # keyboard key bound to the fishing spell/action bar slot
key_press_duration = 0.05  # seconds to hold the fishing key down
mouse_move_duration = 0.1  # seconds for the mouse to travel to the bobber position
reel_click_button = "right"  # mouse button used to interact with / reel in the bobber
reel_click_modifier_key = "shift"  # held during the reel click to trigger WoW's auto-loot
#endregion

