"""One cancellable background export; coalesced progress and bounded diagnostics."""
from collections import deque
from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
import threading
import uuid
from .media import MediaInfo
from .models import EditOptions
from .output import OutputReservation, publish_output
from .render import prepare_render
from .resources import user_data_dir

@dataclass(frozen=True)
class WorkerEvent:
    kind: str
    progress: float | None = None
    message: str = ''
    output: Path | None = None


class RenderWorker:
    def __init__(self):
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._events = deque(maxlen=8)
        self._progress = None
        self._thread = None
        self._process = None
        self._running = False

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def _emit(self, event: WorkerEvent) -> None:
        with self._lock:
            if event.kind == 'progress':
                self._progress = event
            else:
                self._events.append(event)

    def poll(self) -> list[WorkerEvent]:
        with self._lock:
            result = ([self._progress] if self._progress else []) + list(self._events)
            self._progress = None
            self._events.clear()
            return result

    def start(self, source: Path, info: MediaInfo, options: EditOptions, reservation: OutputReservation) -> None:
        with self._lock:
            if self._running:
                raise RuntimeError('Một tác vụ xuất đang chạy')
            if source.resolve() != reservation.source:
                raise ValueError('Input không khớp xác nhận output')
            self._running = True
            self._cancel.clear()
            self._events.clear()
            self._progress = None
            self._process = None
            self._thread = threading.Thread(target=self._run, args=(source, info, options, reservation), daemon=True)
            self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def _run(self, source, info, options, reservation):
        temp = None
        reader = None
        process = None
        diagnostic = deque(maxlen=80)
        terminal = None
        try:
            root = user_data_dir()
            logs = root / 'logs'
            logs.mkdir(exist_ok=True)
            # One bounded stderr log per job; keep only the latest 10 logs.
            for old in sorted(logs.glob('render-*.log'), key=lambda p: p.stat().st_mtime, reverse=True)[9:]:
                old.unlink(missing_ok=True)
            log = logs / f'render-{uuid.uuid4().hex}.log'
            fd, name = tempfile.mkstemp(prefix='.videoeditor-render-', suffix='.mp4', dir=reservation.destination.parent)
            import os
            os.close(fd)
            temp = Path(name)
            with tempfile.TemporaryDirectory(prefix='render-', dir=root) as workspace:
                prepared = prepare_render(source, info, options, temp, Path(workspace))
                if self._cancel.is_set():
                    terminal = WorkerEvent('cancelled')
                else:
                    process = subprocess.Popen(prepared.args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', bufsize=1)
                    with self._lock:
                        self._process = process
                    def read_progress():
                        for line in process.stdout:
                            if line.startswith('out_time_us='):
                                try:
                                    progress = min(.999, max(0, int(line.split('=',1)[1]) / 1_000_000 / prepared.duration))
                                    self._emit(WorkerEvent('progress', progress))
                                except ValueError:
                                    pass
                    def read_errors():
                        # FFmpeg can produce long lines; cap each and the overall tail.
                        for line in iter(lambda: process.stderr.readline(4096), ''):
                            diagnostic.append(line[-4096:])
                    reader = threading.Thread(target=read_progress, daemon=True)
                    error_reader = threading.Thread(target=read_errors, daemon=True)
                    reader.start()
                    error_reader.start()
                    while process.poll() is None:
                        if self._cancel.wait(.05):
                            process.terminate()
                            try:
                                process.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait(timeout=3)
                            break
                    reader.join(timeout=5)
                    error_reader.join(timeout=5)
                    process.stdout.close()
                    process.stderr.close()
                    log.write_text(''.join(diagnostic), encoding='utf-8')
                    if self._cancel.is_set():
                        terminal = WorkerEvent('cancelled')
                    elif process.returncode != 0:
                        terminal = WorkerEvent('error', message='FFmpeg xuất thất bại; xem log: ' + str(log) + '\n' + ''.join(diagnostic)[-2000:])
                    else:
                        output = publish_output(temp, reservation)
                        terminal = WorkerEvent('completed', 1, output=output)
        except Exception as exc:
            terminal = WorkerEvent('cancelled' if self._cancel.is_set() else 'error', message=str(exc))
        finally:
            cleanup_errors = []
            try:
                if process is not None and process.poll() is None:
                    try:
                        process.kill()
                        process.wait(timeout=5)
                    except Exception as exc:
                        cleanup_errors.append(f'Không dừng được FFmpeg: {exc}')
                if temp is not None:
                    try:
                        temp.unlink(missing_ok=True)
                    except OSError as exc:
                        cleanup_errors.append(f'Không xóa được file tạm {temp}: {exc}')
            finally:
                if cleanup_errors:
                    previous = terminal.message if terminal else ''
                    terminal = WorkerEvent('error', message='\n'.join([previous, *cleanup_errors]).strip(), output=terminal.output if terminal else None)
                with self._lock:
                    self._running = False
                    self._process = None
                    self._events.append(terminal or WorkerEvent('error', message='Tác vụ không có kết quả'))
