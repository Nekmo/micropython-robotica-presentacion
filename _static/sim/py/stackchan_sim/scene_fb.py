"""MicroPython backend for the LVGL scene graph: framebuf tiles.

Adapted from esp-emulator's ``scene_fb.py`` for the in-browser simulator.
A Tile is one RGB565 raster where a reserved *key colour* marks
transparent pixels (1-bit alpha: opa >= 128 paints). Compositing uses
``FrameBuffer.blit(..., key)``, which runs in C: pure-Python per-pixel
loops are far too slow on the WebAssembly VM.
"""

import math

import framebuf

from stackchan_sim import pnglite
from stackchan_sim.raster_fb import FbRaster, _load_font, _c565

KEY = 0x0841          # RGB565 key colour = transparent
_KEY_SAFE = 0x080C08  # what to paint instead when a colour maps to KEY
_image_cache = {}


def _safe(color):
    return _KEY_SAFE if _c565(color) == KEY else color


class Tile:
    def __init__(self, w, h):
        self.w = max(1, int(w))
        self.h = max(1, int(h))
        self.col = FbRaster(self.w, self.h)
        self.col._fb.fill(KEY)

    def clear(self):
        self.col._fb.fill(KEY)

    def fill_round_rect(self, x, y, w, h, radius, color, opa):
        if opa < 128:
            return  # 1-bit alpha: semi-transparent backgrounds are dropped
        self.col.round_rect(x, y, w, h, radius, _safe(color), True)

    def outline_round_rect(self, x, y, w, h, radius, color, width):
        for i in range(max(1, int(width))):
            self.col.round_rect(x + i, y + i, w - 2 * i, h - 2 * i,
                                max(0, radius - i), _safe(color), False)

    def text(self, s, x, y, px, color, opa=255):
        if opa < 128:
            return
        self.col.text(s, x, y, px, _safe(color))

    def blit_image(self, img, x, y):
        w, h, rgba = img
        key = id(rgba)
        fb = _image_cache.get(key)
        if fb is None:   # convert once: RGBA -> keyed RGB565 framebuffer
            raster = FbRaster(w, h)
            raster._fb.fill(KEY)
            raster.blit_rgba(w, h, rgba, 0, 0)
            fb = raster._fb
            _image_cache[key] = fb
        self.col._fb.blit(fb, int(x), int(y), KEY)

    def composite(self, child, x, y):
        """Copy child's painted pixels onto this tile."""
        self.col._fb.blit(child.col._fb, int(x), int(y), KEY)

    def rotated(self, deg, pivot_x, pivot_y):
        """Clockwise rotation around the pivot -> (Tile, origin offset)."""
        rad = math.radians(deg)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        def fwd(sx, sy):
            dx, dy = sx - pivot_x, sy - pivot_y
            return (pivot_x + dx * cos_a - dy * sin_a,
                    pivot_y + dx * sin_a + dy * cos_a)

        corners = [fwd(0, 0), fwd(self.w, 0), fwd(0, self.h),
                   fwd(self.w, self.h)]
        min_x = int(math.floor(min(c[0] for c in corners))) - 1
        min_y = int(math.floor(min(c[1] for c in corners))) - 1
        max_x = int(math.ceil(max(c[0] for c in corners))) + 1
        max_y = int(math.ceil(max(c[1] for c in corners))) + 1
        out = Tile(max_x - min_x, max_y - min_y)
        src = self.col._fb
        dst = out.col._fb
        w, h, ow = self.w, self.h, out.w
        for dy in range(out.h):
            fy = dy + min_y + 0.5 - pivot_y
            for dx in range(ow):
                fx = dx + min_x + 0.5 - pivot_x
                sx = int(pivot_x + fx * cos_a + fy * sin_a)
                sy = int(pivot_y - fx * sin_a + fy * cos_a)
                if 0 <= sx < w and 0 <= sy < h:
                    c = src.pixel(sx, sy)
                    if c != KEY:
                        dst.pixel(dx, dy, c)
        return out, (min_x, min_y)


def measure(text, px):
    """(width, line_height) of a single line of text."""
    font = _load_font(px)
    width = 0
    for ch in text:
        width += font.glyph(ord(ch))[0]
    return width, font.height


def load_image(path):
    with open(path, "rb") as fh:
        return pnglite.decode(fh.read())


def image_size(img):
    return img[0], img[1]


def transform_image(img, scale=(1.0, 1.0), rot_deg=0):
    w, h, rgba = img
    if scale != (1.0, 1.0):
        dw = max(1, int(w * scale[0]))
        dh = max(1, int(h * scale[1]))
        out = bytearray(dw * dh * 4)
        for dy in range(dh):
            sbase = (dy * h // dh) * w * 4
            dbase = dy * dw * 4
            for dx in range(dw):
                s = sbase + (dx * w // dw) * 4
                d = dbase + dx * 4
                out[d:d + 4] = rgba[s:s + 4]
        w, h, rgba = dw, dh, out
    rot = int(rot_deg) % 360
    if rot:
        if rot % 90:
            rot = (rot // 90) * 90  # nearest 90: arbitrary angles skipped
        for _ in range(rot // 90):
            out = bytearray(w * h * 4)
            # rotate 90 deg clockwise: (x, y) -> (h - 1 - y, x)
            for yy in range(h):
                for xx in range(w):
                    s = (yy * w + xx) * 4
                    d = (xx * h + (h - 1 - yy)) * 4
                    out[d:d + 4] = rgba[s:s + 4]
            w, h = h, w
            rgba = out
    return w, h, rgba


def composite_to_gfx(tile, gfx, rects):
    """Copy the scene tile onto the GFX when any region is dirty."""
    if not rects:
        return
    with gfx.lock:
        gfx._r._fb.blit(tile.col._fb, 0, 0, KEY)
        gfx._dirty()
