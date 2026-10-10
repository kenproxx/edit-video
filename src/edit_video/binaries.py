from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import sys
import subprocess

@dataclass(frozen=True)
class Binaries:
    ffmpeg: Path
    ffprobe: Path

def process_options():
    return {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}

def resolve_binaries() -> Binaries:
    root = Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[2]))
    bundled = root/'bin'
    configured = os.environ.get('EDIT_VIDEO_FFMPEG_DIR')
    suffix = '.exe' if os.name == 'nt' else ''
    paths = []
    for name in ('ffmpeg','ffprobe'):
        candidates = [bundled/(name+suffix)]
        if not getattr(sys,'frozen',False):
            if configured: candidates.append(Path(configured)/(name+suffix))
            found = shutil.which(name)
            if found: candidates.append(Path(found))
        selected = next((p for p in candidates if p.is_file()),None)
        if not selected: raise FileNotFoundError(f'Không tìm thấy {name}. Hãy giải nén đầy đủ bộ ứng dụng.')
        paths.append(selected)
    return Binaries(*paths)
