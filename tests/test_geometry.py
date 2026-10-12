import pytest
from app.models import Rect
from app.geometry import canvas_to_pixel, preset_crop

def test_letterbox_mapping():
    box=Rect(20,30,200,100)
    assert canvas_to_pixel(120,80,box,(400,200)) == (200,100)
    assert canvas_to_pixel(10,80,box,(400,200)) is None
    assert canvas_to_pixel(220,130,box,(400,200)) is None

@pytest.mark.parametrize('ratio',[(9,16),(16,9),(1,1)])
def test_presets(ratio):
    r=preset_crop(320,240,ratio)
    assert r.width%2==r.height%2==0
    assert r.width*ratio[1]==r.height*ratio[0]
    assert 0<=r.x<=320-r.width and 0<=r.y<=240-r.height

def test_tiny_preset_rejected():
    with pytest.raises(ValueError):
        preset_crop(2,2,(9,16))


@pytest.mark.parametrize('handle,dx,dy,expected',[
 ('nw',-10,-10,Rect(10,10,110,90)),('n',0,-10,Rect(20,10,100,90)),
 ('ne',10,-10,Rect(20,10,110,90)),('e',10,0,Rect(20,20,110,80)),
 ('se',10,10,Rect(20,20,110,90)),('s',0,10,Rect(20,20,100,90)),
 ('sw',-10,10,Rect(10,20,110,90)),('w',-10,0,Rect(10,20,110,80))])
def test_resize_each_handle(handle,dx,dy,expected):
    from app.geometry import resize_region
    assert resize_region(Rect(20,20,100,80),handle,dx,dy,(320,240))==expected


def test_handle_resize_and_move_clamp_bounds_and_even_crop():
    from app.geometry import resize_region,move_region
    original=Rect(20,20,100,80)
    assert resize_region(original,'nw',-100,-100,(320,240),True)==Rect(0,0,120,100)
    assert resize_region(original,'se',999,999,(320,240),True)==Rect(20,20,300,220)
    crossed=resize_region(original,'nw',999,999,(320,240),True)
    assert crossed.width>=2 and crossed.height>=2 and crossed.x%2==crossed.y%2==0
    assert move_region(original,999,999,(320,240),True)==Rect(220,160,100,80)
