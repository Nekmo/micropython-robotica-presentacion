"""Minimal app framework, in the spirit of mooncake.

Apps implement ``on_create/on_open/on_running/on_close``.  The launcher
is a special app: it is opened at boot and re-opened whenever the active
app closes (the original firmware warm-reboots instead).

Touch input is polled via ``M5.Touch`` (``TapTracker``) instead of LVGL
click events, because the emulator's lvgl shim has no event callbacks.
"""

import lvgl as lv

from .. import lvcompat as lvc


class App(object):
    name = 'APP'
    theme_color = 0xFFFFFF

    def __init__(self):
        self._manager = None

    def close(self):
        if self._manager is not None:
            self._manager.request_close()

    def on_create(self):
        pass

    def on_open(self):
        pass

    def on_running(self):
        pass

    def on_close(self):
        pass


class Mooncake(object):
    def __init__(self):
        self._apps = []
        self._launcher = None
        self._current = None
        self._close_requested = False

    def install_launcher(self, launcher):
        launcher._manager = self
        self._launcher = launcher
        launcher.on_create()

    def install_app(self, app):
        app._manager = self
        self._apps.append(app)
        app.on_create()
        return len(self._apps) - 1

    def apps(self):
        return self._apps

    def start(self):
        self._current = self._launcher
        self._launcher.on_open()

    def open_app(self, index):
        if index < 0 or index >= len(self._apps):
            return
        if self._current is not None:
            self._current.on_close()
        self._current = self._apps[index]
        self._current.on_open()

    def request_close(self):
        self._close_requested = True

    def update(self):
        if self._close_requested:
            self._close_requested = False
            if self._current is not None and self._current is not self._launcher:
                self._current.on_close()
                self._current = self._launcher
                self._launcher.on_open()
        if self._current is not None:
            self._current.on_running()


_mooncake = None


def get_mooncake():
    global _mooncake
    if _mooncake is None:
        _mooncake = Mooncake()
    return _mooncake


# ------------------------------------------------------------- touch input

class TapTracker(object):
    """Reports (x, y) once when a touch press begins.

    Starts primed so a press already in progress when the tracker is
    (re)armed — e.g. the tap that opened the app — is not re-reported.
    """

    def __init__(self):
        self._was_down = True

    def rearm(self):
        self._was_down = True

    def poll(self):
        try:
            import M5
            down = M5.Touch.getCount() > 0
            if down and not self._was_down:
                self._was_down = True
                return (M5.Touch.getX(), M5.Touch.getY())
            if not down:
                self._was_down = False
        except Exception:
            pass
        return None


_HOME_RECT = (110, 212, 210, 240)  # generous hit box around the pill


def in_home_region(x, y):
    return _HOME_RECT[0] <= x <= _HOME_RECT[2] and \
        _HOME_RECT[1] <= y <= _HOME_RECT[3]


# ------------------------------------------------- common home indicator

class HomeIndicator(object):
    """Bottom pill; tap detection is done by the apps via TapTracker."""

    def __init__(self, color=0xFFFFFF):
        self._obj = lvc.container(lv.screen_active())
        self._obj.set_size(72, 8)
        self._obj.set_style_radius(4, 0)
        lvc.bg(self._obj, color, 140)
        lvc.align(self._obj, lv.ALIGN.BOTTOM_MID, 0, -4)
        try:
            self._obj.move_foreground()
        except Exception:
            pass

    def destroy(self):
        lvc.delete(self._obj)
        self._obj = None
