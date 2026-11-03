from dataclasses import dataclass
import numpy as np


@dataclass
class ScreenshotFrame:
    """One captured screenshot plus the metadata needed to map crop-local
    pixel coordinates back to screen coordinates."""
    image: np.ndarray          # BGR, shape (H, W, 3)
    timestamp: float      # time.time() at capture
    origin: tuple[int, int]    # (left, top) of the captured region, in screen pixels
