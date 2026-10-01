from pathlib import Path

from . import APP_NAME


ROOT = Path(__file__).resolve().parent.parent
SCREENSHOTS_DIR = ROOT / "screenshots"
RECORDINGS_DIR = ROOT / "recordings"
WINDOW_NAME = APP_NAME

CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30.0
RECORDING_FPS = 30.0
DETECTION_MAX_WIDTH = 960

MEME_PATHS = {
    "thinking": ROOT / "memes" / "thinking.jpg",
    "pointing": ROOT / "memes" / "pointing.jpg",
    "shocked": ROOT / "memes" / "shocked.jpg",
    "staring": ROOT / "memes" / "staring.jpg",
    "snide": ROOT / "memes" / "snide.jpg",
    "midfing": ROOT / "memes" / "midfing.jpg",
    "love": ROOT / "memes" / "love.jpg",
    "power": ROOT / "memes" / "jeck_power.jpg",
}

POSE_NAMES = {
    "staring": "live",
    "thinking": "thinking",
    "pointing": "pointing",
    "shocked": "shocked",
    "snide": "snide",
    "midfing": "mid finger",
    "love": "love",
    "power": "power",
}

PHOTO_POSES = frozenset({"snide", "midfing", "love", "power"})

CYRILLIC_KEYS = {
    "й": "q", "ы": "s", "к": "r", "п": "g", "р": "h", "е": "t",
    "з": "p", "с": "c", "т": "n", "а": "f", "ь": "m", "и": "b",
    "ш": "i", "я": "z", "ч": "x", "в": "d", "ц": "w", "м": "v",
    "ф": "a", "н": "y",
}

CONTROL_ROWS = (
    ("S", "save screenshot"),
    ("R", "record video"),
    ("G", "save recent frames"),
    ("H", "show help"),
    ("T", "toggle Telegram output"),
    ("Q", "quit"),
    ("P", "pause"),
    ("C", "switch camera"),
    ("N", "smooth transitions"),
    ("F", "fullscreen"),
)
