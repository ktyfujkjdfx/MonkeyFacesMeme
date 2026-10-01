import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

import main


class LayoutTests(unittest.TestCase):
    def test_default_even_and_odd_split(self):
        camera = np.full((120, 200, 3), (0, 200, 0), np.uint8)
        meme = np.full((200, 120, 3), (0, 0, 200), np.uint8)
        for width, height in ((1280, 720), (1279, 719), (641, 481), (640, 480)):
            with self.subTest(width=width):
                result = main.compose_output_frame(camera, meme, main.AppState(), width, height)
                self.assertEqual(result.shape, (height, width, 3))
                mid = width // 2
                self.assertTrue(np.all(result[:, :mid - 1] == (0, 200, 0)))
                self.assertTrue(np.all(result[:, mid + 1 + width % 2:] == (0, 0, 200)))
                self.assertTrue(np.all(result[:, mid - 1:mid + 1 + width % 2] == 85))

    def test_circle_stays_round_in_all_orientations(self):
        for source_width, source_height in ((400, 200), (200, 400), (301, 301)):
            image = np.zeros((source_height, source_width, 3), np.uint8)
            cv2.circle(image, (source_width // 2, source_height // 2), 25, (255, 255, 255), -1)
            for width, height in ((160, 180), (320, 360), (401, 201), (201, 401)):
                with self.subTest(source=image.shape, target=(width, height)):
                    result = main.resize_to_fill(image, width, height)
                    self.assertEqual(result.shape, (height, width, 3))
                    y, x = np.where(result[:, :, 0] > 128)
                    self.assertLessEqual(abs(int(x.max() - x.min()) - int(y.max() - y.min())), 2)

    def test_center_crop(self):
        image = np.zeros((100, 300, 3), np.uint8)
        image[:, :100] = (255, 0, 0)
        image[:, 100:200] = (0, 255, 0)
        image[:, 200:] = (0, 0, 255)
        result = main.resize_to_fill(image, 100, 100)
        self.assertTrue(np.all(result == (0, 255, 0)))

    def test_interpolation(self):
        original = cv2.resize
        for target, expected in ((50, cv2.INTER_AREA), (200, cv2.INTER_CUBIC)):
            with patch.object(main.cv2, 'resize', wraps=original) as resize:
                main.resize_to_fill(np.zeros((100, 100, 3), np.uint8), target, target)
                self.assertEqual(resize.call_args.kwargs['interpolation'], expected)

    def test_invalid_inputs(self):
        for image, width, height in ((np.zeros((0, 3, 3)), 10, 10),
                                     (np.zeros((10, 10, 3)), 0, 10)):
            with self.assertRaises(ValueError):
                main.resize_to_fill(image, width, height)

    def test_meme_only_pip_and_portrait(self):
        camera = np.full((480, 640, 3), 50, np.uint8)
        meme = np.full((200, 100, 3), 150, np.uint8)
        state = main.AppState()
        state.meme_only = True
        self.assertTrue(np.all(main.compose_output_frame(camera, meme, state, 641, 481) == 150))
        state.meme_only = False
        state.pip_mode = True
        output = main.compose_output_frame(camera, meme, state, 641, 481)
        self.assertEqual(output.shape, (481, 641, 3))
        self.assertTrue(np.all(output[80:120, 500:530] == 50))
        self.assertTrue(np.all(output[300:, :100] == 150))
        state.vertical_mode = True
        for width in (1280, 539):
            output = main.compose_output_frame(camera, meme, state, width, 720)
            w = min(width, 540)
            h = int(w * 16 / 9)
            self.assertEqual(output.shape, (h, w, 3))
            self.assertTrue(np.all(output[:h // 2] == 50))
            self.assertTrue(np.all(output[h // 2:] == 150))

    def test_mode_keys(self):
        state = main.AppState()
        frame = np.zeros((100, 100, 3), np.uint8)
        def key(letter):
            main.handle_keypress(ord(letter), state, frame, Mock(), list(main.MEME_PATHS))
        key('v')
        key('b')
        self.assertTrue(state.side_by_side)
        self.assertFalse(state.vertical_mode or state.meme_only or state.pip_mode)
        key('m')
        self.assertTrue(state.meme_only)
        key('i')
        self.assertTrue(state.pip_mode)
        self.assertFalse(state.meme_only)
        key('b')
        self.assertFalse(state.pip_mode)

    def test_screenshot_and_sequence_use_output_pixels(self):
        state = main.AppState()
        output = np.arange(240 * 320 * 3, dtype=np.uint8).reshape(240, 320, 3)
        state.frame_buffer.append(output.copy())
        with patch.object(main.cv2, 'imwrite') as write:
            main.handle_keypress(ord('s'), state, output, Mock(), [])
            np.testing.assert_array_equal(write.call_args.args[1], output)
            main.handle_keypress(ord('g'), state, output, Mock(), [])
            np.testing.assert_array_equal(write.call_args.args[1], output)

    def test_recording_writes_each_camera_sequence_once(self):
        state = main.AppState()
        state.recording = True
        state.recording_size = (320, 240)
        state.video_writer = Mock()
        output = np.zeros((240, 320, 3), np.uint8)

        main.write_recording_frame(state, output, sequence=41)
        main.write_recording_frame(state, output, sequence=41)
        main.write_recording_frame(state, output, sequence=42)

        self.assertEqual(state.video_writer.write.call_count, 2)
        self.assertEqual(state.last_record_sequence, 42)

    def test_loading_screen_is_square_minimal_and_animated(self):
        first = main.draw_loading_screen(width=720, height=720, now=0.0)
        second = main.draw_loading_screen(width=720, height=720, now=0.5)
        error = main.draw_loading_screen('CAMERA ERROR', width=960, height=540, now=0.0)

        self.assertEqual(first.shape, (720, 720, 3))
        self.assertEqual(error.shape, (540, 960, 3))
        self.assertFalse(np.array_equal(first, second))
        self.assertTrue(np.all(first[0, 0] == (12, 14, 18)))

    def test_welcome_screen_lists_controls_before_camera(self):
        first = main.draw_welcome_screen(960, 540, now=0.0)
        second = main.draw_welcome_screen(720, 720, now=0.5)
        self.assertEqual(first.shape, (540, 960, 3))
        self.assertEqual(second.shape, (720, 720, 3))
        self.assertGreater(np.count_nonzero(first != (12, 14, 18)), 1000)

    def test_hotkeys_accept_caps_lock_and_russian_layout(self):
        pairs = {
            ord('Q'): ord('q'), ord('S'): ord('s'), ord('T'): ord('t'),
            ord('й'): ord('q'), ord('ы'): ord('s'), ord('е'): ord('t'),
            ord('Й'): ord('q'), ord('Ы'): ord('s'), ord('Е'): ord('t'),
            ord('К'): ord('r'), ord('П'): ord('g'), ord('Р'): ord('h'),
            'р'.encode('cp1251')[0]: ord('h'),
            'к'.encode('cp1251')[0]: ord('r'),
            'п'.encode('cp1251')[0]: ord('g'),
            'Й'.encode('cp1251')[0]: ord('q'),
        }
        for raw, expected in pairs.items():
            with self.subTest(raw=raw):
                self.assertEqual(main.normalize_key(raw), expected)

    def test_intro_waits_for_enter_and_quits_on_q(self):
        with patch.object(main.cv2, 'namedWindow'), \
                patch.object(main.cv2, 'resizeWindow'), \
                patch.object(main.cv2, 'moveWindow'), \
                patch.object(main.cv2, 'imshow') as show, \
                patch.object(main, 'wait_key', side_effect=[-1, 13, -1]):
            self.assertTrue(main.show_splash_screen({}))
            self.assertGreaterEqual(show.call_count, 3)
        with patch.object(main.cv2, 'namedWindow'), \
                patch.object(main.cv2, 'resizeWindow'), \
                patch.object(main.cv2, 'moveWindow'), \
                patch.object(main.cv2, 'imshow'), \
                patch.object(main, 'wait_key', return_value=ord('q')):
            self.assertFalse(main.show_splash_screen({}))

    def test_recording_resolution_change_starts_segment_without_resizing(self):
        state = main.AppState()
        state.recording = True
        state.recording_size = (1280, 720)
        old_writer = Mock()
        state.video_writer = old_writer
        new_writer = Mock()
        output = np.zeros((960, 540, 3), np.uint8)
        with patch.object(main.cv2, 'VideoWriter', return_value=new_writer) as factory:
            main.write_recording_frame(state, output)
        old_writer.release.assert_called_once()
        self.assertEqual(factory.call_args.args[-1], (540, 960))
        self.assertIs(new_writer.write.call_args.args[0], output)
        self.assertEqual(state.recording_size, (540, 960))

    def test_minimal_label_keeps_rest_of_image_clear(self):
        state = main.AppState()
        output = np.full((720, 1280, 3), 200, np.uint8)
        main.draw_header_ui(output, state, 1280, 'thinking')
        self.assertTrue(np.all(output[:, :1100] == 200))
        self.assertTrue(np.all(output[40:] == 200))


if __name__ == '__main__':
    unittest.main()
