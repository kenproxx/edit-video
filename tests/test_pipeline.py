import subprocess
from dataclasses import replace
from PIL import Image, ImageChops, ImageStat
import pytest
from edit_video.media import probe
from edit_video.models import EditSettings, Rect, TextLayer, BlurLayer, LogoLayer
from edit_video.pipeline import RenderRequest, build_command

@pytest.fixture
def render(tmp_path,binaries,qapp):
    count=0
    def run(source,settings=EditSettings(),mode='video',ext=None,time=0):
        nonlocal count
        count+=1
        out=tmp_path/f'out{count}.{ext or ("mp4" if mode=="video" else "png")}'
        req=RenderRequest(probe(source,binaries),settings,out,mode,time)
        cmd=build_command(req,binaries,tmp_path/f'assets{count}')
        p=subprocess.run(cmd,capture_output=True,timeout=30)
        assert p.returncode==0,p.stderr.decode(errors='replace')
        return out
    return run

@pytest.mark.parametrize('speed',[.25,1,4])
def test_speed_duration_and_audio(sample_video,binaries,render,speed):
    out=render(sample_video,EditSettings(speed=speed)); info=probe(out,binaries)
    assert info.duration==pytest.approx(1/speed,abs=.08)
    assert info.audio_index is not None
    raw=subprocess.check_output([str(binaries.ffmpeg),'-v','error','-i',str(out),'-vn','-f','s16le','-ar','48000','-ac','1','-'])
    assert len(raw)/96000==pytest.approx(1/speed,abs=.12)

def test_crop_flip_corners(sample_video,render):
    original=Image.open(render(sample_video,mode='preview')).convert('RGB')
    out=Image.open(render(sample_video,EditSettings(flip_h=True,flip_v=True),mode='preview')).convert('RGB')
    expected=original.transpose(Image.Transpose.ROTATE_180)
    assert max(ImageStat.Stat(ImageChops.difference(out,expected)).mean)<2
    cropped=Image.open(render(sample_video,EditSettings(crop=Rect(0,0,.5,.5)),mode='preview'))
    assert cropped.size==(80,60)

def test_blur_locality(sample_video,render):
    original=Image.open(render(sample_video,mode='preview')).convert('RGB')
    blurred=Image.open(render(sample_video,EditSettings(blur=BlurLayer(Rect(0,0,.5,.5),12)),mode='preview')).convert('RGB')
    assert sum(ImageStat.Stat(blurred.crop((0,0,80,60))).var)<sum(ImageStat.Stat(original.crop((0,0,80,60))).var)
    assert max(ImageStat.Stat(ImageChops.difference(original.crop((100,80,160,120)),blurred.crop((100,80,160,120)))).mean)<2

def test_combined_overlays_and_cover(sample_video,render,tmp_path,binaries):
    logo=tmp_path/'logo.png'; Image.new('RGBA',(20,10),(255,0,0,128)).save(logo)
    settings=EditSettings(speed=2,flip_h=True,crop=Rect(0,0,.9,.9),blur=BlurLayer(Rect(0,0,.5,.5)),logo=LogoLayer(logo),watermark=TextLayer(text='Việt',size_px=14),cover=TextLayer(text='BÌA',size_px=30,y=.5))
    assert probe(render(sample_video,settings),binaries).width==144
    preview=Image.open(render(sample_video,settings,'preview')).convert('RGB')
    cover=Image.open(render(sample_video,settings,'thumbnail')).convert('RGB')
    assert ImageChops.difference(preview,cover).getbbox() is not None
    assert Image.open(render(sample_video,settings,'thumbnail','jpg')).size==cover.size

def test_silent_export(silent_video,render,binaries):
    assert probe(render(silent_video),binaries).audio_index is None

def test_rotation_sar_odd_output(rotated_video,odd_sar_video,render,binaries):
    for source,expected in [(rotated_video,(120,160)),(odd_sar_video,(320,120))]:
        out=probe(render(source),binaries)
        assert (out.width,out.height)==expected
        assert out.rotation==0
        assert Image.open(render(source,mode='preview')).size==expected
