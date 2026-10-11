"""Build a shared FFmpeg pipeline for previews and video export."""
from dataclasses import dataclass
import math
from pathlib import Path
import subprocess
import tempfile
from .media import MediaInfo, normalization_filter
from .models import EditOptions, validate_options
from .overlays import write_text, write_logo
from .resources import binary_path

@dataclass(frozen=True)
class PreparedRender:
    args: list[str]
    duration: float


def _audio_speed(speed: float) -> str:
    factors = []
    while speed < .5:
        factors.append(.5)
        speed /= .5
    while speed > 2:
        factors.append(2)
        speed /= 2
    factors.append(speed)
    return ','.join(f'atempo={value:g}' for value in factors)


def _pipeline(source: Path, info: MediaInfo, options: EditOptions, workspace: Path) -> tuple[list[str], str]:
    if info.is_hdr:
        raise ValueError('HDR chưa được hỗ trợ')
    validate_options(options, info.width, info.height, info.duration)
    workspace.mkdir(parents=True, exist_ok=True)
    args = [str(binary_path('ffmpeg')), '-hide_banner', '-loglevel', 'error', '-nostdin', '-y', '-threads', '2', '-i', str(source.resolve())]
    filters = [normalization_filter(info), 'format=yuv444p']
    if options.flip_horizontal:
        filters.append('hflip')
    if options.flip_vertical:
        filters.append('vflip')
    if options.crop:
        r = options.crop
        filters.append(f'crop={r.width}:{r.height}:{r.x}:{r.y}:exact=1')
    else:
        filters.append(f'crop={info.width // 2 * 2}:{info.height // 2 * 2}:0:0:exact=1')
    filters.append(f'setpts=(PTS-STARTPTS)/{options.speed:g}')
    graph = [f'[0:v:0]{",".join(filters)}[v0]']
    label = 'v0'
    if options.blur:
        r = options.blur
        graph += [f'[{label}]split=2[base][area]', f'[area]crop={r.width}:{r.height}:{r.x}:{r.y}:exact=1,gblur=sigma={options.blur_strength}[blur]', f'[base][blur]overlay=x={r.x}:y={r.y}:format=auto[vblur]']
        label = 'vblur'
    index = 1
    for kind, overlay in (('logo', options.logo), ('watermark', options.watermark), ('intro', options.intro)):
        if overlay is None or (kind != 'logo' and not overlay.text.strip()):
            continue
        asset = workspace / f'{kind}.png'
        if kind == 'logo':
            write_logo(overlay, asset)
        else:
            write_text(overlay, asset)
        args += ['-i', str(asset.resolve())]
        enable = f":enable='lt(t,{options.intro_duration:g})'" if kind == 'intro' else ''
        graph.append(f'[{label}][{index}:v:0]overlay=x={overlay.x}:y={overlay.y}:format=auto:eof_action=repeat{enable}[v{index}]')
        label = f'v{index}'
        index += 1
    graph.append(f'[{label}]format=yuv420p[vout]')
    return args, ';'.join(graph)


def prepare_render(source: Path, info: MediaInfo, options: EditOptions, destination: Path, workspace: Path) -> PreparedRender:
    args, graph = _pipeline(source, info, options, workspace)
    duration = info.duration / options.speed
    if info.has_audio:
        graph += f';[0:a:0]asetpts=PTS-STARTPTS,{_audio_speed(options.speed)}[aout]'
    args += ['-filter_complex_threads', '2', '-filter_complex', graph, '-map', '[vout]']
    if info.has_audio:
        args += ['-map', '[aout]', '-c:a', 'aac', '-b:a', '192k']
    else:
        args += ['-an']
    args += ['-c:v', 'libx264', '-threads', '2', '-crf', '20', '-preset', 'medium', '-pix_fmt', 'yuv420p', '-r', f'{info.fps:.9g}', '-t', f'{duration:.9g}', '-map_metadata', '-1', '-map_chapters', '-1', '-metadata:s:v:0', 'rotate=0', '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats', str(destination.resolve())]
    return PreparedRender(args, duration)


def render_preview(source: Path, info: MediaInfo, options: EditOptions, time: float, destination: Path) -> Path:
    if not math.isfinite(time) or not 0 <= time < info.duration / options.speed:
        raise ValueError('Thời điểm preview nằm ngoài video')
    with tempfile.TemporaryDirectory(prefix='video-preview-') as directory:
        args, graph = _pipeline(source, info, options, Path(directory))
        # Output seek preserves output-timeline intro enable and the same filter graph.
        args += ['-filter_complex_threads', '2', '-filter_complex', graph, '-map', '[vout]', '-an', '-ss', f'{time:.9g}', '-frames:v', '1', '-threads', '2', str(destination.resolve())]
        try:
            subprocess.run(args, capture_output=True, check=True, timeout=60)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            detail = getattr(exc, 'stderr', b'') or b''
            raise ValueError('Không render được preview: ' + detail.decode('utf-8', errors='replace')[-2000:]) from exc
    if not destination.is_file():
        raise ValueError('Không có khung hình preview')
    return destination
