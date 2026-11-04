"""Port of avatar/decorators (Heart, Angry, Sweat, Shy, Dizzy).

Images are the original firmware sprites converted to PNG, expected at
``/flash/res/stackchan/``.  If an image cannot be loaded the decorator
falls back to a simple LVGL primitive so behaviour still works.
"""

import lvgl as lv

from .avatar import Decorator
from . import lvcompat as lvc
from .hal import get_hal

ASSET_DIR = '/flash/res/stackchan/'

_HEART_POS = (108, -70)
_HEART_COLOR = 0xE13232
_HEART_ROT_FRAMES = (150, 200)

_ANGRY_POS = (108, -70)
_ANGRY_COLOR = 0xFDB034
_ANGRY_ROT_FRAMES = (150, 200)

_SWEAT_POS = (-116, -72)
_SWEAT_COLOR = 0x75E1FF
_SWEAT_Y_FRAMES = (-72, -68, -62, -58, 0)   # 0 -> hidden frame

_SHY_LEFT_POS = (-108, 28)
_SHY_RIGHT_POS = (108, 28)
_SHY_COLOR = 0xF7A59E

_DIZZY_LEFT_POS = (-70, -16)
_DIZZY_RIGHT_POS = (70, -16)
_DIZZY_COLOR = 0xFFFFFF

# sprite pixel sizes (for rotation pivots and fallbacks)
_SPRITE_SIZES = {
    'decorator_heart': (40, 40),
    'decorator_angry': (40, 40),
    'decorator_sweat': (40, 40),
    'decorator_shy': (39, 18),
    'decorator_dizzy': (33, 36),
}


def _make_sprite(parent, name, color, pos):
    """Load a sprite image centred at ``pos``; fallback to a circle."""
    w, h = _SPRITE_SIZES.get(name, (24, 24))
    img = lvc.load_image(parent, ASSET_DIR + name + '.png')
    if img is not None:
        lvc.set_pivot(img, w // 2, h // 2)
        lvc.image_recolor(img, color)
        lvc.align_center(img, pos[0], pos[1])
        return img
    # Fallback primitive
    obj = lvc.container(parent)
    lvc.bg(obj, color)
    obj.set_style_radius(lvc.RADIUS_CIRCLE, 0)
    obj.set_size(w // 2, h // 2)
    lvc.set_pivot(obj, w // 4, h // 4)
    lvc.align_center(obj, pos[0], pos[1])
    return obj


class _TimedDecorator(Decorator):
    """Shared destroy/animation timing used by every decorator."""

    def __init__(self, destroy_after_ms=0, animation_interval_ms=0):
        Decorator.__init__(self)
        self._hal = get_hal()
        now = self._hal.millis()
        self._animation_interval_ms = animation_interval_ms
        self._has_lifetime = destroy_after_ms > 0
        self._destroy_at = now + destroy_after_ms
        self._next_animation_tick = now + animation_interval_ms
        self._animation_index = 0

    def _check_lifetime(self, now):
        if self._has_lifetime and now >= self._destroy_at:
            self.request_destroy()
            return True
        return False

    def _animation_due(self, now):
        if self._animation_interval_ms > 0 and now >= self._next_animation_tick:
            self._next_animation_tick = now + self._animation_interval_ms
            return True
        return False


class HeartDecorator(_TimedDecorator):
    def __init__(self, parent, destroy_after_ms=0, animation_interval_ms=500):
        _TimedDecorator.__init__(self, destroy_after_ms, animation_interval_ms)
        self._img = _make_sprite(parent, 'decorator_heart',
                                 _HEART_COLOR, _HEART_POS)
        lvc.set_rotation(self._img, _HEART_ROT_FRAMES[0])

    def on_destroy(self):
        lvc.delete(self._img)
        self._img = None

    def _update(self):
        now = self._hal.millis()
        if self._check_lifetime(now):
            return
        if self._animation_due(now):
            self._animation_index = (self._animation_index + 1) % len(_HEART_ROT_FRAMES)
            lvc.set_rotation(self._img, _HEART_ROT_FRAMES[self._animation_index])


class AngryDecorator(_TimedDecorator):
    def __init__(self, parent, destroy_after_ms=0, animation_interval_ms=500):
        _TimedDecorator.__init__(self, destroy_after_ms, animation_interval_ms)
        self._img = _make_sprite(parent, 'decorator_angry',
                                 _ANGRY_COLOR, _ANGRY_POS)
        lvc.set_rotation(self._img, _ANGRY_ROT_FRAMES[0])

    def on_destroy(self):
        lvc.delete(self._img)
        self._img = None

    def _update(self):
        now = self._hal.millis()
        if self._check_lifetime(now):
            return
        if self._animation_due(now):
            self._animation_index = (self._animation_index + 1) % len(_ANGRY_ROT_FRAMES)
            lvc.set_rotation(self._img, _ANGRY_ROT_FRAMES[self._animation_index])


class SweatDecorator(_TimedDecorator):
    def __init__(self, parent, destroy_after_ms=0, animation_interval_ms=700):
        _TimedDecorator.__init__(self, destroy_after_ms, animation_interval_ms)
        self._img = _make_sprite(parent, 'decorator_sweat',
                                 _SWEAT_COLOR, _SWEAT_POS)

    def on_destroy(self):
        lvc.delete(self._img)
        self._img = None

    def _update(self):
        now = self._hal.millis()
        if self._check_lifetime(now):
            return
        if self._animation_due(now):
            frame_y = _SWEAT_Y_FRAMES[self._animation_index]
            if frame_y == 0:
                lvc.hidden(self._img, True)
            else:
                lvc.hidden(self._img, False)
                lvc.align_center(self._img, _SWEAT_POS[0], frame_y)
            self._animation_index = (self._animation_index + 1) % len(_SWEAT_Y_FRAMES)


class ShyDecorator(_TimedDecorator):
    def __init__(self, parent, destroy_after_ms=0):
        _TimedDecorator.__init__(self, destroy_after_ms, 0)
        self._left = _make_sprite(parent, 'decorator_shy',
                                  _SHY_COLOR, _SHY_LEFT_POS)
        self._right = _make_sprite(parent, 'decorator_shy',
                                   _SHY_COLOR, _SHY_RIGHT_POS)

    def on_destroy(self):
        lvc.delete(self._left)
        lvc.delete(self._right)
        self._left = self._right = None

    def _update(self):
        self._check_lifetime(self._hal.millis())


class DizzyDecorator(_TimedDecorator):
    def __init__(self, parent, destroy_after_ms=0, animation_interval_ms=500):
        _TimedDecorator.__init__(self, destroy_after_ms, animation_interval_ms)
        self._left = _make_sprite(parent, 'decorator_dizzy',
                                  _DIZZY_COLOR, _DIZZY_LEFT_POS)
        self._right = _make_sprite(parent, 'decorator_dizzy',
                                   _DIZZY_COLOR, _DIZZY_RIGHT_POS)

    def on_destroy(self):
        lvc.delete(self._left)
        lvc.delete(self._right)
        self._left = self._right = None

    def _update(self):
        now = self._hal.millis()
        if self._check_lifetime(now):
            return
        if self._animation_due(now):
            self._animation_index = (self._animation_index + 300) % 3600
            rotation = -self._animation_index
            lvc.set_rotation(self._left, rotation)
            lvc.set_rotation(self._right, (rotation + 450) % 3600)