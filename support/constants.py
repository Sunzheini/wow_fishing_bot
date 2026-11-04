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
# Counting a fixed number of attempts (at the nominal
# wait_time_between_screenshots cadence) to approximate a time budget
# was confirmed unreliable in practice: real screenshot capture +
# detection overhead pushes the actual per-attempt cadence well above
# the nominal sleep (observed ~0.5s/attempt instead of 0.2s), making a
# 150-attempt budget take ~75s instead of the intended ~30s. Track
# real wall-clock elapsed time instead (WoW Forever's max bite wait
# time is ~30s).
splash_watch_timeout_seconds = 30
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
# The player always casts toward the water in a fairly constrained
# central region of the screen, confirmed directly by the user: when
# the screen height is divided into 9 equal parts, the bobber only ever
# appears in parts 2-6 (never the very top -- sky/wall/UI -- or the
# bottom ~1/3, which includes the action bar); when the width is
# divided into 9 parts, it only ever appears in parts 4-7 (never near
# the left/right edges). Restricting the search to exactly this
# central bounding box (instead of just excluding top/bottom strips)
# is far more robust: it was the only way to reliably eliminate
# false-positive matches that kept appearing near screen corners/edges.
bobber_search_region_x_fraction = (2 / 9, 7 / 9)  # (left, right) as a fraction of frame width
# Tightened further after confirming part of the beach (a static
# terrain patch, not water) was included around rows 500-600 of a
# 1080p frame -- this acted as a persistent low-confidence distractor
# whenever the real bobber was hard to match. Bottom bound lowered from
# 6/9 (720px) to 500px so rows 500+ are excluded entirely.
bobber_search_region_y_fraction = (1 / 9, 500 / 1080)  # (top, bottom) as a fraction of frame height

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

# Template matching (grayscale shape) is sensitive to camera zoom/angle
# changes between casts/sessions, which repeatedly caused real bobber
# scores to drop below threshold even right after a successful recrop.
# The feather colors are far more stable across zoom levels than exact
# shape, so when the template match fails, fall back to directly
# scanning for a blue blob near a red blob (the two feathers always sit
# close together, just above the body) -- independent of template size
# or exact silhouette entirely.
bobber_color_fallback_min_blob_area = 15  # minimum connected-component pixel area to count as a real blob (filters noise specks)
bobber_color_fallback_max_pair_distance = 60  # max pixel distance between a blue blob and red blob centroid
# Scanning the entire central bounding box for color blobs picks up too
# much noise (water highlights, distant foliage, etc. can coincidentally
# look blue/red). The template match's best-guess location -- even when
# its score is below threshold -- was empirically confirmed to still
# land close to the real bobber, so use it as a search seed and only
# look for color blobs within this radius of it, instead of the whole
# central region. Falls back to the full central region only if no
# template is loaded at all (no seed available).
bobber_color_fallback_search_radius = 100  # pixels around the template's best guess to search for color blobs
# Confirmed via a real missed detection: the template's single
# GLOBAL-best-scoring location is not always the real bobber -- an
# unrelated location elsewhere in the frame can occasionally score
# almost identically (both ~0.467 in one observed case), causing the
# fallback to search in the wrong place entirely and miss a bobber that
# would otherwise have passed the color check. Trying several of the
# top-scoring (but mutually distant) candidate locations as fallback
# seeds, instead of just the single best one, makes this far more robust.
bobber_fallback_seed_candidates = 4  # how many distinct top-scoring locations to try as fallback seeds
bobber_fallback_seed_min_distance = 80  # min pixel distance between candidate seeds to count as "distinct"

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
# Confirmed via 4 real missed splashes (user visually confirmed real
# splashes across 3 different timed-out casts) that scored only
# 0.0003-0.0016 at brightness_threshold=200 -- apparently not an
# occasional fluke but a common occurrence (roughly 1/3 of real splashes
# in that session). Direct pixel analysis of those exact frames showed
# their foam pixels peaked around grayscale 225-255 but most of the
# foam area was only in the 150-200 range, i.e. not pure/saturated
# white -- too dim to count under the old threshold. At
# brightness_threshold=150, those same 4 frames scored 0.0063-0.0131 (a
# clean, strong signal), while confirmed non-splash baseline frames
# from the very same casts still scored exactly 0.0000 (max pixel value
# stayed at 94-132, safely below 150) -- so lowering the brightness
# threshold is well-supported and doesn't risk false positives.
splash_brightness_threshold = 150  # grayscale value (0-255) considered "bright" (splash foam/water)
# Set well above the confirmed 0.0000 baseline noise floor and safely
# below the weakest observed real splash (0.0063) for a wide margin.
splash_pixel_ratio_threshold = 0.003  # fraction of bright pixels in the region needed to count as a splash
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
# After looting, park the mouse cursor out of the way so it doesn't
# linger over the water -- an idle cursor can show a tooltip/highlight
# over nearby objects, and keeping it away from the capture area avoids
# any chance of it visually interfering with the next screenshot's
# bobber/splash detection.
park_mouse_after_reel = True
park_mouse_position = (5, 5)  # absolute screen coordinates (near top-left corner)
park_mouse_move_duration = 0.2  # deliberately longer than mouse_move_duration, so the move is clearly visible
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
