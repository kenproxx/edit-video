from dataclasses import replace
import threading
import pytest
from edit_video.jobs import run_export, Cancelled, PreviewCoordinator
from edit_video.pipeline import RenderRequest
from edit_video.models import EditSettings
from edit_video.media import probe

def request(source,binaries,path,mode='video'):
    return RenderRequest(probe(source,binaries),EditSettings(),path,mode)

def test_failed_export_preserves_destination(sample_video,binaries,tmp_path,qapp):
    out=tmp_path/'out.mp4'; out.write_bytes(b'old')
    req=request(sample_video,binaries,out)
    req=replace(req,media=replace(req.media,path=tmp_path/'missing.mp4'))
    with pytest.raises(Exception): run_export(req,binaries,True,threading.Event(),lambda _:None)
    assert out.read_bytes()==b'old'
    assert not list(tmp_path.glob('.edit-video-*'))

def test_cancel_cleans_partial(sample_video,binaries,tmp_path,qapp):
    event=threading.Event(); event.set(); out=tmp_path/'out.mp4'; out.write_bytes(b'old')
    with pytest.raises(Cancelled): run_export(request(sample_video,binaries,out),binaries,True,event,lambda _:None)
    assert out.read_bytes()==b'old'
    assert not list(tmp_path.glob('.edit-video-*'))

def test_progress_finishes_after_publish(sample_video,binaries,tmp_path,qapp):
    out=tmp_path/'out.mp4'; progress=[]
    def update(value):
        progress.append(value)
        if value==1: assert out.is_file()
    run_export(request(sample_video,binaries,out),binaries,False,threading.Event(),update)
    assert progress[-1]==1
    assert probe(out,binaries).width==160

def test_newest_preview_wins(sample_video,binaries,tmp_path,qtbot):
    coordinator=PreviewCoordinator(binaries); ready=[]
    coordinator.ready.connect(lambda gen,path: ready.append(gen))
    for i in range(4): last=coordinator.submit(request(sample_video,binaries,tmp_path/f'p{i}.png','preview'))
    qtbot.waitUntil(lambda:last in ready,timeout=15000)
    assert ready==[last]
    coordinator.close()

def test_close_terminates_children(sample_video,binaries,tmp_path,qapp):
    coordinator=PreviewCoordinator(binaries)
    coordinator.submit(request(sample_video,binaries,tmp_path/'p.png','preview'))
    coordinator.close()
    assert coordinator.closed
    assert all(f.done() for f in coordinator.futures)
