from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import json
import math
import subprocess
from .binaries import Binaries, process_options

class MediaError(ValueError): pass

@dataclass(frozen=True)
class MediaInfo:
    path: Path
    video_index: int
    audio_index: int | None
    width: int
    height: int
    duration: float
    fps: float
    rotation: int
    sar: float

def _ratio(value, default=1.0):
    try: return float(Fraction(str(value).replace(':','/')))
    except (ValueError,ZeroDivisionError): return default

def probe(path: Path, binaries: Binaries) -> MediaInfo:
    try:
        result = subprocess.run([str(binaries.ffprobe),'-v','error','-show_streams','-show_format','-of','json',str(path)],capture_output=True,timeout=30,**process_options())
        if result.returncode: raise MediaError(result.stderr.decode('utf-8',errors='replace'))
        data = json.loads(result.stdout)
        video = next((s for s in data['streams'] if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic')),None)
        if not video: raise MediaError('Không có luồng video.')
        audio = next((s for s in data['streams'] if s['codec_type']=='audio'),None)
        rotation = int(float(video.get('tags',{}).get('rotate',0)))
        for side in video.get('side_data_list',[]):
            if 'rotation' in side: rotation = int(round(float(side['rotation'])))
        rotation %= 360
        sar = _ratio(video.get('sample_aspect_ratio','1:1')) or 1
        w,h = round(video['width']*sar),video['height']
        if rotation in (90,270): w,h = h,w
        duration = float(video.get('duration') or data.get('format',{}).get('duration',0))
        fps = _ratio(video.get('avg_frame_rate'),25) or 25
        if not math.isfinite(duration) or duration<=0 or min(w,h)<2: raise MediaError('Thời lượng hoặc kích thước video không hợp lệ.')
        return MediaInfo(Path(path).resolve(),video['index'],audio['index'] if audio else None,w,h,duration,fps,rotation,sar)
    except (OSError,subprocess.TimeoutExpired,ValueError,KeyError,TypeError) as exc:
        raise MediaError(f'Không đọc được video: {exc}') from exc
