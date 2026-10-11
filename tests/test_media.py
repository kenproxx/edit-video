import json
from pathlib import Path
import pytest
from PIL import Image
from app.media import probe, extract_source_frame, _parse_info
from app.resources import binary_path, user_data_dir


def test_probe_real_media(clips):
    info=probe(clips['source'])
    assert (info.width,info.height)==(320,240)
    assert info.duration==pytest.approx(4,abs=.1)
    assert info.fps==30 and info.has_audio
    assert not probe(clips['silent']).has_audio


def test_rotation_and_sar(clips,tmp_path):
    rotated=probe(clips['rotated'])
    assert (rotated.width,rotated.height)==(240,320)
    assert rotated.rotation in (-90,90,270)
    path=extract_source_frame(clips['rotated'],.5,tmp_path/'r.png')
    with Image.open(path) as image:
        assert image.size==(240,320)
        # rotation 90 metadata is displayed counterclockwise: source right-top green -> left-top.
        r,g,b=image.getpixel((15,15))[:3]
        assert g>r and g>b
    sar=probe(clips['sar'])
    assert (sar.width,sar.height)==(640,240)
    with Image.open(extract_source_frame(clips['sar'],0,tmp_path/'s.png')) as im:
        assert im.size==(640,240)


def test_hdr_and_bad_file(clips,tmp_path):
    with pytest.raises(ValueError,match='HDR'):
        probe(clips['hdr'])
    path=tmp_path/'bad.mp4'
    path.write_text('invalid')
    with pytest.raises(ValueError):
        probe(path)


def test_fps_fallback_and_nonfinite_metadata():
    data={'streams':[{'codec_type':'video','width':320,'height':240,'avg_frame_rate':'0/0','r_frame_rate':'25/1','duration':'4'}], 'format':{'duration':'4'}}
    assert _parse_info(data).fps==25
    data['streams'][0]['r_frame_rate']='0/0'
    assert _parse_info(data).fps==30
    data['format']['duration']='nan'
    data['streams'][0]['duration']='nan'
    with pytest.raises(ValueError):
        _parse_info(data)


def test_resources(tmp_path,monkeypatch):
    assert binary_path('ffmpeg').is_file()
    monkeypatch.setenv('LOCALAPPDATA',str(tmp_path))
    assert user_data_dir().is_dir()


def test_negative_frame_time(clips,tmp_path):
    with pytest.raises(ValueError):
        extract_source_frame(clips['source'],-1,tmp_path/'no.png')


def test_combined_rotation_and_sar(clips,tmp_path):
    import subprocess
    path=tmp_path/'rotated-sar.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-display_rotation','90','-i',str(clips['sar']),'-c','copy',str(path)],check=True)
    info=probe(path)
    assert (info.width,info.height)==(240,640)
    with Image.open(extract_source_frame(path,.5,tmp_path/'combined.png')) as image:
        assert image.size==(240,640)
        r,g,b=image.getpixel((15,15))[:3]
        assert g>r and g>b


def test_no_stale_source_frame_at_eof(tmp_path):
    import subprocess
    source=tmp_path/'short.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=blue:size=320x240:rate=30:duration=1','-c:v','libx264','-threads','2',str(source)],check=True)
    destination=tmp_path/'frame.png'
    Image.new('RGB',(5,5),'red').save(destination)
    old=destination.read_bytes()
    with pytest.raises(ValueError):
        extract_source_frame(source,.99,destination)
    assert destination.read_bytes()==old
