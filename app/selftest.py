"""Headless checks used by the source CLI and the actual packaged executable."""
import json
from pathlib import Path
import re
import subprocess
import time

from .media import probe
from .models import EditOptions, default_output
from .output import reserve_output
from .resources import binary_path, resource_root
from .worker import RenderWorker

REQUIRED_FILTERS = {'scale','setsar','format','hflip','vflip','crop','setpts','fps','split','gblur','overlay','atrim','asetpts','atempo','trim','adelay','apad'}


def _run(args):
    result = subprocess.run([str(a) for a in args],check=True,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    return result.stdout


def verify_media_tools() -> dict:
    ffmpeg,ffprobe,ffplay = binary_path('ffmpeg'),binary_path('ffprobe'),binary_path('ffplay')
    versions = {name:_run([path,'-version']).splitlines()[0] for name,path in [('ffmpeg',ffmpeg),('ffprobe',ffprobe),('ffplay',ffplay)]}
    encoders = _run([ffmpeg,'-hide_banner','-encoders'])
    filters = _run([ffmpeg,'-hide_banner','-filters'])
    # FFmpeg 8 removed the command-support column; FFmpeg 7 has three flags.
    names = {match.group(1) for line in filters.splitlines() if (match:=re.match(r'^\s*[TSC.]{2,3}\s+(\w+)\s',line))}
    missing = REQUIRED_FILTERS - names
    for media,codec in (('V','libx264'),('A','aac')):
        if not re.search(rf'^\s*{media}\S*\s+{codec}\s',encoders,re.M):
            missing.add(codec)
    if missing:
        raise ValueError('FFmpeg thiếu codec/filter: '+', '.join(sorted(missing)))
    return versions


def smoke_export(source: Path, directory: Path, timeout: float = 120) -> dict:
    versions = verify_media_tools()
    info = probe(source)
    destination = default_output(source,directory)
    reservation = reserve_output(source,destination,False)
    worker = RenderWorker()
    worker.start(source,info,EditOptions(),reservation)
    deadline = time.monotonic()+timeout
    terminal = None
    while worker.running or terminal is None:
        for event in worker.poll():
            if event.kind != 'progress': terminal = event
        if terminal is not None and not worker.running: break
        if time.monotonic() > deadline:
            worker.cancel()
            # Wait for the worker's bounded native-process shutdown and cleanup.
            while worker.running: time.sleep(.05)
            raise TimeoutError('Smoke export timed out')
        time.sleep(.02)
    if terminal.kind != 'completed': raise ValueError(terminal.message or terminal.kind)
    data = json.loads(_run([binary_path('ffprobe'),'-v','error','-show_streams','-show_format','-of','json',destination]))
    video = next(stream for stream in data['streams'] if stream['codec_type']=='video')
    audio = next((stream for stream in data['streams'] if stream['codec_type']=='audio'),None)
    duration = float(data['format']['duration'])
    if video['codec_name'] != 'h264' or (info.has_audio and (audio is None or audio['codec_name'] != 'aac')):
        raise ValueError('Smoke output codec mismatch')
    if abs(duration-info.duration) > max(.15,2/info.fps): raise ValueError('Smoke output duration mismatch')
    return {'ok':True,'output':str(destination),'duration':duration,'width':video['width'],'height':video['height'],'video_codec':video['codec_name'],'audio_codec':audio['codec_name'] if audio else None,'tools':versions,'resource_root':str(resource_root())}


def smoke_embedded_playback(source: Path) -> dict:
    from .ui import VideoEditorApp
    from .models import Rect
    from .timing import format_time
    app=VideoEditorApp()
    state={'phase':'load','frames':0,'audio':False,'duration':0}
    errors=[];processes=[]
    original=app._handle_playback_event
    def observe(event):
        if event.kind=='frame':
            state['frames']+=1
            reader=app.playback._reader
            if reader is not None:
                for process in (reader.process,reader.audio_process):
                    if process is not None and process not in processes: processes.append(process)
                state['audio']=state['audio'] or reader.audio_process is not None
        if event.kind=='error': errors.append(event.message)
        original(event)
    app._handle_playback_event=observe
    def callback_error(*args):
        errors.append(str(args[1]));app.request_close()
    app.report_callback_exception=callback_error
    def supervise():
        if app._destroyed: return
        try:
            if errors: app.request_close();return
            if state['phase']=='load' and app.media_info is not None:
                if app.media_info.duration<1.75: raise ValueError('Playback smoke fixture must be at least 1.75 seconds')
                with app.options.batch():
                    app.options.vars['trim_enabled'].set(True)
                    app.options.vars['trim_start'].set(format_time(.25))
                    app.options.vars['trim_end'].set(format_time(1.75))
                    app.options.vars['speed'].set('1.5')
                    app.options.vars['flip_horizontal'].set(True)
                app.options.apply_region('crop',Rect(0,0,app.media_info.width//4*2,app.media_info.height//4*2))
                app.start_playback();state['phase']='first'
            elif state['phase']=='first' and state['frames']>=3:
                state['duration']=app.playback.duration
                app.pause_playback()
                if not app.playback.ready: raise ValueError('Pause lost prepared preview')
                app.time_var.set(.4);app.start_playback();state['phase']='second'
            elif state['phase']=='second' and state['frames']>=4 and app.time_var.get()>=.4:
                state['phase']='closed';app.request_close();return
        except Exception as exc:
            errors.append(str(exc));app.request_close();return
        app.after(25,supervise)
    def timeout():
        if not app._destroyed: errors.append('Embedded playback smoke timed out');app.request_close()
    app.load_video(source);app.after(25,supervise);app.after(20000,timeout);app.mainloop()
    if errors: raise ValueError('; '.join(errors))
    if state['phase']!='closed' or state['frames']<4 or app.playback.busy or any(p.poll() is None for p in processes):
        raise ValueError('Playback did not close and reap native processes')
    return {'ok':True,'playback':True,'frames':state['frames'],'audio':state['audio'],'duration':state['duration']}
