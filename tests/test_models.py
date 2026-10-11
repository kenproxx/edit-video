from dataclasses import replace
from pathlib import Path
import pytest
from app.models import Rect, EditOptions, TextOverlay, LogoOverlay, validate_options, default_output

@pytest.mark.parametrize('speed', [.25, 1, 4])
def test_speed_endpoints(speed):
    validate_options(EditOptions(speed=speed), 320, 240, 8)

@pytest.mark.parametrize('speed', [0, .24, 4.01, float('nan'), float('inf')])
def test_invalid_speed(speed):
    with pytest.raises(ValueError):
        validate_options(EditOptions(speed=speed), 320, 240, 8)

@pytest.mark.parametrize('rect', [Rect(-1,0,100,100), Rect(0,0,0,100), Rect(0,0,321,240), Rect(0,0,101,100)])
def test_invalid_crop(rect):
    with pytest.raises(ValueError):
        validate_options(EditOptions(crop=rect), 320, 240, 8)

def test_blur_coordinates_use_crop():
    with pytest.raises(ValueError):
        validate_options(EditOptions(crop=Rect(0,0,100,100), blur=Rect(90,0,20,20)), 320,240,8)

def test_intro_duration_and_assets(tmp_path):
    text = TextOverlay('Tiếng Việt', tmp_path/'absent.ttf', 20, 'white', 'black', 1, 0, 0, 1)
    with pytest.raises(ValueError):
        validate_options(EditOptions(intro=text),320,240,8)
    font = Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')
    if not font.exists():
        pytest.fail('Install font fixture prerequisite')
    text = replace(text,font=font)
    validate_options(EditOptions(intro=text),320,240,8)
    with pytest.raises(ValueError):
        validate_options(EditOptions(speed=4,intro=text,intro_duration=3),320,240,8)
    validate_options(EditOptions(intro=replace(text,text='',font=tmp_path/'missing')),320,240,8)
    with pytest.raises(ValueError):
        validate_options(EditOptions(logo=LogoOverlay(tmp_path/'bad.png',0,0,50,1)),320,240,8)

def test_output_default(tmp_path):
    assert default_output(Path('đầu.mov'),tmp_path)==tmp_path/'đầu.mp4'
