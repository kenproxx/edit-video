"""Text dimensions shared by validation and PNG rasterization."""
from PIL import Image, ImageDraw, ImageFont
from .models import TextOverlay


def text_bounds(overlay: TextOverlay, font: ImageFont.FreeTypeFont):
    with Image.new('RGBA', (1, 1)) as image:
        box = ImageDraw.Draw(image).multiline_textbbox((0, 0), overlay.text, font=font, stroke_width=overlay.stroke_width, spacing=4)
    return box, (max(1, box[2] - box[0]), max(1, box[3] - box[1]))
