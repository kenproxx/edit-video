"""Measure actual exported samples, not FFmpeg command strings."""
from array import array
import math
from pathlib import Path
import subprocess
import pytest
from app.media import probe
from app.models import EditOptions,validate_options
from app.render import prepare_render


def run(*args):
    return subprocess.run([str(a) for a in args],check=True,capture_output=True)


@pytest.fixture
def soundtrack(tmp_path):
    path=tmp_path/'nhạc chèn.wav'
    run('ffmpeg','-v','error','-y','-f','lavfi','-i','sine=frequency=880:sample_rate=44100:duration=0.4',path)
    return path


def samples(path):
    result=run('ffmpeg','-v','error','-i',path,'-vn','-ac','1','-ar','48000','-f','f32le','pipe:1')
    values=array('f');values.frombytes(result.stdout)
    return values


def tone(values,frequency,start=.15,end=.35):
    segment=values[int(start*48000):int(end*48000)]
    assert len(segment)>100
    real=sum(v*math.cos(2*math.pi*frequency*i/48000) for i,v in enumerate(segment))
    imag=sum(v*math.sin(2*math.pi*frequency*i/48000) for i,v in enumerate(segment))
    return 2*math.hypot(real,imag)/len(segment)


def render(source,edit,tmp_path,preview=False):
    output=tmp_path/('preview.mp4' if preview else 'export.mp4')
    prepared=prepare_render(source,probe(source),edit,output,tmp_path/'assets',preview=preview)
    run(*prepared.args)
    return output


@pytest.mark.parametrize('field',['source_volume','added_volume'])
@pytest.mark.parametrize('value',[-.01,2.01,float('nan'),float('inf')])
def test_volume_validation(field,value):
    with pytest.raises(ValueError): validate_options(EditOptions(**{field:value}),320,240,4)


@pytest.mark.parametrize('gain',[0,.25,2])
def test_original_volume_changes_real_audio(clips,tmp_path,gain):
    output=render(clips['source'],EditOptions(source_volume=gain),tmp_path)
    assert probe(output).has_audio
    assert tone(samples(output),440)==pytest.approx(.125*gain,abs=.003)


@pytest.mark.parametrize('preview',[False,True])
def test_independent_mix_levels_after_trim_speed_and_with_image_input(clips,tmp_path,soundtrack,preview):
    from app.models import LogoOverlay
    from PIL import Image
    logo=tmp_path/'logo.png';Image.new('RGBA',(10,10),'white').save(logo)
    edit=EditOptions(source_volume=.5,added_volume=.25,audio_path=soundtrack,audio_loop=True,trim_start=1,trim_end=3,speed=2,logo=LogoOverlay(logo,0,0,10,1))
    output=render(clips['source'],edit,tmp_path,preview)
    values=samples(output)
    assert probe(output).duration==pytest.approx(1,abs=.07)
    assert tone(values,440,.6,.8)==pytest.approx(.0625,abs=.004)
    assert tone(values,880,.6,.8)==pytest.approx(.03125,abs=.004)


@pytest.mark.parametrize('loop',[False,True])
def test_insert_into_silent_video_loop_or_play_once(clips,tmp_path,soundtrack,loop):
    edit=EditOptions(audio_path=soundtrack,added_volume=.5,audio_loop=loop,trim_end=2)
    output=render(clips['silent'],edit,tmp_path)
    assert probe(output).has_audio and probe(output).duration==pytest.approx(2,abs=.07)
    values=samples(output)
    assert tone(values,880)==pytest.approx(.0625,abs=.003)
    assert tone(values,880,1.2,1.4)==pytest.approx(.0625 if loop else 0,abs=.003)


@pytest.mark.parametrize('preview',[False,True])
def test_mixed_delayed_original_preserves_alignment(tmp_path,soundtrack,preview):
    source=tmp_path/'delayed.mp4'
    run('ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:size=320x240:rate=30:duration=3','-itsoffset','1','-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=2','-c:v','libx264','-threads','2','-c:a','aac',source)
    edit=EditOptions(audio_path=soundtrack,source_volume=.5,added_volume=.25,audio_loop=True)
    values=samples(render(source,edit,tmp_path,preview))
    assert tone(values,440)==pytest.approx(0,abs=.003)
    assert tone(values,880)==pytest.approx(.03125,abs=.004)
    assert tone(values,440,1.3,1.5)==pytest.approx(.0625,abs=.004)
    assert tone(values,880,1.3,1.5)==pytest.approx(.03125,abs=.004)


def test_missing_inserted_audio_rejected(tmp_path):
    with pytest.raises(ValueError): validate_options(EditOptions(audio_path=tmp_path/'missing.wav'),320,240,4)


def test_inserted_audio_cannot_be_export_destination(clips,soundtrack,tmp_path):
    from app.worker import RenderWorker
    from app.output import reserve_output
    target=tmp_path/'audio-alias.mp4';target.hardlink_to(soundtrack)
    original=soundtrack.read_bytes();worker=RenderWorker()
    try:
        reservation=reserve_output(clips['silent'],target,True)
        with pytest.raises(ValueError,match='âm thanh'):
            worker.start(clips['silent'],probe(clips['silent']),EditOptions(audio_path=soundtrack),reservation)
        assert soundtrack.read_bytes()==original and target.read_bytes()==original
    finally:
        worker.cancel()
        if worker._thread is not None: worker._thread.join(timeout=10)


def test_non_audio_file_fails_without_replacing_destination(clips,tmp_path):
    from app.worker import RenderWorker
    from app.output import reserve_output
    target=tmp_path/'existing.mp4';target.write_bytes(b'old destination')
    worker=RenderWorker()
    worker.start(clips['source'],probe(clips['source']),EditOptions(audio_path=clips['silent']),reserve_output(clips['source'],target,True))
    worker._thread.join(timeout=15)
    assert not worker.running
    events=worker.poll()
    assert events[-1].kind=='error' and events[-1].message
    assert target.read_bytes()==b'old destination'
    assert not list(tmp_path.glob('.videoeditor-render-*'))


def test_stereo_insert_preserves_opposite_phase_channels_with_mono_source(clips,tmp_path):
    audio=tmp_path/'stereo.wav'
    run('ffmpeg','-v','error','-y','-f','lavfi','-i','aevalsrc=0.1*sin(2*PI*880*t)|-0.1*sin(2*PI*880*t):s=48000:d=0.4',audio)
    output=render(clips['source'],EditOptions(source_volume=0,audio_path=audio,added_volume=.5),tmp_path)
    metadata=run('ffprobe','-v','error','-show_streams','-of','json',output)
    import json
    stream=next(s for s in json.loads(metadata.stdout)['streams'] if s['codec_type']=='audio')
    assert stream['channels']==2
    data=run('ffmpeg','-v','error','-i',output,'-vn','-ar','48000','-f','f32le','pipe:1').stdout
    values=array('f');values.frombytes(data)
    left,right=values[::2],values[1::2]
    assert tone(left,880,1.2,1.4)==pytest.approx(.05,abs=.004)
    assert tone(right,880,1.2,1.4)==pytest.approx(.05,abs=.004)
    assert max(abs(a+b) for a,b in zip(left[57600:67200],right[57600:67200]))<.002
