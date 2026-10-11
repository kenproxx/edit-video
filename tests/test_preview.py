import threading
import time
from PIL import Image
import pytest
from app.preview import PreviewController
from app.media import probe
from app.models import EditOptions


def wait_result(controller,timeout=15):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        results=controller.poll()
        if results: return results[-1]
        time.sleep(.01)
    pytest.fail('Preview timed out')


def test_real_preview_and_close(clips):
    controller=PreviewController()
    generation=controller.request(clips['source'],probe(clips['source']),EditOptions(),.5)
    result=wait_result(controller)
    assert result.generation==generation and not result.error
    assert result.image.size==(320,240)
    result.image.close()
    directory=controller.directory
    controller.close()
    assert not directory.exists()
    with pytest.raises(RuntimeError): controller.request(clips['source'],probe(clips['source']),EditOptions(),0)


def test_latest_request_replaces_pending_and_ignores_old(clips,monkeypatch):
    # Slow native operation is controlled; assertions are on controller's public results.
    import app.preview as module
    entered=threading.Event(); release=threading.Event(); calls=[]
    real=module.render_preview
    def slow(source,info,options,time,destination,**kwargs):
        calls.append(time)
        if time==0:
            entered.set(); assert release.wait(5)
        return real(source,info,options,time,destination,**kwargs)
    monkeypatch.setattr(module,'render_preview',slow)
    controller=PreviewController()
    try:
        info=probe(clips['source'])
        first=controller.request(clips['source'],info,EditOptions(),0)
        assert entered.wait(5)
        controller.request(clips['source'],info,EditOptions(),.3)
        newest=controller.request(clips['source'],info,EditOptions(),.7)
        release.set()
        result=wait_result(controller)
        assert result.generation==newest and newest>first
        assert calls==[0,.7]  # no unbounded executor queue
        result.image.close()
    finally:
        release.set(); controller.close()


def test_invalidate_hides_completed_result(clips):
    controller=PreviewController()
    try:
        controller.request(clips['source'],probe(clips['source']),EditOptions(),0)
        end=time.monotonic()+10
        while controller.busy and time.monotonic()<end: time.sleep(.01)
        controller.invalidate()
        assert controller.poll()==[]
    finally: controller.close()


def test_preview_reports_error_and_recovers(clips):
    controller=PreviewController()
    try:
        info=probe(clips['source'])
        controller.request(clips['source'],info,EditOptions(speed=0),0)
        assert wait_result(controller).error
        controller.request(clips['source'],info,EditOptions(),0)
        result=wait_result(controller)
        assert result.image is not None and not result.error
        result.image.close()
    finally: controller.close()


def test_close_cancels_native_preview(clips,tmp_path):
    import subprocess
    from app.models import Rect
    source=tmp_path/'long.mp4'
    subprocess.run(['ffmpeg','-v','error','-y','-stream_loop','-1','-i',str(clips['source']),'-t','240','-c','copy',str(source)],check=True)
    controller=PreviewController()
    controller.request(source,probe(source),EditOptions(blur=Rect(0,0,320,240),blur_strength=100),230)
    end=time.monotonic()+5
    while not controller.busy and time.monotonic()<end: time.sleep(.01)
    time.sleep(.1)
    controller.close()
    controller._thread.join(timeout=3)
    assert not controller._thread.is_alive() and not controller.directory.exists()


def test_preview_cleanup_error_does_not_leave_busy(clips,monkeypatch):
    from pathlib import Path
    original=Path.unlink
    def deny_frame_unlink(path,*args,**kwargs):
        if path.name.startswith('frame-') and path.parent.name.startswith('preview-'):
            raise PermissionError('locked preview frame')
        return original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',deny_frame_unlink)
    controller=PreviewController()
    try:
        controller.request(clips['source'],probe(clips['source']),EditOptions(),0)
        end=time.monotonic()+5
        while controller.busy and time.monotonic()<end: time.sleep(.01)
        assert not controller.busy
        result=controller.poll()[-1]
        assert 'locked' in result.error
    finally: controller.close()
