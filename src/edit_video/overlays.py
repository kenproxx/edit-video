"""Render overlays once, then use the exact same PNGs in all outputs."""
from pathlib import Path
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QImage, QPainter, QPainterPath, QFont, QFontMetricsF, QColor, QPen
from .models import TextLayer, LogoLayer, EditSettings

def canvas(size):
    img=QImage(*size,QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    return img

def _place(image, size, x, y, opacity):
    out=canvas(size)
    image=image.scaled(min(image.width(),size[0]),min(image.height(),size[1]),Qt.KeepAspectRatio,Qt.SmoothTransformation)
    px=min(round(x*size[0]),size[0]-image.width())
    py=min(round(y*size[1]),size[1]-image.height())
    painter=QPainter(out)
    painter.setOpacity(opacity)
    painter.drawImage(px,py,image)
    painter.end()
    return out

def text_overlay(layer: TextLayer, size: tuple[int,int]) -> QImage:
    if not layer.text: return canvas(size)
    font=QFont(layer.font_family); font.setPixelSize(layer.size_px); font.setBold(True)
    metrics=QFontMetricsF(font)
    path=QPainterPath()
    for index,line in enumerate(layer.text.splitlines()):
        path.addText(QPointF(0,metrics.ascent()+index*metrics.lineSpacing()),font,line)
    bounds=path.boundingRect().adjusted(-layer.stroke_px-1,-layer.stroke_px-1,layer.stroke_px+1,layer.stroke_px+1)
    if bounds.isEmpty(): return canvas(size)
    scale=min(1,size[0]/bounds.width(),size[1]/bounds.height())
    image=canvas((max(1,round(bounds.width()*scale)),max(1,round(bounds.height()*scale))))
    painter=QPainter(image); painter.setRenderHint(QPainter.Antialiasing)
    painter.scale(scale,scale); painter.translate(-bounds.x(),-bounds.y())
    if layer.stroke_px:
        painter.setPen(QPen(QColor(layer.stroke_color),layer.stroke_px*2,Qt.SolidLine,Qt.RoundCap,Qt.RoundJoin))
    else: painter.setPen(Qt.NoPen)
    painter.setBrush(QColor(layer.color)); painter.drawPath(path); painter.end()
    return _place(image,size,layer.x,layer.y,layer.opacity)

def logo_overlay(layer: LogoLayer, size: tuple[int,int]) -> QImage:
    image=QImage(str(layer.path))
    if image.isNull(): raise ValueError('Không đọc được ảnh logo.')
    image=image.scaledToWidth(max(1,round(layer.width*size[0])),Qt.SmoothTransformation)
    return _place(image,size,layer.x,layer.y,layer.opacity)

def write_overlays(settings: EditSettings, size: tuple[int,int], directory: Path, include_cover: bool) -> list[Path]:
    directory.mkdir(parents=True,exist_ok=True)
    result=[]
    layers=[('logo',settings.logo),('watermark',settings.watermark)]
    if include_cover: layers.append(('cover',settings.cover))
    for name,layer in layers:
        if layer is None: continue
        image=logo_overlay(layer,size) if isinstance(layer,LogoLayer) else text_overlay(layer,size)
        path=directory/(name+'.png')
        if not image.save(str(path),'PNG'): raise OSError('Không lưu được lớp chữ/logo.')
        result.append(path)
    return result
