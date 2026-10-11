"""A single background renderer with one replaceable pending request.

Results carry monotonically increasing generations. The controller never calls
Tk; only the UI's main-thread polling touches widgets. No stale image survives
invalidation, and obsolete queued work is discarded before expensive FFmpeg.
"""
from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
import threading
from PIL import Image
from .media import MediaInfo
from .models import EditOptions
from .render import render_preview
from .resources import user_data_dir

@dataclass
class PreviewResult:
    generation: int
    image: Image.Image | None = None
    error: str = ''


class PreviewController:
    def __init__(self):
        self.directory = Path(tempfile.mkdtemp(prefix='preview-', dir=user_data_dir()))
        self._condition = threading.Condition()
        self._generation = 0
        self._pending = None
        self._result = None
        self._active = False
        self._cancel_active = None
        self._closed = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    @property
    def busy(self) -> bool:
        with self._condition:
            return self._active or self._pending is not None

    def request(self, source: Path, info: MediaInfo, options: EditOptions, time: float) -> int:
        with self._condition:
            if self._closed:
                raise RuntimeError('Preview controller đã đóng')
            self._invalidate_locked()
            self._pending = (self._generation, source, info, options, time)
            self._condition.notify()
            return self._generation

    def _invalidate_locked(self):
        self._generation += 1
        if self._cancel_active is not None: self._cancel_active.set()
        if self._result and self._result.image:
            self._result.image.close()
        self._result = None
        self._pending = None

    def invalidate(self) -> int:
        with self._condition:
            self._invalidate_locked()
            return self._generation

    def poll(self) -> list[PreviewResult]:
        with self._condition:
            if self._result is None:
                return []
            result, self._result = self._result, None
            return [result]

    def _run(self):
        try:
            while True:
                with self._condition:
                    self._condition.wait_for(lambda: self._closed or self._pending is not None)
                    if self._closed:
                        return
                    generation, source, info, options, time = self._pending
                    self._pending = None
                    self._active = True
                    cancel = self._cancel_active = threading.Event()
                destination = self.directory / f'frame-{generation}.png'
                result = PreviewResult(generation)
                try:
                    render_preview(source, info, options, time, destination, cancel=cancel)
                    with Image.open(destination) as image:
                        result.image = image.convert('RGB')
                except Exception as exc:
                    result.error = str(exc)
                finally:
                    try:
                        destination.unlink(missing_ok=True)
                    except OSError as exc:
                        if result.image:
                            result.image.close();result.image = None
                        result.error = f'Không dọn được ảnh preview {destination}: {exc}'
                with self._condition:
                    self._active = False
                    self._cancel_active = None
                    if generation == self._generation and not self._closed:
                        self._result = result
                    elif result.image:
                        result.image.close()
        finally:
            shutil.rmtree(self.directory, ignore_errors=True)

    def close(self) -> None:
        with self._condition:
            self._closed = True
            self._invalidate_locked()
            self._condition.notify_all()
        # Cancellation is signaled above; renderer thread owns child reaping
        # and directory cleanup. UI waits for busy=False before destroying Tk.
        self._thread.join(timeout=.1)
