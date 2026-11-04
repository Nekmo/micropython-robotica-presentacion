"""Port of stackchan/addons/neon_light (side RGB strips, 6 LEDs each)."""

from .uitk import AnimateRgb, hex_to_rgb
from .hal import get_hal


class NeonLight(object):
    def __init__(self, strip, led_count=6):
        self._strip = strip
        self._led_count = led_count
        self._hal = get_hal()
        self._anim = AnimateRgb(self._hal.millis)
        self._is_inited = False
        self._last_written = None

    def get_led_count(self):
        return self._led_count

    def set_duration(self, duration_sec):
        try:
            self._anim.set_duration(int(float(duration_sec) * 1000))
        except (ValueError, TypeError):
            pass

    def set_color(self, value):
        """Accepts (r,g,b), 0xRRGGBB int or '#RRGGBB' string."""
        if value is None:
            return
        if isinstance(value, str):
            if not value.strip():
                return
            try:
                rgb = hex_to_rgb(value)
            except ValueError:
                return
        elif isinstance(value, (tuple, list)):
            rgb = (int(value[0]), int(value[1]), int(value[2]))
        else:
            rgb = hex_to_rgb(value)
        self._anim.set_target(rgb)

    def set_rgb(self, r, g, b):
        self._anim.set_target((int(r), int(g), int(b)))

    def update(self):
        if not self._is_inited:
            self._is_inited = True
            self._anim.teleport((0, 0, 0))
            self._write((0, 0, 0))
            return
        if self._anim.update():
            value = self._anim.value()
            if value != self._last_written:
                self._write(value)

    def _write(self, rgb):
        self._last_written = rgb
        r, g, b = rgb
        for index in range(self._led_count):
            self._hal.set_neon_color(self._strip, index, r, g, b)


class LeftNeonLight(NeonLight):
    def __init__(self):
        NeonLight.__init__(self, 0)


class RightNeonLight(NeonLight):
    def __init__(self):
        NeonLight.__init__(self, 1)