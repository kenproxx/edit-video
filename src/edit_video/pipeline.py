from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from .models import EditSettings, crop_pixels, validate
from .media import MediaInfo
from .binaries import Binaries
from .overlays import write_overlays

@dataclass(frozen=True)
class RenderRequest:
    media: MediaInfo
    settings: EditSettings
    destination: Path
    mode: Literal['video','preview','thumbnail']
    source_time: float = 0.0

def output_size(media: MediaInfo, settings: EditSettings) -> tuple[int,int]:
    return crop_pixels(settings.crop,media.width,media.height)[2:]

def build_command(request: RenderRequest, binaries: Binaries, workspace: Path) -> list[str]:
    m,s=request.media,request.settings
    validate(s)
    if request.mode not in ('video','preview','thumbnail'): raise ValueError('Chế độ xuất không hợp lệ.')
    x,y,w,h=crop_pixels(s.crop,m.width,m.height)
    overlays=write_overlays(s,(w,h),workspace,request.mode=='thumbnail')
    cmd=[str(binaries.ffmpeg),'-hide_banner','-loglevel','error','-nostdin','-y','-threads','1','-filter_complex_threads','1']
    if request.mode!='video':
        time=max(0,min(request.source_time,m.duration-1/m.fps))
        cmd+=['-ss',f'{time:.6f}']
    cmd+=['-i',str(m.path)]
    for overlay in overlays: cmd+=['-i',str(overlay)]
    filters=[f'[{0}:{m.video_index}]scale={m.width}:{m.height},setsar=1,crop={w}:{h}:{x}:{y}:exact=1']
    if s.flip_h: filters[0]+=',hflip'
    if s.flip_v: filters[0]+=',vflip'
    filters[0]+='[base]'
    label='base'
    if s.blur:
        r=s.blur.rect
        bx,by=int(r.x*w),int(r.y*h)
        bw,bh=max(1,min(w-bx,int(r.width*w))),max(1,min(h-by,int(r.height*h)))
        filters += [f'[{label}]split=2[clear][region]',f'[region]crop={bw}:{bh}:{bx}:{by}:exact=1,gblur=sigma={s.blur.sigma}[blurred]',f'[clear][blurred]overlay={bx}:{by}:format=auto[soft]']
        label='soft'
    for index,_ in enumerate(overlays,1):
        nxt=f'layer{index}'
        filters.append(f'[{label}][{index}:v]overlay=0:0:format=auto:eof_action=repeat[{nxt}]')
        label=nxt
    if request.mode=='video':
        filters.append(f'[{label}]setpts=(PTS-STARTPTS)/{s.speed},format=yuv420p[vout]')
        if m.audio_index is not None:
            remaining=s.speed; tempos=[]
            while remaining<.5: tempos.append(.5); remaining/=.5
            while remaining>2: tempos.append(2); remaining/=2
            tempos.append(remaining)
            af=','.join(f'atempo={v}' for v in tempos)
            filters.append(f'[0:{m.audio_index}]asetpts=PTS-STARTPTS,{af}[aout]')
        cmd+=['-filter_complex',';'.join(filters),'-map','[vout]']
        if m.audio_index is not None: cmd+=['-map','[aout]','-c:a','aac','-b:a','192k']
        cmd+=['-c:v','libx264','-preset','medium','-crf','20','-r',str(m.fps),'-t',f'{m.duration/s.speed:.6f}','-threads','1','-map_metadata','-1','-metadata:s:v:0','rotate=0','-movflags','+faststart','-progress','pipe:1','-nostats']
    else:
        filters.append(f'[{label}]format=rgb24[vout]')
        cmd+=['-filter_complex',';'.join(filters),'-map','[vout]','-frames:v','1','-an','-threads','1','-update','1']
        if request.destination.suffix.lower() in ('.jpg','.jpeg'): cmd+=['-q:v','2']
    return cmd+[str(request.destination)]
