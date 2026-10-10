"""Immutable settings shared by the editor, preview and exporter."""
from dataclasses import dataclass
from pathlib import Path
import math

@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float

@dataclass(frozen=True)
class TextLayer:
    text: str = ''
    font_family: str = 'Arial'
    size_px: int = 48
    color: str = '#ffffff'
    stroke_color: str = '#000000'
    stroke_px: int = 2
    opacity: float = 1.0
    x: float = .05
    y: float = .05

@dataclass(frozen=True)
class LogoLayer:
    path: Path
    x: float = .75
    y: float = .05
    width: float = .2
    opacity: float = 1.0

@dataclass(frozen=True)
class BlurLayer:
    rect: Rect
    sigma: float = 12.0

@dataclass(frozen=True)
class EditSettings:
    speed: float = 1.0
    flip_h: bool = False
    flip_v: bool = False
    crop: Rect | None = None
    blur: BlurLayer | None = None
    logo: LogoLayer | None = None
    watermark: TextLayer | None = None
    cover: TextLayer | None = None

def bounded(value, low, high, label):
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f'{label}: phải nằm trong {low}–{high}.')

def validate_rect(rect):
    for v in (rect.x, rect.y, rect.width, rect.height): bounded(v, 0, 1, 'Vùng ảnh')
    if rect.width <= 0 or rect.height <= 0 or rect.x + rect.width > 1.0000001 or rect.y + rect.height > 1.0000001:
        raise ValueError('Vùng ảnh phải có diện tích và nằm trong khung hình.')

def validate(settings: EditSettings) -> None:
    bounded(settings.speed, .25, 4, 'Tốc độ')
    if settings.crop: validate_rect(settings.crop)
    if settings.blur:
        validate_rect(settings.blur.rect)
        bounded(settings.blur.sigma, .1, 100, 'Cường độ mờ')
    for layer in (settings.watermark, settings.cover, settings.logo):
        if layer is None: continue
        bounded(layer.opacity, 0, 1, 'Độ trong suốt')
        bounded(layer.x, 0, 1, 'Vị trí X')
        bounded(layer.y, 0, 1, 'Vị trí Y')
        if isinstance(layer, TextLayer):
            bounded(layer.size_px, 1, 1000, 'Cỡ chữ')
            bounded(layer.stroke_px, 0, 100, 'Viền chữ')
        else: bounded(layer.width, .001, 1, 'Chiều rộng logo')

def crop_pixels(crop: Rect | None, width: int, height: int) -> tuple[int,int,int,int]:
    r = crop or Rect(0,0,1,1)
    validate_rect(r)
    x, y = int(r.x * width), int(r.y * height)
    w, h = int(r.width * width) // 2 * 2, int(r.height * height) // 2 * 2
    if w < 2 or h < 2: raise ValueError('Vùng crop quá nhỏ (tối thiểu 2×2 pixel).')
    return min(x,width-w), min(y,height-h), w, h
