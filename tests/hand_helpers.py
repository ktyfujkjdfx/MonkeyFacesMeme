from types import SimpleNamespace as NS

import numpy as np


def hand(extended=(5,), spread=True, scale=80, angle=0, mirrored=False, tilt=0):
    points = np.zeros((21, 3), dtype=float)
    for mcp, base in ((5, (-.35, 1)), (9, (-.05, 1.15)),
                      (13, (.25, 1)), (17, (.55, .8))):
        points[mcp, :2] = base
        if mcp in extended:
            direction = np.array(((-.5 if mcp == 5 else .4) if spread else 0, 1, 0))
            for offset, distance in enumerate((.4, .75, 1.1), 1):
                points[mcp + offset] = points[mcp] + direction * distance
        else:
            for offset, delta in enumerate(((0, .4, 0), (.15, .15, 0), (.1, .02, 0)), 1):
                points[mcp + offset] = points[mcp] + delta
    if mirrored:
        points[:, 0] *= -1
    planar, depth = np.radians(angle), np.radians(tilt)
    rotation = np.array([[np.cos(planar), -np.sin(planar), 0],
                         [np.sin(planar), np.cos(planar), 0], [0, 0, 1]])
    depth_rotation = np.array([[np.cos(depth), 0, np.sin(depth)], [0, 1, 0],
                               [-np.sin(depth), 0, np.cos(depth)]])
    points = points @ rotation.T @ depth_rotation.T * scale
    points[:, 1] *= -1
    points += (640, 300, 0)
    return NS(landmark=[NS(x=x / 1280, y=y / 720, z=z / 1280) for x, y, z in points])


def results(left=None, right=None, body=True):
    pose = NS(landmark=[NS(x=.5, y=.55) for _ in range(33)]) if body else None
    if pose:
        pose.landmark[9] = NS(x=.45, y=.6)
        pose.landmark[10] = NS(x=.55, y=.6)
        pose.landmark[11].y = pose.landmark[12].y = .75
    return NS(left_hand_landmarks=left, right_hand_landmarks=right,
              pose_landmarks=pose, face_landmarks=None)
