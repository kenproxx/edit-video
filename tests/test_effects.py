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


def test_moving_preview_uses_output_time(tmp_path,font):
    source=tmp_path/'moving.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x240:rate=30:duration=4','-c:v','libx264','-threads','2',str(source)],check=True)
    options=EditOptions(speed=4,intro=TextOverlay('Đầu video',font,18,'white','black',1,10,10,1),intro_duration=.4)
    out=export(source,options,tmp_path)
    rendered=image_at(out,.6,tmp_path,'rendered.png')
    preview=render_preview(source,probe(source),options,.6,tmp_path/'preview.png')
    # CFR selects a source frame within one output-frame interval, not an exact
    # fractional source timestamp. Still prove mapping is near .6 * 4, not .6.
    candidates=[image_at(source,2.4+step/30,tmp_path,f'source-{step}.png') for step in (-2,-1,0,1,2)]
    with Image.open(preview) as frame:
        assert sum(ImageStat.Stat(ImageChops.difference(frame.convert('RGB'),rendered)).mean)<15
        assert min(sum(ImageStat.Stat(ImageChops.difference(frame.convert('RGB'),candidate)).mean) for candidate in candidates)<15


def test_odd_blur_region_does_not_shift(clips,tmp_path):
    options=EditOptions(blur=Rect(41,41,57,57),blur_strength=8)
    frame=image_at(export(clips['source'],options,tmp_path),.5,tmp_path)
    original=image_at(clips['source'],.5,tmp_path,'base.png')
    assert ImageStat.Stat(frame.crop((50,50,90,90))).var[0]<ImageStat.Stat(original.crop((50,50,90,90))).var[0]*.2


def test_intro_duration_boundary(clips,tmp_path,font):
    intro=TextOverlay('Đầu video',font,18,'white','black',1,10,130,1)
    options=EditOptions(intro=intro,intro_duration=1)
    out=export(clips['source'],options,tmp_path)
    boundary=image_at(out,1,tmp_path,'boundary.png')
    original=image_at(clips['source'],1,tmp_path,'original.png')
    assert sum(ImageStat.Stat(ImageChops.difference(boundary,original)).mean)<4


@pytest.mark.parametrize('speed',[1,4])
def test_delayed_audio_stays_synchronized(tmp_path,speed):
    import json
    source=tmp_path/'delayed.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:size=320x240:rate=30:duration=4','-itsoffset','1','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=3','-c:v','libx264','-threads','2','-c:a','aac',str(source)],check=True)
    out=export(source,EditOptions(speed=speed),tmp_path)
    metadata=json.loads(subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(out)],capture_output=True,check=True).stdout)
    audio=next(s for s in metadata['streams'] if s['codec_type']=='audio')
    assert float(audio['start_time'])==pytest.approx(1/speed,abs=.06)


def test_no_stale_preview_at_eof(tmp_path):
    source=tmp_path/'short.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:size=320x240:rate=30:duration=1','-c:v','libx264','-threads','2',str(source)],check=True)
    destination=tmp_path/'preview.png'
    Image.new('RGB',(5,5),'red').save(destination)
    old=destination.read_bytes()
    with pytest.raises(ValueError):
        render_preview(source,probe(source),EditOptions(),.99,destination)
    assert destination.read_bytes()==old
