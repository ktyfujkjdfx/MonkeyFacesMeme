"""Application lifecycle and frame pipeline."""

from dataclasses import dataclass
import random
import time

import cv2
import mediapipe as mp
import numpy as np

from .camera import CameraCancelled, CameraError
from .telegram import crop_camera_to_square, TELEGRAM_WINDOW_NAME
from .windowing import focus_window

from .config import DETECTION_MAX_WIDTH, MEME_PATHS, PHOTO_POSES
from .gestures import detect_current_pose, stabilize_pose
from .media import (compose_output_frame, face_box, meme_panel_size, overlay_face,
                    prepare_meme_image, resize_to_fill, should_overlay_face)
from .ui import draw_header_ui, draw_help, draw_notice, draw_optional_status, draw_recording


FACE_TARGETS = {
    "thinking": (.25, .08, .75, .58),
    "pointing": (.20, .08, .65, .55),
    "shocked": (.25, .05, .75, .55),
    "staring": (.25, .08, .75, .58),
}


@dataclass
class Dependencies:
    app_name: str
    window_name: str
    screenshots_dir: object
    recordings_dir: object
    state_factory: object
    camera_candidates: object
    initialize_camera: object
    setup_directories: object
    load_images: object
    show_intro: object
    camera_status: object
    show_camera_error: object
    create_detector: object
    window_open: object
    wait_key: object
    handle_key: object
    write_recording: object


class MemeCache:
    def __init__(self, images):
        self.images = images
        self.size = None
        self.frames = {}
        self.fallback = np.full((240, 320, 3), 18, np.uint8)
        cv2.putText(self.fallback, "image unavailable", (52, 124),
                    cv2.FONT_HERSHEY_SIMPLEX, .52, (160, 160, 166), 1, cv2.LINE_AA)

    def get(self, pose, size, flip=False):
        if size != self.size:
            self.size = size
            self.frames.clear()
        key = pose, bool(flip and pose not in PHOTO_POSES)
        if key not in self.frames:
            source = self.images.get(pose, self.fallback)
            frame = prepare_meme_image(source, pose, *size)
            self.frames[key] = cv2.flip(frame, 1) if key[1] else frame
        return self.frames[key].copy()


def detection_image(frame):
    height, width = frame.shape[:2]
    if width > DETECTION_MAX_WIDTH:
        ratio = DETECTION_MAX_WIDTH / width
        frame = cv2.resize(frame, (DETECTION_MAX_WIDTH, round(height * ratio)),
                           interpolation=cv2.INTER_AREA)
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def _zoom_to_face(frame, results):
    if results.pose_landmarks is None:
        return frame
    height, width = frame.shape[:2]
    nose = results.pose_landmarks.landmark[0]
    side = min(width, height) // 2
    x = min(max(0, int(nose.x * width) - side // 2), width - side)
    y = min(max(0, int(nose.y * height) - side // 2), height - side)
    crop = frame[y:y + side, x:x + side]
    return resize_to_fill(crop, width, height) if crop.size else frame


def _face_destination(pose, meme):
    relative = FACE_TARGETS.get(pose)
    if relative is None:
        return None
    height, width = meme.shape[:2]
    return tuple(int(value * dimension) for value, dimension in zip(
        relative, (width, height, width, height)))


def _render_standard(frame, results, state, pose, flip, cache):
    height, width = frame.shape[:2]
    selected = (list(MEME_PATHS)[state.manual_pose_index]
                if state.manual_pose_index >= 0 else pose)
    panel_size = meme_panel_size(state, width, height)
    meme = cache.get(selected, panel_size, flip)
    if should_overlay_face(state, selected, results.face_landmarks):
        destination = _face_destination(selected, meme)
        if destination:
            meme = overlay_face(frame, meme, face_box(results.face_landmarks, width, height),
                                destination)
    if state.current_meme is None or state.current_meme.shape != meme.shape:
        state.current_meme = meme.copy()
        state.current_pose = selected
    elif selected != state.current_pose:
        state.transition_from = state.current_meme.copy()
        state.transition_started = time.monotonic()
        state.current_pose = selected
    if state.transition_from is not None and state.smooth_transition:
        progress = min(1.0, (time.monotonic() - state.transition_started) / .18)
        eased = progress * progress * (3 - 2 * progress)
        meme = cv2.addWeighted(state.transition_from, 1 - eased, meme, eased, 0)
        if progress >= 1:
            state.transition_from = None
    else:
        state.transition_from = None
    state.current_meme = meme.copy()
    if state.chaos_mode and meme.shape[0] > 24 and random.random() < .20:
        top = random.randrange(0, meme.shape[0] - 12)
        bottom = min(meme.shape[0], top + random.randrange(8, 24))
        meme[top:bottom] = np.roll(meme[top:bottom], random.randrange(-20, 21), axis=1)
    camera = _zoom_to_face(frame, results) if state.zoom_face else frame
    output = compose_output_frame(camera, meme, state, width, height)
    draw_header_ui(output, state, output.shape[1], selected)
    draw_optional_status(output, state, selected)
    if state.show_help:
        draw_help(output)
    draw_recording(output, state.recording)
    draw_notice(output, state)
    return output


def _safe_close(label, callback):
    if callback is None:
        return
    try:
        callback()
    except Exception as error:
        print(f"Error closing {label}: {error}", flush=True)


def run(deps, argv):
    capture = None
    detector = None
    state = deps.state_factory()
    telegram_mode = "--telegram" in argv
    window_name = deps.window_name
    try:
        deps.setup_directories()
        images = deps.load_images(strict=False)
        if not deps.show_intro(images):
            return
        candidates = iter(deps.camera_candidates())
        capture = deps.initialize_camera(candidates, deps.camera_status)
        state.camera_index = capture.index

        frame = cv2.flip(capture.latest(), 1)
        cv2.imshow(window_name, frame)
        if deps.wait_key(5) == ord("q"):
            return
        if telegram_mode:
            state.telegram.toggle(frame)
            focus_window(window_name)
        detector = deps.create_detector()
        cache = MemeCache(images)
        processed_sequence = None
        results = None
        last_loop = time.monotonic()

        while deps.window_open():
            state.telegram.check_window()
            if state.switch_camera:
                capture.release()
                order = tuple((state.camera_index + step) % 3 for step in (1, 2, 3))
                candidates = iter(deps.camera_candidates(order))
                capture = deps.initialize_camera(candidates, deps.camera_status)
                state.camera_index = capture.index
                state.switch_camera = False
                state.pose_history.clear()
                processed_sequence = None

            if not capture.healthy():
                print(f"Camera lost: index={capture.index}, backend={capture.backend_name}; reconnecting",
                      flush=True)
                capture.release()
                capture = deps.initialize_camera(candidates, deps.camera_status)
                processed_sequence = None

            frame = cv2.flip(capture.latest(), 1)
            sequence = capture.sequence
            telegram_active = telegram_mode or state.telegram.enabled

            if state.paused and not telegram_active:
                output = state.last_output if state.last_output is not None else frame
            else:
                if sequence != processed_sequence or results is None:
                    results = detector.process(detection_image(frame))
                    processed_sequence = sequence
                raw_pose, raw_flip = detect_current_pose(results, frame.shape[1], frame.shape[0])
                if sequence != state.last_camera_sequence:
                    pose, flip = stabilize_pose(state, raw_pose, raw_flip)
                    state.last_camera_sequence = sequence
                else:
                    pose, flip = state.stable_pose, state.stable_flip

                state.pose_counts[pose] += 1
                state.telegram.present(frame, raw_pose, images, sequence,
                                       smooth=state.smooth_transition)
                output = _render_standard(frame, results, state, pose, flip, cache)
                if state.paused and state.last_output is not None:
                    output = state.last_output

            export_frame = (state.telegram.last_frame
                            if telegram_mode and state.telegram.last_frame is not None else output)
            deps.write_recording(state, export_frame, sequence)
            if sequence != state.last_export_sequence:
                state.frame_buffer.append(export_frame.copy())
                state.last_export_sequence = sequence
            state.last_output = output
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN,
                                  cv2.WINDOW_FULLSCREEN if state.fullscreen else cv2.WINDOW_NORMAL)
            cv2.imshow(window_name, output)
            if not deps.handle_key(deps.wait_key(5), state, output, capture,
                                   list(MEME_PATHS), camera_frame=frame):
                break
            now = time.monotonic()
            instantaneous = 1 / max(now - last_loop, 1e-6)
            state.fps = instantaneous if not state.fps else state.fps * .9 + instantaneous * .1
            last_loop = now
    except CameraCancelled:
        pass
    except CameraError as error:
        state.telegram.close()
        try:
            deps.show_camera_error(error)
        except KeyboardInterrupt:
            print("Interrupted by Ctrl+C; closing application.", flush=True)
    except KeyboardInterrupt:
        print("Interrupted by Ctrl+C; closing application.", flush=True)
    finally:
        _safe_close("Telegram output", state.telegram.close)
        _safe_close("camera", capture.release if capture is not None else None)
        _safe_close("VideoWriter", state.video_writer.release if state.video_writer is not None else None)
        _safe_close("pose detector", detector.close if detector is not None else None)
        _safe_close("windows", cv2.destroyAllWindows)
