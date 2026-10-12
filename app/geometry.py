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


def move_region(original: Rect, dx, dy, bounds, even=False) -> Rect:
    width,height=bounds
    x=max(0,min(width-original.width,original.x+int(dx)))
    y=max(0,min(height-original.height,original.y+int(dy)))
    if even: x,y=x//2*2,y//2*2
    return Rect(x,y,original.width,original.height)


def resize_region(original: Rect, handle: str, dx, dy, bounds, even=False) -> Rect:
    width,height=bounds
    minimum=2 if even else 1
    if even: width,height=width//2*2,height//2*2
    left,top=original.x,original.y
    right,bottom=left+original.width,top+original.height
    if 'w' in handle: left=max(0,min(right-minimum,left+int(dx)))
    if 'e' in handle: right=min(width,max(left+minimum,right+int(dx)))
    if 'n' in handle: top=max(0,min(bottom-minimum,top+int(dy)))
    if 's' in handle: bottom=min(height,max(top+minimum,bottom+int(dy)))
    if even: left,top,right,bottom=(v//2*2 for v in (left,top,right,bottom))
    return Rect(left,top,max(minimum,right-left),max(minimum,bottom-top))
