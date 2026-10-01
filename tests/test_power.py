import unittest
from types import SimpleNamespace as NS

import numpy as np

import main
from tests.hand_helpers import hand, results


class PowerTests(unittest.TestCase):
    def test_two_fists_and_priority_over_thinking(self):
        r = results(left=hand(extended=(), mirrored=True), right=hand(extended=()))
        r.pose_landmarks.landmark[10] = r.right_hand_landmarks.landmark[8]
        self.assertEqual(main.detect_current_pose(r, 1280, 720), ('power', False))
        r.pose_landmarks = None
        self.assertEqual(main.detect_current_pose(r, 1280, 720), ('power', False))

    def test_one_or_no_hand_is_not_power(self):
        for r in (results(), results(left=hand(extended=())), results(right=hand(extended=()))):
            self.assertFalse(main.is_power_gesture(r, 1280, 720))
            self.assertNotEqual(main.detect_current_pose(r, 1280, 720)[0], 'power')

    def test_open_or_extended_fingers_rejected_on_either_hand(self):
        for fingers in ((5,), (9,), (13,), (17,), (5, 9), (5, 9, 13, 17)):
            for side in ('left', 'right'):
                r = results(left=hand(extended=()), right=hand(extended=()))
                setattr(r, side + '_hand_landmarks', hand(extended=fingers))
                self.assertFalse(main.is_power_gesture(r, 1280, 720))

    def test_scale_rotation_and_thumb(self):
        for scale in (25, 80, 130):
            for angle in (-45, 0, 45):
                left = hand(extended=(), mirrored=True, scale=scale, angle=angle, tilt=25)
                right = hand(extended=(), scale=scale, angle=-angle, tilt=-25)
                for h in (left, right):
                    for i in range(1, 5):
                        h.landmark[i] = NS(x=.9, y=.9, z=.1)
                self.assertTrue(main.is_power_gesture(results(left=left, right=right), 1280, 720))

    def test_invalid_hand_is_not_fist(self):
        for h in (None, NS(landmark=[]), NS(landmark=[NS(x=0, y=0, z=0)] * 21)):
            self.assertFalse(main.is_closed_fist(h, 1280, 720))

    def test_pointing_with_one_fist(self):
        r = results(left=hand(extended=()), right=hand(extended=(5,)))
        self.assertEqual(main.detect_current_pose(r, 1280, 720)[0], 'pointing')

    def test_stabilized_entry_and_release(self):
        state = main.AppState()
        main.stabilize_pose(state, 'staring', now=0)
        self.assertEqual(main.stabilize_pose(state, 'power', now=.05)[0], 'staring')
        main.stabilize_pose(state, 'staring', now=.1)
        for t in (.15, .2, .25, .3, .35):
            main.stabilize_pose(state, 'power', now=t)
        self.assertEqual(state.stable_pose, 'power')
        self.assertEqual(main.stabilize_pose(state, 'thinking', now=.4)[0], 'power')
        for t in (.45, .5, .55, .6, .65, .7):
            main.stabilize_pose(state, 'staring', now=t)
        self.assertEqual(state.stable_pose, 'staring')

    def test_photo_load_and_fill_without_face_overlay(self):
        photo = main.load_meme_images()['power']
        self.assertGreater(photo.size, 0)
        state = main.AppState()
        state.face_crop = True
        self.assertFalse(main.should_overlay_face(state, 'power', object()))
        self.assertEqual(main.POSE_DISPLAY_NAMES['power'], 'power')
        self.assertIn('power', state.pose_counts)
        source = np.full((300, 600, 3), 200, np.uint8)
        panel = main.prepare_meme_image(source, 'power', 640, 720)
        self.assertEqual(panel.shape, (720, 640, 3))
        self.assertTrue(np.all(panel == 200))


if __name__ == '__main__':
    unittest.main()
