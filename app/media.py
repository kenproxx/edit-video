"""ffprobe metadata and display-oriented square-pixel source frames."""
from dataclasses import dataclass
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
from .resources import binary_path

@dataclass(frozen=True)
class MediaInfo:
    width: int
    height: int
    duration: float
    fps: float
    has_audio: bool
    rotation: int
    is_hdr: bool


def _ratio(value, fallback: float) -> float:
    try:
        result = float(Fraction(str(value).replace(':', '/')))
        return result if math.isfinite(result) and result > 0 else fallback
    except (ValueError, ZeroDivisionError):
        return fallback


def _parse_info(data: dict) -> MediaInfo:
    videos = [s for s in data.get('streams', []) if s.get('codec_type') == 'video']
    if not videos:
        raise ValueError('File không có video stream')
    stream = videos[0]
    try:
        w, h = int(stream['width']), int(stream['height'])
        duration = float(stream.get('duration', data.get('format', {}).get('duration', 0)))
        rotation = float(stream.get('tags', {}).get('rotate', 0))
        for side in stream.get('side_data_list', []):
            if 'rotation' in side:
                rotation = float(side['rotation'])
        if not math.isfinite(rotation) or abs(rotation - round(rotation / 90) * 90) > .01:
            raise ValueError('Chỉ hỗ trợ rotation theo bội số 90 độ')
        rotation = int(round(rotation)) % 360
        if min(w, h) < 2 or not math.isfinite(duration) or duration <= 0:
            raise ValueError('Kích thước/thời lượng không hợp lệ')
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError('Thông tin video không hợp lệ') from exc
    sar = _ratio(stream.get('sample_aspect_ratio', '1:1'), 1)
    # FFmpeg autorotate inverts SAR at quarter turns; scale matches its display shape.
    w = max(2, round(w * sar))
    if rotation in (90, 270):
        w, h = h, w
    fps = _ratio(stream.get('avg_frame_rate'), _ratio(stream.get('r_frame_rate'), 30))
    hdr = stream.get('color_transfer') in ('smpte2084', 'arib-std-b67') or stream.get('color_primaries') == 'bt2020'
    if hdr:
        raise ValueError('HDR chưa được hỗ trợ; hãy dùng video SDR')
    return MediaInfo(w, h, duration, fps, any(s.get('codec_type') == 'audio' for s in data.get('streams', [])), rotation, False)


def probe(path: Path) -> MediaInfo:
    try:
        result = subprocess.run([str(binary_path('ffprobe')), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path.resolve())], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30, check=True)
        return _parse_info(json.loads(result.stdout))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ValueError('Không đọc được video (file hỏng, codec hoặc thời gian đọc quá lâu)') from exc


def normalization_filter(info: MediaInfo) -> str:
    return f'scale={info.width}:{info.height},setsar=1'


def extract_source_frame(path: Path, time: float, destination: Path) -> Path:
    info = probe(path)
    if not math.isfinite(time) or not 0 <= time < info.duration:
        raise ValueError('Thời điểm preview nằm ngoài video')
    command = [str(binary_path('ffmpeg')), '-v', 'error', '-y', '-threads', '2', '-ss', str(time), '-i', str(path.resolve()), '-map', '0:v:0', '-vf', normalization_filter(info), '-frames:v', '1', '-threads', '2', str(destination.resolve())]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise ValueError('Không trích được ảnh preview') from exc
    if not destination.is_file():
        raise ValueError('Không có khung hình tại thời điểm đã chọn')
    return destination
