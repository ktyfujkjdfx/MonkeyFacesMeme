from datetime import datetime
from pathlib import Path
import random

import cv2

from .config import CYRILLIC_KEYS, RECORDING_FPS


def _keyboard_map():
    mapping = {}
    for russian, english in CYRILLIC_KEYS.items():
        mapping[ord(russian)] = ord(english)
        mapping[ord(russian.upper())] = ord(english)
        for symbol in (russian, russian.upper()):
            mapping[symbol.encode("cp1251")[0]] = ord(english)
    return mapping


KEY_MAP = _keyboard_map()
MESSAGES = (
    "hold that pose", "camera caught the vibe", "clean timing",
    "main character energy", "one more take",
)


def normalize_key(key):
    if key is None or key < 0:
        return -1
    if ord("A") <= key <= ord("Z"):
        key += 32
    return KEY_MAP.get(key, key)


def timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def start_recording(state, frame, recordings_dir):
    height, width = frame.shape[:2]
    Path(recordings_dir).mkdir(parents=True, exist_ok=True)
    path = Path(recordings_dir) / f"camera_{timestamp()}_{width}x{height}.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"),
                             RECORDING_FPS, (width, height))
    if not writer.isOpened():
        writer.release()
        state.recording = False
        state.notify("recording could not start", 3)
        print(f"Could not start recording: {path}", flush=True)
        return
    state.video_writer = writer
    state.recording_size = (width, height)
    state.recording_path = str(path)
    state.last_record_sequence = None
    state.notify("recording started")
    print(f"Recording started: {path}", flush=True)


def write_recording_frame(state, frame, sequence=None, recordings_dir=None):
    if not state.recording or (sequence is not None and sequence == state.last_record_sequence):
        return
    size = (frame.shape[1], frame.shape[0])
    if state.video_writer is None:
        start_recording(state, frame, recordings_dir)
    elif state.recording_size != size:
        state.close_recording()
        print("Recording size changed; starting a new video segment", flush=True)
        start_recording(state, frame, recordings_dir)
    if state.video_writer is not None:
        state.video_writer.write(frame)
        state.last_record_sequence = sequence


def _save_screenshot(state, frame, directory):
    Path(directory).mkdir(parents=True, exist_ok=True)
    path = Path(directory) / f"shot_{timestamp()}.png"
    if cv2.imwrite(str(path), frame, [cv2.IMWRITE_PNG_COMPRESSION, 2]):
        state.notify("screenshot saved")
        print(f"Screenshot saved: {path}", flush=True)
    else:
        state.notify("screenshot could not be saved", 3)
        print(f"Could not save screenshot: {path}", flush=True)


def _save_sequence(state, directory):
    if not state.frame_buffer:
        state.notify("no recent frames yet")
        return
    folder = Path(directory) / f"sequence_{timestamp()}"
    folder.mkdir(parents=True, exist_ok=False)
    for number, frame in enumerate(state.frame_buffer):
        cv2.imwrite(str(folder / f"frame_{number:03d}.png"), frame,
                    [cv2.IMWRITE_PNG_COMPRESSION, 2])
    state.notify("recent frames saved")
    print(f"Frame sequence saved: {folder}", flush=True)


def handle_keypress(key, state, frame, capture, poses, camera_frame=None,
                    screenshots_dir="screenshots", recordings_dir="recordings"):
    key = normalize_key(key)
    if key == ord("q"):
        return False
    if key == ord("h"):
        state.show_help = not state.show_help
        print("Help shown" if state.show_help else "Help hidden", flush=True)
    elif key == ord("s"):
        _save_screenshot(state, frame, screenshots_dir)
    elif key == ord("r"):
        state.recording = not state.recording
        if state.recording:
            start_recording(state, frame, recordings_dir)
        else:
            state.close_recording()
            state.notify("recording saved")
            print(f"Recording saved: {state.recording_path}", flush=True)
    elif key == ord("g"):
        _save_sequence(state, screenshots_dir)
    elif key == ord("t"):
        state.telegram.toggle(camera_frame if camera_frame is not None else frame)
        state.notify("Telegram output on" if state.telegram.enabled else "Telegram output off")
    elif key == ord("p"):
        state.paused = not state.paused
    elif key == ord("c"):
        state.switch_camera = True
    elif key == ord("f"):
        state.fullscreen = not state.fullscreen
    elif key == ord("n"):
        state.smooth_transition = not state.smooth_transition
    elif key == ord("d"):
        state.debug_mode = not state.debug_mode
    elif key == ord("m"):
        state.meme_only, state.pip_mode, state.vertical_mode = True, False, False
    elif key == ord("b"):
        state.side_by_side, state.meme_only, state.pip_mode, state.vertical_mode = True, False, False, False
    elif key == ord("i"):
        state.pip_mode = not state.pip_mode
        state.meme_only, state.vertical_mode = False, False
    elif key == ord("v"):
        state.vertical_mode = not state.vertical_mode
    elif key == ord("w"):
        state.watermark = not state.watermark
    elif key == ord("a"):
        state.face_crop = not state.face_crop
    elif key == ord("z"):
        state.zoom_face = not state.zoom_face
    elif key == ord("x"):
        state.chaos_mode = not state.chaos_mode
    elif key == ord("y"):
        state.notify(random.choice(MESSAGES), 2.5)
    elif key in (81, 2):
        state.manual_pose_index = ((state.manual_pose_index - 1) % len(poses)
                                   if state.manual_pose_index >= 0 else len(poses) - 1)
    elif key in (83, 3):
        state.manual_pose_index = (state.manual_pose_index + 1) % len(poses)
    elif key in (82, 0):
        state.manual_pose_index = -1
    return True
