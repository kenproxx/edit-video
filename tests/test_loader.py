import threading
import time
import pytest
from app.loader import MediaLoader
from app.processes import MediaCancelled


def test_latest_file_selection_wins(clips,monkeypatch):
    import app.loader as module
    entered=threading.Event();release=threading.Event();calls=[]
    real=module.probe
    def controlled_probe(path,**kwargs):
        calls.append(path)
        if path==clips['source']:
            entered.set();assert release.wait(5)
        return real(path,**kwargs)
    monkeypatch.setattr(module,'probe',controlled_probe)
    loader=MediaLoader()
    try:
        loader.request(clips['source']);assert entered.wait(5)
        loader.request(clips['silent'])
        newest=loader.request(clips['rotated']);release.set()
        end=time.monotonic()+5;results=[]
        while time.monotonic()<end:
            results=loader.poll()
            if results:break
            time.sleep(.01)
        assert results and results[0].generation==newest and results[0].path==clips['rotated']
        assert results[0].info.width==240
        assert calls==[clips['source'],clips['rotated']]
    finally:
        release.set();loader.close()


def test_close_cancels_probe_and_disallows_new_requests(clips,monkeypatch):
    import app.loader as module
    entered=threading.Event()
    def wait_probe(path,cancel):
        entered.set();assert cancel.wait(5);raise MediaCancelled('cancelled')
    monkeypatch.setattr(module,'probe',wait_probe)
    loader=MediaLoader()
    loader.request(clips['source']);assert entered.wait(5)
    loader.close();loader._thread.join(timeout=3)
    assert not loader._thread.is_alive() and not loader.busy
    with pytest.raises(RuntimeError): loader.request(clips['silent'])
