import unittest
from types import SimpleNamespace as NS

import main
from tests.hand_helpers import hand, results


def finger_heart(mirrored=False):
    landmarks = hand(extended=(5,), mirrored=mirrored)
    index_tip = landmarks.landmark[8]
    landmarks.landmark[4] = NS(x=index_tip.x + .002, y=index_tip.y + .002, z=index_tip.z)
    return landmarks


def large_two_hand_heart():
    left, right = hand(extended=(5,), mirrored=True), hand(extended=(5,))
    left.landmark[0], right.landmark[0] = NS(x=.40, y=.55, z=0), NS(x=.60, y=.55, z=0)
    left.landmark[8], right.landmark[8] = NS(x=.48, y=.30, z=0), NS(x=.52, y=.30, z=0)
    left.landmark[4], right.landmark[4] = NS(x=.48, y=.42, z=0), NS(x=.52, y=.42, z=0)
    return left, right


def snide_face(furrowed=True, smiling=True):
    landmarks = [NS(x=.5, y=.5, z=0) for _ in range(468)]
    landmarks[33], landmarks[263] = NS(x=.35, y=.45, z=0), NS(x=.65, y=.45, z=0)
    mouth_half = .07 if smiling else .04
    landmarks[78] = NS(x=.5 - mouth_half, y=.60, z=0)
    landmarks[308] = NS(x=.5 + mouth_half, y=.60, z=0)
    landmarks[13], landmarks[14] = NS(x=.5, y=.595, z=0), NS(x=.5, y=.61, z=0)
    brow_half = .05 if furrowed else .10
    landmarks[107] = NS(x=.5 - brow_half, y=.40, z=0)
    landmarks[336] = NS(x=.5 + brow_half, y=.40, z=0)
    return NS(landmark=landmarks)


class NewGestureTests(unittest.TestCase):
    def test_midfing_on_either_hand(self):
        for side in ('left', 'right'):
            gesture = hand(extended=(9,), mirrored=side == 'left')
            pose = results(**{side: gesture})
            self.assertTrue(main.is_midfing_gesture(gesture, 1280, 720))
            self.assertEqual(main.detect_current_pose(pose, 1280, 720)[0], 'midfing')

    def test_midfing_rejects_other_finger_shapes(self):
        for extended in ((), (5,), (5, 9), (9, 13)):
            self.assertFalse(main.is_midfing_gesture(hand(extended=extended), 1280, 720))

    def test_love_requires_two_finger_hearts(self):
        left, right = finger_heart(True), finger_heart(False)
        self.assertTrue(main.is_finger_heart(left, 1280, 720))
        self.assertTrue(main.is_love_gesture(results(left=left, right=right), 1280, 720))
        self.assertEqual(main.detect_current_pose(results(left=left, right=right), 1280, 720)[0], 'love')
        self.assertFalse(main.is_love_gesture(results(left=left), 1280, 720))

    def test_love_accepts_one_large_two_hand_heart(self):
        left, right = large_two_hand_heart()
        pose = results(left=left, right=right)
        self.assertTrue(main.is_two_hand_heart(pose, 1280, 720))
        self.assertTrue(main.is_love_gesture(pose, 1280, 720))
        self.assertFalse(main.is_power_gesture(pose, 1280, 720))
        self.assertEqual(main.detect_current_pose(pose, 1280, 720)[0], 'love')

    def test_love_rejects_fists_and_clasped_hands(self):
        fists = results(left=hand(extended=(), mirrored=True), right=hand(extended=()))
        self.assertFalse(main.is_love_gesture(fists, 1280, 720))
        self.assertEqual(main.detect_current_pose(fists, 1280, 720)[0], 'power')
        fists.face_landmarks = snide_face()
        self.assertFalse(main.is_love_gesture(fists, 1280, 720))
        self.assertEqual(main.detect_current_pose(fists, 1280, 720)[0], 'snide')

    def test_snide_requires_clasped_hands_smile_and_furrow(self):
        pose = results(left=hand(extended=(), mirrored=True), right=hand(extended=()))
        pose.face_landmarks = snide_face()
        self.assertTrue(main.is_snide_gesture(pose, 1280, 720))
        self.assertEqual(main.detect_current_pose(pose, 1280, 720)[0], 'snide')
        pose.face_landmarks = snide_face(furrowed=False)
        self.assertFalse(main.is_snide_gesture(pose, 1280, 720))
        pose.face_landmarks = snide_face(smiling=False)
        self.assertFalse(main.is_snide_gesture(pose, 1280, 720))

    def test_new_photos_load_and_disable_face_overlay(self):
        images = main.load_meme_images()
        state = main.AppState()
        state.face_crop = True
        for pose in ('snide', 'midfing', 'love'):
            self.assertGreater(images[pose].size, 0)
            self.assertIn(pose, state.pose_counts)
            self.assertFalse(main.should_overlay_face(state, pose, object()))


if __name__ == '__main__':
    unittest.main()
