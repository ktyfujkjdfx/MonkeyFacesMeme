"""Geometry-only gesture recognition built on MediaPipe landmarks."""

from collections import Counter
import math
import time

import numpy as np


CHIN_DISTANCE = 0.08
MOUTH_OPEN_RATIO = 0.50
POINT_ABOVE_HEAD = 0.05


def distance(a, b):
    return math.dist(a, b)


def joint_angle(a, pivot, b):
    first = np.asarray(a, dtype=float) - pivot
    second = np.asarray(b, dtype=float) - pivot
    length = np.linalg.norm(first) * np.linalg.norm(second)
    if length <= 1e-10:
        return 0.0
    cosine = np.clip(np.dot(first, second) / length, -1.0, 1.0)
    return float(np.degrees(np.arccos(cosine)))


def hand_points(hand, width, height):
    if hand is None or len(hand.landmark) < 21:
        return None
    points = np.asarray([
        (mark.x * width, mark.y * height, getattr(mark, "z", 0.0) * width)
        for mark in hand.landmark
    ], dtype=float)
    if not np.isfinite(points).all() or np.linalg.norm(points[5] - points[17]) < 1e-8:
        return None
    return points


def _extended(points, base):
    wrist, mcp, pip, dip, tip = points[0], *points[base:base + 4]
    return (
        joint_angle(wrist, mcp, pip) > 100
        and joint_angle(mcp, pip, dip) > 155
        and joint_angle(pip, dip, tip) > 150
        and np.linalg.norm(tip - wrist) > 1.12 * np.linalg.norm(pip - wrist)
        and np.linalg.norm(tip - wrist) > 1.30 * np.linalg.norm(mcp - wrist)
    )


def _folded(points, base):
    mcp, pip, dip, tip = points[base:base + 4]
    bent = joint_angle(mcp, pip, dip) < 135 or joint_angle(pip, dip, tip) < 135
    return bool(bent and np.linalg.norm(tip - points[0]) < 1.15 * np.linalg.norm(pip - points[0]))


def is_closed_fist(hand, width, height, points=None):
    points = hand_points(hand, width, height) if points is None else points
    if points is None:
        return False
    palm = np.linalg.norm(points[5] - points[17])
    if palm < 1e-8:
        return False
    compact = all(np.linalg.norm(points[base + 3] - points[0]) < palm * 1.9
                  for base in (5, 9, 13, 17))
    return bool(compact and all(_folded(points, base) for base in (5, 9, 13, 17)))


def is_power_gesture(results, width, height, points=None):
    left, right = points or (None, None)
    return bool(
        is_closed_fist(results.left_hand_landmarks, width, height, left)
        and is_closed_fist(results.right_hand_landmarks, width, height, right)
    )


def is_midfing_gesture(hand, width, height, points=None):
    points = hand_points(hand, width, height) if points is None else points
    return bool(points is not None
                and _extended(points, 9)
                and _folded(points, 5)
                and _folded(points, 13)
                and _folded(points, 17))


def is_finger_heart(hand, width, height, points=None):
    points = hand_points(hand, width, height) if points is None else points
    if points is None:
        return False
    palm = np.linalg.norm(points[5] - points[17])
    if palm < 1e-8:
        return False
    pinch = np.linalg.norm(points[4] - points[8]) / palm
    reach = np.linalg.norm((points[4] + points[8]) / 2 - points[0]) / palm
    folded = sum(_folded(points, base) for base in (9, 13, 17))
    return bool(pinch < 0.45 and reach > 1.45 and folded >= 2)


def is_two_hand_heart(results, width, height, points=None):
    if points is None:
        left = hand_points(results.left_hand_landmarks, width, height)
        right = hand_points(results.right_hand_landmarks, width, height)
    else:
        left, right = points
    if left is None or right is None:
        return False
    palm = (np.linalg.norm(left[5] - left[17]) + np.linalg.norm(right[5] - right[17])) / 2
    if palm < 1e-8:
        return False
    index_gap = np.linalg.norm(left[8] - right[8]) / palm
    thumb_gap = np.linalg.norm(left[4] - right[4]) / palm
    index_center = (left[8] + right[8]) / 2
    thumb_center = (left[4] + right[4]) / 2
    heart_height = (thumb_center[1] - index_center[1]) / palm
    wrists = np.linalg.norm(left[0] - right[0]) / palm
    return bool(index_gap < 1.1 and thumb_gap < 1.1
                and 0.35 < heart_height < 2.5 and wrists > 1.4
                and np.linalg.norm(left[8] - left[0]) / palm > 1.5
                and np.linalg.norm(right[8] - right[0]) / palm > 1.5)


def is_love_gesture(results, width, height, points=None):
    if points is None:
        left = hand_points(results.left_hand_landmarks, width, height)
        right = hand_points(results.right_hand_landmarks, width, height)
    else:
        left, right = points
    small_hearts = (
        is_finger_heart(results.left_hand_landmarks, width, height, left)
        and is_finger_heart(results.right_hand_landmarks, width, height, right)
    )
    return bool(small_hearts or is_two_hand_heart(results, width, height, (left, right)))


def _hands_together(results, width, height, points):
    left, right = points
    if left is None or right is None:
        return False
    palm = (np.linalg.norm(left[5] - left[17]) + np.linalg.norm(right[5] - right[17])) / 2
    if palm < 1e-8:
        return False
    centers = (left[[0, 5, 9, 13, 17]].mean(axis=0), right[[0, 5, 9, 13, 17]].mean(axis=0))
    close = np.linalg.norm(centers[0] - centers[1]) / palm < 1.8
    return bool(close)


def _snide_face(face):
    if face is None or len(face.landmark) <= 386:
        return False
    marks = face.landmark
    mouth_width = distance((marks[78].x, marks[78].y), (marks[308].x, marks[308].y))
    eye_width = distance((marks[33].x, marks[33].y), (marks[263].x, marks[263].y))
    if eye_width < 1e-8:
        return False
    smile = mouth_width / eye_width > 0.38
    brow_gap = distance((marks[107].x, marks[107].y), (marks[336].x, marks[336].y))
    furrow = brow_gap / eye_width < 0.50
    return bool(smile and furrow)


def is_snide_gesture(results, width, height, points=None):
    if points is None:
        points = (hand_points(results.left_hand_landmarks, width, height),
                  hand_points(results.right_hand_landmarks, width, height))
    return bool(_hands_together(results, width, height, points)
                and _snide_face(results.face_landmarks))


def mouth_openness(face):
    if face is None or len(face.landmark) <= 308:
        return 0.0
    marks = face.landmark
    height = distance((marks[13].x, marks[13].y), (marks[14].x, marks[14].y))
    width = distance((marks[78].x, marks[78].y), (marks[308].x, marks[308].y))
    return height / width if width > 1e-10 else 0.0


def _index_tip(hand):
    if hand is None or len(hand.landmark) <= 8:
        return None
    tip = hand.landmark[8]
    return tip.x, tip.y


def detect_current_pose(results, width, height):
    points = (hand_points(results.left_hand_landmarks, width, height),
              hand_points(results.right_hand_landmarks, width, height))
    for name, matched in (
        ("snide", is_snide_gesture(results, width, height, points)),
        ("power", is_power_gesture(results, width, height, points)),
        ("midfing", is_midfing_gesture(results.left_hand_landmarks, width, height, points[0])
         or is_midfing_gesture(results.right_hand_landmarks, width, height, points[1])),
        ("love", is_love_gesture(results, width, height, points)),
    ):
        if matched:
            return name, False

    if results.pose_landmarks is None:
        return "staring", False
    body = results.pose_landmarks.landmark
    nose_y = body[0].y
    shoulder_y = (body[11].y + body[12].y) / 2
    left_tip = _index_tip(results.left_hand_landmarks)
    right_tip = _index_tip(results.right_hand_landmarks)
    left_mouth = (body[9].x, body[9].y)
    right_mouth = (body[10].x, body[10].y)

    if right_tip and distance(right_tip, right_mouth) < CHIN_DISTANCE and right_tip[1] < shoulder_y:
        return "thinking", True
    if left_tip and distance(left_tip, left_mouth) < CHIN_DISTANCE and left_tip[1] < shoulder_y:
        return "thinking", False
    if right_tip and right_tip[1] < nose_y - POINT_ABOVE_HEAD:
        return "pointing", False
    if left_tip and left_tip[1] < nose_y - POINT_ABOVE_HEAD:
        return "pointing", True
    if mouth_openness(results.face_landmarks) > MOUTH_OPEN_RATIO:
        return "shocked", False
    return "staring", False


def stabilize_pose(state, pose, flip=False, now=None):
    now = time.monotonic() if now is None else now
    state.pose_history.append((now, pose, bool(flip)))
    state.pose_history[:] = [sample for sample in state.pose_history if now - sample[0] <= 0.30]
    matching = [sample for sample in state.pose_history if sample[1] == pose]
    if len(matching) >= 3 and len(matching) > len(state.pose_history) / 2:
        if now - matching[0][0] >= 0.15:
            state.stable_pose = pose
            state.stable_flip = Counter(sample[2] for sample in matching).most_common(1)[0][0]
    return state.stable_pose, state.stable_flip
