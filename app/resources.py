"""Resolve bundled tools and writable user data without changing process cwd."""
import os
from pathlib import Path
import shutil
import sys


def resource_root() -> Path:
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def binary_path(name: str) -> Path:
    if name not in ('ffmpeg', 'ffprobe'):
        raise ValueError('Unsupported media binary')
    candidate = resource_root() / 'tools' / (name + ('.exe' if os.name == 'nt' else ''))
    if candidate.is_file():
        return candidate
    if not getattr(sys, 'frozen', False):
        system = shutil.which(name)
        if system:
            return Path(system)
    raise FileNotFoundError(f'Không tìm thấy {name}; hãy chạy script setup/build')


def user_data_dir() -> Path:
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))
    path = base / 'VideoEditor'
    path.mkdir(parents=True, exist_ok=True)
    return path
