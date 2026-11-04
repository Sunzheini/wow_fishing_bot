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
bobber_match_threshold = 0.70  # cv2.matchTemplate TM_CCOEFF_NORMED score required to accept a match
# The bobber's apparent on-screen size varies with camera zoom, which the
# player can change between casts/sessions. Instead of needing a template
# recropped for the exact current zoom, search multiple scaled versions
# of the template and keep whichever scores best.
bobber_match_scales = [0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.25, 1.4, 1.6, 1.8]
# The player always casts toward the water roughly in the center of the
# screen, never right at the very top (which only ever shows sky/wall/UI
# elements like minimap icons -- one of which was confirmed to
# consistently produce a false-positive template match score close to
# real bobber detections). Excluding this top strip from the search
# entirely is more robust than just raising the match threshold, since
# real bobber scores can sometimes be just as low.
bobber_search_exclude_top_fraction = 0.12  # fraction of frame height excluded from the top of the search

# The bobber's two feathers have distinctive, saturated blue and red
# colors that plain water never has -- template matching alone works on
# grayscale and ignores this entirely. As an additional confirmation
# step (alongside the motion check), verify that a candidate position
# actually has both colors nearby. Calibrated directly against the real
# bobber.jpg template (100 blue / 25 red pixels out of 644 total) vs. a
# plain water patch (0 of each) -- clean separation, so fairly generous
# minimums still safely reject pure water false positives.
bobber_color_check_radius = 15  # pixels around the candidate position to inspect for feather colors
bobber_color_min_saturation = 40  # HSV saturation required to count as a "colorful" (non-water) pixel
bobber_color_min_value = 40  # HSV value (brightness) required to count as a "colorful" pixel
bobber_color_blue_hue_range = (95, 140)  # HSV hue range (0-179) for the blue feather
bobber_color_red_hue_ranges = [(0, 12), (168, 179)]  # HSV hue wraps around 0/179 for red
bobber_color_min_blue_pixels = 5  # minimum blue pixels required in the region
bobber_color_min_red_pixels = 3  # minimum red pixels required in the region

# The splash is a randomly-scattered particle/foam effect -- the
# relative positions of its bright pixels differ every time, even
# though the general appearance is similar. That makes rigid template
# matching fundamentally unreliable here (validated against 2 real
# sessions: scores for confirmed real splashes landed in the same
# 0.6-0.7 range as plain background noise). A brightness/pixel-density
# heuristic is position/shape-invariant and was validated as a clean,
# repeatable signal across 3 independent real screenshots: ratio>200
# was exactly 0.0 on every non-splash frame, and 0.004-0.009 on every
# confirmed real splash frame.
splash_region_radius = 40  # pixels around the bobber to inspect for a splash
splash_brightness_threshold = 200  # grayscale value (0-255) considered "bright" (splash foam/water)
splash_pixel_ratio_threshold = 0.002  # fraction of bright pixels in the region needed to count as a splash
#endregion

#region Controls Interaction Constants
fishing_keybind = "1"  # keyboard key bound to the fishing spell/action bar slot
key_press_duration = 0.05  # seconds to hold the fishing key down
mouse_move_duration = 0.05  # seconds for the mouse to travel to the bobber position
reel_click_button = "right"  # mouse button used to interact with / reel in the bobber
reel_click_modifier_key = "shift"  # held during the reel click to trigger WoW's auto-loot
# pydirectinput's click() performs mouseDown+mouseUp almost instantly. Some
# games (including WoW) poll modifier key state and can miss a modifier
# that wasn't held for at least a few ms before/during the click, so the
# right-click registers but Shift isn't seen -> reels in without looting.
# These delays ensure Shift is clearly down before the click starts and
# still down for a moment after it ends. (Looting is now confirmed
# working in practice, so these were trimmed down from more cautious
# initial values -- just enough margin, not excessive.)
reel_modifier_press_delay = 0.05  # held after keyDown(shift), before the mouse click starts
reel_click_hold_duration = 0.04  # how long the mouse button itself stays down
reel_modifier_release_delay = 0.05  # held after the click ends, before keyUp(shift)
# WoW's clickable hitbox for the fishing bobber is notoriously tiny (a
# few pixels), while the detected position is only the center of the
# visual template match, which can be slightly offset from the real
# interactable point. A small cross spray around the detected position
# greatly increases the odds of landing on the bobber -- any clicks
# that miss just land harmlessly on water. Trimmed to a tighter 5-point
# cross (center + 4 adjacent points) now that looting is confirmed
# working, since the 9-point version made each reel-in take ~5s.
reel_click_spray_offsets = [
    (0, 0), (0, -4), (0, 4), (-4, 0), (4, 0),
]
reel_click_spray_delay = 0.05  # pause between consecutive spray click attempts
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
