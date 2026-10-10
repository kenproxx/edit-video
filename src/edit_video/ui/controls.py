from pathlib import Path
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (QWidget,QFormLayout,QVBoxLayout,QHBoxLayout,QGroupBox,QDoubleSpinBox,QSpinBox,QCheckBox,QPlainTextEdit,QLineEdit,QPushButton,QFileDialog,QFontComboBox,QComboBox,QColorDialog)
from ..models import EditSettings, Rect, TextLayer, LogoLayer, BlurLayer

def number(low,high,value,decimals=2):
    widget=QDoubleSpinBox(); widget.setRange(low,high); widget.setDecimals(decimals); widget.setValue(value)
    widget.setKeyboardTracking(False); return widget

class RegionControls(QGroupBox):
    changed=Signal()
    def __init__(self,title):
        super().__init__(title); self.enabled=QCheckBox('Bật'); form=QFormLayout(self); form.addRow(self.enabled)
        self.values=[number(0,100,v) for v in (0,0,100,100)]
        for name,box in zip(('X (%)','Y (%)','Rộng (%)','Cao (%)'),self.values):
            form.addRow(name,box); box.valueChanged.connect(self.changed)
        self.enabled.toggled.connect(self.changed)
    def rect(self): return Rect(*(box.value()/100 for box in self.values))
    def set_rect(self,rect):
        for box,value in zip(self.values,(rect.x,rect.y,rect.width,rect.height)):
            box.blockSignals(True); box.setValue(value*100); box.blockSignals(False)
        self.enabled.setChecked(True); self.changed.emit()

class TextControls(QGroupBox):
    changed=Signal()
    def __init__(self,title):
        super().__init__(title); form=QFormLayout(self)
        self.enabled=QCheckBox('Bật'); self.text=QPlainTextEdit(); self.text.setMaximumHeight(75)
        self.text.setPlaceholderText('Nhập nội dung tiếng Việt…')
        self.font=QFontComboBox(); self.font.setCurrentFont(QFont('Arial'))
        self.size=number(1,1000,48,0); self.stroke=number(0,100,2,0)
        self.color=QPushButton('#ffffff'); self.outline=QPushButton('#000000')
        self.x=number(0,100,5); self.y=number(0,100,5); self.opacity=number(0,100,100)
        for label,item in [('',self.enabled),('Nội dung',self.text),('Font',self.font),('Cỡ chữ (px)',self.size),('Màu chữ',self.color),('Màu viền',self.outline),('Viền (px)',self.stroke),('X (%)',self.x),('Y (%)',self.y),('Hiển thị (%)',self.opacity)]: form.addRow(label,item)
        for button in (self.color,self.outline): button.clicked.connect(lambda checked=False,b=button:self.choose_color(b))
        self.enabled.toggled.connect(self.changed); self.text.textChanged.connect(self.changed); self.font.currentFontChanged.connect(self.changed)
        for spin in (self.size,self.stroke,self.x,self.y,self.opacity): spin.valueChanged.connect(self.changed)
    def choose_color(self,button):
        color=QColorDialog.getColor(QColor(button.text()),self)
        if color.isValid(): button.setText(color.name()); self.changed.emit()
    def layer(self):
        if not self.enabled.isChecked() or not self.text.toPlainText(): return None
        return TextLayer(self.text.toPlainText(),self.font.currentFont().family(),int(self.size.value()),self.color.text(),self.outline.text(),int(self.stroke.value()),self.opacity.value()/100,self.x.value()/100,self.y.value()/100)

class EditorControls(QWidget):
    changed=Signal()
    def __init__(self):
        super().__init__(); layout=QVBoxLayout(self)
        group=QGroupBox('Video'); form=QFormLayout(group)
        self.speed=number(.25,4,1); self.speed.setSingleStep(.25)
        self.flip_h=QCheckBox('Lật ngang'); self.flip_v=QCheckBox('Lật dọc')
        form.addRow('Tốc độ ×',self.speed); form.addRow(self.flip_h); form.addRow(self.flip_v)
        layout.addWidget(group)
        self.crop=RegionControls('Crop / cắt khung hình'); self.preset=QComboBox(); self.preset.addItems(['Tự do','9:16','16:9','1:1'])
        self.crop.layout().insertRow(1,'Tỷ lệ',self.preset); layout.addWidget(self.crop)
        self.blur=RegionControls('Làm mờ vùng cố định'); self.sigma=number(.1,100,12)
        self.blur.layout().addRow('Cường độ',self.sigma); layout.addWidget(self.blur)
        logo=QGroupBox('Logo watermark'); form=QFormLayout(logo)
        self.logo_enabled=QCheckBox('Bật'); self.logo_path=QLineEdit(); self.logo_button=QPushButton('Chọn ảnh…')
        form.addRow(self.logo_enabled); form.addRow(self.logo_path); form.addRow(self.logo_button)
        self.logo_x=number(0,100,75); self.logo_y=number(0,100,5); self.logo_width=number(.1,100,20); self.logo_opacity=number(0,100,100)
        for label,item in [('X (%)',self.logo_x),('Y (%)',self.logo_y),('Rộng (%)',self.logo_width),('Hiển thị (%)',self.logo_opacity)]: form.addRow(label,item)
        layout.addWidget(logo)
        self.watermark=TextControls('Chữ watermark trên video'); self.cover=TextControls('Chữ ảnh bìa riêng')
        layout.addWidget(self.watermark); layout.addWidget(self.cover)
        self.reset=QPushButton('Đặt lại hiệu ứng'); layout.addWidget(self.reset); layout.addStretch()
        for widget in (self.crop,self.blur,self.watermark,self.cover): widget.changed.connect(self.changed)
        for widget in (self.speed,self.sigma,self.logo_x,self.logo_y,self.logo_width,self.logo_opacity): widget.valueChanged.connect(self.changed)
        for widget in (self.flip_h,self.flip_v,self.logo_enabled): widget.toggled.connect(self.changed)
        self.logo_path.textChanged.connect(self.changed); self.logo_button.clicked.connect(self.choose_logo)
        self.reset.clicked.connect(self.reset_all)
    def choose_logo(self):
        path,_=QFileDialog.getOpenFileName(self,'Chọn logo','','Ảnh (*.png *.jpg *.jpeg)')
        if path: self.logo_path.setText(path); self.logo_enabled.setChecked(True)
    def settings(self):
        logo=None
        if self.logo_enabled.isChecked() and self.logo_path.text():
            logo=LogoLayer(Path(self.logo_path.text()),self.logo_x.value()/100,self.logo_y.value()/100,self.logo_width.value()/100,self.logo_opacity.value()/100)
        return EditSettings(self.speed.value(),self.flip_h.isChecked(),self.flip_v.isChecked(),self.crop.rect() if self.crop.enabled.isChecked() else None,BlurLayer(self.blur.rect(),self.sigma.value()) if self.blur.enabled.isChecked() else None,logo,self.watermark.layer(),self.cover.layer())
    def reset_all(self):
        self.speed.setValue(1); self.flip_h.setChecked(False); self.flip_v.setChecked(False)
        for widget in (self.crop.enabled,self.blur.enabled,self.logo_enabled,self.watermark.enabled,self.cover.enabled): widget.setChecked(False)
        self.preset.setCurrentText('Tự do'); self.changed.emit()
