"""Square OBS output with cached media and timed transitions."""
from dataclasses import dataclass
import time

import cv2
import numpy as np

from .windowing import lock_capture_window

TELEGRAM_WINDOW_NAME = "MonkeyFacesMeme Output"
OUTPUT_SIZE = 720


def _validate(image):
    if (image is None or image.size == 0 or image.ndim != 3
            or image.shape[2] != 3 or image.dtype != np.uint8):
        raise ValueError("Expected a nonempty uint8 BGR image")


def _resize(image, width, height):
    if (image.shape[1], image.shape[0]) == (width, height):
        # HighGUI needs a contiguous buffer after the crop
        return np.ascontiguousarray(image)
    interpolation = cv2.INTER_AREA if width < image.shape[1] else cv2.INTER_CUBIC
    return cv2.resize(image, (width, height), interpolation=interpolation)


def crop_camera_to_square(frame, output_size=OUTPUT_SIZE):
    _validate(frame)
    if output_size < 1:
        raise ValueError("Output size must be positive")
    height, width = frame.shape[:2]
    side = min(height, width)
    x, y = (width - side) // 2, (height - side) // 2
    return _resize(frame[y:y + side, x:x + side], output_size, output_size)


def compose_square_media(image, output_size=OUTPUT_SIZE):
    """Create a full-bleed square with a subtle circular cinematic grade."""
    _validate(image)
    square = crop_camera_to_square(image, output_size)

    # apply the light grade once and reuse the cached frame
    blurred = cv2.GaussianBlur(square, (0, 0), 1.1)
    graded = cv2.addWeighted(square, 1.10, blurred, -0.10, 2)

    axis = np.linspace(-1.0, 1.0, output_size, dtype=np.float32)
    radius = np.sqrt(axis[:, None] ** 2 + axis[None, :] ** 2)
    edge = np.clip((radius - 0.58) / 0.42, 0.0, 1.0)
    smooth_edge = edge * edge * (3.0 - 2.0 * edge)
    vignette = 1.0 - 0.16 * smooth_edge
    return np.clip(graded.astype(np.float32) * vignette[..., None], 0, 255).astype(np.uint8)


def prepare_telegram_media(meme_images):
    cache = {}
    for pose, image in meme_images.items():
        if pose == "staring":
            continue
        try:
            prepared = compose_square_media(image)
            prepared.setflags(write=False)
            cache[pose] = prepared
        except (ValueError, cv2.error) as error:
            print(f"Telegram image unavailable: {pose}: {error}; using camera", flush=True)
    return cache


@dataclass(frozen=True)
class TelegramRenderState:
    source_frame: object = None
    alpha: float = 1.0


def render_telegram_frame(camera_frame, active_pose, meme_images, telegram_state=None):
    """Pure render: meme_images is the precomputed square cache, never disk paths."""
    target = crop_camera_to_square(camera_frame) if active_pose == "staring" else meme_images.get(active_pose)
    if target is None:
        return crop_camera_to_square(camera_frame)
    if telegram_state is not None and telegram_state.source_frame is not None and telegram_state.alpha < 1:
        alpha = max(0.0, telegram_state.alpha)
        return cv2.addWeighted(telegram_state.source_frame, 1 - alpha, target, alpha, 0)
    return target


def smoothstep(value):
    """Ease a normalized transition without abrupt speed changes at its ends."""
    value = min(1.0, max(0.0, value))
    return value * value * (3.0 - 2.0 * value)


class TelegramOutputState:
    # show the gesture first, then bring in the reaction image
    CONFIRM_SECONDS = 0.30
    CONFIRM_FRAMES = 2
    RELEASE_SECONDS = 0.22
    RELEASE_FRAMES = 3
    MIN_HOLD_SECONDS = 0.95
    APPEAR_TRANSITION_SECONDS = 0.12
    DISAPPEAR_TRANSITION_SECONDS = 0.32

    def __init__(self):
        self.active_pose = "staring"
        self.phase = "CAMERA"
        self.candidate = None
        self.candidate_since = 0.0
        self.candidate_count = 0
        self.activated_at = float("-inf")
        self.transition_at = float("-inf")
        self.transition_from = None
        self.last_observation = None

    def update(self, pose, now=None):
        """Call only for distinct camera frames; time is injectable in tests."""
        now = time.monotonic() if now is None else now
        if self.last_observation is not None and now - self.last_observation > 0.5:
            self.candidate = None
        self.last_observation = now
        if pose == self.active_pose:
            self.candidate = None
            self.candidate_count = 0
            self.phase = "CAMERA" if pose == "staring" else "MEME_ACTIVE"
            return False
        if pose != self.candidate:
            self.candidate = pose
            self.candidate_since = now
            self.candidate_count = 0
        self.candidate_count += 1
        self.phase = "CANDIDATE_RELEASE" if pose == "staring" else "CANDIDATE_GESTURE"
        releasing = pose == "staring"
        confirm = self.RELEASE_SECONDS if releasing else self.CONFIRM_SECONDS
        required_frames = self.RELEASE_FRAMES if releasing else self.CONFIRM_FRAMES
        held = self.active_pose == "staring" or now - self.activated_at >= self.MIN_HOLD_SECONDS
        if self.candidate_count >= required_frames and now - self.candidate_since >= confirm and held:
            self.active_pose = pose
            self.activated_at = self.transition_at = now
            self.candidate = None
            self.phase = "CAMERA" if pose == "staring" else "MEME_ACTIVE"
            return True
        return False

    def render_state(self, now, smooth=True):
        duration = (self.DISAPPEAR_TRANSITION_SECONDS if self.active_pose == "staring"
                    else self.APPEAR_TRANSITION_SECONDS)
        progress = (now - self.transition_at) / duration
        alpha = smoothstep(progress) if smooth else 1.0
        return TelegramRenderState(self.transition_from, alpha)


class TelegramOutput:
    """Owns just a HighGUI window and caches; never owns a camera."""
    def __init__(self):
        self.enabled = False
        self.cache = None
        self.controller = TelegramOutputState()
        self.last_sequence = None
        self.camera_square = None
        self.last_frame = None
        self.warned_missing = set()
        self.window_locked = False

    def toggle(self, initial_frame=None):
        if self.enabled:
            self.close()
            return
        try:
            cv2.namedWindow(TELEGRAM_WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
            first_frame = (crop_camera_to_square(initial_frame) if initial_frame is not None
                           else np.zeros((OUTPUT_SIZE, OUTPUT_SIZE, 3), np.uint8))
            cv2.imshow(TELEGRAM_WINDOW_NAME, first_frame)
            self.window_locked = lock_capture_window(TELEGRAM_WINDOW_NAME, OUTPUT_SIZE)
            self.controller = TelegramOutputState()
            self.last_sequence = None
            self.camera_square = first_frame
            self.last_frame = first_frame
            self.enabled = True
            print("MonkeyFacesMeme output ready: 720x720", flush=True)
            print(f"Capture window in OBS: {TELEGRAM_WINDOW_NAME}", flush=True)
        except cv2.error as error:
            print(f"Could not open output window: {error}", flush=True)
            self.close()

    def check_window(self):
        if self.enabled:
            try:
                visible = cv2.getWindowProperty(TELEGRAM_WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1
            except cv2.error:
                visible = False
            if not visible:
                self.close()
        return self.enabled

    def present(self, camera_frame, detected_pose, meme_images, sequence, smooth=True, now=None):
        if not self.check_window():
            return
        now = time.monotonic() if now is None else now
        if self.cache is None:
            self.cache = prepare_telegram_media(meme_images)
        pose = detected_pose
        if pose != "staring" and pose not in self.cache:
            if pose not in self.warned_missing:
                print(f"Telegram image unavailable: {pose}; using camera", flush=True)
                self.warned_missing.add(pose)
            pose = "staring"
        if sequence != self.last_sequence:
            self.camera_square = crop_camera_to_square(camera_frame)
            if self.controller.update(pose, now):
                self.controller.transition_from = self.last_frame
            self.last_sequence = sequence
        if self.camera_square is None:
            self.camera_square = crop_camera_to_square(camera_frame)
        render_state = self.controller.render_state(now, smooth)
        output = render_telegram_frame(self.camera_square, self.controller.active_pose,
                                       self.cache, render_state)
        self.last_frame = output
        try:
            cv2.imshow(TELEGRAM_WINDOW_NAME, output)
            if not self.window_locked:
                self.window_locked = lock_capture_window(TELEGRAM_WINDOW_NAME, OUTPUT_SIZE)
        except cv2.error as error:
            print(f"Output window closed: {error}", flush=True)
            self.close()

    def close(self):
        was_enabled = self.enabled
        self.enabled = False
        self.camera_square = None
        self.last_frame = None
        self.window_locked = False
        self.controller.transition_from = None
        if was_enabled:
            try:
                cv2.destroyWindow(TELEGRAM_WINDOW_NAME)
            except cv2.error:
                pass
            print("Output window disabled", flush=True)
