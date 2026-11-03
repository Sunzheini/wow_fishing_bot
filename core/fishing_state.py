from enum import Enum, auto


class FishingState(Enum):
    IDLE = auto()                   # not fishing, waiting to start
    CASTING = auto()                # press fishing key, bobber in flight
    WAITING_FOR_BOBBER = auto()     # looking for the bobber on screen
    WATCHING_FOR_SPLASH = auto()    # bobber found, waiting for the bite
    REELING = auto()                # right-click bobber / press interact
    LOOTING = auto()                # loot window, pick up fish
    STOPPED = auto()                # bag full or error — terminate
