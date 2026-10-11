"""ffprobe metadata and display-oriented square-pixel source frames."""
from dataclasses import dataclass
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
import os
import tempfile
from contextlib import contextmanager
from PIL import Image
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
    audio_offset: float = 0


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
    audio = next((s for s in data.get('streams', []) if s.get('codec_type') == 'audio'), None)
    try:
        offset = float(audio.get('start_time', 0)) - float(stream.get('start_time', 0)) if audio else 0
        if not math.isfinite(offset):
            raise ValueError('Nonfinite start time')
    except (TypeError, ValueError) as exc:
        raise ValueError('Thời điểm audio/video không hợp lệ') from exc
    return MediaInfo(w, h, duration, fps, audio is not None, rotation, False, offset)


def probe(path: Path) -> MediaInfo:
    try:
        result = subprocess.run([str(binary_path('ffprobe')), '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path.resolve())], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30, check=True)
        return _parse_info(json.loads(result.stdout))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ValueError('Không đọc được video (file hỏng, codec hoặc thời gian đọc quá lâu)') from exc


def normalization_filter(info: MediaInfo) -> str:
    return f'scale={info.width}:{info.height},setsar=1'


@contextmanager
def frame_destination(source: Path, destination: Path):
    """An existing preview remains intact unless a fresh PNG has been validated."""
    if source.resolve() == destination.resolve() or (destination.exists() and os.path.samefile(source, destination)):
        raise ValueError('Ảnh preview không được ghi đè video nguồn')
    fd, name = tempfile.mkstemp(prefix='.videoeditor-frame-', suffix='.png', dir=destination.parent)
    os.close(fd)
    temp = Path(name)
    # A placeholder is not proof that FFmpeg wrote an image.
    temp.unlink()
    try:
        yield temp
        if not temp.is_file():
            raise ValueError('Không có khung hình tại thời điểm đã chọn')
        try:
            with Image.open(temp) as image:
                image.verify()
        except OSError as exc:
            raise ValueError('Ảnh preview không hợp lệ') from exc
        os.replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)


def extract_source_frame(path: Path, time: float, destination: Path) -> Path:
    info = probe(path)
    if not math.isfinite(time) or not 0 <= time < info.duration:
        raise ValueError('Thời điểm preview nằm ngoài video')
    with frame_destination(path, destination) as temp:
        command = [str(binary_path('ffmpeg')), '-v', 'error', '-y', '-threads', '2', '-ss', str(time), '-i', str(path.resolve()), '-map', '0:v:0', '-vf', normalization_filter(info), '-frames:v', '1', '-threads', '2', str(temp.resolve())]
        try:
            subprocess.run(command, check=True, capture_output=True, timeout=30)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise ValueError('Không trích được ảnh preview') from exc
    return destination
