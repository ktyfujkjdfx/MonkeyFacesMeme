import contextlib
import io
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

import main
from monkeyfacesmeme import telegram as tg


def solid(color, width=1280, height=720):
    return np.full((height, width, 3), color, np.uint8)


class TelegramRenderTests(unittest.TestCase):
    def test_staring_is_only_camera(self):
        camera = solid((20, 180, 40))
        with patch.object(tg.cv2, 'putText', side_effect=AssertionError('no UI')):
            result = tg.render_telegram_frame(camera, 'staring', {})
        self.assertEqual(result.shape, (720, 720, 3))
        self.assertTrue(np.all(result == (20, 180, 40)))

    def test_every_gesture_replaces_entire_camera(self):
        camera = solid((0, 255, 0))
        images = {pose: solid((0, 0, 200), 180, 300) for pose in main.MEME_PATHS}
        cache = tg.prepare_telegram_media(images)
        for pose in main.MEME_PATHS:
            if pose == 'staring':
                continue
            with self.subTest(pose=pose), patch.object(tg.cv2, 'putText', side_effect=AssertionError('no text')):
                result = tg.render_telegram_frame(camera, pose, cache)
                self.assertEqual(result.shape, (720, 720, 3))
                self.assertLess(int(result[:, :, 1].max()), 10)
                np.testing.assert_array_equal(result, cache[pose])

    def test_real_photos_are_in_cache(self):
        images = main.load_meme_images()
        cache = tg.prepare_telegram_media(images)
        for pose in ('snide', 'midfing', 'love', 'power'):
            self.assertEqual(cache[pose].shape, (720, 720, 3))
            self.assertFalse(cache[pose].flags.writeable)

    def test_center_crop_all_resolutions(self):
        for width, height in ((1280, 720), (1920, 1080), (721, 1281), (639, 481)):
            frame = np.zeros((height, width, 3), np.uint8)
            cv2.circle(frame, (width // 2, height // 2), min(width, height) // 8,
                       (255, 255, 255), -1)
            original = frame.copy()
            result = tg.crop_camera_to_square(frame)
            y, x = np.where(result[:, :, 0] > 128)
            self.assertLessEqual(abs(int(x.max() - x.min()) - int(y.max() - y.min())), 2)
            self.assertEqual(result.shape, (720, 720, 3))
            np.testing.assert_array_equal(frame, original)

    def test_media_is_full_bleed_and_preserves_geometry(self):
        for width, height in ((200, 400), (400, 400), (2000, 40), (40, 2000)):
            image = np.zeros((height, width, 3), np.uint8)
            cv2.circle(image, (width // 2, height // 2), max(2, min(width, height) // 5),
                       (240, 240, 240), -1)
            result = tg.compose_square_media(image)
            y, x = np.where(result[:, :, 0] > 220)
            self.assertLessEqual(abs((x.max() - x.min()) - (y.max() - y.min())), 3)
            self.assertEqual(result.shape, (720, 720, 3))

    def test_portrait_fills_circle_without_inner_card_edges(self):
        image = solid((60, 120, 200), 200, 400)
        result = tg.compose_square_media(image)
        self.assertTrue(np.all(result[360, 0] > 0))
        self.assertTrue(np.all(result[360, -1] > 0))
        self.assertTrue(np.all(result[0, 360] > 0))
        self.assertTrue(np.all(result[-1, 360] > 0))
        self.assertLess(np.max(np.abs(np.diff(result[360, :, 2].astype(int)))), 8)

    def test_square_cover_uses_center_crop(self):
        image = np.zeros((200, 600, 3), np.uint8)
        image[:, :200] = (255, 0, 0)
        image[:, 200:400] = (0, 255, 0)
        image[:, 400:] = (0, 0, 255)
        result = tg.compose_square_media(image)
        self.assertGreater(result[360, 360, 1], 200)
        self.assertLess(result[360, 360, 0], 20)
        self.assertLess(result[360, 360, 2], 20)

    def test_missing_media_falls_back_even_during_fade(self):
        camera = solid(80)
        snapshot = tg.TelegramRenderState(solid(200, 720, 720), .2)
        result = tg.render_telegram_frame(camera, 'missing', {}, snapshot)
        self.assertTrue(np.all(result == 80))

    def test_render_is_pure_and_blends_both_directions(self):
        camera = solid(20)
        cache = {'thinking': solid(220, 720, 720)}
        with patch.object(tg.time, 'sleep', side_effect=AssertionError('no sleep')), \
                patch.object(tg.cv2, 'imread', side_effect=AssertionError('no disk')):
            result = tg.render_telegram_frame(camera, 'thinking', cache,
                                             tg.TelegramRenderState(solid(20, 720, 720), .5))
            self.assertTrue(np.all(result == 120))
            result = tg.render_telegram_frame(camera, 'staring', cache,
                                             tg.TelegramRenderState(cache['thinking'], .5))
            self.assertTrue(np.all(result == 120))
        self.assertTrue(np.all(camera == 20))
        self.assertTrue(np.all(cache['thinking'] == 220))

    def test_nonfatal_image_loader(self):
        with patch.dict(main.MEME_PATHS, {'pointing': 'memes/absent.jpg'}, clear=True), \
                contextlib.redirect_stdout(io.StringIO()) as log:
            self.assertEqual(main.load_meme_images(strict=False), {})
        self.assertIn('MEME IMAGE ERROR', log.getvalue())


class TelegramStateTests(unittest.TestCase):
    def activate(self):
        state = tg.TelegramOutputState()
        for now in (-.25, -.10, .05):
            state.update('thinking', now)
        self.assertEqual(state.active_pose, 'thinking')
        return state

    def test_single_frame_does_not_switch(self):
        state = tg.TelegramOutputState()
        state.update('thinking', 0)
        state.update('staring', .1)
        self.assertEqual(state.active_pose, 'staring')

    def test_confirmation_and_phases(self):
        state = tg.TelegramOutputState()
        state.update('thinking', 0)
        self.assertEqual(state.phase, 'CANDIDATE_GESTURE')
        state.update('thinking', .05)
        self.assertEqual(state.active_pose, 'staring')
        state.update('thinking', .29)
        self.assertEqual(state.active_pose, 'staring')
        state.update('thinking', .30)
        self.assertEqual(state.active_pose, 'thinking')
        self.assertEqual(state.phase, 'MEME_ACTIVE')

    def test_loss_does_not_blink_and_hold_is_respected(self):
        state = self.activate()
        state.update('staring', .3)
        self.assertEqual(state.phase, 'CANDIDATE_RELEASE')
        state.update('thinking', .4)
        self.assertEqual(state.active_pose, 'thinking')
        for now in (.5, .7, .9):
            state.update('staring', now)
        self.assertEqual(state.active_pose, 'thinking')
        state.update('staring', 1.01)
        self.assertEqual(state.active_pose, 'staring')

    def test_gesture_to_gesture_without_camera_flash(self):
        state = self.activate()
        for now in (.3, .5, .8, .9):
            state.update('pointing', now)
            self.assertEqual(state.active_pose, 'thinking')
        state.update('pointing', 1.01)
        self.assertEqual(state.active_pose, 'pointing')

    def test_gap_does_not_confirm_stale_evidence(self):
        state = tg.TelegramOutputState()
        state.update('thinking', 0)
        state.update('thinking', 1)
        self.assertEqual(state.active_pose, 'staring')

    def test_transition_duration_and_disable(self):
        state = self.activate()
        self.assertAlmostEqual(state.render_state(.11).alpha, .5)
        self.assertEqual(state.render_state(.2).alpha, 1)
        self.assertEqual(state.render_state(.06, smooth=False).alpha, 1)

        for now in (.8, .9, 1.03):
            state.update('staring', now)
        self.assertEqual(state.active_pose, 'staring')
        self.assertAlmostEqual(state.render_state(1.19).alpha, .5)
        self.assertEqual(state.render_state(1.4).alpha, 1)


class TelegramWindowTests(unittest.TestCase):
    def setUp(self):
        self.patches = [patch.object(tg.cv2, name) for name in
                        ('namedWindow', 'imshow', 'destroyWindow')]
        self.named, self.show, self.destroy = [p.start() for p in self.patches]
        self.visible_patch = patch.object(tg.cv2, 'getWindowProperty', return_value=1)
        self.visible = self.visible_patch.start()
        self.addCleanup(self.visible_patch.stop)
        for p in self.patches:
            self.addCleanup(p.stop)
        self.output = tg.TelegramOutput()

    def test_toggle_and_reopen_without_camera(self):
        with patch.object(tg.cv2, 'VideoCapture', side_effect=AssertionError('second camera')):
            self.output.toggle()
            self.named.assert_called_with(tg.TELEGRAM_WINDOW_NAME, cv2.WINDOW_AUTOSIZE)
            self.assertTrue(self.output.enabled)
            self.output.toggle()
            self.assertFalse(self.output.enabled)
            self.output.toggle()
            self.assertTrue(self.output.enabled)
        self.destroy.assert_called_once()

    def test_toggle_can_start_with_real_camera_frame(self):
        camera = solid((10, 20, 30))
        self.output.toggle(camera)
        first = self.show.call_args.args[1]
        self.assertEqual(first.shape, (720, 720, 3))
        self.assertTrue(np.all(first == (10, 20, 30)))
        np.testing.assert_array_equal(self.output.last_frame, first)

    def test_close_button_only_disables_secondary_window(self):
        self.output.toggle()
        self.visible.return_value = 0
        with patch.object(tg.cv2, 'destroyAllWindows') as destroy_all:
            self.assertFalse(self.output.check_window())
            self.assertFalse(self.output.enabled)
            destroy_all.assert_not_called()

    def test_repeated_camera_frame_does_not_confirm_gesture(self):
        self.output.toggle()
        images = {'thinking': solid(180, 200, 400)}
        for now in (0, .1, .2, .3):
            self.output.present(solid(20), 'thinking', images, 1, now=now)
        self.assertEqual(self.output.controller.active_pose, 'staring')

    def test_cache_prepared_only_once_across_toggles(self):
        images = {'thinking': solid(180, 200, 400)}
        with patch.object(tg, 'compose_square_media', wraps=tg.compose_square_media) as compose, \
                patch.object(tg.cv2, 'imread', side_effect=AssertionError('no disk')):
            self.output.toggle()
            for i in range(5):
                self.output.present(solid(20), 'thinking', images, i, now=i * .1)
            self.output.toggle()
            self.output.toggle()
            self.output.present(solid(20), 'thinking', images, 6, now=.6)
            compose.assert_called_once()

    def test_missing_image_warning_once(self):
        self.output.toggle()
        with contextlib.redirect_stdout(io.StringIO()) as log:
            for i in range(4):
                self.output.present(solid(80), 'thinking', {}, i, now=i * .1)
        self.assertEqual(log.getvalue().count('unavailable'), 1)
        self.assertTrue(np.all(self.output.last_frame == 80))

    def test_t_key_owns_only_telegram_window(self):
        state = main.AppState()
        capture = Mock()
        frame = solid(20)
        main.handle_keypress(ord('t'), state, frame, capture, list(main.MEME_PATHS))
        self.assertTrue(state.telegram.enabled)
        main.handle_keypress(ord('t'), state, frame, capture, list(main.MEME_PATHS))
        self.assertFalse(state.telegram.enabled)
        self.assertEqual(capture.mock_calls, [])


if __name__ == '__main__':
    unittest.main()
