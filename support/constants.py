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
wait_time_between_screenshots = 0.2  # delay between consecutive splash-watch screenshots
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
max_state_machine_iterations = 100_000  # safety cap to avoid a truly infinite loop
start_delay_seconds = 10  # countdown after Start is pressed, before the first cast (time to alt-tab into WoW)
# At wait_time_between_screenshots=0.2s, 150 attempts is ~30s of watching for a
# bite before giving up on this cast and recasting (WoW Forever's max bite
# wait time is ~30s).
max_splash_watch_attempts = 150
cast_animation_wait_seconds = 1.5  # time to wait for the cast animation to finish before looking for the bobber
max_bobber_search_attempts = 10  # how many WAITING_FOR_BOBBER attempts before giving up entirely
bobber_search_retry_delay_seconds = 0.5  # delay between WAITING_FOR_BOBBER retries
emergency_stop_hotkey = "esc"  # global hotkey that immediately stops the bot
#endregion

#region Bobber Motion Confirmation Constants
# Template matching can occasionally lock onto a static background/UI
# element that happens to resemble the bobber template (a false
# positive). Real water (with a real bobber on it) always has at least
# subtle ripple motion, so after finding a candidate we take one more
# quick screenshot and reject the candidate if that area is suspiciously
# frozen (pixel-identical) between the two frames.
bobber_motion_check_delay_seconds = 0.3  # gap between the two confirmation frames
bobber_motion_check_radius = 20  # pixels around the candidate position to check for motion
bobber_motion_min_diff = 15  # min per-pixel BGR-sum difference required to call it "moving water"
#endregion

#region Object Detection Constants
assets_dir_name = "assets"
templates_dir_name = "templates"
bobber_template_file_name = "bobber.jpg"  # cropped reference image of the bobber icon/float
bobber_match_threshold = 0.65  # cv2.matchTemplate TM_CCOEFF_NORMED score required to accept a match
# The bobber's apparent on-screen size varies with camera zoom, which the
# player can change between casts/sessions. Instead of needing a template
# recropped for the exact current zoom, search multiple scaled versions
# of the template and keep whichever scores best.
bobber_match_scales = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4, 1.6, 1.8]

splash_template_file_name = "splash.jpg"  # cropped reference image of the splash/foam effect
splash_match_threshold = 0.8  # cv2.matchTemplate TM_CCOEFF_NORMED score required to accept a splash match
splash_search_radius = 80  # pixels around the bobber position to search for the splash template
splash_match_scales = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4, 1.6, 1.8]  # same rationale as bobber_match_scales
#endregion

#region Controls Interaction Constants
fishing_keybind = "1"  # keyboard key bound to the fishing spell/action bar slot
key_press_duration = 0.05  # seconds to hold the fishing key down
mouse_move_duration = 0.1  # seconds for the mouse to travel to the bobber position
reel_click_button = "right"  # mouse button used to interact with / reel in the bobber
reel_click_modifier_key = "shift"  # held during the reel click to trigger WoW's auto-loot
wow_window_title_substring = "World of Warcraft"  # used to find & focus the game window before sending input
#endregion

#region GUI Constants
gui_window_title = "WoW Fishing Bot"
gui_window_size = "560x660"
gui_poll_interval_ms = 150  # how often the GUI polls the background bot thread's log/state queue
gui_step_color_active = "#2e7d32"  # green background for the currently active step
gui_step_color_stopped = "#b71c1c"  # red background for the STOPPED step when reached
gui_step_color_inactive = "#e0e0e0"  # default/inactive step background
gui_log_font = ("Consolas", 8)  # smaller, monospaced font for the log panel
#endregion
