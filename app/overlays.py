"""Text dimensions shared by validation and PNG rasterization."""
from PIL import Image, ImageDraw, ImageFont
from .models import TextOverlay


def text_bounds(overlay: TextOverlay, font: ImageFont.FreeTypeFont):
    with Image.new('RGBA', (1, 1)) as image:
        box = ImageDraw.Draw(image).multiline_textbbox((0, 0), overlay.text, font=font, stroke_width=overlay.stroke_width, spacing=4)
    return box, (max(1, box[2] - box[0]), max(1, box[3] - box[1]))


def write_text(overlay: TextOverlay, destination):
    font = ImageFont.truetype(str(overlay.font), overlay.size)
    box, size = text_bounds(overlay, font)
    image = Image.new('RGBA', size, (0, 0, 0, 0))
    ImageDraw.Draw(image).multiline_text((-box[0], -box[1]), overlay.text, font=font, fill=overlay.color, stroke_fill=overlay.stroke_color, stroke_width=overlay.stroke_width, spacing=4)
    image.putalpha(image.getchannel('A').point(lambda value: round(value * overlay.opacity)))
    image.save(destination)
    image.close()


def write_logo(overlay, destination):
    with Image.open(overlay.path) as source:
        image = source.convert('RGBA')
        size = (overlay.width, max(1, round(image.height * overlay.width / image.width)))
        image = image.resize(size, Image.Resampling.LANCZOS)
        image.putalpha(image.getchannel('A').point(lambda value: round(value * overlay.opacity)))
        image.save(destination)
        image.close()
