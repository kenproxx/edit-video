"""Edited proxy preparation and bounded embedded frames; Tk is never called here."""
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from PIL import Image
from .models import validate_options
from .output import reserve_output
from .render import preview_size
from .resources import binary_path,user_data_dir,quiet_process_options
from .timing import trimmed_duration,source_interval
from .worker import RenderWorker


@dataclass
class PlaybackEvent:
    kind: str
    generation: int
    image: Image.Image | None = None
    time: float = 0
    progress: float = 0
    message: str = ''


class FrameReader:
    """One latest frame, two native processes, one decoder thread."""
    def __init__(self,path,size,fps,start,generation,audio):
        self.path,self.size,self.fps,self.start=path,size,min(15,fps),start
        self.generation,self.audio=generation,audio
        self.process=self.audio_process=None
        self._cancel=threading.Event();self._finished=threading.Event()
        self._lock=threading.Lock();self._frame=self._terminal=None
        self._thread=threading.Thread(target=self._run,daemon=True)
        self._thread.start()

    @property
    def active(self): return not self._finished.is_set()

    @property
    def pending_frames(self):
        with self._lock: return int(self._frame is not None)

    def _terminate(self,process):
        if process is not None and process.poll() is None:
            try: process.terminate()
            except OSError: pass

    def stop(self):
        self._cancel.set()
        self._terminate(self.process);self._terminate(self.audio_process)
        with self._lock:
            if self._frame is not None: self._frame.image.close();self._frame=None

    def poll(self):
        with self._lock:
            events=([self._frame] if self._frame is not None else [])+([self._terminal] if self._terminal is not None else [])
            self._frame=self._terminal=None
            return events

    def _reap(self,process):
        if process is None: return
        self._terminate(process)
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired: process.kill();process.wait(timeout=3)
        if process.stdout is not None: process.stdout.close()
        if process.stderr is not None: process.stderr.close()

    def _run(self):
        error=''
        try:
            args=[binary_path('ffmpeg'),'-hide_banner','-loglevel','error','-nostdin','-threads','2','-ss',f'{self.start:.9g}','-re','-i',self.path,'-an','-vf',f'fps={self.fps:.9g}','-pix_fmt','rgb24','-threads','2','-f','rawvideo','pipe:1']
            self.process=subprocess.Popen([str(a) for a in args],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,**quiet_process_options())
            if self.audio and not self._cancel.is_set():
                args=[binary_path('ffplay'),'-hide_banner','-loglevel','error','-nodisp','-vn','-autoexit','-ss',f'{self.start:.9g}',self.path]
                self.audio_process=subprocess.Popen([str(a) for a in args],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,**quiet_process_options())
            if self._cancel.is_set(): self.stop()
            count=0;length=self.size[0]*self.size[1]*3
            while not self._cancel.is_set():
                data=self.process.stdout.read(length)
                if len(data)!=length: break
                image=Image.frombytes('RGB',self.size,data)
                with self._lock:
                    if self._cancel.is_set(): image.close();break
                    if self._frame is not None: self._frame.image.close()
                    self._frame=PlaybackEvent('frame',self.generation,image,self.start+count/self.fps)
                count+=1
            if not self._cancel.is_set() and self.process.wait(timeout=3)!=0: error='Không giải mã được preview video'
        except Exception as exc:
            if not self._cancel.is_set(): error=str(exc)
        finally:
            self._reap(self.process);self._reap(self.audio_process)
            with self._lock:
                if not self._cancel.is_set(): self._terminal=PlaybackEvent('error' if error else 'completed',self.generation,message=error)
            self._finished.set()


class PlaybackController:
    def __init__(self):
        self.directory=Path(tempfile.mkdtemp(prefix='playback-',dir=user_data_dir()))
        self._worker=RenderWorker();self._generation=0
        self._pending=self._active=self._proxy=None
        self._reader=None;self._retired=[]
        self._closed=False;self._removed=False;self._garbage=set()
        self.duration=0

    @property
    def ready(self): return self._proxy is not None

    @property
    def playing(self): return self._reader is not None and self._reader.active and not self._reader._cancel.is_set()

    @property
    def busy(self): return self._native_busy or (self._closed and not self._removed)

    @property
    def _native_busy(self): return self._worker.running or self._pending is not None or (self._reader is not None and self._reader.active) or any(r.active for r in self._retired)

    def pause(self):
        if self._reader is not None:
            self._reader.stop();self._retired.append(self._reader);self._reader=None

    def invalidate(self):
        self._generation+=1;self.pause();self._pending=None;self._worker.cancel()
        if self._proxy is not None:
            self._garbage.add(self._proxy[0]);self._proxy=None
        return self._generation

    def prepare(self,source,info,options):
        if self._closed: raise RuntimeError('Playback controller đã đóng')
        validate_options(options,info.width,info.height,info.duration)
        self.invalidate()
        self._pending=(self._generation,source,info,options)
        self.duration=trimmed_duration(options,info.duration)
        self._launch()
        return self._generation

    def _launch(self):
        if self._closed or self._pending is None or self._worker.running: return
        generation,source,info,options=self._pending;self._pending=None
        path=self.directory/f'proxy-{generation}.mp4'
        self._active=(generation,path,info,options)
        self._worker.start(source,info,options,reserve_output(source,path,False),preview=True)

    def play(self,time=0):
        if self._closed or self._proxy is None: raise ValueError('Preview chưa sẵn sàng')
        if not 0<=time<self.duration: raise ValueError('Thời điểm phát nằm ngoài preview')
        self.pause()
        path,info,options=self._proxy
        _,end=source_interval(options,info.duration)
        audio=info.has_audio and end>info.audio_offset
        self._reader=FrameReader(path,preview_size(info,options),info.fps,time,self._generation,audio)

    def poll(self):
        events=[]
        self._retired=[r for r in self._retired if r.active]
        held={r.path for r in self._retired}
        if self._reader is not None and self._reader.active: held.add(self._reader.path)
        for path in list(self._garbage-held):
            try: path.unlink(missing_ok=True);self._garbage.remove(path)
            except PermissionError: pass
        for event in self._worker.poll():
            if self._active is None: continue
            generation,path,info,options=self._active
            if event.kind=='progress':
                if generation==self._generation and not self._closed: events.append(PlaybackEvent('progress',generation,progress=event.progress or 0))
                continue
            self._active=None
            if generation!=self._generation or self._closed:
                path.unlink(missing_ok=True)
            elif event.kind=='completed':
                self._proxy=(path,info,options);events.append(PlaybackEvent('ready',generation))
            elif event.kind=='error': events.append(PlaybackEvent('error',generation,message=event.message))
        self._launch()
        if self._reader is not None:
            events.extend(self._reader.poll())
            if not self._reader.active: self._reader=None
        if self._closed and not self._native_busy and not self._removed:
            shutil.rmtree(self.directory,ignore_errors=True);self._removed=True
        return events

    def close(self):
        self._closed=True;self.invalidate()
        self.poll()
