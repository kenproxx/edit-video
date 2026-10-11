"""Transactional output publication with atomic no-replace links.

Never replace a path that could have appeared since confirmation. For explicit
replacement, move the confirmed old file aside, verify its identity again, then
link the new video into the vacant name. A conflicting external writer keeps its
file; if restoration is blocked, retain the old file at the reported backup path.
Filesystems lacking hard links fail closed, without reverting to unsafe rename.
"""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
import tempfile

Fingerprint = tuple[int, int, int, int]

@dataclass(frozen=True)
class OutputReservation:
    source: Path
    destination: Path
    expected: Fingerprint | None
    overwrite: bool


def _fingerprint(path: Path) -> Fingerprint | None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('Đích xuất phải là file thường, không phải link/thư mục')
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def reserve_output(source: Path, destination: Path, overwrite: bool) -> OutputReservation:
    source = source.resolve(strict=True)
    if not source.is_file():
        raise ValueError('Input phải là file video')
    try:
        parent = destination.parent.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError('Thư mục xuất không tồn tại') from exc
    if not parent.is_dir() or destination.suffix.lower() != '.mp4':
        raise ValueError('Chọn thư mục xuất có sẵn và tên file MP4')
    name = destination.name
    reserved_names = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1,10)), *(f'LPT{i}' for i in range(1,10))}
    if any(c in name for c in '<>:"/\\|?*') or name.endswith((' ', '.')) or name.split('.')[0].upper() in reserved_names:
        raise ValueError('Tên output không hợp lệ trên Windows')
    target = parent / name
    if os.path.normcase(str(target)) == os.path.normcase(str(source)) or (target.exists() and os.path.samefile(source, target)):
        raise ValueError('Không được ghi đè video nguồn')
    expected = _fingerprint(target)
    if expected is not None and not overwrite:
        raise FileExistsError('File đích đã tồn tại; cần xác nhận ghi đè')
    # Actual writable-directory check, not just a permission-bit prediction.
    with tempfile.NamedTemporaryFile(prefix='.videoeditor-check-', dir=parent):
        pass
    return OutputReservation(source, target, expected, overwrite)


def _restore_backup(backup: Path, target: Path) -> None:
    try:
        os.link(backup, target)
    except OSError as exc:
        raise FileExistsError(f'File đích đã thay đổi. Bản cũ được giữ tại: {backup}') from exc
    backup.unlink()


def publish_output(temp: Path, reservation: OutputReservation) -> Path:
    target = reservation.destination
    if temp.parent.resolve() != target.parent or not temp.is_file():
        raise ValueError('File render tạm cần nằm trong thư mục đích')
    if temp.resolve() in (target, reservation.source) or os.path.samefile(temp, reservation.source):
        raise ValueError('File render tạm không được trùng input/đích')
    digest = hashlib.sha256(os.fsencode(target)).hexdigest()[:24]
    lock = target.parent / f'.videoeditor-lock-{digest}'
    # Coordinate our exporters; external path writers are caught by no-replace link.
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    backup = None
    moved = False
    try:
        if _fingerprint(target) != reservation.expected:
            raise FileExistsError('File đích đã thay đổi sau khi xác nhận')
        if reservation.expected is not None:
            if not reservation.overwrite:
                raise FileExistsError('Chưa cho phép ghi đè')
            handle, name = tempfile.mkstemp(prefix='.videoeditor-backup-', suffix='.mp4', dir=target.parent)
            os.close(handle)
            backup = Path(name)
            try:
                os.replace(target, backup)
                moved = True
            except FileNotFoundError as exc:
                raise FileExistsError('File đích đã bị chuyển/xóa') from exc
            if _fingerprint(backup) != reservation.expected:
                raise FileExistsError('File đích đã đổi trong lúc chuẩn bị xuất')
        # Atomic O_EXCL-like publication, including on Windows NTFS. Never os.replace(temp,target).
        os.link(temp, target)
        temp.unlink()
        if backup:
            backup.unlink()
            moved = False
        return target
    except BaseException:
        if moved and backup is not None:
            _restore_backup(backup, target)
            moved = False
        raise
    finally:
        if backup is not None and not moved:
            backup.unlink(missing_ok=True)
        os.close(fd)
        lock.unlink(missing_ok=True)
