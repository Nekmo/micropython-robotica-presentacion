"""Retained-mode scene graph emulating a small LVGL v9 subset.

Faithful detail: like real LVGL, only *dirty regions* are composited onto
the M5GFX framebuffer, so M5GFX content (e.g. the Stack-chan mouth drawn
with fillRoundRect) survives outside LVGL objects — matching the firmware
behaviour documented in the uiflow docs.

Runs on both runtimes: nodes paint into backend Tiles (scene_pil on
CPython, scene_fb on MicroPython). Keep this module in the common subset.
"""

from stackchan_sim import compat

if compat.IS_MICROPYTHON:
    from stackchan_sim import scene_fb as _backend
else:
    from stackchan_sim import scene_pil as _backend

RADIUS_CIRCLE = 0x7FFF

FLAG_HIDDEN = 1 << 0
FLAG_SCROLLABLE = 1 << 1
FLAG_CLICKABLE = 1 << 2

_warned = set()


def warn_once(name):
    if name not in _warned:
        _warned.add(name)
        try:
            from . import bridge
            bridge.get().log("lvgl shim: '%s' not implemented (no-op)"
                             % name)
        except Exception:
            pass


class SceneNode:
    """Base LVGL object: position, size, styles, children."""

    def __init__(self, parent=None, w=100, h=100):
        self.parent = None
        self.children = []
        self.x = 0
        self.y = 0
        self.w = w
        self.h = h
        self.flags = 0
        self.styles = {
            "radius": 0,
            "bg_color": 0xFFFFFF,
            "bg_opa": 255,
            "border_width": 2,
            "border_color": 0x2196F3,
            "pad_all": 0,
            "transform_rotation": 0,   # 0.1 deg units
            "transform_pivot_x": None,
            "transform_pivot_y": None,
            "text_color": 0x000000,
            "text_opa": 255,
            "shadow_width": 0,
            "outline_width": 0,
        }
        self.deleted = False
        if parent is not None:
            parent._add_child(self)

    # ── tree ────────────────────────────────────────────────────────────
    def _add_child(self, child):
        child.parent = self
        self.children.append(child)
        get_scene().invalidate(child)

    def delete(self):
        get_scene().invalidate(self)
        if self.parent:
            try:
                self.parent.children.remove(self)
            except ValueError:
                pass
        self.deleted = True

    def clean(self):
        for child in list(self.children):
            child.delete()

    # ── geometry ─────────────────────────────────────────────────────────
    def abs_pos(self):
        x, y, node = self.x, self.y, self.parent
        while node is not None:
            x += node.x
            y += node.y
            node = node.parent
        return x, y

    def abs_bbox(self):
        """Absolute bounding box, inflated if the object is rotated."""
        x, y = self.abs_pos()
        rot = self.styles.get("transform_rotation") or 0
        if rot:
            m = int(0.5 * (self.w + self.h)) + 4
            return (x - m, y - m, x + self.w + m, y + self.h + m)
        return (x, y, x + self.w, y + self.h)

    # ── change tracking ─────────────────────────────────────────────────
    def _mutate(self):
        get_scene().invalidate(self)

    # ── LVGL API ─────────────────────────────────────────────────────────
    def invalidate(self):
        """lv_obj_invalidate(): mark the object's area for redraw."""
        self._mutate()

    def invalidate_area(self, area=None):
        self._mutate()

    def set_pos(self, x, y):
        self._mutate()
        self.x, self.y = int(x), int(y)
        self._mutate()

    def set_x(self, x):
        self.set_pos(x, self.y)

    def set_y(self, y):
        self.set_pos(self.x, y)

    def set_size(self, w, h):
        self._mutate()
        self.w, self.h = int(w), int(h)
        self._mutate()

    def get_x(self):
        return self.x

    def get_y(self):
        return self.y

    def get_width(self):
        return self.w

    def get_height(self):
        return self.h

    def add_flag(self, flag):
        self._mutate()
        self.flags |= flag

    def remove_flag(self, flag):
        self.flags &= ~flag
        self._mutate()

    def has_flag(self, flag):
        return bool(self.flags & flag)

    def is_hidden(self):
        return bool(self.flags & FLAG_HIDDEN)

    def move_foreground(self):
        if self.parent:
            self.parent.children.remove(self)
            self.parent.children.append(self)
            self._mutate()

    def move_background(self):
        if self.parent:
            self.parent.children.remove(self)
            self.parent.children.insert(0, self)
            self._mutate()

    def align(self, align, dx=0, dy=0):
        if self.parent is not None:
            self._align_in(self.parent.w, self.parent.h, align, dx, dy)

    def align_to(self, other, align, dx=0, dy=0):
        # simplified: align inside `other`'s box
        ox, oy = other.abs_pos()
        px, py = self.parent.abs_pos() if self.parent else (0, 0)
        self._align_in(other.w, other.h, align, dx + ox - px, dy + oy - py)

    def _align_in(self, cw, ch, align, dx, dy):
        from . import lvgl_align as A
        x, y = A.resolve(align, cw, ch, self.w, self.h)
        self.set_pos(x + dx, y + dy)

    def center(self):
        self.align(9, 0, 0)  # ALIGN.CENTER

    def add_event_cb(self, *a, **k):
        warn_once("add_event_cb")

    def set_style_radius(self, v, part=0):
        self._set_style("radius", v)

    def set_style_bg_color(self, v, part=0):
        self._set_style("bg_color", v)

    def set_style_bg_opa(self, v, part=0):
        self._set_style("bg_opa", v)

    def set_style_border_width(self, v, part=0):
        self._set_style("border_width", v)

    def set_style_border_color(self, v, part=0):
        self._set_style("border_color", v)

    def set_style_shadow_width(self, v, part=0):
        self._set_style("shadow_width", v)

    def set_style_outline_width(self, v, part=0):
        self._set_style("outline_width", v)

    def set_style_pad_all(self, v, part=0):
        self._set_style("pad_all", v)

    def set_style_text_color(self, v, part=0):
        self._set_style("text_color", v)

    def set_style_text_opa(self, v, part=0):
        self._set_style("text_opa", v)

    def set_style_transform_rotation(self, v, part=0):
        self._set_style("transform_rotation", v)

    def set_style_transform_pivot_x(self, v, part=0):
        self._set_style("transform_pivot_x", v)

    def set_style_transform_pivot_y(self, v, part=0):
        self._set_style("transform_pivot_y", v)

    def _set_style(self, key, value):
        self._mutate()
        self.styles[key] = value
        self._mutate()

    def __getattr__(self, name):
        # tolerate unimplemented set_style_* / set_* calls with a warning
        if name.startswith(("set_style_", "set_", "add_style",
                            "remove_style")):
            def _noop(*a, **k):
                warn_once(name)
            return _noop
        raise AttributeError(name)

    # ── rendering ─────────────────────────────────────────────────────────
    def render(self, into=None):
        """Render self + children into a transparent Tile of own size.

        `into` reuses a previous root tile (cleared) — avoids reallocating
        a full-screen buffer per flush, which fragments small MicroPython
        heaps."""
        if into is not None and (into.w, into.h) == (self.w, self.h):
            tile = into
            tile.clear()
        else:
            tile = _backend.Tile(self.w, self.h)
        self.draw_self(tile)
        for child in self.children:
            if child.is_hidden():
                continue
            ctile = child.render()
            ctile, off = child.apply_transform(ctile)
            tile.composite(ctile, child.x + off[0], child.y + off[1])
        return tile

    def apply_transform(self, tile):
        """Apply LVGL transform_rotation around the pivot: (tile, offset)."""
        rot = self.styles.get("transform_rotation") or 0
        if not rot:
            return tile, (0, 0)
        deg = rot / 10.0
        px = self.styles.get("transform_pivot_x")
        py = self.styles.get("transform_pivot_y")
        px = self.w // 2 if px is None else px
        py = self.h // 2 if py is None else py
        return tile.rotated(deg, px, py)

    def draw_self(self, tile):
        opa = self.styles.get("bg_opa", 255)
        radius = self.styles.get("radius", 0)
        if radius == RADIUS_CIRCLE:
            radius = min(self.w, self.h) // 2
        radius = min(radius, min(self.w, self.h) // 2)
        if opa > 0:
            tile.fill_round_rect(0, 0, self.w, self.h, radius,
                                 self.styles.get("bg_color", 0xFFFFFF), opa)
        bw = self.styles.get("border_width", 0)
        if bw and bw > 0:
            tile.outline_round_rect(0, 0, self.w, self.h, radius,
                                    self.styles.get("border_color", 0), bw)


class LabelNode(SceneNode):
    def __init__(self, parent=None):
        super().__init__(parent, w=1, h=1)
        self.text = ""
        self.font_px = 14
        self.styles["bg_opa"] = 0
        self.styles["border_width"] = 0
        self._autosize()

    def set_text(self, text):
        self._mutate()
        self.text = str(text)
        self._autosize()
        self._mutate()

    def get_text(self):
        return self.text

    def set_text_font_px(self, px):
        self._mutate()
        self.font_px = px
        self._autosize()
        self._mutate()

    def set_style_text_font(self, font, part=0):
        px = getattr(font, "px", None) or 14
        self.set_text_font_px(px)

    def _autosize(self):
        lines = self.text.split("\n") or [""]
        w = line_h = 0
        for line in lines:
            lw, lh = _backend.measure(line or " ", self.font_px)
            w = max(w, lw)
            line_h = max(line_h, lh)
        self.w = max(1, int(w))
        self.h = max(1, int(line_h * len(lines)))

    def draw_self(self, tile):
        bg_opa = self.styles.get("bg_opa", 0)
        if bg_opa:
            SceneNode.draw_self(self, tile)
        color = self.styles.get("text_color", 0)
        opa = int(self.styles.get("text_opa", 255))
        _w, line_h = _backend.measure(" ", self.font_px)
        for i, line in enumerate(self.text.split("\n")):
            if line:
                tile.text(line, 0, i * line_h, self.font_px, color, opa)


class ImageNode(SceneNode):
    def __init__(self, parent=None):
        super().__init__(parent, w=1, h=1)
        self.styles["bg_opa"] = 0
        self.styles["border_width"] = 0
        self._img = None
        self._src = None
        self.rotation90 = 0
        self.scale = (1.0, 1.0)

    def set_src(self, path):
        from . import bridge
        self._mutate()
        self._src = path
        try:
            real = bridge.get().map_path(path)
            self._img = _backend.load_image(real)
        except Exception as e:
            self._img = None
            warn_once("image '%s': %s" % (path, e))
        self._update_size()
        self._mutate()

    set_image = set_src

    def set_rotation(self, deg, *a, **k):
        self._mutate()
        self.rotation90 = int(deg) % 360
        self._update_size()
        self._mutate()

    def set_scale(self, sx, sy=None):
        self._mutate()
        sx = sx / 256 if sx > 8 else sx  # lvgl uses 256=100% ints
        sy = sx if sy is None else (sy / 256 if sy > 8 else sy)
        self.scale = (sx, sy)
        self._update_size()
        self._mutate()

    def set_flag(self, flag, value):
        if value:
            self.add_flag(flag)
        else:
            self.remove_flag(flag)

    def _final_image(self):
        if self._img is None:
            return None
        if self.scale == (1.0, 1.0) and not self.rotation90:
            return self._img
        return _backend.transform_image(self._img, self.scale,
                                        self.rotation90)

    def _update_size(self):
        img = self._final_image()
        if img is not None:
            self.w, self.h = _backend.image_size(img)

    def draw_self(self, tile):
        img = self._final_image()
        if img is None:
            tile.outline_round_rect(0, 0, self.w, self.h, 0, 0xFF00FF, 1)
            return
        tile.blit_image(img, 0, 0)


class Scene:
    """Owns the active screen (root node) and dirty regions."""

    def __init__(self):
        self.lock = compat.RLock()
        self.active_screen = None
        self.dirty = []          # list of bbox tuples
        self.gfx = None          # framebuffer to composite onto
        self.enabled = False
        self._root_tile = None   # reused full-screen tile (see render)

    def attach(self, gfx):
        self.gfx = gfx
        self.enabled = True
        try:
            from stackchan_sim import bridge
            bridge.get().scene = self  # M5.update() flushes through this
        except Exception:
            pass

    def load_screen(self, screen):
        with self.lock:
            self.active_screen = screen
            if self.gfx:
                screen.w, screen.h = self.gfx.width(), self.gfx.height()
            self.dirty = [(0, 0, screen.w, screen.h)]

    def invalidate(self, node):
        if node is None:
            return
        with self.lock:
            # only objects attached to the active screen produce dirty rects
            root = node
            while root.parent is not None:
                root = root.parent
            if root is self.active_screen:
                self.dirty.append(node.abs_bbox())

    def flush(self):
        """Composite dirty regions of the scene onto the framebuffer."""
        if not self.enabled or self.gfx is None or self.active_screen is None:
            return
        with self.lock:
            if not self.dirty:
                return
            rects = self.dirty
            self.dirty = []
            scene_tile = self.active_screen.render(into=self._root_tile)
            self._root_tile = scene_tile
        _backend.composite_to_gfx(scene_tile, self.gfx, rects)


_scene = Scene()


def get_scene():
    return _scene
