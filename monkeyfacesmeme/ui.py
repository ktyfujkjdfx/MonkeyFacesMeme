import math
import time

import cv2
import numpy as np

from . import APP_NAME
from .config import CONTROL_ROWS, POSE_NAMES


BACKGROUND = (12, 14, 18)
TEXT = (232, 229, 238)
MUTED = (132, 130, 144)
ACCENT = (199, 120, 255)


def _centered_text(canvas, text, y, scale, color=TEXT, thickness=1):
    size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)[0]
    cv2.putText(canvas, text, ((canvas.shape[1] - size[0]) // 2, y),
                cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def draw_loading_screen(status="CONNECTING", width=720, height=720, now=None):
    now = time.monotonic() if now is None else now
    canvas = np.full((height, width, 3), BACKGROUND, np.uint8)
    center = (width // 2, height // 2)
    radius = max(34, min(width, height) // 12)
    phase = int(now * 110) % 360
    cv2.circle(canvas, center, radius, (45, 43, 52), 2, cv2.LINE_AA)
    color = (80, 90, 245) if status == "CAMERA ERROR" else ACCENT
    cv2.ellipse(canvas, center, (radius, radius), 0, phase, phase + 88, color, 4, cv2.LINE_AA)
    title = "CAMERA ERROR" if status == "CAMERA ERROR" else APP_NAME.upper()
    _centered_text(canvas, title, center[1] + radius + 42, 0.45)
    _centered_text(canvas, "check the console" if status == "CAMERA ERROR" else "starting camera",
                   center[1] + radius + 68, 0.34, MUTED)
    return canvas


def draw_welcome_screen(width=960, height=540, now=None):
    now = time.monotonic() if now is None else now
    canvas = np.full((height, width, 3), BACKGROUND, np.uint8)
    glow = canvas.copy()
    cv2.circle(glow, (width // 2, 0), min(width, height) // 2, (52, 28, 66), -1, cv2.LINE_AA)
    cv2.addWeighted(glow, 0.24, canvas, 0.76, 0, canvas)
    _centered_text(canvas, APP_NAME, 58, 0.84 if width >= 900 else 0.65)
    _centered_text(canvas, "camera controls", 85, 0.36, MUTED)

    card_width = min(760, width - 48)
    rows = math.ceil(len(CONTROL_ROWS) / 2)
    card_height = rows * 42 + 36
    left, top = (width - card_width) // 2, 108
    cv2.rectangle(canvas, (left, top), (left + card_width, top + card_height), (19, 20, 27), -1)
    cv2.rectangle(canvas, (left, top), (left + card_width, top + card_height), (61, 48, 72), 1)
    column_width = card_width // 2
    for index, (key, label) in enumerate(CONTROL_ROWS):
        column, row = divmod(index, rows)
        x = left + 22 + column * column_width
        y = top + 32 + row * 42
        cv2.circle(canvas, (x + 10, y - 6), 13, (55, 36, 64), -1, cv2.LINE_AA)
        cv2.putText(canvas, key, (x + 5, y - 1), cv2.FONT_HERSHEY_SIMPLEX, .42,
                    ACCENT, 1, cv2.LINE_AA)
        cv2.putText(canvas, label, (x + 35, y), cv2.FONT_HERSHEY_SIMPLEX, .39,
                    (205, 202, 214), 1, cv2.LINE_AA)
    pulse = 185 + int((math.sin(now * 3) + 1) * 30)
    prompt_y = min(height - 28, top + card_height + 54)
    _centered_text(canvas, "PRESS ENTER TO START", prompt_y, .48, (pulse, 155, 255))
    return canvas


def draw_header_ui(frame, _state, width, pose):
    label = POSE_NAMES.get(pose, pose)
    scale = 0.43
    text_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)[0]
    right = width - 12
    left = right - text_size[0] - 28
    cv2.rectangle(frame, (left, 8), (right, 34), (18, 18, 22), -1, cv2.LINE_AA)
    cv2.circle(frame, (left + 10, 21), 4, ACCENT, -1, cv2.LINE_AA)
    cv2.putText(frame, label, (left + 19, 26), cv2.FONT_HERSHEY_SIMPLEX,
                scale, (220, 218, 225), 1, cv2.LINE_AA)


def draw_notice(frame, state):
    if not state.notice_text or time.monotonic() >= state.notice_until:
        return
    text = state.notice_text
    size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, .42, 1)[0]
    x = (frame.shape[1] - size[0]) // 2
    y = frame.shape[0] - 28
    cv2.rectangle(frame, (x - 14, y - 20), (x + size[0] + 14, y + 8), (18, 18, 22), -1)
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, .42, TEXT, 1, cv2.LINE_AA)


def draw_help(frame):
    overlay = frame.copy()
    cv2.rectangle(overlay, (18, 18), (370, 312), (10, 11, 15), -1)
    cv2.addWeighted(overlay, .91, frame, .09, 0, frame)
    cv2.putText(frame, "CONTROLS", (38, 52), cv2.FONT_HERSHEY_SIMPLEX, .55, ACCENT, 1, cv2.LINE_AA)
    for index, (key, label) in enumerate(CONTROL_ROWS):
        y = 82 + index * 22
        cv2.putText(frame, key, (38, y), cv2.FONT_HERSHEY_SIMPLEX, .38, ACCENT, 1, cv2.LINE_AA)
        cv2.putText(frame, label, (72, y), cv2.FONT_HERSHEY_SIMPLEX, .38, TEXT, 1, cv2.LINE_AA)


def draw_recording(frame, recording):
    if recording:
        cv2.circle(frame, (20, frame.shape[0] - 20), 6, (40, 50, 245), -1, cv2.LINE_AA)
        cv2.putText(frame, "REC", (33, frame.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX,
                    .4, (230, 230, 235), 1, cv2.LINE_AA)


def draw_optional_status(frame, state, pose):
    if state.debug_mode:
        cv2.putText(frame, f"{state.fps:4.1f} FPS  {pose}", (14, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, .42, (110, 245, 180), 1, cv2.LINE_AA)
    if state.watermark:
        text = APP_NAME
        size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, .36, 1)[0]
        cv2.putText(frame, text, (frame.shape[1] - size[0] - 12, frame.shape[0] - 12),
                    cv2.FONT_HERSHEY_SIMPLEX, .36, (205, 202, 214), 1, cv2.LINE_AA)
