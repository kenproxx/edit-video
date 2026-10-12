"""Build a shared FFmpeg pipeline for previews and video export."""
from dataclasses import dataclass
import math
from pathlib import Path
import subprocess
import tempfile
import threading
from .processes import run_media_process
from .media import MediaInfo, normalization_filter, frame_destination
from .models import EditOptions, validate_options
from .overlays import write_text, write_logo
from .resources import binary_path
from .timing import source_interval, trimmed_duration

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
    if options.trim_start or options.trim_end is not None:
        start,end = source_interval(options,info.duration)
        filters += ['setpts=PTS-STARTPTS',f'trim=start={start:.9g}:end={end:.9g}']
    filters.append(f'setpts=(PTS-STARTPTS)/{options.speed:g}')
    filters.append(f'fps={info.fps:.9g}:start_time=0:round=near')
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


def preview_size(info: MediaInfo, options: EditOptions) -> tuple[int,int]:
    width,height=(options.crop.width,options.crop.height) if options.crop else (info.width//2*2,info.height//2*2)
    factor=min(1,960/width,540/height)
    return max(2,int(width*factor)//2*2),max(2,int(height*factor)//2*2)


def prepare_render(source: Path, info: MediaInfo, options: EditOptions, destination: Path, workspace: Path, preview: bool = False) -> PreparedRender:
    args, graph = _pipeline(source, info, options, workspace)
    if preview:
        width,height=preview_size(info,options)
        graph=graph.replace('format=yuv420p[vout]',f'scale={width}:{height},setsar=1,format=yuv420p[vout]')
    if options.audio_path is not None:
        audio_path=options.audio_path.resolve()
        if audio_path==destination.resolve() or (destination.exists() and audio_path.samefile(destination)):
            raise ValueError('Output không được trùng file âm thanh chèn')
        # Video/overlay inputs are already present; use the actual next input index.
        audio_index=args.count('-i')
        if options.audio_loop: args += ['-stream_loop','-1']
        args += ['-threads','2','-i',str(audio_path)]
    start,end = source_interval(options,info.duration)
    duration = trimmed_duration(options,info.duration)
    has_audio = info.has_audio and end > info.audio_offset
    if has_audio:
        if options.trim_start or options.trim_end is not None:
            astart,aend = max(0,start-info.audio_offset),max(0,end-info.audio_offset)
            trim = f'atrim=start={astart:.9g}:end={aend:.9g},'
        else:
            trim = f'atrim=start={-info.audio_offset:.9g},' if info.audio_offset < 0 else ''
        offset = max(0, info.audio_offset-start) / options.speed
        materialize=preview or options.audio_path is not None
        source_label='original' if options.audio_path is not None else 'aout'
        gain=f',volume={options.source_volume:.9g}'
        if materialize:
            # Audio-only playback starts at zero: include the source delay as
            # actual silence, rather than relying on container timestamps.
            graph += f';[0:a:0]{trim}asetpts=PTS-STARTPTS,{_audio_speed(options.speed)},adelay={offset*1000:.9g}:all=1,apad=whole_dur={duration:.9g},asetpts=N/SR/TB{gain}[{source_label}]'
        else:
            graph += f';[0:a:0]{trim}asetpts=PTS-STARTPTS,{_audio_speed(options.speed)},asetpts=PTS+{offset:.9g}/TB{gain}[{source_label}]'
    if options.audio_path is not None:
        graph += f';[{audio_index}:a:0]asetpts=PTS-STARTPTS,volume={options.added_volume:.9g},apad=whole_dur={duration:.9g},atrim=duration={duration:.9g},asetpts=N/SR/TB[added]'
        if has_audio:
            # Negotiate stereo before mixing: a mono original must not collapse
            # stereo music (opposite-phase channels can cancel completely).
            graph += ';[original]aformat=channel_layouts=stereo[original_stereo];[added]aformat=channel_layouts=stereo[added_stereo];[original_stereo][added_stereo]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[aout]'
        else:
            graph += ';[added]anull[aout]'
    args += ['-filter_complex_threads', '2', '-filter_complex', graph, '-map', '[vout]']
    if has_audio or options.audio_path is not None:
        args += ['-map', '[aout]', '-c:a', 'aac', '-b:a', '192k']
    else:
        args += ['-an']
    args += ['-c:v', 'libx264', '-threads', '2', '-crf', '28' if preview else '20', '-preset', 'ultrafast' if preview else 'medium', '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough', '-t', f'{duration:.9g}', '-map_metadata', '-1', '-map_chapters', '-1', '-metadata:s:v:0', 'rotate=0', '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats', str(destination.resolve())]
    return PreparedRender(args, duration)


def render_preview(source: Path, info: MediaInfo, options: EditOptions, time: float, destination: Path, cancel: threading.Event | None = None) -> Path:
    if not math.isfinite(time) or not 0 <= time < trimmed_duration(options,info.duration):
        raise ValueError('Thời điểm preview nằm ngoài video')
    with tempfile.TemporaryDirectory(prefix='video-preview-') as directory, frame_destination(source, destination) as temp:
        args, graph = _pipeline(source, info, options, Path(directory))
        # Output seek preserves output-timeline intro enable and the same filter graph.
        args += ['-filter_complex_threads', '2', '-filter_complex', graph, '-map', '[vout]', '-an', '-ss', f'{time:.9g}', '-frames:v', '1', '-threads', '2', str(temp.resolve())]
        try:
            run_media_process(args,60,cancel)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            detail = getattr(exc, 'stderr', b'') or b''
            raise ValueError('Không render được preview: ' + detail.decode('utf-8', errors='replace')[-2000:]) from exc
    return destination
