# Templates

Place reference images used for `cv2.matchTemplate` here.

## `bobber.jpg`

A small, tightly cropped screenshot of the WoW fishing bobber icon/float
as it appears floating on water, at the same zoom/resolution you intend
to run the bot at. Used by `core.object_detection.ObjectDetection.find_bobber`.

Until this file exists, `ObjectDetection.find_bobber()` will log a warning
and always return `None`.
