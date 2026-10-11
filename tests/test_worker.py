import subprocess
import time
from pathlib import Path
import pytest
from app.models import EditOptions,Rect
from app.media import probe
from app.worker import RenderWorker, WorkerEvent
from app.output import reserve_output


def wait_done(worker,timeout=20):
    events=[]; end=time.monotonic()+timeout
    while time.monotonic()<end:
        events+=worker.poll()
        if not worker.running:
            events+=worker.poll()
            return events
        time.sleep(.01)
    worker.cancel()
    pytest.fail('Worker did not finish in time')


def test_real_export(clips,tmp_path):
    worker=RenderWorker()
    target=tmp_path/'out.mp4'
    worker.start(clips['source'],probe(clips['source']),EditOptions(),reserve_output(clips['source'],target,False))
    events=wait_done(worker)
    assert events[-1].kind=='completed'
    assert target.is_file() and probe(target).duration==pytest.approx(4,abs=.07)
    assert any(e.kind=='progress' for e in events)
    assert not list(tmp_path.glob('.videoeditor-*'))


def test_failure_preserves_destination(clips,tmp_path):
    source=tmp_path/'bad.mp4'; source.write_bytes(b'not a video')
    target=tmp_path/'out.mp4'; target.write_bytes(b'old')
    worker=RenderWorker()
    worker.start(source,probe(clips['source']),EditOptions(),reserve_output(source,target,True))
    events=wait_done(worker)
    assert events[-1].kind=='error' and events[-1].message
    assert target.read_bytes()==b'old'
    assert not list(tmp_path.glob('.videoeditor-*'))
    assert list((tmp_path/'user'/'VideoEditor'/'logs').glob('*.log'))


def test_cancel_live_process_and_single_job(clips,tmp_path):
    source=tmp_path/'long.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-stream_loop','-1','-i',str(clips['source']),'-t','120','-c','copy',str(source)],check=True)
    target=tmp_path/'out.mp4'; target.write_bytes(b'old')
    unrelated=tmp_path/'.videoeditor-unrelated'; unrelated.write_bytes(b'keep')
    worker=RenderWorker()
    info=probe(source)
    worker.start(source,info,EditOptions(speed=.25,blur=Rect(0,0,300,200)),reserve_output(source,target,True))
    with pytest.raises(RuntimeError):
        worker.start(source,info,EditOptions(),reserve_output(source,tmp_path/'second.mp4',False))
    end=time.monotonic()+10
    while worker._process is None and worker.running and time.monotonic()<end: time.sleep(.01)
    process=worker._process
    assert process is not None and process.poll() is None
    worker.cancel()
    events=wait_done(worker)
    assert events[-1].kind=='cancelled'
    assert process.poll() is not None
    assert target.read_bytes()==b'old'
    assert list(tmp_path.glob('.videoeditor-*'))==[unrelated]


def test_progress_is_coalesced():
    worker=RenderWorker()
    for i in range(10000): worker._emit(WorkerEvent('progress',i/10000))
    events=worker.poll()
    assert len(events)==1 and events[0].progress==.9999


def test_cleanup_error_always_finishes_worker(clips,tmp_path,monkeypatch):
    source=clips['source']; target=tmp_path/'out.mp4'
    worker=RenderWorker()
    original=Path.unlink
    def fail_cleanup(path,*args,**kwargs):
        if path.name.startswith('.videoeditor-render-'):
            raise PermissionError('locked temporary file')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',fail_cleanup)
    worker.start(source,probe(source),EditOptions(speed=0),reserve_output(source,target,False))
    worker._thread.join(timeout=10)
    assert not worker.running
    events=worker.poll()
    assert events[-1].kind=='error' and 'locked' in events[-1].message
