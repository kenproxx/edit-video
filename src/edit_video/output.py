from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class OutputTarget:
    source: Path
    destination: Path
    overwrite: bool

def validate_target(target: OutputTarget) -> None:
    source,dest=target.source.resolve(),target.destination.resolve()
    same=os.path.normcase(str(source))==os.path.normcase(str(dest))
    if source.exists() and dest.exists(): same=same or os.path.samefile(source,dest)
    if same: raise ValueError('Không được ghi đè video nguồn. Hãy chọn thư mục hoặc tên khác.')
    if dest.exists() and not target.overwrite: raise FileExistsError(f'File đã tồn tại: {dest.name}')
    if not dest.parent.is_dir(): raise ValueError('Thư mục xuất không tồn tại.')

def publish(temporary: Path, target: OutputTarget) -> None:
    validate_target(target)
    if target.overwrite:
        os.replace(temporary,target.destination)
    else:
        # Same-volume hard-link creation is atomic and fails if destination appears.
        os.link(temporary,target.destination)
        temporary.unlink()
