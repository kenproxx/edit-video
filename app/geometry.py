"""Map preview coordinates without treating letterbox margins as image pixels."""
from math import gcd
from .models import Rect


def canvas_to_pixel(x: float, y: float, image_box: Rect, image_size: tuple[int, int]) -> tuple[int, int] | None:
    if image_box.width <= 0 or image_box.height <= 0:
        return None
    if not (image_box.x <= x < image_box.x + image_box.width and image_box.y <= y < image_box.y + image_box.height):
        return None
    w, h = image_size
    return (int((x - image_box.x) * w / image_box.width), int((y - image_box.y) * h / image_box.height))


def preset_crop(width: int, height: int, ratio: tuple[int, int]) -> Rect:
    a, b = ratio
    if min(width, height, a, b) <= 0:
        raise ValueError('Kích thước/tỷ lệ không hợp lệ')
    d = gcd(a, b)
    a, b = a // d, b // d
    factor = min(width // a, height // b) // 2 * 2
    if not factor:
        raise ValueError('Video quá nhỏ cho crop này')
    w, h = a * factor, b * factor
    return Rect((width - w) // 4 * 2, (height - h) // 4 * 2, w, h)
