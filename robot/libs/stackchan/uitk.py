"""Math / animation helpers ported from smooth_ui_toolkit (uitk).

Provides clamp, map_range, Random and the spring-based AnimateValue used by
the servo motion layer, plus a linear RGB color animation for the neon
lights.  Pure Python, no hardware dependencies.
"""

import math

try:
    import urandom as _random
except ImportError:
    import random as _random


def clamp(value, lo, hi):
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def map_range(value, in_min, in_max, out_min, out_max):
    """Linear map, mirrors uitk::map_range (float aware)."""
    if in_max == in_min:
        return out_min
    result = (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    if isinstance(in_min, int) and isinstance(out_min, int) \
            and isinstance(out_max, int) and isinstance(value, int) \
            and isinstance(in_max, int):
        return int(result)
    return result


class Random(object):
    """Port of uitk Random singleton (inclusive integer ranges)."""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_int(self, lo, hi):
        if hi < lo:
            lo, hi = hi, lo
        return _random.randint(lo, hi)

    def get_float(self, lo, hi):
        return lo + _random.random() * (hi - lo)


class SpringOptions(object):
    """Subset of uitk::SpringOptions_t used by the firmware."""

    def __init__(self):
        self.stiffness = 170.0
        self.damping = 26.0
        self.mass = 1.0
        self.velocity = 0.0
        self.rest_speed = 0.1
        self.rest_delta = 0.1


DEFAULT_SPRING = SpringOptions()


class AnimateValue(object):
    """Damped spring animation toward a target value.

    Semantics follow uitk::AnimateValue as used by motion::Servo:
      - ``teleport(v)``  jump to value (zero velocity)
      - ``set_target(v)`` retarget keeping current value/velocity
      - ``update_with_delta(dt)`` integrate
      - ``done()``  True when at rest near the target
    """

    def __init__(self, value=0.0):
        self._value = float(value)
        self._velocity = 0.0
        self.end = float(value)
        self._done = True
        self.spring = SpringOptions()

    def teleport(self, value):
        self._value = float(value)
        self._velocity = 0.0
        self.end = float(value)
        self._done = True

    def set_target(self, value):
        self.end = float(value)
        self._done = False

    def direct_value(self):
        return self._value

    def done(self):
        return self._done

    def update_with_delta(self, dt):
        if self._done:
            return
        s = self.spring
        # Semi-implicit Euler integration of a damped spring, sub-stepped
        # for stability at high stiffness (dt=0.02 & k=650 is fine with 4).
        steps = 4
        h = dt / steps
        x = self._value
        v = self._velocity
        k = s.stiffness
        c = s.damping
        m = s.mass if s.mass > 0 else 1.0
        target = self.end
        for _ in range(steps):
            a = (-k * (x - target) - c * v) / m
            v += a * h
            x += v * h
        self._value = x
        self._velocity = v
        if abs(v) <= s.rest_speed and abs(x - target) <= s.rest_delta:
            self._value = x
            self._velocity = 0.0
            self._done = True


class AnimateRgb(object):
    """Linear RGB interpolation over a duration (neon light animation)."""

    def __init__(self, millis_fn):
        self._millis = millis_fn
        self._from = (0, 0, 0)
        self._to = (0, 0, 0)
        self._value = (0, 0, 0)
        self._start = 0
        self._duration_ms = 300
        self._done = True

    def set_duration(self, duration_ms):
        self._duration_ms = max(0, int(duration_ms))

    def teleport(self, rgb):
        self._from = self._to = self._value = rgb
        self._done = True

    def set_target(self, rgb):
        if rgb == self._to and self._done:
            return
        self._from = self._value
        self._to = rgb
        self._start = self._millis()
        self._done = False

    def done(self):
        return self._done

    def value(self):
        return self._value

    def update(self):
        if self._done:
            return False
        elapsed = self._millis() - self._start
        if self._duration_ms <= 0 or elapsed >= self._duration_ms:
            self._value = self._to
            self._done = True
            return True
        t = elapsed / self._duration_ms
        f = self._from
        to = self._to
        self._value = (
            int(f[0] + (to[0] - f[0]) * t),
            int(f[1] + (to[1] - f[1]) * t),
            int(f[2] + (to[2] - f[2]) * t),
        )
        return True


def hex_to_rgb(value):
    """Accepts 0xRRGGBB int or '#RRGGBB'/'RRGGBB' string."""
    if isinstance(value, str):
        value = value.strip().lstrip('#')
        value = int(value, 16)
    value = int(value) & 0xFFFFFF
    return ((value >> 16) & 0xFF, (value >> 8) & 0xFF, value & 0xFF)