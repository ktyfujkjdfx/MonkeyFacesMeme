"""Regression tests: no physical camera or GUI is used."""
import multiprocessing
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np

from monkeyfacesmeme import camera


class FakeCapture:
    def open(self, index, backend):
        self.index = index
        return True

    def isOpened(self):
        return True

    def set(self, prop, value):
        return False

    def read(self):
        if self.index == 0:
            time.sleep(60)
        time.sleep(0.02)
        return True, np.full((48, 64, 3), 123, dtype=np.uint8)

    def release(self):
        pass


class CameraTests(unittest.TestCase):
    def test_candidate_order(self):
        self.assertEqual([(i, name) for i, _, name in camera.camera_candidates()],
                         [(0, 'DSHOW'), (0, 'MSMF'), (1, 'DSHOW'),
                          (1, 'MSMF'), (2, 'DSHOW'), (2, 'MSMF')])

    def test_blocked_read_falls_back_and_shuts_down(self):
        children_before = {p.pid for p in multiprocessing.active_children()}
        pumps = []
        capture = None
        start = time.monotonic()
        try:
            candidates = camera.camera_candidates()
            capture = camera.initialize_camera(
                iter((candidates[0], candidates[2])), lambda message: pumps.append(message) or True,
                timeout=4, factory=FakeCapture)
            self.assertEqual(capture.index, 1)
            self.assertTrue(capture.healthy())
            np.testing.assert_array_equal(capture.latest(), np.full((48, 64, 3), 123))
            self.assertGreater(len(pumps), 10)
            self.assertLess(time.monotonic() - start, 10)
            capture.timestamp = time.monotonic() - camera.FRAME_TIMEOUT - 1
            self.assertFalse(capture.healthy())
        finally:
            if capture is not None:
                capture.release()
                capture.release()
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, children_before)

    def test_cancel_stops_worker(self):
        before = {p.pid for p in multiprocessing.active_children()}
        with self.assertRaises(camera.CameraCancelled):
            camera.initialize_camera(iter(camera.camera_candidates()), lambda _: False,
                                     factory=FakeCapture)
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)

    def test_empty_candidates_fail(self):
        with self.assertRaises(camera.CameraError):
            camera.initialize_camera(iter(()), lambda _: True)

    def test_worker_rejects_empty_frames_and_releases(self):
        context = multiprocessing.get_context('spawn')
        capture = Mock()
        capture.read.return_value = (True, np.empty((0, 0, 3), dtype=np.uint8))
        metadata = context.RawArray('d', 4)
        with patch.object(camera, 'FRAME_TIMEOUT', 0), patch.object(camera.signal, 'signal'):
            camera._capture_worker(0, cv2.CAP_DSHOW,
                                   context.RawArray('B', camera.WIDTH * camera.HEIGHT * 3),
                                   metadata, context.Lock(), context.Event(), lambda: capture)
        self.assertEqual(metadata[3], 0)
        capture.release.assert_called_once()

    def test_worker_rejects_driver_blank_frames(self):
        context = multiprocessing.get_context('spawn')
        capture = Mock()
        capture.read.return_value = (True, np.zeros((48, 64, 3), dtype=np.uint8))
        metadata = context.RawArray('d', 4)
        with patch.object(camera, 'FRAME_TIMEOUT', 0), patch.object(camera.signal, 'signal'):
            camera._capture_worker(0, cv2.CAP_DSHOW,
                                   context.RawArray('B', camera.WIDTH * camera.HEIGHT * 3),
                                   metadata, context.Lock(), context.Event(), lambda: capture)
        self.assertEqual(metadata[3], 0)
        capture.release.assert_called_once()

    def test_worker_releases_after_read_exception(self):
        context = multiprocessing.get_context('spawn')
        capture = Mock()
        capture.read.side_effect = RuntimeError('simulated driver error')
        with patch.object(camera.signal, 'signal'):
            camera._capture_worker(0, cv2.CAP_DSHOW,
                                   context.RawArray('B', camera.WIDTH * camera.HEIGHT * 3),
                                   context.RawArray('d', 4), context.Lock(), context.Event(),
                                   lambda: capture)
        capture.release.assert_called_once()


class MainLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main
        cls.app = main

    def run_app(self, splash=True, failure=None, run_loop=False, paused=False, pose='staring', telegram=False, telegram_cli=False):
        app = self.app
        capture = Mock(index=0)
        capture.latest.return_value = np.zeros((480, 640, 3), dtype=np.uint8)
        detector = Mock()
        detector.process.return_value = SimpleNamespace(
            pose_landmarks=None, face_landmarks=None,
            right_hand_landmarks=None, left_hand_landmarks=None)
        state = app.AppState()
        state.telegram.enabled = telegram
        state.watermark = telegram
        state.paused = paused
        state.stable_pose = pose
        state.last_camera_sequence = capture.sequence
        state.recording = run_loop and not paused
        state.recording_size = (720, 720) if telegram_cli else (640, 480)
        writer = Mock()
        state.video_writer = writer
        events = []

        def intro(_):
            events.append('splash')
            return splash

        def initialize(*args):
            events.append('camera')
            if failure is not None:
                raise failure
            return capture

        with patch.object(app.sys, 'argv', ['main.py', '--telegram'] if telegram_cli else ['main.py']), \
                patch.object(app.cv2, 'namedWindow'), \
                patch.object(app, 'setup_directories'), \
                patch.object(app, 'load_meme_images', return_value={
                    name: np.zeros((90, 160, 3), dtype=np.uint8) for name in app.MEME_PATHS}), \
                patch.object(app, 'show_splash_screen', side_effect=intro), \
                patch.object(app, 'initialize_camera', side_effect=initialize), \
                patch.object(app, 'create_pose_detector', return_value=detector), \
                patch.object(app, 'AppState', return_value=state), \
                patch.object(app, 'wait_key', side_effect=[-1, ord('q')]), \
                patch.object(app, 'window_is_open', return_value=run_loop), \
                patch.object(app.cv2, 'imshow') as display, \
                patch.object(app.cv2, 'setWindowProperty'), \
                patch.object(app.cv2, 'getWindowProperty', return_value=1), \
                patch.object(app.cv2, 'destroyWindow') as destroy_secondary, \
                patch.object(app.cv2, 'destroyAllWindows') as destroy, \
                patch.object(app, 'show_camera_error') as error:
            app.main()
        if telegram:
            destroy_secondary.assert_called_once_with(app.TELEGRAM_WINDOW_NAME)
            self.assertFalse(state.telegram.enabled)
            if run_loop:
                clean_frames = [call.args[1] for call in display.call_args_list
                                if call.args[0] == app.TELEGRAM_WINDOW_NAME]
                self.assertEqual(len(clean_frames), 1)
                self.assertEqual(clean_frames[0].shape, (720, 720, 3))
                self.assertTrue(np.all(clean_frames[0] == 0))
        if run_loop and not paused:
            self.assertEqual(detector.process.call_args.args[0].shape, (480, 640, 3))
            output = display.call_args.args[1]
            self.assertEqual(output.shape, (480, 640, 3))
            exported = writer.write.call_args.args[0]
            self.assertEqual(exported.shape, (720, 720, 3) if telegram_cli else (480, 640, 3))
            np.testing.assert_array_equal(state.frame_buffer[-1], exported)
        destroy.assert_called_once()
        if telegram_cli:
            main_frames = [call.args[1] for call in display.call_args_list
                           if call.args[0] == app.APP_NAME]
            square_frames = [call.args[1] for call in display.call_args_list
                             if call.args[0] == app.TELEGRAM_WINDOW_NAME]
            self.assertGreaterEqual(len(main_frames), 2)
            self.assertEqual(main_frames[-1].shape, (480, 640, 3))
            self.assertGreaterEqual(len(square_frames), 1)
            self.assertTrue(all(frame.shape == (720, 720, 3) for frame in square_frames))
            self.assertEqual(app.WINDOW_NAME, app.APP_NAME)
        writer.release.assert_called_once()
        return capture, detector, events, error

    def test_splash_precedes_camera_and_close_releases_resources(self):
        capture, detector, events, _ = self.run_app()
        self.assertEqual(events, ['splash', 'camera'])
        capture.release.assert_called_once()
        detector.close.assert_called_once()

    def test_telegram_cli_separates_full_main_and_square_output(self):
        self.run_app(run_loop=True, telegram_cli=True)

    def test_splash_quit_does_not_open_camera(self):
        capture, detector, events, _ = self.run_app(splash=False)
        self.assertEqual(events, ['splash'])
        capture.release.assert_not_called()
        detector.close.assert_not_called()

    def test_camera_failure_shows_error_and_cleans_up(self):
        _, detector, _, error = self.run_app(failure=camera.CameraError('no camera'))
        error.assert_called_once()
        detector.close.assert_not_called()

    def test_ctrl_c_during_open_cleans_up(self):
        self.run_app(failure=KeyboardInterrupt())

    def test_close_button_maps_to_quit(self):
        with patch.object(self.app.cv2, 'waitKeyEx', return_value=-1), \
                patch.object(self.app.cv2, 'getWindowProperty', return_value=0):
            self.assertEqual(self.app.wait_key(), ord('q'))

    def test_q_after_rendering_releases_resources(self):
        capture, detector, _, _ = self.run_app(run_loop=True)
        detector.process.assert_called_once()
        capture.release.assert_called_once()
        detector.close.assert_called_once()

    def test_q_while_paused_releases_resources(self):
        capture, detector, _, _ = self.run_app(run_loop=True, paused=True)
        detector.process.assert_not_called()
        capture.release.assert_called_once()
        detector.close.assert_called_once()

    def test_power_renders_and_exports_without_key_errors(self):
        capture, detector, _, _ = self.run_app(run_loop=True, pose='power')
        detector.process.assert_called_once()
        capture.release.assert_called_once()

    def test_telegram_uses_one_capture_and_one_detector_then_closes(self):
        capture, detector, events, _ = self.run_app(run_loop=True, telegram=True)
        self.assertEqual(events, ['splash', 'camera'])
        detector.process.assert_called_once()
        detector.close.assert_called_once()
        capture.release.assert_called_once()

    def test_telegram_continues_recognition_while_main_view_paused(self):
        capture, detector, _, _ = self.run_app(run_loop=True, paused=True, telegram=True)
        detector.process.assert_called_once()
        capture.release.assert_called_once()

    def test_camera_error_closes_telegram(self):
        self.run_app(failure=camera.CameraError('no camera'), telegram=True)


if __name__ == '__main__':
    unittest.main()
