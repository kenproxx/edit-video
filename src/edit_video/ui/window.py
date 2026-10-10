from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QLineEdit,QSlider,QComboBox,QProgressBar,QScrollArea,QSplitter,QPlainTextEdit,QGroupBox)
from .preview import PreviewCanvas
from .controls import EditorControls

class EditorWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.controller=None; self.setWindowTitle('Edit Video • Trình chỉnh sửa video'); self.resize(1200,850)
        root=QWidget(); self.setCentralWidget(root); layout=QVBoxLayout(root); layout.setContentsMargins(20,16,20,16)
        top=QHBoxLayout(); title=QLabel('EDIT VIDEO'); title.setStyleSheet('font-size:24px;font-weight:700;color:#58d9b1')
        self.open_button=QPushButton('＋ Chọn video'); self.source_label=QLabel('Chưa chọn video'); self.source_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        top.addWidget(title); top.addStretch(); top.addWidget(self.open_button); layout.addLayout(top); layout.addWidget(self.source_label)
        split=QSplitter(); left=QWidget(); center=QVBoxLayout(left); center.setContentsMargins(0,0,12,0)
        self.info=QLabel('Chỉnh video • Tạo ảnh bìa • Xuất tại máy'); center.addWidget(self.info)
        self.canvas=PreviewCanvas(); center.addWidget(self.canvas,1)
        tools=QHBoxLayout(); self.mode=QComboBox()
        for label,key in [('Xem kết quả video','result'),('Chọn vùng crop','crop'),('Chọn vùng làm mờ','blur'),('Đặt logo','logo'),('Đặt chữ watermark','watermark'),('Ảnh bìa / đặt chữ','cover')]: self.mode.addItem(label,key)
        tools.addWidget(self.mode); self.time_label=QLabel('00:00.000'); tools.addStretch(); tools.addWidget(self.time_label); center.addLayout(tools)
        self.timeline=QSlider(Qt.Horizontal); self.timeline.setRange(0,1000); center.addWidget(self.timeline)
        hint=QLabel('Kéo thanh thời gian để xem khung hình. Chọn chế độ rồi kéo vùng hoặc nhấn vị trí trên ảnh.'); hint.setWordWrap(True); center.addWidget(hint)
        self.controls=EditorControls(); scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setWidget(self.controls); scroll.setMinimumWidth(310)
        split.addWidget(left); split.addWidget(scroll); split.setSizes([800,340]); layout.addWidget(split,1)
        group=QGroupBox('Xuất thành phẩm'); box=QVBoxLayout(group); row=QHBoxLayout()
        self.output_dir=QLineEdit(); self.output_dir.setPlaceholderText('Chọn thư mục xuất'); self.folder_button=QPushButton('Thư mục…')
        self.output_name=QLineEdit(); self.output_name.setPlaceholderText('Tên video.mp4')
        row.addWidget(self.output_dir,2); row.addWidget(self.folder_button); row.addWidget(self.output_name,1); box.addLayout(row)
        actions=QHBoxLayout(); self.progress=QProgressBar(); self.progress.setRange(0,100)
        self.format=QComboBox(); self.format.addItems(['PNG','JPG']); self.cover_button=QPushButton('Xuất ảnh bìa'); self.export_button=QPushButton('Xuất video MP4'); self.cancel_button=QPushButton('Hủy'); self.cancel_button.setEnabled(False)
        actions.addWidget(self.progress,1); actions.addWidget(self.format); actions.addWidget(self.cover_button); actions.addWidget(self.export_button); actions.addWidget(self.cancel_button); box.addLayout(actions)
        layout.addWidget(group)
        self.status=QLabel('Sẵn sàng'); self.status.setWordWrap(True); self.status.setTextInteractionFlags(Qt.TextSelectableByMouse); layout.addWidget(self.status)
        self.log=QPlainTextEdit(); self.log.setReadOnly(True); self.log.setMaximumHeight(80); self.log.hide(); layout.addWidget(self.log)
        self.setStyleSheet('QMainWindow,QWidget{background:#18222d;color:#e4edf5;font-size:13px;} QLineEdit,QPlainTextEdit,QComboBox,QDoubleSpinBox{background:#101820;border:1px solid #344658;border-radius:4px;padding:5px;} QPushButton{background:#2b4051;border:1px solid #435e70;border-radius:5px;padding:8px 12px;} QPushButton:hover{background:#375369;} QPushButton:disabled{color:#657584;} QGroupBox{border:1px solid #344658;border-radius:6px;margin-top:12px;padding-top:12px;} QGroupBox::title{subcontrol-origin:margin;left:10px;} QProgressBar{border:1px solid #344658;text-align:center;} QProgressBar::chunk{background:#259d7b;}')
    def closeEvent(self,event):
        if self.controller: self.controller.close()
        event.accept()
