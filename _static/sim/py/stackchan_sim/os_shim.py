"""Route /flash and /sd paths in os.* calls to the mounted files dir.

open() is already mapped by the runners; this covers listdir/stat/remove/
mkdir/rename & co so firmware filesystem code works unchanged. On
MicroPython the builtin module cannot be patched, so a delegating wrapper
is planted in sys.modules; on CPython the functions are patched in place.
Non-device paths pass through untouched (bridge.map_path is a no-op for
them), so emulator-internal code is unaffected.
"""

import os as _os
import sys

from stackchan_sim import bridge as _bridge_mod

_PATH_FUNCS = ("listdir", "ilistdir", "stat", "statvfs", "remove",
               "unlink", "rmdir", "mkdir", "makedirs", "chdir")


def _wrap_path_func(real):
    def wrapped(path=".", *a, **k):
        return real(_bridge_mod.get().map_path(path), *a, **k)
    return wrapped


def _wrap_rename(real):
    def wrapped(src, dst):
        map_path = _bridge_mod.get().map_path
        return real(map_path(src), map_path(dst))
    return wrapped


class _OsModule:
    """Delegating stand-in for the os module (MicroPython runtime)."""

    def __getattr__(self, name):
        real = getattr(_os, name)
        if name in _PATH_FUNCS:
            return _wrap_path_func(real)
        if name == "rename":
            return _wrap_rename(real)
        return real


def install():
    if sys.implementation.name == "micropython":
        wrapper = _OsModule()
        sys.modules["os"] = wrapper
        sys.modules["uos"] = wrapper
    else:
        for name in _PATH_FUNCS:
            real = getattr(_os, name, None)
            if real is not None and not hasattr(real, "_esp_emu_wrapped"):
                wrapped = _wrap_path_func(real)
                wrapped._esp_emu_wrapped = True
                setattr(_os, name, wrapped)
        if not hasattr(_os.rename, "_esp_emu_wrapped"):
            wrapped = _wrap_rename(_os.rename)
            wrapped._esp_emu_wrapped = True
            _os.rename = wrapped
        sys.modules["uos"] = _os
