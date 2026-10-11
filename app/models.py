"""Validated, GUI-independent edit configuration; coordinates are display pixels."""
from dataclasses import dataclass
import math
from pathlib import Path
from PIL import Image, ImageColor, ImageFont

@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

@dataclass(frozen=True)
class TextOverlay:
    text: str
    font: Path
    size: int
    color: str
    stroke_color: str
    stroke_width: int
    x: int
    y: int
    opacity: float

@dataclass(frozen=True)
class LogoOverlay:
    path: Path
    x: int
    y: int
    width: int
    opacity: float

@dataclass(frozen=True)
class EditOptions:
    speed: float = 1
    flip_horizontal: bool = False
    flip_vertical: bool = False
    crop: Rect | None = None
    blur: Rect | None = None
    blur_strength: int = 10
    logo: LogoOverlay | None = None
    watermark: TextOverlay | None = None
    intro: TextOverlay | None = None
    intro_duration: float = 1


def _integer(value: int, name: str, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f'{name}: giá trị nguyên tối thiểu {minimum}')


def _region(region: Rect, width: int, height: int, even: bool = False) -> None:
    for name in ('x', 'y', 'width', 'height'):
        _integer(getattr(region, name), name, 1 if name in ('width', 'height') else 0)
    if region.x + region.width > width or region.y + region.height > height:
        raise ValueError('Vùng chọn vượt kích thước video')
    if even and any(v % 2 for v in (region.x, region.y, region.width, region.height)):
        raise ValueError('Crop cần tọa độ và kích thước chẵn')


def _opacity(value: float) -> None:
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError('Độ trong suốt phải từ 0 đến 1')


def validate_options(options: EditOptions, width: int, height: int, duration: float) -> None:
    _integer(width, 'width', 2)
    _integer(height, 'height', 2)
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('Thời lượng video không hợp lệ')
    if not math.isfinite(options.speed) or not .25 <= options.speed <= 4:
        raise ValueError('Tốc độ phải từ 0.25 đến 4')
    if options.crop:
        _region(options.crop, width, height, even=True)
        width, height = options.crop.width, options.crop.height
    else:
        width, height = width // 2 * 2, height // 2 * 2
    if options.blur:
        _region(options.blur, width, height)
        _integer(options.blur_strength, 'blur_strength', 1)
        if options.blur_strength > 100:
            raise ValueError('Mức blur tối đa 100')
    for overlay in (options.watermark, options.intro):
        if overlay is None or not overlay.text.strip():
            continue
        _integer(overlay.size, 'font size', 1)
        _integer(overlay.stroke_width, 'stroke width')
        _integer(overlay.x, 'text x')
        _integer(overlay.y, 'text y')
        _opacity(overlay.opacity)
        try:
            font = ImageFont.truetype(str(overlay.font), overlay.size)
            ImageColor.getcolor(overlay.color, 'RGBA')
            ImageColor.getcolor(overlay.stroke_color, 'RGBA')
            # Shared raster geometry, including stroke and multiline spacing.
            from .overlays import text_bounds
            ow, oh = text_bounds(overlay, font)[1]
        except (OSError, ValueError) as exc:
            raise ValueError('Font hoặc màu chữ không hợp lệ') from exc
        if overlay.x + ow > width or overlay.y + oh > height:
            raise ValueError('Text vượt vùng video; giảm font hoặc đổi vị trí')
    if options.intro and options.intro.text.strip():
        if not math.isfinite(options.intro_duration) or not 0 < options.intro_duration <= duration / options.speed:
            raise ValueError('Thời gian text đầu vượt thời lượng video đầu ra')
    if options.logo:
        logo = options.logo
        _integer(logo.width, 'logo width', 1)
        _integer(logo.x, 'logo x')
        _integer(logo.y, 'logo y')
        _opacity(logo.opacity)
        try:
            with Image.open(logo.path) as image:
                if image.format not in ('PNG', 'JPEG'):
                    raise ValueError('Logo phải là PNG/JPEG')
                image.load()
                lh = max(1, round(image.height * logo.width / image.width))
        except OSError as exc:
            raise ValueError('Không đọc được logo') from exc
        if logo.x + logo.width > width or logo.y + lh > height:
            raise ValueError('Logo vượt vùng video')


def default_output(input_path: Path, directory: Path) -> Path:
    return directory / (input_path.stem + '.mp4')
