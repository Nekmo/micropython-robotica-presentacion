"""camera shim (UIFlow CoreS3): frames come from the presenter's webcam.

``snapshot()`` returns a QVGA RGB565 image that ``M5.Lcd.show()`` can
draw, with the drawing helpers used by the demos.
"""

import framebuf

from stackchan_sim import bridge as _bridge_mod

RGB565 = 0
GRAYSCALE = 1
JPEG = 2
QVGA = 5
QQVGA = 1
VGA = 8

_SIZES = {QVGA: (320, 240), QQVGA: (160, 120)}
_size = (320, 240)


class Image:
    def __init__(self, width, height):
        self._w = width
        self._h = height
        self._buf = bytearray(width * height * 2)
        self._fb = framebuf.FrameBuffer(self._buf, width, height, framebuf.RGB565)

    def framebuffer(self):
        return self._fb

    def width(self):
        return self._w

    def height(self):
        return self._h

    def bytearray(self):
        return self._buf

    @staticmethod
    def _c565(color):
        color = int(color) & 0xFFFFFF
        r, g, b = (color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    def draw_rectangle(self, x, y, w, h, color=0xFFFFFF, thickness=2, fill=False):
        c = self._c565(color)
        for i in range(1 if fill else thickness):
            self._fb.rect(int(x) + i, int(y) + i, int(w) - 2 * i, int(h) - 2 * i, c, fill)

    def draw_circle(self, x, y, r, color=0xFFFFFF, thickness=2, fill=False):
        self._fb.ellipse(int(x), int(y), int(r), int(r), self._c565(color), fill)

    def draw_line(self, x0, y0, x1, y1, color=0xFFFFFF, thickness=1):
        self._fb.line(int(x0), int(y0), int(x1), int(y1), self._c565(color))

    def draw_string(self, x, y, text, color=0xFFFFFF, scale=1):
        self._fb.text(str(text), int(x), int(y), self._c565(color))


def init(pixformat=RGB565, framesize=QVGA, **kwargs):
    global _size
    _size = _SIZES.get(framesize, (320, 240))
    _bridge_mod.get().log("camera.init %dx%d (webcam)" % _size)
    return True


def deinit():
    pass


def snapshot():
    _bridge_mod.get().maybe_tick()
    img = Image(320, 240)
    if not _bridge_mod.get().camera_frame(img._buf):
        img.draw_string(64, 112, "Activa la camara", 0xFFFFFF)
    return img


def set_hmirror(enable):
    pass


def set_vflip(enable):
    pass
