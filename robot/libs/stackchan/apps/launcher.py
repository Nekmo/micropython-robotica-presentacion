"""App launcher — port of apps/app_launcher.

Shows one tile per installed app (theme colour + name).  After 30 s of
inactivity it starts the DVD-bounce screensaver with the little
Stack-chan logo face, exactly like the original.
"""

import lvgl as lv

from .. import lvcompat as lvc
from ..uitk import Random
from ..hal import get_hal
from . import App, TapTracker

_SCREENSAVER_TIMEOUT_MS = 30000

# screensaver.cpp constants
_LOGO_SIZE = (64, 48)
_LOGO_COLORS = (0xFFFFFF, 0xFFFA01, 0xFF8300, 0x00FEFF,
                0xFF2600, 0xBE00FF, 0x0026FF, 0xFF008B)
_LOGO_SPEED = 110.0  # px/s

_TILE_W = 88
_TILE_H = 110
_TILE_GAP = 12
_TILE_CY = 14  # vertical offset of the tile row from screen centre


class Screensaver(object):
    def __init__(self):
        self._hal = get_hal()
        self._screen = lvc.container(lv.screen_active())
        self._screen.set_size(320, 240)
        lvc.bg(self._screen, 0x000000)
        lvc.align_center(self._screen)

        self._logo = lvc.container(self._screen)
        self._logo.set_size(_LOGO_SIZE[0], _LOGO_SIZE[1])
        lvc.bg(self._logo, _LOGO_COLORS[0])

        for ex in (-15, 15):
            eye = lvc.container(self._logo)
            eye.set_style_radius(lvc.RADIUS_CIRCLE, 0)
            lvc.bg(eye, 0x000000)
            eye.set_size(6, 6)
            lvc.align_center(eye, ex, -3)

        mouth = lvc.container(self._logo)
        lvc.bg(mouth, 0x000000)
        mouth.set_size(18, 2)
        lvc.align_center(mouth, 0, 5)

        random = Random.get_instance()
        dx = random.get_float(0.3, 0.7)
        dy = random.get_float(0.3, 0.7)
        norm = (dx * dx + dy * dy) ** 0.5
        self._dir = [dx / norm, dy / norm]
        self._pos = [160.0 - _LOGO_SIZE[0] / 2, 120.0 - _LOGO_SIZE[1] / 2]
        self._color_index = 0
        self._last_tick = self._hal.millis()
        self._place()

    def _place(self):
        self._logo.set_pos(int(self._pos[0]), int(self._pos[1]))

    def update(self):
        now = self._hal.millis()
        dt = (now - self._last_tick) / 1000.0
        self._last_tick = now
        if dt <= 0 or dt > 0.5:
            return

        self._pos[0] += self._dir[0] * _LOGO_SPEED * dt
        self._pos[1] += self._dir[1] * _LOGO_SPEED * dt

        collided = False
        max_x = 320 - _LOGO_SIZE[0]
        max_y = 240 - _LOGO_SIZE[1]
        if self._pos[0] <= 0:
            self._pos[0] = 0
            self._dir[0] = abs(self._dir[0])
            collided = True
        elif self._pos[0] >= max_x:
            self._pos[0] = max_x
            self._dir[0] = -abs(self._dir[0])
            collided = True
        if self._pos[1] <= 0:
            self._pos[1] = 0
            self._dir[1] = abs(self._dir[1])
            collided = True
        elif self._pos[1] >= max_y:
            self._pos[1] = max_y
            self._dir[1] = -abs(self._dir[1])
            collided = True

        if collided:
            self._color_index = (self._color_index + 1) % len(_LOGO_COLORS)
            lvc.bg(self._logo, _LOGO_COLORS[self._color_index])

        self._place()

    def destroy(self):
        lvc.delete(self._screen)
        self._screen = None


class AppLauncher(App):
    name = 'LAUNCHER'

    def __init__(self):
        App.__init__(self)
        self._hal = get_hal()
        self._panel = None
        self._tiles = []
        self._tile_rects = []   # screen-space hit boxes
        self._screensaver = None
        self._screensaver_timecount = 0
        self._last_activity = 0
        self._taps = TapTracker()

    # -- view -----------------------------------------------------------
    def on_open(self):
        self._last_activity = self._hal.millis()

        self._panel = lvc.container(lv.screen_active())
        self._panel.set_size(320, 240)
        lvc.bg(self._panel, 0x101018)
        lvc.align_center(self._panel)

        title = lv.label(self._panel)
        title.set_text('Stack-chan')
        title.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
        font = getattr(lv, 'font_montserrat_22', None) \
            or getattr(lv, 'font_montserrat_16', None)
        if font is not None:
            try:
                title.set_style_text_font(font, 0)
            except Exception:
                pass
        lvc.align(title, lv.ALIGN.TOP_MID, 0, 16)

        apps = self._manager.apps()
        count = len(apps)
        total_w = count * _TILE_W + (count - 1) * _TILE_GAP
        start_cx = -(total_w // 2) + _TILE_W // 2

        self._tiles = []
        self._tile_rects = []
        for index, app in enumerate(apps):
            cx = start_cx + index * (_TILE_W + _TILE_GAP)

            tile = lvc.container(self._panel)
            tile.set_size(_TILE_W, _TILE_H)
            tile.set_style_radius(16, 0)
            lvc.bg(tile, app.theme_color)
            lvc.align_center(tile, cx, _TILE_CY)

            # tiny face on the tile
            for ex in (-14, 14):
                eye = lvc.container(tile)
                eye.set_style_radius(lvc.RADIUS_CIRCLE, 0)
                lvc.bg(eye, 0x000000)
                eye.set_size(10, 10)
                lvc.align_center(eye, ex, -18)
            mouth = lvc.container(tile)
            lvc.bg(mouth, 0x000000)
            mouth.set_style_radius(2, 0)
            mouth.set_size(26, 4)
            lvc.align_center(mouth, 0, -4)

            label = lv.label(tile)
            label.set_text(app.name)
            label.set_style_text_color(lv.color_hex(0x000000), 0)
            lvc.align(label, lv.ALIGN.BOTTOM_MID, 0, -10)

            # hit box in screen coordinates
            left = 160 + cx - _TILE_W // 2
            top = 120 + _TILE_CY - _TILE_H // 2
            self._tile_rects.append((left, top, left + _TILE_W, top + _TILE_H))
            self._tiles.append(tile)

    def on_running(self):
        tap = self._taps.poll()

        if tap is not None:
            self._last_activity = self._hal.millis()
            if self._screensaver is not None:
                self._screensaver.destroy()
                self._screensaver = None
                return
            x, y = tap
            for index, rect in enumerate(self._tile_rects):
                if rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]:
                    self._manager.open_app(index)
                    return

        self._screensaver_update()

    def on_close(self):
        if self._screensaver is not None:
            self._screensaver.destroy()
            self._screensaver = None
        for tile in self._tiles:
            lvc.delete(tile)
        self._tiles = []
        self._tile_rects = []
        lvc.delete(self._panel)
        self._panel = None

    # -- screensaver -------------------------------------------------------
    def _screensaver_update(self):
        now = self._hal.millis()

        if self._is_user_active():
            self._last_activity = now
            if self._screensaver is not None:
                self._screensaver.destroy()
                self._screensaver = None
            return

        if now - self._last_activity >= _SCREENSAVER_TIMEOUT_MS:
            if self._screensaver is None:
                self._screensaver = Screensaver()

        if self._screensaver is not None and now - self._screensaver_timecount > 30:
            self._screensaver_timecount = now
            self._screensaver.update()

    @staticmethod
    def _is_user_active():
        try:
            import M5
            if M5.Touch.getCount() > 0:
                return True
            if M5.BtnPWR.isPressed():
                return True
        except Exception:
            pass
        return False
