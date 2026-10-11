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

REQUIRED_FILTERS = {'scale','setsar','format','hflip','vflip','crop','setpts','fps','split','gblur','overlay','atrim','asetpts','atempo'}


def _run(args):
    result = subprocess.run([str(a) for a in args],check=True,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30)
    return result.stdout


def verify_media_tools() -> dict:
    ffmpeg,ffprobe = binary_path('ffmpeg'),binary_path('ffprobe')
    versions = {name:_run([path,'-version']).splitlines()[0] for name,path in [('ffmpeg',ffmpeg),('ffprobe',ffprobe)]}
    encoders = _run([ffmpeg,'-hide_banner','-encoders'])
    filters = _run([ffmpeg,'-hide_banner','-filters'])
    names = {match.group(1) for line in filters.splitlines() if (match:=re.match(r'^\s*[TSC.]{3}\s+(\w+)\s',line))}
    missing = REQUIRED_FILTERS - names
    if missing or not re.search(r'^\s*V\S*\s+libx264\s',encoders,re.M) or not re.search(r'^\s*A\S*\s+aac\s',encoders,re.M):
        raise ValueError('FFmpeg thiếu libx264/AAC hoặc filters: '+', '.join(sorted(missing)))
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
