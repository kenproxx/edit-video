from dataclasses import replace
from pathlib import Path
import subprocess
import pytest
from PIL import Image,ImageChops,ImageStat
from app.models import EditOptions,LogoOverlay,validate_options
from app.media import probe,extract_source_frame
from app.render import prepare_render,render_preview


def options(**values):
    assert 'trim_start' in EditOptions.__dataclass_fields__, 'Source interval model missing'
    return EditOptions(**values)


@pytest.mark.parametrize('text,seconds',[('2:30',150),('01:02:03.5',3723.5),('2.5',150),('0:00.25',.25),('2,5',150)])
def test_source_time_format(text,seconds):
    from app import timing
    assert timing.parse_time(text)==pytest.approx(seconds)


@pytest.mark.parametrize('start,end',[(-1,2),(2,2),(3,2),(float('nan'),3),(0,float('inf'))])
def test_invalid_source_interval_rejected(start,end):
    with pytest.raises(ValueError): validate_options(options(trim_start=start,trim_end=end),320,240,4)


def test_intro_uses_trimmed_duration(font):
    from app.models import TextOverlay
    intro=TextOverlay('intro',font,12,'white','black',1,0,0,1)
    with pytest.raises(ValueError): validate_options(options(trim_start=2,trim_end=3,speed=2,intro=intro,intro_duration=1),320,240,4)


@pytest.mark.parametrize('speed',[.5,2])
def test_trim_export_duration_audio_and_preview(tmp_path,speed):
    source=tmp_path/'moving.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','testsrc2=size=320x240:rate=30:duration=4','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=4','-c:v','libx264','-threads','2','-pix_fmt','yuv420p','-c:a','aac',str(source)],check=True)
    edit=options(trim_start=1,trim_end=3,speed=speed)
    output=tmp_path/'out.mp4';prepared=prepare_render(source,probe(source),edit,output,tmp_path/'workspace')
    assert prepared.duration==pytest.approx(2/speed)
    subprocess.run(prepared.args,check=True,capture_output=True)
    info=probe(output)
    assert info.duration==pytest.approx(2/speed,abs=.07) and info.has_audio
    preview=tmp_path/'preview.png';render_preview(source,probe(source),edit,.4,preview)
    extracted=extract_source_frame(output,.4,tmp_path/'exported.png')
    with Image.open(preview) as a,Image.open(extracted) as b:
        assert sum(ImageStat.Stat(ImageChops.difference(a.convert('RGB'),b.convert('RGB'))).mean)<12
    with pytest.raises(ValueError): render_preview(source,probe(source),edit,2/speed,tmp_path/'eof.png')


@pytest.mark.parametrize('start,end,expected_offset',[(.5,2.5,.5),(2,3,0),(0,.5,None)])
def test_trim_delayed_audio_alignment(tmp_path,start,end,expected_offset):
    source=tmp_path/'delayed.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:size=320x240:rate=30:duration=4','-itsoffset','1','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=3','-c:v','libx264','-threads','2','-c:a','aac',str(source)],check=True)
    edit=options(trim_start=start,trim_end=end)
    output=tmp_path/'trimmed.mp4';prepared=prepare_render(source,probe(source),edit,output,tmp_path/'assets')
    subprocess.run(prepared.args,check=True,capture_output=True)
    info=probe(output)
    assert info.duration==pytest.approx(end-start,abs=.07)
    if expected_offset is None: assert not info.has_audio
    else:
        assert info.has_audio
        assert info.audio_offset==pytest.approx(expected_offset,abs=.06)


def test_logo_height_can_stretch_without_changing_legacy_aspect(tmp_path):
    from app.overlays import write_logo
    path=tmp_path/'logo.png';Image.new('RGBA',(20,10),'white').save(path)
    assert 'height' in LogoOverlay.__dataclass_fields__, 'Independent logo height missing'
    legacy=LogoOverlay(path,0,0,40,1)
    stretched=replace(legacy,height=30)
    validate_options(EditOptions(logo=stretched),320,240,4)
    write_logo(stretched,tmp_path/'stretched.png');write_logo(legacy,tmp_path/'legacy.png')
    with Image.open(tmp_path/'stretched.png') as a,Image.open(tmp_path/'legacy.png') as b: assert a.size==(40,30) and b.size==(40,20)


def test_trim_early_audio_selects_correct_content(tmp_path):
    from array import array
    source=tmp_path/'early.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-itsoffset','1','-f','lavfi','-i','color=blue:size=320x240:rate=30:duration=3','-f','lavfi','-i',r'aevalsrc=if(lt(t\,1)\,sin(2*PI*440*t)\,sin(2*PI*880*t)):s=48000:d=4','-c:v','libx264','-threads','2','-fps_mode','passthrough','-c:a','aac',str(source)],check=True)
    info=probe(source)
    assert info.audio_offset==pytest.approx(-1,abs=.06)
    output=tmp_path/'trim.mp4'
    prepared=prepare_render(source,info,options(trim_start=.5,trim_end=1.5),output,tmp_path/'assets')
    subprocess.run(prepared.args,check=True,capture_output=True)
    raw=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-vn','-ac','1','-ar','48000','-f','f32le','pipe:1'],capture_output=True,check=True).stdout
    samples=array('f');samples.frombytes(raw);middle=samples[10000:34000]
    crossings=sum(a<=0<b for a,b in zip(middle,middle[1:]))
    assert crossings/.5==pytest.approx(880,rel=.03)

@pytest.mark.parametrize('duration',[4.066667,59.999999,60.000001])
def test_formatted_endpoint_never_exceeds_source(duration):
    from app.timing import format_time,parse_time
    assert 0<=duration-parse_time(format_time(duration))<.0011


@pytest.mark.parametrize('duration,start,end,expected',[(4,1,6,(0,4)),(8,1,6,(1,6)),(6,1,6,(1,6)),(4,5,6,(0,4)),(4,5,None,(0,4))])
def test_short_source_kept_whole_when_requested_cut_does_not_fit(duration,start,end,expected):
    from app.timing import source_interval,trimmed_duration
    edit=EditOptions(trim_start=start,trim_end=end,speed=2)
    validate_options(edit,320,240,duration)
    assert source_interval(edit,duration)==expected
    assert trimmed_duration(edit,duration)==(expected[1]-expected[0])/2


@pytest.mark.parametrize('preview',[False,True])
def test_short_source_fallback_keeps_full_video_audio_and_first_frame(clips,tmp_path,preview):
    from array import array
    edit=EditOptions(trim_start=2,trim_end=6,speed=2)
    output=tmp_path/'fallback.mp4';info=probe(clips['source'])
    prepared=prepare_render(clips['source'],info,edit,output,tmp_path/'assets',preview=preview)
    subprocess.run(prepared.args,check=True,capture_output=True)
    assert probe(output).duration==pytest.approx(2,abs=.07) and probe(output).has_audio
    frame=tmp_path/'fallback.png';render_preview(clips['source'],info,edit,0,frame)
    with Image.open(frame) as image: assert image.getpixel((10,10))[0]>200
    raw=subprocess.run(['ffmpeg','-v','error','-i',str(output),'-vn','-ac','1','-ar','48000','-f','f32le','pipe:1'],capture_output=True,check=True).stdout
    values=array('f');values.frombytes(raw)
    assert len(values)>=int(1.9*48000) and max(abs(v) for v in values[48000:60000])>.05
