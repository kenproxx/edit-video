from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import queue
from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtGui import QImage
from .binaries import Binaries, process_options
from .media import probe
from .pipeline import RenderRequest, build_command, output_size
from .output import OutputTarget, validate_target, publish

class Cancelled(Exception): pass

def run_process(command: list[str], cancel: threading.Event, duration: float, progress) -> None:
    if cancel.is_set(): raise Cancelled('Đã hủy tác vụ.')
    with tempfile.TemporaryFile() as err:
        proc=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=err,**process_options())
        lines=queue.Queue()
        def read():
            for line in proc.stdout: lines.put(line)
        reader=threading.Thread(target=read,daemon=True); reader.start()
        try:
            while proc.poll() is None:
                if cancel.wait(.03):
                    proc.terminate()
                    try: proc.wait(timeout=3)
                    except subprocess.TimeoutExpired: proc.kill(); proc.wait()
                    raise Cancelled('Đã hủy tác vụ.')
                while not lines.empty():
                    line=lines.get_nowait().decode(errors='replace').strip()
                    if line.startswith('out_time_us='):
                        try: progress(min(.99,max(0,float(line.split('=')[1])/1e6/duration)))
                        except ValueError: pass
            if cancel.is_set(): raise Cancelled('Đã hủy tác vụ.')
            if proc.returncode:
                err.seek(0)
                raise RuntimeError('FFmpeg không xử lý được video:\n'+err.read()[-16000:].decode('utf-8',errors='replace'))
        finally:
            if proc.poll() is None: proc.kill(); proc.wait()
            reader.join(timeout=3); proc.stdout.close()

def run_export(request: RenderRequest, binaries: Binaries, overwrite: bool, cancel: threading.Event, progress) -> Path:
    target=OutputTarget(request.media.path,request.destination,overwrite)
    validate_target(target)
    if cancel.is_set(): raise Cancelled('Đã hủy tác vụ.')
    with tempfile.TemporaryDirectory(prefix='.edit-video-',dir=request.destination.parent) as folder:
        workspace=Path(folder)
        temp=workspace/('result'+request.destination.suffix)
        cmd=build_command(replace(request,destination=temp),binaries,workspace)
        run_process(cmd,cancel,request.media.duration/request.settings.speed,progress)
        expected=output_size(request.media,request.settings)
        if request.mode=='video':
            info=probe(temp,binaries)
            actual=(info.width,info.height)
        else:
            image=QImage(str(temp)); actual=(image.width(),image.height())
        if actual!=expected: raise RuntimeError('Kích thước file xuất không đúng. Chưa thay thế file đích.')
        if cancel.is_set(): raise Cancelled('Đã hủy tác vụ.')
        publish(temp,target)
    progress(1.0)
    return request.destination

class PreviewCoordinator(QObject):
    ready=Signal(int,str)
    failed=Signal(int,str)
    _result=Signal(int,str,str)
    def __init__(self,binaries: Binaries):
        super().__init__()
        self.binaries=binaries; self.generation=0; self.closed=False
        self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='preview')
        self.futures=[]; self.events=[]; self.pending=None
        self.timer=QTimer(self); self.timer.setSingleShot(True); self.timer.setInterval(150)
        self.timer.timeout.connect(self._launch)
        self._result.connect(self._deliver)
    def submit(self,request: RenderRequest) -> int:
        if self.closed: raise RuntimeError('Preview đã đóng.')
        self.generation+=1
        for event in self.events: event.set()
        self.pending=(self.generation,request)
        self.timer.start()
        return self.generation
    def _launch(self):
        generation,request=self.pending
        event=threading.Event(); self.events.append(event)
        def work():
            try:
                path=run_export(request,self.binaries,True,event,lambda _:None)
                self._result.emit(generation,str(path),'')
            except Cancelled: pass
            except Exception as exc: self._result.emit(generation,'',str(exc))
        self.futures=[f for f in self.futures if not f.done()]
        self.futures.append(self.executor.submit(work))
    def _deliver(self,generation,path,error):
        if self.closed or generation!=self.generation: return
        if error: self.failed.emit(generation,error)
        else: self.ready.emit(generation,path)
    def close(self) -> None:
        self.closed=True; self.timer.stop()
        for event in self.events: event.set()
        self.executor.shutdown(wait=True,cancel_futures=True)
