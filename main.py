"""MonkeyFacesMeme launcher.

The implementation lives in the monkeyfacesmeme package. This module keeps a
small, stable entry point for direct launches and automated checks.
"""

from pathlib import Path
import sys
import time

import cv2
import mediapipe as mp

from monkeyfacesmeme.camera import camera_candidates, initialize_camera
from monkeyfacesmeme.telegram import TELEGRAM_WINDOW_NAME

from monkeyfacesmeme import APP_NAME
from monkeyfacesmeme.application import Dependencies, run
from monkeyfacesmeme.config import (MEME_PATHS, POSE_NAMES as POSE_DISPLAY_NAMES,
                                    RECORDINGS_DIR, SCREENSHOTS_DIR)
from monkeyfacesmeme.controls import (handle_keypress as _handle_keypress,
                                      normalize_key, write_recording_frame as _write_recording)
from monkeyfacesmeme.gestures import (detect_current_pose, distance as calculate_distance,
                                      is_closed_fist, is_finger_heart, is_love_gesture,
                                      is_midfing_gesture, is_power_gesture, is_snide_gesture,
                                      is_two_hand_heart, mouth_openness as calculate_mouth_openness,
                                      stabilize_pose)
from monkeyfacesmeme.media import (compose_output_frame, load_meme_images,
                                   prepare_meme_image, resize_to_fill, should_overlay_face)
from monkeyfacesmeme.state import AppState
from monkeyfacesmeme.ui import draw_header_ui, draw_loading_screen, draw_welcome_screen


WINDOW_NAME = APP_NAME


def setup_directories():
    Path(SCREENSHOTS_DIR).mkdir(parents=True, exist_ok=True)
    Path(RECORDINGS_DIR).mkdir(parents=True, exist_ok=True)


def create_pose_detector():
    return mp.solutions.holistic.Holistic(
        min_detection_confidence=.6,
        min_tracking_confidence=.6,
        smooth_landmarks=True,
        model_complexity=1,
        refine_face_landmarks=True,
    )


def window_is_open():
    try:
        return cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) >= 1
    except cv2.error:
        return False


def wait_key(delay=5):
    key = normalize_key(cv2.waitKeyEx(delay))
    return key if window_is_open() else ord("q")


def show_splash_screen(_images=None):
    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL | cv2.WINDOW_FREERATIO)
    cv2.resizeWindow(WINDOW_NAME, 960, 540)
    cv2.moveWindow(WINDOW_NAME, 16, 32)
    try:
        cv2.setWindowProperty(WINDOW_NAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    except cv2.error:
        pass
    try:
        import ctypes
        width, height = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
    except (AttributeError, OSError):
        width, height = 960, 540
    print("Press Enter to start the camera. Press Q or Escape to quit.", flush=True)
    while True:
        cv2.imshow(WINDOW_NAME, draw_welcome_screen(width, height))
        key = wait_key(25)
        if key in (10, 13):
            cv2.imshow(WINDOW_NAME, draw_loading_screen(width=width, height=height))
            wait_key(1)
            return True
        if key in (ord("q"), 27):
            return False


def camera_status(message):
    if not window_is_open():
        return False
    status = "CAMERA ERROR" if message == "CAMERA ERROR" else "CONNECTING"
    width, height = ((720, 720) if WINDOW_NAME == TELEGRAM_WINDOW_NAME else (960, 540))
    cv2.imshow(WINDOW_NAME, draw_loading_screen(status, width, height))
    return wait_key(20) != ord("q")


def show_camera_error(error):
    print(f"CAMERA ERROR: {error}", flush=True)
    print("Close other apps using the webcam. Check the privacy shutter, Windows camera "
          "permissions, Device Manager, and the Windows Camera app.", flush=True)
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline and camera_status("CAMERA ERROR"):
        pass


def handle_keypress(key, state, output, capture, pose_list, camera_frame=None):
    return _handle_keypress(key, state, output, capture, pose_list, camera_frame,
                            screenshots_dir=SCREENSHOTS_DIR, recordings_dir=RECORDINGS_DIR)


def write_recording_frame(state, output, sequence=None):
    return _write_recording(state, output, sequence, recordings_dir=RECORDINGS_DIR)


def main():
    dependencies = Dependencies(
            app_name=APP_NAME,
            window_name=WINDOW_NAME,
            screenshots_dir=SCREENSHOTS_DIR,
            recordings_dir=RECORDINGS_DIR,
            state_factory=AppState,
            camera_candidates=camera_candidates,
            initialize_camera=initialize_camera,
            setup_directories=setup_directories,
            load_images=load_meme_images,
            show_intro=show_splash_screen,
            camera_status=camera_status,
            show_camera_error=show_camera_error,
            create_detector=create_pose_detector,
            window_open=window_is_open,
            wait_key=wait_key,
            handle_key=handle_keypress,
            write_recording=write_recording_frame,
    )
    run(dependencies, sys.argv)


if __name__ == "__main__":
    main()
