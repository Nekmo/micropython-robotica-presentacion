"""M5GFX-compatible drawing surface over a runtime raster backend.

GFX implements the M5.Display / M5.Lcd API; the actual pixels live in a
raster backend chosen per runtime (raster_pil on CPython, raster_fb on
MicroPython — see compat.create_raster). A version counter marks dirty
frames for the bridge sender thread. Common subset: no PIL/threading here.
"""

from stackchan_sim import compat


def rgb(color):
    """0xRRGGBB int (or (r,g,b) tuple) -> (r, g, b)."""
    if isinstance(color, tuple):
        return color[:3]
    color = int(color) & 0xFFFFFF
    return ((color >> 16) & 0xFF, (color >> 8) & 0xFF, color & 0xFF)


def _cint(color):
    """Any color spec -> 0xRRGGBB int (raster backends take ints)."""
    if isinstance(color, tuple):
        return ((int(color[0]) & 0xFF) << 16) | \
            ((int(color[1]) & 0xFF) << 8) | (int(color[2]) & 0xFF)
    return int(color) & 0xFFFFFF


class FontSpec:
    """Mirror of Widgets.FONTS constants: carries a pixel size."""

    def __init__(self, name, px):
        self.name = name
        self.px = px

    def __repr__(self):
        return "<Font %s %dpx>" % (self.name, self.px)


class GFX:
    """M5GFX drawing surface backed by a runtime raster."""

    def __init__(self, width, height, is_canvas=False):
        self._w = width
        self._h = height
        self._r = compat.create_raster(width, height)
        self.lock = compat.RLock()
        self.version = 0
        self._is_canvas = is_canvas
        # text state
        self._cursor = [0, 0]
        self._font = FontSpec("DejaVu12", 12)
        self._text_size = 1.0
        self._text_fg = 0xFFFFFF
        self._text_bg = None
        self._text_scroll = False
        self._rotation = 0
        self._brightness = 200
        self._path_mapper = lambda p: p

    # internal ------------------------------------------------------------
    def _dirty(self):
        if not self._is_canvas:
            self.version += 1
            try:
                from . import bridge
                bridge.get().maybe_tick()
            except RuntimeError:
                pass

    def _px(self):
        return self._font.px * self._text_size

    def snapshot_region(self, x, y, w, h):
        with self.lock:
            box = (max(0, x), max(0, y), min(self._w, x + w),
                   min(self._h, y + h))
            if box[2] <= box[0] or box[3] <= box[1]:
                return None, box
            return self._r.snapshot(box), box

    def restore_region(self, snap, box):
        if snap is None:
            return
        with self.lock:
            self._r.restore(snap, box[0], box[1])
            self._dirty()

    def paste_image(self, img, x, y):
        """Blit a PIL image (CPython runtime only; honours alpha)."""
        with self.lock:
            self._r.paste_pil(img, int(x), int(y))
            self._dirty()

    def show(self, img=None, x=0, y=0, w=None, h=None):
        """Blit a camera image (UIFlow ``M5.Lcd.show``); no-op without one."""
        if img is None:
            return
        with self.lock:
            self._r._fb.blit(img.framebuffer(), int(x), int(y))
            self._dirty()

    def encode_frame(self):
        """(fmt, payload) of the current frame for the GUI."""
        with self.lock:
            return self._r.encode_frame()

    # screen info ----------------------------------------------------------
    def width(self):
        return self._w

    def height(self):
        return self._h

    def getRotation(self):
        return self._rotation

    def setRotation(self, r):
        r = int(r) % 4
        with self.lock:
            self._rotation = r
            w, h = (self._w, self._h)
            base = (min(w, h), max(w, h))  # portrait native
            self._w, self._h = (base[1], base[0]) if r % 2 else base
            self._r = self._r.make(self._w, self._h)
            self._dirty()

    def getBrightness(self):
        return self._brightness

    def setBrightness(self, b):
        self._brightness = max(0, min(255, int(b)))
        try:
            from . import bridge
            br = bridge.get()
            with br.state.lock:
                br.state.brightness = self._brightness
        except Exception:
            pass

    def powerSaveOn(self):
        pass

    def powerSaveOff(self):
        pass

    # cursor / text ---------------------------------------------------------
    def getCursor(self):
        return tuple(self._cursor)

    def setCursor(self, x, y):
        self._cursor = [int(x), int(y)]

    def setFont(self, font):
        if isinstance(font, FontSpec):
            self._font = font

    def loadFont(self, path):
        pass  # custom vlw fonts not supported; keep current

    def unloadFont(self):
        pass

    def setTextColor(self, fg, bg=None):
        self._text_fg = _cint(fg)
        self._text_bg = _cint(bg) if bg is not None else None

    def setTextSize(self, scale):
        self._text_size = float(scale)

    def setTextWrap(self, wrap_x, wrap_y=False):
        self._text_wrap = bool(wrap_x)

    def setTextScroll(self, enable):
        self._text_scroll = bool(enable)

    def measure_text(self, text, px=None):
        """(width, ascent, descent) for `text` at `px` (default: current)."""
        return self._r.measure(str(text), px if px is not None
                               else self._px())

    def textWidth(self, text):
        return self.measure_text(text)[0]

    def fontHeight(self):
        _w, asc, desc = self.measure_text(" ")
        return asc + desc

    def _draw_text(self, text, x, y, anchor="la", fg=None, bg=None, px=None):
        """Draw text; anchor: [l|m|r][a|m] like PIL (top/middle only)."""
        text = str(text)
        px = px if px is not None else self._px()
        fg = _cint(fg) if fg is not None else self._text_fg
        bg = _cint(bg) if bg is not None else self._text_bg
        w, asc, desc = self._r.measure(text, px)
        h = asc + desc
        if anchor[0] == "m":
            x = x - w // 2
        elif anchor[0] == "r":
            x = x - w
        if len(anchor) > 1 and anchor[1] == "m":
            y = y - h // 2
        with self.lock:
            if bg is not None:
                self._r.rect(int(x), int(y), w, h, bg, True)
            self._r.text(text, int(x), int(y), px, fg)
            self._dirty()

    def drawString(self, text, x, y):
        self._draw_text(text, x, y, anchor="la")

    def drawCenterString(self, text, cx, y):
        self._draw_text(text, cx, y, anchor="ma")

    def drawCentreString(self, text, cx, y):
        self.drawCenterString(text, cx, y)

    def drawRightString(self, text, x, y):
        self._draw_text(text, x, y, anchor="ra")

    def _wrap(self, text):
        """Word-wrap text to the screen width (setTextWrap)."""
        lines = []
        for para in text.split("\n"):
            line = ""
            x0 = self._cursor[0] if not lines else 0
            for word in para.split(" "):
                probe = word if not line else line + " " + word
                if line and x0 + self.textWidth(probe) > self._w:
                    lines.append(line)
                    line, x0 = word, 0
                else:
                    line = probe
            lines.append(line)
        return "\n".join(lines)

    def print(self, *args, **kwargs):
        text = " ".join(str(a) for a in args)
        if getattr(self, "_text_wrap", False):
            text = self._wrap(text)
        lh = self.fontHeight()
        with self.lock:
            parts = text.split("\n")
            for i, part in enumerate(parts):
                if i > 0:
                    self._cursor = [0, self._cursor[1] + lh]
                if not part:
                    continue
                if self._cursor[1] > self._h - lh and self._text_scroll:
                    self._r.scroll_up(lh)
                    self._cursor[1] -= lh
                self._draw_text(part, self._cursor[0], self._cursor[1])
                self._cursor[0] += self.textWidth(part)
        return len(text)

    def println(self, *args):
        self.print(*args)
        self._cursor = [0, self._cursor[1] + self.fontHeight()]

    def printf(self, fmt, *args):
        try:
            self.print(fmt % args if args else fmt)
        except TypeError:
            self.print(fmt, *args)

    # fill / clear ----------------------------------------------------------
    def fillScreen(self, color):
        with self.lock:
            self._r.fill(_cint(color))
            self._dirty()

    def clear(self, color=0):
        self.fillScreen(color)
        self._cursor = [0, 0]

    # primitives -------------------------------------------------------------
    def drawPixel(self, x, y, color=0xFFFFFF):
        with self.lock:
            self._r.pixel(x, y, _cint(color))
            self._dirty()

    def drawLine(self, x0, y0, x1, y1, color=0xFFFFFF):
        with self.lock:
            self._r.line(x0, y0, x1, y1, _cint(color))
            self._dirty()

    def drawFastHLine(self, x, y, w, color=0xFFFFFF):
        self.drawLine(x, y, x + w - 1, y, color)

    def drawFastVLine(self, x, y, h, color=0xFFFFFF):
        self.drawLine(x, y, x, y + h - 1, color)

    def drawRect(self, x, y, w, h, color=0xFFFFFF):
        with self.lock:
            self._r.rect(x, y, w, h, _cint(color), False)
            self._dirty()

    def fillRect(self, x, y, w, h, color=0xFFFFFF):
        with self.lock:
            self._r.rect(x, y, w, h, _cint(color), True)
            self._dirty()

    def drawRoundRect(self, x, y, w, h, r, color=0xFFFFFF):
        with self.lock:
            self._r.round_rect(x, y, w, h, r, _cint(color), False)
            self._dirty()

    def fillRoundRect(self, x, y, w, h, r, color=0xFFFFFF):
        with self.lock:
            self._r.round_rect(x, y, w, h, r, _cint(color), True)
            self._dirty()

    def drawCircle(self, x, y, r, color=0xFFFFFF):
        with self.lock:
            self._r.ellipse(x, y, r, r, _cint(color), False)
            self._dirty()

    def fillCircle(self, x, y, r, color=0xFFFFFF):
        with self.lock:
            self._r.ellipse(x, y, r, r, _cint(color), True)
            self._dirty()

    def drawEllipse(self, x, y, rx, ry, color=0xFFFFFF):
        with self.lock:
            self._r.ellipse(x, y, rx, ry, _cint(color), False)
            self._dirty()

    def fillEllipse(self, x, y, rx, ry, color=0xFFFFFF):
        with self.lock:
            self._r.ellipse(x, y, rx, ry, _cint(color), True)
            self._dirty()

    def drawTriangle(self, x0, y0, x1, y1, x2, y2, color=0xFFFFFF):
        with self.lock:
            self._r.triangle(x0, y0, x1, y1, x2, y2, _cint(color), False)
            self._dirty()

    def fillTriangle(self, x0, y0, x1, y1, x2, y2, color=0xFFFFFF):
        with self.lock:
            self._r.triangle(x0, y0, x1, y1, x2, y2, _cint(color), True)
            self._dirty()

    def drawArc(self, x, y, r0, r1, angle0, angle1, color=0xFFFFFF):
        """Arc between radii r0..r1 (M5GFX: angles in degrees)."""
        with self.lock:
            self._r.arc(x, y, r0, r1, angle0, angle1, _cint(color))
            self._dirty()

    def fillArc(self, x, y, r0, r1, angle0, angle1, color=0xFFFFFF):
        self.drawArc(x, y, r0, r1, angle0, angle1, color)

    def drawEllipseArc(self, x, y, rx0, rx1, ry0, ry1, angle0, angle1,
                       color=0xFFFFFF):
        with self.lock:
            self._r.arc(x, y, max(rx0, rx1), min(rx0, rx1), angle0, angle1,
                        _cint(color))
            self._dirty()

    fillEllipseArc = drawEllipseArc

    # QR ---------------------------------------------------------------------
    def drawQR(self, text, x=0, y=0, size=100, version=1):
        with self.lock:
            done = self._r.draw_qr(str(text), int(x), int(y), int(size))
            self._dirty()
        if not done:
            self.fillRect(x, y, size, size, 0xFFFFFF)
            self.drawRect(x, y, size, size, 0x000000)
            self._draw_text("QR", x + size // 2, y + size // 2, anchor="mm",
                            fg=0x000000)

    # images -------------------------------------------------------------------
    def drawImage(self, source, x=0, y=0, *args, **kwargs):
        scale_x = kwargs.get("scaleX", args[4] if len(args) > 4 else 1.0) \
            or 1.0
        scale_y = kwargs.get("scaleY", args[5] if len(args) > 5 else 0.0) \
            or scale_x
        if isinstance(source, str):
            source = self._path_mapper(source)
        try:
            with self.lock:
                done = self._r.draw_image(source, int(x), int(y),
                                          scale_x, scale_y)
                self._dirty()
        except Exception as e:
            done = False
            self._log_warn("drawImage(%r) failed: %s" % (source, e))
        if not done:
            self._log_warn("drawImage(%r): no se pudo decodificar "
                           "(placeholder)" % (source,))
            self.drawRect(x, y, 32, 32, 0x888888)
            self.drawLine(x, y, x + 31, y + 31, 0x888888)
            self.drawLine(x + 31, y, x, y + 31, 0x888888)
        return done

    drawPng = drawImage
    drawJpg = drawImage
    drawBmp = drawImage

    def image_size(self, source):
        """(w, h) of an image, or None if undecodable on this runtime."""
        if isinstance(source, str):
            source = self._path_mapper(source)
        try:
            return self._r.image_size(source)
        except Exception:
            return None

    def _log_warn(self, msg):
        try:
            from . import bridge
            bridge.get().log(msg, "warn")
        except Exception:
            pass

    def drawRawBuf(self, buf, x, y, w, h, fmt=None):
        try:
            from PIL import Image
            img = Image.frombytes("RGB", (w, h), bytes(buf))
            self.paste_image(img, x, y)
        except Exception:
            pass

    # canvas ---------------------------------------------------------------
    def newCanvas(self, w, h, bpp=16, psram=False):
        return Canvas(self, int(w), int(h))

    # batching / epd ---------------------------------------------------------
    def startWrite(self):
        pass

    def endWrite(self):
        pass

    def isEPD(self):
        return False

    def setEpdMode(self, mode):
        pass

    def waitDisplay(self):
        pass


class Canvas(GFX):
    """Off-screen sprite: draws on its own raster, push() blits to parent."""

    def __init__(self, parent, w, h):
        GFX.__init__(self, w, h, is_canvas=True)
        self._parent = parent
        self._path_mapper = parent._path_mapper

    def push(self, x=0, y=0):
        with self.lock:
            with self._parent.lock:
                self._parent._r.blit(self._r, int(x), int(y))
                self._parent._dirty()

    def delete(self):
        pass
