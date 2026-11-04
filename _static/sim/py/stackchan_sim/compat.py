"""Runtime compatibility layer for the in-browser simulator.

Adapted from esp-emulator's ``compat.py``. The browser build of
MicroPython (WebAssembly, running in a Web Worker) is single threaded:
locks are no-ops and timers are cooperative (they fire from the bridge
whenever the user program sleeps or calls ``M5.update()``).
"""

import sys
import time as _real_time

IS_MICROPYTHON = True


def monotonic():
    return _real_time.time_ns() / 1_000_000_000


class _NoLock:
    def acquire(self, *args):
        return True

    def release(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def Lock():
    return _NoLock()


def RLock():
    return _NoLock()


def start_thread(fn, *args):
    raise OSError("threads are not available in the simulator")


def print_exception(exc, file=None):
    sys.print_exception(exc, file or sys.stderr)


def b64encode_str(data):
    import binascii
    return binascii.b2a_base64(data)[:-1].decode()


def b64decode(s):
    import binascii
    return binascii.a2b_base64(s)


class Timer:
    """One-shot timer scheduled on the bridge's cooperative loop."""

    def __init__(self, interval_s, callback):
        self._interval = interval_s
        self._callback = callback
        self.due = 0.0
        self.cancelled = False

    def start(self):
        from stackchan_sim import bridge
        self.due = monotonic() + self._interval
        bridge.get().add_timer(self)

    def cancel(self):
        self.cancelled = True

    def fire(self):
        if not self.cancelled:
            self.cancelled = True
            self._callback()


class SimpleQueue:
    def __init__(self, maxsize=0):
        self._items = []
        self._maxsize = maxsize

    def put(self, item):
        if self._maxsize and len(self._items) >= self._maxsize:
            self._items.pop(0)
        self._items.append(item)

    def get_nowait(self):
        return self._items.pop(0) if self._items else None


def hard_exit(code=0):
    raise SystemExit(code)


# ---- paths (MicroPython has no os.path) ----

def path_join(*parts):
    out = ""
    for part in parts:
        if not part:
            continue
        if part.startswith("/"):
            out = part
        elif out:
            out = out.rstrip("/") + "/" + part
        else:
            out = part
    return out


def path_abs(path):
    import os
    if path.startswith("/"):
        return path
    return path_join(os.getcwd(), path)


def path_dirname(path):
    i = path.rstrip("/").rfind("/")
    return path[:i] if i > 0 else ("/" if path.startswith("/") else "")


def path_basename(path):
    return path.rstrip("/").rsplit("/", 1)[-1]


def _stat_mode(path):
    import os
    try:
        return os.stat(path)[0]
    except OSError:
        return 0


def path_isdir(path):
    return bool(_stat_mode(path) & 0x4000)


def path_isfile(path):
    return bool(_stat_mode(path) & 0x8000)


def create_raster(width, height):
    from stackchan_sim.raster_fb import FbRaster
    return FbRaster(width, height)
