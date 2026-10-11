from pathlib import Path
import subprocess
import pytest
from PIL import Image, ImageDraw


def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, capture_output=True, **kwargs)


@pytest.fixture(scope='session')
def font():
    paths=[Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('C:/Windows/Fonts/arial.ttf')]
    found=next((p for p in paths if p.is_file()),None)
    if not found:
        pytest.fail('Required Unicode test font unavailable')
    return found


@pytest.fixture(scope='session')
def clips(tmp_path_factory):
    root=tmp_path_factory.mktemp('media')
    image=Image.new('RGB',(320,240))
    d=ImageDraw.Draw(image)
    for bounds,color in [((0,0,159,119),'red'),((160,0,319,119),'green'),((0,120,159,239),'blue'),((160,120,319,239),'yellow')]:
        d.rectangle(bounds, fill=color)
    # Checkerboard gives a measurable fixed blur region.
    for y in range(40,100,4):
        for x in range(40,100,4):
            d.rectangle((x,y,x+3,y+3),fill='white' if (x+y)//4%2 else 'black')
    image.save(root/'frame.png')
    source=root/'đầu video\' : clip.mp4'
    run('ffmpeg','-v','error','-y','-loop','1','-i',root/'frame.png','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','4','-r','30','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac',source)
    silent=root/'silent.mp4'
    run('ffmpeg','-v','error','-y','-i',source,'-an','-c:v','copy',silent)
    rotated=root/'rotated.mp4'
    run('ffmpeg','-v','error','-y','-display_rotation','90','-i',source,'-c','copy',rotated)
    sar=root/'sar.mp4'
    run('ffmpeg','-v','error','-y','-i',silent,'-vf','setsar=2','-c:v','libx264','-threads','2',sar)
    hdr=root/'hdr.mp4'
    run('ffmpeg','-v','error','-y','-i',silent,'-c:v','libx264','-threads','2','-x264-params','colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc',hdr)
    return dict(source=source,silent=silent,rotated=rotated,sar=sar,hdr=hdr)

@pytest.fixture(autouse=True)
def user_directories(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'user'))
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path/'user'))
