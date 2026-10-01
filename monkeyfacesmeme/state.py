from collections import deque
from dataclasses import dataclass, field
import time

from .telegram import TelegramOutput

from .config import MEME_PATHS


@dataclass
class AppState:
    debug_mode: bool = False
    fullscreen: bool = True
    meme_only: bool = False
    paused: bool = False
    side_by_side: bool = True
    pip_mode: bool = False
    zoom_face: bool = False
    recording: bool = False
    watermark: bool = False
    vertical_mode: bool = False
    face_crop: bool = False
    smooth_transition: bool = True
    chaos_mode: bool = False
    show_help: bool = False
    telegram: TelegramOutput = field(default_factory=TelegramOutput)
    fps: float = 0.0
    streak: int = 0
    manual_pose_index: int = -1
    camera_index: int = 0
    switch_camera: bool = False
    video_writer: object | None = None
    recording_size: tuple[int, int] | None = None
    recording_path: str | None = None
    last_record_sequence: object | None = None
    last_camera_sequence: object | None = None
    last_export_sequence: object | None = None
    last_output: object | None = None
    last_detected_pose: str = "staring"
    stable_pose: str = "staring"
    stable_flip: bool = False
    pose_history: list = field(default_factory=list)
    pose_counts: dict = field(default_factory=lambda: dict.fromkeys(MEME_PATHS, 0))
    frame_buffer: deque = field(default_factory=lambda: deque(maxlen=90))
    notice_text: str = ""
    notice_until: float = 0.0
    current_meme: object | None = None
    current_pose: str | None = None
    transition_from: object | None = None
    transition_started: float = 0.0
    frame_timestamp: float = field(default_factory=time.time)

    def notify(self, message, duration=2.0):
        self.notice_text = message
        self.notice_until = time.monotonic() + duration

    def close_recording(self):
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
