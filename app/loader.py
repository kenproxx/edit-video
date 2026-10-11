"""Bounded asynchronous media probing, without Tk calls or an executor backlog."""
from dataclasses import dataclass
from pathlib import Path
import threading
from .media import MediaInfo, probe

@dataclass(frozen=True)
class LoadResult:
    generation: int
    path: Path
    info: MediaInfo | None = None
    error: str = ''


class MediaLoader:
    def __init__(self):
        self._condition = threading.Condition()
        self._generation = 0
        self._pending = self._result = None
        self._closed = False
        self._active = False
        self._cancel_active = None
        self._thread = threading.Thread(target=self._run,daemon=True)
        self._thread.start()

    @property
    def busy(self):
        with self._condition: return self._active or self._pending is not None

    def request(self,path):
        with self._condition:
            if self._closed: raise RuntimeError("Media loader đã đóng")
            if self._cancel_active is not None: self._cancel_active.set()
            self._generation += 1
            self._pending = (self._generation,path)
            self._result = None
            self._condition.notify()
            return self._generation

    def poll(self):
        with self._condition:
            result,self._result = self._result,None
            return [result] if result else []

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda:self._pending is not None or self._closed)
                if self._closed: return
                generation,path = self._pending
                self._pending = None
                self._active = True
                cancel = self._cancel_active = threading.Event()
            try: result = LoadResult(generation,path,probe(path,cancel=cancel))
            except Exception as exc: result = LoadResult(generation,path,error=str(exc))
            with self._condition:
                self._active = False
                self._cancel_active = None
                if generation == self._generation and not self._closed: self._result = result

    def close(self):
        with self._condition:
            self._closed = True
            if self._cancel_active is not None: self._cancel_active.set()
            self._pending = self._result = None
            self._condition.notify()
        self._thread.join(timeout=.1)
