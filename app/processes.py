"""Cancellable native calls with timeout and unconditional child reaping."""
import subprocess
import threading
import time


class MediaCancelled(ValueError):
    pass


def run_media_process(args: list[str], timeout: float, cancel: threading.Event | None = None) -> subprocess.CompletedProcess:
    if cancel is not None and cancel.is_set():
        raise MediaCancelled('Tác vụ media đã hủy')
    with subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
        deadline = time.monotonic() + timeout
        try:
            while True:
                if cancel is not None and cancel.is_set():
                    raise MediaCancelled('Tác vụ media đã hủy')
                remaining = deadline - time.monotonic()
                if remaining <= 0: raise subprocess.TimeoutExpired(args,timeout)
                try:
                    stdout,stderr = process.communicate(timeout=min(.1,remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode,args,output=stdout,stderr=stderr)
            return subprocess.CompletedProcess(args,process.returncode,stdout,stderr)
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.communicate(timeout=3)
