"""Camera capture isolated from the UI and blocking Windows driver calls."""

import multiprocessing as multiprocessing
import signal
import time

import cv2
import numpy as np


WIDTH, HEIGHT = 1280, 720
TARGET_FPS = 30
OPEN_TIMEOUT = 10.0
FRAME_TIMEOUT = 5.0
BLANK_FRAME_TIMEOUT = 1.5


class CameraError(RuntimeError):
    pass


class CameraCancelled(Exception):
    pass


def camera_candidates(indices=(0, 1, 2)):
    # try both backends for one index before moving to the next one
    return [(index, backend, name)
            for index in indices
            for backend, name in ((cv2.CAP_DSHOW, "DSHOW"), (cv2.CAP_MSMF, "MSMF"))]


def _capture_worker(index, backend, pixels, metadata, lock, stop, factory=None):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    capture = None
    try:
        capture = (factory or cv2.VideoCapture)()
        if not capture.open(index, backend) or not capture.isOpened():
            print(f"Camera index {index}: backend could not open device", flush=True)
            return
        # keep the native format because some cameras return black frames after MJPG
        properties = ((cv2.CAP_PROP_FRAME_WIDTH, WIDTH),
                      (cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT),
                      (cv2.CAP_PROP_FPS, TARGET_FPS),
                      (cv2.CAP_PROP_BUFFERSIZE, 1))
        for prop, value in properties:
            try:
                if not capture.set(prop, value):
                    print(f"Camera index {index}: property {prop}={value} unsupported", flush=True)
            except cv2.error as error:
                print(f"Camera property unavailable: {error}", flush=True)
        buffer = np.frombuffer(pixels, dtype=np.uint8)
        last_success = time.monotonic()
        reported_mode = False
        warned_blank = False
        while not stop.is_set():
            success, frame = capture.read()
            if (not success or frame is None or frame.size == 0
                    or frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8):
                if time.monotonic() - last_success >= FRAME_TIMEOUT:
                    print(f"Camera index {index}: no valid frames for {FRAME_TIMEOUT}s", flush=True)
                    return
                stop.wait(0.05)
                continue
            # a blank driver buffer is not a valid camera frame
            blank_sample = frame[::16, ::16]
            if int(blank_sample.max()) <= 2 and float(blank_sample.mean()) < 1.0:
                if not warned_blank:
                    print(f"Camera index {index}: blank frames received; waiting for image data",
                          flush=True)
                    warned_blank = True
                if time.monotonic() - last_success >= BLANK_FRAME_TIMEOUT:
                    print(f"Camera index {index}: only blank frames for "
                          f"{BLANK_FRAME_TIMEOUT}s", flush=True)
                    return
                stop.wait(0.05)
                continue
            # use the native size when the camera cannot provide 720p
            if frame.size > buffer.size:
                scale = min(WIDTH / frame.shape[1], HEIGHT / frame.shape[0])
                frame = cv2.resize(frame, (max(1, int(frame.shape[1] * scale)),
                                           max(1, int(frame.shape[0] * scale))))
            last_success = time.monotonic()
            with lock:
                buffer[:frame.size] = frame.reshape(-1)
                metadata[:] = (last_success, frame.shape[0], frame.shape[1], metadata[3] + 1)
            if not reported_mode:
                try:
                    fps = float(capture.get(cv2.CAP_PROP_FPS))
                except (AttributeError, TypeError, ValueError, cv2.error):
                    fps = 0.0
                print(f"Camera stream: {frame.shape[1]}x{frame.shape[0]}"
                      f" at {fps:.1f} FPS requested={TARGET_FPS}; "
                      f"brightness={float(frame.mean()):.1f}, range={int(frame.min())}-{int(frame.max())}",
                      flush=True)
                reported_mode = True
            stop.wait(0.001)
    except Exception as error:
        print(f"Camera index {index}: {type(error).__name__}: {error}", flush=True)
    finally:
        if capture is not None:
            capture.release()


class CameraCapture:
    def __init__(self, candidate, factory=None):
        self.index, self.backend, self.backend_name = candidate
        context = multiprocessing.get_context("spawn")
        self.pixels = context.RawArray("B", WIDTH * HEIGHT * 3)
        self.metadata = context.RawArray("d", 4)
        self.lock = context.Lock()
        self.stop = context.Event()
        self.process = context.Process(
            target=_capture_worker,
            args=(self.index, self.backend, self.pixels, self.metadata, self.lock, self.stop, factory),
            daemon=True,
        )
        self.last_frame = None
        self.timestamp = 0.0
        self.sequence = 0
        self.closed = False

    def latest(self):
        # never wait on a lock owned by a dead worker
        if self.lock.acquire(timeout=0.01):
            try:
                timestamp, height, width, sequence = self.metadata[:]
                if sequence > self.sequence:
                    size = int(height * width * 3)
                    self.last_frame = np.frombuffer(self.pixels, dtype=np.uint8)[:size].reshape(
                        int(height), int(width), 3).copy()
                    self.timestamp, self.sequence = timestamp, sequence
            finally:
                self.lock.release()
        return self.last_frame

    def healthy(self):
        return (not self.closed and self.process.is_alive()
                and time.monotonic() - self.timestamp < FRAME_TIMEOUT)

    def release(self):
        if self.closed:
            return
        self.closed = True
        self.stop.set()
        if self.process.pid is not None:
            self.process.join(0.3)
            if self.process.is_alive():
                print("Camera worker blocked in driver; terminating capture process", flush=True)
                # stop a blocked read together with its isolated process
                self.process.terminate()
                self.process.join(1.0)
            if self.process.is_alive():
                raise CameraError("Camera process could not be stopped; no further device opens")
            self.process.close()


def initialize_camera(candidates, pump, timeout=OPEN_TIMEOUT, factory=None):
    """Consume a finite candidate iterator; pump keeps the GUI responsive."""
    for candidate in candidates:
        index, _, name = candidate
        print(f"Trying camera index {index} with {name}...", flush=True)
        capture = CameraCapture(candidate, factory=factory)
        accepted = False
        try:
            capture.process.start()
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if not pump(f"OPENING CAMERA {index} / {name}"):
                    raise CameraCancelled()
                frame = capture.latest()
                if frame is not None and capture.healthy():
                    print(f"Camera opened successfully: index={index}, backend={name}", flush=True)
                    accepted = True
                    return capture
                if not capture.process.is_alive():
                    break
                time.sleep(0.01)
            print(f"Camera failed: index={index}, backend={name}; no valid frame within {timeout:g}s or worker exited", flush=True)
        except (OSError, RuntimeError) as error:
            print(f"Camera failed: index={index}, backend={name}; {error}", flush=True)
        finally:
            if not accepted:
                capture.release()
    raise CameraError("All camera backends and indices failed")
