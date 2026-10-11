from array import array
from dataclasses import replace
from pathlib import Path
import subprocess
from PIL import Image, ImageChops, ImageStat
import pytest
from app.models import EditOptions, Rect, TextOverlay, LogoOverlay
from app.media import probe, extract_source_frame
from app.render import prepare_render, render_preview


def export(source,options,tmp_path):
    out=tmp_path/'kết quả \' : video.mp4'
    workspace=tmp_path/'assets'
    workspace.mkdir(exist_ok=True)
    command=prepare_render(source,probe(source),options,out,workspace)
    result=subprocess.run(command.args,capture_output=True)
    assert result.returncode==0,result.stderr.decode(errors='replace')
    return out


def image_at(path,time,tmp_path,name='frame.png'):
    with Image.open(extract_source_frame(path,time,tmp_path/name)) as im:
        return im.convert('RGB')


@pytest.mark.parametrize('speed',[.25,1,4])
def test_speed_duration_and_pitch(clips,tmp_path,speed):
    out=export(clips['source'],EditOptions(speed=speed),tmp_path)
    assert probe(out).duration==pytest.approx(4/speed,abs=.07)
    raw=subprocess.run(['ffmpeg','-v','error','-i',str(out),'-vn','-ac','1','-ar','48000','-f','f32le','pipe:1'],capture_output=True,check=True).stdout
    samples=array('f'); samples.frombytes(raw)
    assert len(samples)/48000==pytest.approx(4/speed,abs=.1)
    middle=samples[24000:48000]
    crossings=sum(a<=0<b for a,b in zip(middle,middle[1:]))
    assert crossings/.5==pytest.approx(440,rel=.02)


@pytest.mark.parametrize('horizontal,vertical,expected',[(True,False,(0,128,0)),(False,True,(0,0,255)),(True,True,(255,255,0))])
def test_flip_crop_pixels(clips,tmp_path,horizontal,vertical,expected):
    options=EditOptions(flip_horizontal=horizontal,flip_vertical=vertical,crop=Rect(0,0,160,120))
    out=export(clips['silent'],options,tmp_path)
    assert (probe(out).width,probe(out).height)==(160,120)
    frame=image_at(out,.5,tmp_path)
    assert max(abs(a-b) for a,b in zip(frame.getpixel((10,10)),expected))<25
    assert not probe(out).has_audio


def test_blur_locality(clips,tmp_path):
    original=image_at(clips['source'],.5,tmp_path,'original.png')
    frame=image_at(export(clips['source'],EditOptions(blur=Rect(40,40,60,60),blur_strength=10),tmp_path),.5,tmp_path)
    area=(50,50,90,90)
    assert ImageStat.Stat(frame.crop(area)).var[0]<ImageStat.Stat(original.crop(area)).var[0]*.2
    assert sum(ImageStat.Stat(ImageChops.difference(frame.crop((200,150,300,220)),original.crop((200,150,300,220)))).mean)<12


def test_intro_watermark_logo_and_preview(clips,tmp_path,font):
    logo=tmp_path/'logo.png'
    Image.new('RGBA',(20,20),(255,255,255,128)).save(logo)
    intro=TextOverlay("Tiếng Việt\n' : %",font,18,'white','black',1,10,130,1)
    watermark=replace(intro,text='wm',x=200,y=10,size=16)
    options=EditOptions(intro=intro,watermark=watermark,logo=LogoOverlay(logo,250,170,20,1))
    out=export(clips['source'],options,tmp_path)
    early=image_at(out,.5,tmp_path,'early.png')
    late=image_at(out,1.5,tmp_path,'late.png')
    original=image_at(clips['source'],.5,tmp_path,'base.png')
    assert sum(ImageStat.Stat(ImageChops.difference(early.crop((0,120,180,200)),original.crop((0,120,180,200)))).mean)>2
    assert sum(ImageStat.Stat(ImageChops.difference(late.crop((0,120,180,200)),original.crop((0,120,180,200)))).mean)<4
    for frame in (early,late):
        assert sum(ImageStat.Stat(ImageChops.difference(frame.crop((190,0,250,40)),original.crop((190,0,250,40)))).mean)>2
        r,g,b=frame.getpixel((260,180))
        assert r>220 and g>220 and 90<b<180  # half white on yellow
    preview=render_preview(clips['source'],probe(clips['source']),options,.5,tmp_path/'preview.png')
    with Image.open(preview) as im:
        assert sum(ImageStat.Stat(ImageChops.difference(im.convert('RGB'),early)).mean)<15


def test_rotated_preview_and_render(clips,tmp_path):
    out=export(clips['rotated'],EditOptions(),tmp_path)
    assert (probe(out).width,probe(out).height)==(240,320)
    original=image_at(clips['rotated'],.5,tmp_path,'original.png')
    rendered=image_at(out,.5,tmp_path)
    assert sum(ImageStat.Stat(ImageChops.difference(original,rendered)).mean)<12
