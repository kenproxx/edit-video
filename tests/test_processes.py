import os
import subprocess
import sys
import threading
import time
import pytest
from app.processes import run_media_process, MediaCancelled


def test_output_and_failure():
    assert run_media_process([sys.executable,'-c','print("ready")'],2).stdout.strip()==b'ready'
    with pytest.raises(subprocess.CalledProcessError): run_media_process([sys.executable,'-c','raise SystemExit(2)'],2)


def test_timeout_reaps_child(tmp_path):
    pidfile=tmp_path/'pid'
    command=[sys.executable,'-c','import os,sys,time;open(sys.argv[1],"w").write(str(os.getpid()));time.sleep(60)',str(pidfile)]
    with pytest.raises(subprocess.TimeoutExpired): run_media_process(command,.5)
    with pytest.raises(ProcessLookupError): os.kill(int(pidfile.read_text()),0)


def test_cancel_reaps_child(tmp_path):
    pidfile=tmp_path/'pid';cancel=threading.Event();errors=[]
    command=[sys.executable,'-c','import os,sys,time;open(sys.argv[1],"w").write(str(os.getpid()));time.sleep(60)',str(pidfile)]
    def work():
        try: run_media_process(command,60,cancel)
        except Exception as error: errors.append(error)
    thread=threading.Thread(target=work);thread.start()
    end=time.monotonic()+5
    while not pidfile.exists() and time.monotonic()<end: time.sleep(.01)
    assert pidfile.exists();cancel.set();thread.join(timeout=5)
    assert not thread.is_alive() and isinstance(errors[0],MediaCancelled)
    with pytest.raises(ProcessLookupError): os.kill(int(pidfile.read_text()),0)
