from pathlib import Path
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QImage
from edit_video.ui.window import EditorWindow
from edit_video.ui.controller import EditorController
from edit_video.ui.preview import PreviewCanvas
from edit_video.media import probe


def setup(qtbot,binaries,sample_video):
    w=EditorWindow(); qtbot.addWidget(w); c=EditorController(w,binaries); w.controller=c
    w.show(); c.load_video(sample_video)
    qtbot.waitUntil(lambda:c.media is not None,timeout=10000)
    return w,c

def test_open_edit_export_flow(qtbot,binaries,sample_video,tmp_path):
    w,c=setup(qtbot,binaries,sample_video)
    assert w.output_name.text()==sample_video.stem+'.mp4'
    w.controls.speed.setValue(2)
    w.controls.watermark.enabled.setChecked(True); w.controls.watermark.text.setPlainText('Tiếng Việt')
    w.controls.cover.enabled.setChecked(True); w.controls.cover.text.setPlainText('Ảnh bìa')
    w.output_dir.setText(str(tmp_path)); w.output_name.setText('new.mp4')
    c.export('video'); qtbot.waitUntil(lambda:not c.busy,timeout=15000)
    assert probe(tmp_path/'new.mp4',binaries).duration<.7
    c.export('thumbnail'); qtbot.waitUntil(lambda:not c.busy,timeout=15000)
    assert (tmp_path/(sample_video.stem+'_thumbnail.png')).is_file()
    c.close()

def test_drag_ignores_letterbox(qtbot):
    canvas=PreviewCanvas(); qtbot.addWidget(canvas); canvas.resize(400,400)
    img=QImage(400,200,QImage.Format_RGB32); img.fill(Qt.red); canvas.set_frame(img); canvas.show()
    canvas.mode='blur'; values=[]; canvas.region_changed.connect(lambda *v:values.append(v))
    qtbot.mousePress(canvas,Qt.LeftButton,pos=QPoint(10,10)); qtbot.mouseRelease(canvas,Qt.LeftButton,pos=QPoint(100,200))
    assert not values
    qtbot.mousePress(canvas,Qt.LeftButton,pos=QPoint(40,120)); qtbot.mouseRelease(canvas,Qt.LeftButton,pos=QPoint(200,200))
    assert values
    rect=values[-1][1]
    assert abs(rect.x-.1)<.01 and abs(rect.y-.1)<.01

def test_crop_presets(qtbot,binaries,sample_video):
    w,c=setup(qtbot,binaries,sample_video)
    for name,ratio in [('9:16',9/16),('16:9',16/9),('1:1',1)]:
        w.controls.preset.setCurrentText(name)
        r=w.controls.settings().crop
        assert abs(r.width*c.media.width/(r.height*c.media.height)-ratio)<.02
    c.close()

def test_export_locks_settings(qtbot,binaries,sample_video,tmp_path):
    w,c=setup(qtbot,binaries,sample_video); w.output_dir.setText(str(tmp_path)); w.output_name.setText('new.mp4')
    c.export('video'); assert not w.controls.isEnabled()
    qtbot.waitUntil(lambda:not c.busy,timeout=15000); assert w.controls.isEnabled()
    c.close()

def test_close_cancels_job(qtbot,binaries,sample_video,tmp_path):
    w,c=setup(qtbot,binaries,sample_video); w.output_dir.setText(str(tmp_path)); w.output_name.setText('new.mp4')
    c.export('video'); c.close()
    assert c.cancel.is_set() and c.preview.closed

def test_error_is_visible(qtbot,binaries,tmp_path):
    w=EditorWindow(); qtbot.addWidget(w); c=EditorController(w,binaries); w.controller=c
    c.load_video(tmp_path/'missing.mp4')
    qtbot.waitUntil(lambda:'Không đọc được' in w.status.text(),timeout=10000)
    assert w.open_button.isEnabled(); c.close()
