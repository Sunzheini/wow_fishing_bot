import keyboard

from support.app_error_handling import handle_errors
from support.app_logging import get_logger
from support.constants import emergency_stop_hotkey

logger = get_logger(__name__)


class EmergencyStop:
    """
    Listens globally (OS-level, regardless of which window has focus) for
    a configured hotkey. Once pressed, is_stop_requested() returns True,
    which the main state machine loop checks every iteration to stop
    immediately, no matter what state it's currently in.
    """

    @handle_errors()
    def __init__(self):
        self._stop_requested = False
        keyboard.add_hotkey(emergency_stop_hotkey, self._on_hotkey_pressed)
        logger.info("Emergency stop hotkey registered: '%s'", emergency_stop_hotkey)

    def _on_hotkey_pressed(self) -> None:
        if not self._stop_requested:
            logger.warning("Emergency stop hotkey ('%s') pressed; requesting stop.", emergency_stop_hotkey)
        self._stop_requested = True

    def is_stop_requested(self) -> bool:
        return self._stop_requested

    def reset(self) -> None:
        """Clears the stop flag, allowing the bot to be started again."""
        self._stop_requested = False

    def stop_listening(self) -> None:
        """Unregisters the hotkey. Should be called when the bot shuts down."""
        try:
            keyboard.remove_hotkey(emergency_stop_hotkey)
            logger.debug("Emergency stop hotkey unregistered: '%s'", emergency_stop_hotkey)
        except KeyError:
            # Hotkey was already removed/never registered successfully.
            pass
