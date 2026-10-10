from PySide6.QtGui import QImage, QColor
from edit_video.models import TextLayer, LogoLayer, EditSettings
from edit_video.overlays import text_overlay, logo_overlay, write_overlays

def test_vietnamese_multiline(qapp):
    img=text_overlay(TextLayer(text='Tiếng Việt\nẢnh bìa',size_px=28),(320,200))
    assert img.pixelColor(319,199).alpha()==0
    assert any(img.pixelColor(x,y).alpha()>0 for x in range(320) for y in range(15,50))
    assert any(img.pixelColor(x,y).alpha()>0 for x in range(320) for y in range(50,90))

def test_logo_alpha_and_aspect(qapp,tmp_path):
    path=tmp_path/'logo.png'; image=QImage(80,40,QImage.Format_ARGB32); image.fill(QColor('red')); image.save(str(path))
    img=logo_overlay(LogoLayer(path,x=0,y=0,width=.5,opacity=.5),(200,200))
    assert 120<=img.pixelColor(10,10).alpha()<=130
    assert img.pixelColor(99,49).alpha()>0
    assert img.pixelColor(101,51).alpha()==0

def test_cover_is_optional(qapp,tmp_path):
    s=EditSettings(cover=TextLayer(text='Bìa'))
    assert write_overlays(s,(320,200),tmp_path,False)==[]
    assert len(write_overlays(s,(320,200),tmp_path,True))==1

def test_oversized_overlay_bounds(qapp):
    img=text_overlay(TextLayer(text='Một dòng rất dài',size_px=500,x=1,y=1),(32,32))
    assert not img.isNull()
    assert any(img.pixelColor(x,y).alpha() for x in range(32) for y in range(32))
