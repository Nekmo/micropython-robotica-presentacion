"""lvgl (lv) shim — small LVGL v9 subset backed by esp_emulator's scene graph."""

from stackchan_sim import lvgl_scene as _scene
from stackchan_sim.gfx import FontSpec
from stackchan_sim.lvgl_align import ALIGN  # noqa: F401  (lv.ALIGN)

RADIUS_CIRCLE = _scene.RADIUS_CIRCLE


class _FLAG:
    HIDDEN = _scene.FLAG_HIDDEN
    SCROLLABLE = _scene.FLAG_SCROLLABLE
    CLICKABLE = _scene.FLAG_CLICKABLE


class obj(_scene.SceneNode):
    FLAG = _FLAG

    def __init__(self, parent=None, w=100, h=100):
        node_parent = getattr(parent, "_node", parent)
        super().__init__(node_parent, w, h)


class label(_scene.LabelNode):
    FLAG = _FLAG

    def __init__(self, parent=None):
        node_parent = getattr(parent, "_node", parent)
        super().__init__(node_parent)


class image(_scene.ImageNode):
    FLAG = _FLAG

    def __init__(self, parent=None):
        node_parent = getattr(parent, "_node", parent)
        super().__init__(node_parent)


img = image


def color_hex(value):
    return int(value) & 0xFFFFFF


def color_make(r, g, b):
    return (int(r) << 16) | (int(g) << 8) | int(b)


def color_white():
    return 0xFFFFFF


def color_black():
    return 0x000000


def screen_active():
    return _scene.get_scene().active_screen


def screen_load(screen):
    node = getattr(screen, "_node", screen)
    _scene.get_scene().load_screen(node)


def task_handler():
    _scene.get_scene().flush()


def tick_inc(ms):
    pass


class PART:
    MAIN = 0
    SCROLLBAR = 1
    INDICATOR = 2
    KNOB = 3


class OPA:
    TRANSP = 0
    COVER = 255


class STATE:
    DEFAULT = 0
    CHECKED = 1
    FOCUSED = 2
    PRESSED = 4
    DISABLED = 8


# fonts: lv.font_montserrat_NN
for _px in (8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38,
            40, 42, 44, 46, 48):
    globals()[f"font_montserrat_{_px}"] = FontSpec(f"montserrat_{_px}", _px)
del _px
