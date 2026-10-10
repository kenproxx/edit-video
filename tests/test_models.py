import pytest
from edit_video.models import EditSettings, Rect, TextLayer, BlurLayer, validate, crop_pixels

@pytest.mark.parametrize('speed', [0.25, 1, 4])
def test_speed_bounds(speed):
    validate(EditSettings(speed=speed))

@pytest.mark.parametrize('speed', [0, 4.01, float('nan')])
def test_invalid_speed(speed):
    with pytest.raises(ValueError): validate(EditSettings(speed=speed))

@pytest.mark.parametrize('rect', [Rect(-.1,0,1,1), Rect(0,0,0,1), Rect(.5,0,1,1)])
def test_rect_bounds(rect):
    with pytest.raises(ValueError): validate(EditSettings(crop=rect))

def test_even_crop():
    assert crop_pixels(None,641,481) == (0,0,640,480)
    with pytest.raises(ValueError): crop_pixels(Rect(0,0,.001,.001),640,480)

def test_invalid_layers():
    with pytest.raises(ValueError): validate(EditSettings(watermark=TextLayer(opacity=2)))
    with pytest.raises(ValueError): validate(EditSettings(blur=BlurLayer(Rect(0,0,1,1),0)))
