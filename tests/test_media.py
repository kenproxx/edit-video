import pytest
from edit_video.media import probe, MediaError

def test_probe_unicode_and_shell_chars(sample_video,binaries):
    info = probe(sample_video,binaries)
    assert (info.width,info.height)==(160,120)
    assert info.duration == pytest.approx(1, abs=.1)
    assert info.audio_index is not None

def test_probe_rotation_sar(rotated_video,odd_sar_video,binaries):
    info = probe(rotated_video,binaries)
    assert (info.width,info.height)==(120,160)
    assert probe(odd_sar_video,binaries).width == 320

def test_probe_silent(silent_video,binaries):
    assert probe(silent_video,binaries).audio_index is None

def test_invalid_media(tmp_path,binaries):
    path=tmp_path/'bad.mp4'; path.write_text('bad')
    with pytest.raises(MediaError): probe(path,binaries)
