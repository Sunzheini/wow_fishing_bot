# WoW Fishing Bot

A research/educational automation example that demonstrates how a vision-based
WoW fishing bot works end-to-end: screen capture → template-matching based
object detection → simulated keyboard/mouse input, driven by a simple state
machine. The goal is to study detection gaps and automation patterns (to help
identify/report issues with automation), not to provide an undetectable
cheat tool.

The architecture is purely visual/input-based — **no memory reading or packet
sniffing**:

1. **MSS** for screenshot capture.
2. **OpenCV** (`cv2.matchTemplate`) to locate the bobber and detect splashes.
3. **PyDirectInput** (SendInput-based) instead of PyAutoGUI, since many games
   ignore synthetic input that isn't sent via SendInput.
4. **`keyboard`** for a global emergency-stop hotkey (`Esc` by default).
5. A **Tkinter** GUI frontend (stdlib only, so it packages cleanly with
   PyInstaller) to start/stop the bot and visualize its progress.

## How it works (the state machine)

Pressing **Start** launches `FishingBot.run()` (in `core/fishing_bot.py`) on a
background thread. It first counts down from `start_delay_seconds` (default
**10 seconds**), logging one message per second (e.g. `"Starting in 10
seconds..."`) — visible live in the GUI's log panel — giving you time to
switch focus into the WoW window before anything is pressed/clicked. Pressing
Stop during this countdown aborts before the first cast ever happens.

After the countdown, it's a loop over `FishingState` (`core/fishing_state.py`):

```
IDLE → CASTING → WAITING_FOR_BOBBER → WATCHING_FOR_SPLASH → REELING → IDLE → ...
```

1. **IDLE** — presses the configured fishing keybind (`fishing_keybind`,
   default `"1"`) to cast the line.
2. **CASTING** — waits `cast_animation_wait_seconds` (default 1.5s) for the
   cast animation to finish and the bobber to land on the water.
3. **WAITING_FOR_BOBBER** — takes a screenshot and runs template matching
   (`bobber.jpg`) to find the bobber. Retries up to `max_bobber_search_attempts`
   times (with a short delay between attempts) before giving up **entirely**
   if the bobber can never be found (this usually means something is visually
   wrong — wrong screen region, no water in view, etc. — so the whole bot
   stops rather than looping forever).
4. **WATCHING_FOR_SPLASH** — once the bobber's position is known, this is the
   background polling loop: a screenshot is taken and analyzed for the splash
   template (`splash.jpg`) near the bobber **every `wait_time_between_screenshots`
   seconds (0.2s by default)**. This repeats for up to `max_splash_watch_attempts`
   (default 150 → ~30 seconds of watching, matching WoW Forever's maximum
   bite wait time).
   - **Splash detected** → go to REELING.
   - **No splash within the watch window** → this is normal (the fish just
     hasn't bitten yet), so the bot **recasts**: it goes back to IDLE and
     starts a brand new cast, rather than stopping.
5. **REELING** — moves the mouse to the bobber and **shift+right-clicks** it,
   which is WoW's auto-loot click: it reels in the catch and loots it in one
   action. Then goes back to IDLE to cast again.

This repeats indefinitely (cast → watch → reel/recast → cast → ...) until you
press **Stop**, close the GUI window, or press the emergency-stop hotkey
(`Esc`).

### Stopping & cleanup

- **Stop button / `Esc` hotkey / closing the window** all go through the same
  `request_stop()` mechanism, which is checked at the top of every loop
  iteration — the bot halts within at most one iteration (at most ~0.2s if
  it's mid-splash-watch).
- On shutdown, the bot:
  - unregisters the global emergency-stop hotkey, and
  - **deletes every screenshot saved during the run** (`core/screenshot_capture.py`'s
    `clear_screenshots()`). Screenshots are only ever useful as a transient
    debugging aid while the bot is actively running (there can be hundreds
    of them, captured every 0.2s while watching for a splash) — they are not
    meant to persist on disk afterward.

### Safety nets

Two independent caps exist purely to avoid a truly runaway process even if
something is misconfigured:
- `max_bobber_search_attempts` — stops the whole bot if the bobber is never
  found after a cast (likely a visual/config problem).
- `max_state_machine_iterations` — a very high hard ceiling (100,000) on total
  loop iterations, as a last-resort safety net.

## GUI

Run `python run_gui.py` (or the packaged `.exe`) to open the frontend:
- A vertical, stacked list of every `FishingState` step, highlighted green for
  the currently active step (red for `STOPPED`).
- **Start** / **Stop** buttons.
- A live, auto-scrolling log panel fed by the same centralized logger used
  everywhere else in the app (`support/app_logging.py`), so you see exactly
  what the bot is doing in real time.

## Multi-monitor setups

It's fine for the GUI to run on a different monitor than WoW:

- **Screen capture** (`mss`) grabs a specific **monitor index**
  (`monitor_number_where_the_screenshot_is_taken` in `support/constants.py`),
  not "whatever window is focused" — so detection works correctly regardless
  of where the GUI window sits, as long as that index points to WoW's monitor.
- **Keyboard/mouse input** is the tricky part: `pydirectinput` only delivers
  input to whichever window currently holds OS focus. Since clicking
  **Start** in the GUI gives *it* focus, input wouldn't reach WoW at all
  without extra handling. To fix this, `ControlsInteraction` automatically
  brings the WoW window to the foreground (via `support/window_utils.py`,
  matching the title against `wow_window_title_substring`, default
  `"World of Warcraft"`) immediately before every cast and every reel-in
  click — so you can safely leave the GUI focused/on a second monitor.

## Logging & error handling

All logs go to both the console and a rotating log file (`logs/app.log`,
5 MB per file, 5 backups kept) — see `support/app_logging.py`. All
application-specific exceptions derive from `AppError`
(`support/app_error_handling.py`), and the `@handle_errors()` decorator
ensures exceptions are logged with a full traceback before propagating.

## Not yet implemented

- **`core/ocr_recognition.py`** — currently an empty stub. The plan is to use
  OCR to detect the "Your bags are full" error text and stop/alert instead of
  continuing to cast, but this isn't wired into the state machine yet.

## Running

```powershell
poetry install
poetry run python run_gui.py   # GUI
poetry run python main.py      # headless CLI
poetry run pytest              # test suite
```

## Packaging (PyInstaller)

`run_gui.py` is the intended entry point for building a standalone `.exe`:

```powershell
pyinstaller --onefile --windowed --add-data "assets;assets" run_gui.py
```

`--add-data "assets;assets"` bundles the `bobber.jpg`/`splash.jpg` template
images the object-detection step depends on.
