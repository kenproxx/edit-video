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
