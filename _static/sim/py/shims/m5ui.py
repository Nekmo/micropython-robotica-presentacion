"""m5ui shim — UIFlow's LVGL widget layer on top of the lvgl shim."""

import lvgl as lv

from stackchan_sim import lvgl_scene as _scene
from stackchan_sim import bridge as _bridge_mod

_initialized = False


def init():
    """Initialise LVGL rendering (hooked into M5.update, like the firmware)."""
    global _initialized
    _initialized = True
    scene = _scene.get_scene()
    if scene.gfx is None:
        import M5
        scene.attach(M5.Display)
    scene.enabled = True


def deinit():
    _scene.get_scene().enabled = False


class _M5Base:
    """Wrapper exposing both m5ui-style and passthrough lvgl-style methods."""

    _node = None

    def __getattr__(self, name):
        return getattr(self._node, name)


class M5Page(_M5Base):
    def __init__(self, bg_c=0xFFFFFF):
        self._node = _scene.SceneNode(None, 320, 240)
        self._node.styles.update(bg_color=bg_c, bg_opa=255, border_width=0,
                                 radius=0)

    def screen_load(self):
        _scene.get_scene().load_screen(self._node)

    def set_bg_color(self, color, opa=255, part=0):
        self._node.set_style_bg_color(color, part)
        self._node.set_style_bg_opa(opa, part)

    def add_event_cb(self, handler, event=None, user_data=None):
        pass


class M5Label(_M5Base):
    def __init__(self, text="", x=0, y=0, text_c=0x000000, bg_c=0xFFFFFF,
                 bg_opa=0, font=None, parent=None):
        node_parent = getattr(parent, "_node", parent)
        if node_parent is None:
            node_parent = _scene.get_scene().active_screen
        self._node = _scene.LabelNode(node_parent)
        self._node.styles.update(text_color=text_c, bg_color=bg_c,
                                 bg_opa=bg_opa)
        if font is not None:
            self._node.set_style_text_font(font)
        self._node.set_text(text)
        self._node.set_pos(x, y)

    def set_text(self, text):
        self._node.set_text(text)

    def get_text(self):
        return self._node.get_text()

    def set_text_color(self, color, opa=255, part=0):
        self._node.set_style_text_color(color)
        self._node.set_style_text_opa(opa)

    def set_bg_color(self, color, opa=255, part=0):
        self._node.set_style_bg_color(color)
        self._node.set_style_bg_opa(opa)

    def set_style_text_font(self, font, part=0):
        self._node.set_style_text_font(font, part)


class M5Image(_M5Base):
    def __init__(self, path=None, x=0, y=0, parent=None):
        node_parent = getattr(parent, "_node", parent)
        if node_parent is None:
            node_parent = _scene.get_scene().active_screen
        self._node = _scene.ImageNode(node_parent)
        if path:
            self._node.set_src(path)
        self._node.set_pos(x, y)

    def set_image(self, path):
        self._node.set_src(path)


class M5LED(_M5Base):
    """LVGL LED widget: filled circle with a soft glow."""

    def __init__(self, x=0, y=0, size=20, color=0xFF0000, on=True,
                 parent=None):
        node_parent = getattr(parent, "_node", parent)
        if node_parent is None:
            node_parent = _scene.get_scene().active_screen
        self._node = _scene.SceneNode(node_parent, size, size)
        self._node.styles.update(radius=_scene.RADIUS_CIRCLE, bg_color=color,
                                 border_width=0)
        self._node.set_pos(x, y)
        self._color = color
        self._brightness = 100
        self._on = on
        self._apply()

    def _apply(self):
        level = self._brightness if self._on else 15
        r = ((self._color >> 16) & 0xFF) * level // 100
        g = ((self._color >> 8) & 0xFF) * level // 100
        b = (self._color & 0xFF) * level // 100
        self._node.set_style_bg_color((r << 16) | (g << 8) | b)

    def on(self):
        self._on = True
        self._apply()

    def off(self):
        self._on = False
        self._apply()

    def toggle(self):
        self._on = not self._on
        self._apply()

    def set_color(self, color):
        self._color = color
        self._apply()

    def set_brightness(self, value):
        self._brightness = max(0, min(100, int(value)))
        self._apply()


class _M5Stub(_M5Base):
    """Placeholder for m5ui widgets not yet emulated: renders a grey box."""

    def __init__(self, *args, parent=None, **kwargs):
        node_parent = getattr(parent, "_node", parent)
        if node_parent is None:
            node_parent = _scene.get_scene().active_screen
        self._node = _scene.SceneNode(node_parent, 60, 30)
        self._node.styles.update(bg_color=0x555555, border_width=1,
                                 border_color=0x999999, radius=4)
        try:
            _bridge_mod.get().log(
                f"m5ui: {type(self).__name__} not fully emulated", "warn")
        except Exception:
            pass

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def _noop(*a, **k):
            return None
        return _noop


for _name in ("M5Arc", "M5Bar", "M5Button", "M5ButtonMatrix", "M5Calendar",
              "M5Canvas", "M5Checkbox", "M5Dropdown", "M5Keyboard", "M5Line",
              "M5List", "M5Menu", "M5Msgbox", "M5Roller", "M5Scale",
              "M5Slider", "M5Spinbox", "M5Spinner", "M5Switch", "M5Table",
              "M5TabView", "M5TextArea", "M5Window"):
    globals()[_name] = type(_name, (_M5Stub,), {})
del _name
