from pathlib import Path
import math

import cv2
import numpy as np

from .config import MEME_PATHS, PHOTO_POSES


def resize_to_fill(image, width, height):
    if image is None or image.size == 0 or width <= 0 or height <= 0:
        raise ValueError("image must be nonempty and target size must be positive")
    source_height, source_width = image.shape[:2]
    ratio = max(width / source_width, height / source_height)
    if ratio == 1 and (source_width, source_height) == (width, height):
        return image.copy()
    scaled = (max(width, math.ceil(source_width * ratio)),
              max(height, math.ceil(source_height * ratio)))
    interpolation = cv2.INTER_AREA if ratio < 1 else cv2.INTER_CUBIC
    image = cv2.resize(image, scaled, interpolation=interpolation)
    left = (scaled[0] - width) // 2
    top = (scaled[1] - height) // 2
    return image[top:top + height, left:left + width].copy()


def prepare_meme_image(image, _pose, width, height):
    return resize_to_fill(image, width, height)


def load_meme_images(strict=True):
    loaded = {}
    for pose, path in MEME_PATHS.items():
        image = cv2.imread(str(path)) if Path(path).is_file() else None
        if image is None or image.size == 0:
            print(f"MEME IMAGE ERROR: missing or unreadable image: {path}", flush=True)
            if strict:
                raise SystemExit(1)
            continue
        loaded[pose] = image
    return loaded


def should_overlay_face(state, pose, face):
    return bool(state.face_crop and pose not in PHOTO_POSES and face is not None)


def face_box(face, width, height, padding=0.30):
    if face is None:
        return None
    xs = np.asarray([point.x for point in face.landmark]) * width
    ys = np.asarray([point.y for point in face.landmark]) * height
    x_pad = (xs.max() - xs.min()) * padding
    y_pad = (ys.max() - ys.min()) * padding
    return (max(0, int(xs.min() - x_pad)), max(0, int(ys.min() - y_pad)),
            min(width, int(xs.max() + x_pad)), min(height, int(ys.max() + y_pad)))


def overlay_face(camera, meme, box, destination):
    if box is None:
        return meme
    x1, y1, x2, y2 = box
    dx1, dy1, dx2, dy2 = destination
    crop = camera[y1:y2, x1:x2]
    target_width, target_height = dx2 - dx1, dy2 - dy1
    if crop.size == 0 or target_width <= 0 or target_height <= 0:
        return meme
    portrait = resize_to_fill(crop, target_width, target_height)
    mask = np.zeros((target_height, target_width), np.uint8)
    cv2.ellipse(mask, (target_width // 2, target_height // 2),
                (max(1, target_width // 2 - 5), max(1, target_height // 2 - 5)),
                0, 0, 360, 255, -1, cv2.LINE_AA)
    mask = cv2.GaussianBlur(mask, (21, 21), 0).astype(np.float32)[:, :, None] / 255
    result = meme.copy()
    background = result[dy1:dy2, dx1:dx2]
    result[dy1:dy2, dx1:dx2] = (portrait * mask + background * (1 - mask)).astype(np.uint8)
    return result


def meme_panel_size(state, width, height):
    if state.vertical_mode:
        canvas_width = min(width, 540)
        canvas_height = int(canvas_width * 16 / 9)
        return canvas_width, canvas_height - canvas_height // 2
    if state.meme_only or state.pip_mode:
        return width, height
    return width - width // 2, height


def compose_output_frame(camera, meme, state, width, height):
    if state.vertical_mode:
        out_width = min(width, 540)
        out_height = int(out_width * 16 / 9)
        split = out_height // 2
        result = np.empty((out_height, out_width, 3), np.uint8)
        result[:split] = resize_to_fill(camera, out_width, split)
        result[split:] = resize_to_fill(meme, out_width, out_height - split)
        return result
    if state.meme_only:
        return resize_to_fill(meme, width, height)
    camera = resize_to_fill(camera, width, height)
    if state.pip_mode:
        size = max(80, round(min(width, height) * .40))
        inset = resize_to_fill(meme, size, size)
        result = camera.copy()
        y = height - size
        result[y:y + size, :size] = inset
        return result
    split = width // 2
    result = np.empty((height, width, 3), np.uint8)
    result[:, :split] = resize_to_fill(camera, split, height)
    result[:, split:] = resize_to_fill(meme, width - split, height)
    result[:, max(0, split - 1):min(width, split + 1 + width % 2)] = 85
    return result
