"""Stack-chan MicroPython firmware core.

Faithful port of the 2026 M5Stack Stack-chan firmware (ESP-IDF/C++) to
UIFlow MicroPython.  This module mirrors ``stackchan/stackchan.h``: the
:class:`StackChan` container owns the avatar, the motion layer, the two
neon-light strips and the modifier pool.
"""

from .pool import ObjectPool
from .addons import LeftNeonLight, RightNeonLight
from . import json_helper


class StackChan(object):
    """Central object (Modifiable in the original firmware)."""

    def __init__(self):
        self._avatar = None
        self._motion = None
        self._left_neon_light = LeftNeonLight()
        self._right_neon_light = RightNeonLight()
        self._modifier_pool = ObjectPool()

    # -- attach / reset --------------------------------------------------
    def attach_motion(self, motion):
        self._motion = motion

    def reset_motion(self):
        self._motion = None

    def attach_avatar(self, avatar):
        self._avatar = avatar

    def reset_avatar(self):
        if self._avatar is not None:
            self._avatar.destroy()
        self._avatar = None

    # -- accessors ---------------------------------------------------------
    def motion(self):
        return self._motion

    def avatar(self):
        return self._avatar

    def has_avatar(self):
        return self._avatar is not None

    def left_neon_light(self):
        return self._left_neon_light

    def right_neon_light(self):
        return self._right_neon_light

    # -- modifiers -----------------------------------------------------------
    def add_modifier(self, modifier):
        return self._modifier_pool.create(modifier)

    def get_modifier(self, modifier_id):
        return self._modifier_pool.get(modifier_id)

    def remove_modifier(self, modifier_id):
        if modifier_id is None or modifier_id < 0:
            return False
        return self._modifier_pool.destroy(modifier_id)

    def clear_modifiers(self):
        self._modifier_pool.clear()

    # -- update ---------------------------------------------------------------
    def update(self):
        self._modifier_pool.for_each(lambda m, i: m._update(self))
        self._modifier_pool.cleanup()

        if self._avatar is not None:
            self._avatar.update()

        if self._motion is not None:
            self._motion.update()

        self._left_neon_light.update()
        self._right_neon_light.update()

    # -- JSON control -----------------------------------------------------------
    def update_avatar_from_json(self, content):
        if self._avatar is not None:
            json_helper.update_avatar_from_json(self._avatar, content)

    def update_motion_from_json(self, content):
        if self._motion is not None:
            json_helper.update_motion_from_json(self._motion, content)

    def update_neon_light_from_json(self, content):
        json_helper.update_neon_light_from_json(
            self._left_neon_light, self._right_neon_light, content)


_stackchan = None


def get_stackchan():
    global _stackchan
    if _stackchan is None:
        _stackchan = StackChan()
    return _stackchan