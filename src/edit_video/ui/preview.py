from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QImage, QPen, QColor
from PySide6.QtWidgets import QWidget
from ..models import Rect

class PreviewCanvas(QWidget):
    region_changed=Signal(str,object)
    position_changed=Signal(str,float,float)
    def __init__(self):
        super().__init__(); self.image=QImage(); self.mode='result'; self.start=None; self.end=None
        self.setMinimumSize(300,240); self.setMouseTracking(True)
    def set_frame(self,image: QImage) -> None:
        self.image=image; self.update()
    def image_rect(self) -> QRectF:
        if self.image.isNull(): return QRectF()
        scale=min(self.width()/self.image.width(),self.height()/self.image.height())
        w,h=self.image.width()*scale,self.image.height()*scale
        return QRectF((self.width()-w)/2,(self.height()-h)/2,w,h)
    def paintEvent(self,event):
        p=QPainter(self); p.fillRect(self.rect(),QColor('#101820'))
        if self.image.isNull():
            p.setPen(QColor('#90a5b8')); p.drawText(self.rect(),Qt.AlignCenter,'Chọn video để bắt đầu\nXem trước khung hình và chỉnh sửa tại đây')
        else: p.drawImage(self.image_rect(),self.image)
        if self.start is not None and self.end is not None:
            p.setPen(QPen(QColor('#56e0bb'),2,Qt.DashLine)); p.drawRect(QRectF(self.start,self.end).normalized())
        p.end()
    def mousePressEvent(self,event):
        if event.button()!=Qt.LeftButton or not self.image_rect().contains(event.position()): return
        self.start=event.position(); self.end=self.start
    def mouseMoveEvent(self,event):
        if self.start is not None: self.end=event.position(); self.update()
    def mouseReleaseEvent(self,event):
        if self.start is None: return
        area=self.image_rect(); point=event.position()
        point=QPointF(max(area.left(),min(area.right(),point.x())),max(area.top(),min(area.bottom(),point.y())))
        if self.mode in ('crop','blur'):
            r=QRectF(self.start,point).normalized()
            if r.width()>2 and r.height()>2:
                self.region_changed.emit(self.mode,Rect((r.x()-area.x())/area.width(),(r.y()-area.y())/area.height(),r.width()/area.width(),r.height()/area.height()))
        elif self.mode in ('logo','watermark','cover'):
            self.position_changed.emit(self.mode,(point.x()-area.x())/area.width(),(point.y()-area.y())/area.height())
        self.start=self.end=None; self.update()
