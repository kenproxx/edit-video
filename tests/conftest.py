import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import subprocess
import pytest

@pytest.fixture(scope='session')
def binaries():
    from edit_video.binaries import resolve_binaries
    return resolve_binaries()

@pytest.fixture
def make_video(tmp_path, binaries):
    def make(name='nguồn & thử.mp4', audio=True, vf=None):
        path = tmp_path / name
        cmd = [str(binaries.ffmpeg), '-v','error','-y','-f','lavfi','-i','testsrc2=size=160x120:rate=20:duration=1']
        if audio: cmd += ['-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=1']
        if vf: cmd += ['-vf',vf]
        cmd += ['-c:v','libx264','-pix_fmt','yuv420p','-threads','1']
        if audio: cmd += ['-c:a','aac']
        subprocess.run(cmd + [str(path)],check=True,capture_output=True)
        return path
    return make

@pytest.fixture
def sample_video(make_video): return make_video()

@pytest.fixture
def silent_video(make_video): return make_video('silent.mp4',False)

@pytest.fixture
def rotated_video(make_video,tmp_path,binaries):
    source = make_video()
    out = tmp_path/'rotated.mp4'
    subprocess.run([str(binaries.ffmpeg),'-v','error','-display_rotation','90','-i',str(source),'-c','copy',str(out)],check=True)
    return out

@pytest.fixture
def odd_sar_video(make_video): return make_video('sar.mp4',False,'setsar=2')
