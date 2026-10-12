"""Sequential folder exports sharing the validated single-video engine."""
from collections import deque
from dataclasses import dataclass,replace,asdict
from pathlib import Path
import json
import math
import threading
import time
import uuid
from PIL import Image,ImageFont
from .media import probe
from .models import Rect,validate_options
from .output import reserve_output
from .resources import user_data_dir
from .worker import RenderWorker

VIDEO_SUFFIXES={'.mp4','.mov','.mkv','.avi','.webm','.m4v','.wmv','.ts','.mts'}

@dataclass(frozen=True)
class BatchJob:
    source: Path
    destination: Path

@dataclass(frozen=True)
class BatchResult:
    source: Path
    output: Path
    status: str
    message: str = ''

@dataclass(frozen=True)
class BatchEvent:
    kind: str
    index: int = 0
    total: int = 0
    progress: float = 0
    source: Path | None = None
    message: str = ''


def scan_videos(directory):
    directory=Path(directory).resolve()
    if not directory.is_dir(): raise ValueError('Thư mục video không hợp lệ')
    return tuple(sorted((p for p in directory.iterdir() if not p.is_symlink() and p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES),key=lambda p:(p.name.casefold(),p.name)))


def plan_batch(files,directory):
    files=tuple(Path(p).resolve() for p in files);directory=Path(directory).resolve()
    if not files: raise ValueError('Thư mục không có video')
    if not directory.is_dir(): raise ValueError('Hãy chọn thư mục xuất có sẵn')
    if any(p.parent==directory for p in files): raise ValueError('Thư mục xuất hàng loạt phải khác thư mục nguồn')
    reserved={p.stem.casefold()+'.mp4' for p in files};used=set();jobs=[]
    for source in files:
        name=source.stem+'.mp4';number=2
        while name.casefold() in used:
            name=f'{source.stem}_{number}.mp4';number+=1
            while name.casefold() in reserved:
                name=f'{source.stem}_{number}.mp4';number+=1
        used.add(name.casefold());jobs.append(BatchJob(source,directory/name))
    return tuple(jobs)


def adapt_options(options,reference,info):
    """Scale relative image regions; timing and sound levels remain unchanged."""
    validate_options(options,reference.width,reference.height,reference.duration)
    def region(rect,old,new,even=False):
        unit=2 if even else 1
        width,height=(v//unit*unit for v in new)
        left=min(width-unit,max(0,math.floor(rect.x*width/old[0]/unit)*unit))
        top=min(height-unit,max(0,math.floor(rect.y*height/old[1]/unit)*unit))
        right=min(width,max(left+unit,math.floor((rect.x+rect.width)*width/old[0]/unit)*unit))
        bottom=min(height,max(top+unit,math.floor((rect.y+rect.height)*height/old[1]/unit)*unit))
        return Rect(left,top,right-left,bottom-top)
    crop=region(options.crop,(reference.width,reference.height),(info.width,info.height),True) if options.crop else None
    old=(options.crop.width,options.crop.height) if options.crop else (reference.width//2*2,reference.height//2*2)
    new=(crop.width,crop.height) if crop else (info.width//2*2,info.height//2*2)
    blur=region(options.blur,old,new) if options.blur else None
    logo=options.logo
    if logo is not None:
        with Image.open(logo.path) as image: height=logo.height if logo.height is not None else max(1,round(image.height*logo.width/image.width))
        r=region(Rect(logo.x,logo.y,logo.width,height),old,new)
        logo=replace(logo,x=r.x,y=r.y,width=r.width,height=r.height)
    def text(overlay):
        if overlay is None or not overlay.text.strip(): return overlay
        from .overlays import text_bounds
        ratio=min(new[0]/old[0],new[1]/old[1])
        x=min(new[0]-1,max(0,math.floor(overlay.x*new[0]/old[0])))
        y=min(new[1]-1,max(0,math.floor(overlay.y*new[1]/old[1])))
        candidate=replace(overlay,x=x,y=y,stroke_width=max(0,math.floor(overlay.stroke_width*ratio)))
        low,high,best=1,max(1,math.floor(overlay.size*ratio)),None
        while low<=high:
            size=(low+high)//2
            width,height=text_bounds(replace(candidate,size=size),ImageFont.truetype(str(candidate.font),size))[1]
            if x+width<=new[0] and y+height<=new[1]: best=size;low=size+1
            else: high=size-1
        if best is None: raise ValueError('Text không vừa video sau co giãn')
        return replace(candidate,size=best)
    return replace(options,crop=crop,blur=blur,logo=logo,watermark=text(options.watermark),intro=text(options.intro))


class BatchWorker:
    def __init__(self):
        self._worker=RenderWorker();self._lock=threading.Lock();self._cancel=threading.Event()
        self._events=deque(maxlen=8);self._progress=None;self._results=[];self._running=False
        self._thread=None;self.report_path=None

    @property
    def running(self):
        with self._lock: return self._running

    @property
    def results(self):
        with self._lock: return tuple(self._results)

    def _emit(self,event):
        with self._lock:
            if event.kind=='progress': self._progress=event
            else: self._events.append(event)

    def poll(self):
        with self._lock:
            events=([self._progress] if self._progress is not None else [])+list(self._events)
            self._progress=None;self._events.clear();return events

    def cancel(self):
        self._cancel.set();self._worker.cancel()

    def start(self,files,directory,options,reference=None,scale=False):
        jobs=plan_batch(files,directory)
        if scale and reference is None: raise ValueError('Hãy chọn video mẫu hợp lệ để co giãn')
        with self._lock:
            if self._running: raise RuntimeError('Đang xuất hàng loạt')
            self._running=True;self._cancel.clear();self._results=[];self._events.clear();self._progress=None;self.report_path=None
            self._thread=threading.Thread(target=self._run,args=(jobs,options,reference,scale),daemon=True);self._thread.start()

    def _run(self,jobs,options,reference,scale):
        terminal='completed';message=''
        try:
            for index,job in enumerate(jobs):
                if self._cancel.is_set(): break
                self._emit(BatchEvent('progress',index+1,len(jobs),index/len(jobs),job.source))
                try:
                    reservation=reserve_output(job.source,job.destination,False)
                    info=probe(job.source,self._cancel)
                    edit=adapt_options(options,reference,info) if scale else options
                    validate_options(edit,info.width,info.height,info.duration)
                    if self._cancel.is_set(): break
                    self._worker.start(job.source,info,edit,reservation)
                    result=None
                    while self._worker.running or result is None:
                        if self._cancel.is_set(): self._worker.cancel()
                        for event in self._worker.poll():
                            if event.kind=='progress': self._emit(BatchEvent('progress',index+1,len(jobs),(index+(event.progress or 0))/len(jobs),job.source))
                            else: result=event
                        if result is not None and not self._worker.running: break
                        time.sleep(.02)
                    row=BatchResult(job.source,job.destination,result.kind,result.message)
                except FileExistsError as exc: row=BatchResult(job.source,job.destination,'skipped',str(exc))
                except Exception as exc: row=BatchResult(job.source,job.destination,'cancelled' if self._cancel.is_set() else 'error',str(exc))
                with self._lock: self._results.append(row)
                self._emit(BatchEvent('item',index+1,len(jobs),(index+1)/len(jobs),job.source,row.message))
            if self._cancel.is_set(): terminal='cancelled'
            # Record unstarted files too: the result never silently loses jobs.
            with self._lock:
                self._results.extend(BatchResult(j.source,j.destination,'cancelled','Chưa xử lý do hủy') for j in jobs[len(self._results):])
            reports=user_data_dir()/'reports';reports.mkdir(exist_ok=True)
            path=reports/f'batch-{uuid.uuid4().hex}.json'
            with path.open('x',encoding='utf-8') as report:
                json.dump({'status':terminal,'results':[asdict(row) for row in self.results]},report,ensure_ascii=False,indent=2,default=str)
            self.report_path=path
        except Exception as exc: terminal='error';message=str(exc)
        finally:
            self._worker.cancel()
            if self._worker._thread is not None: self._worker._thread.join()
            with self._lock:
                self._running=False;self._events.append(BatchEvent(terminal,total=len(jobs),progress=1 if terminal=='completed' else 0,message=message))
