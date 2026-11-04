"""Small helpers over the LVGL v9 MicroPython bindings.

Centralises the calls whose names/availability vary between builds
(UIFlow firmware vs the esp-emulator's lvgl shim) so the rest of the
port stays clean.

Positioning model: we only use ``obj.align(lv.ALIGN.*, dx, dy)``.  On
real LVGL that sets a persistent alignment; on the emulator shim it is
a one-shot computation, so callers re-align after changing an object's
size (harmless on real LVGL).
"""

import lvgl as lv

RADIUS_CIRCLE = getattr(lv, 'RADIUS_CIRCLE', 0x7FFF)


def color(value):
    return lv.color_hex(value)


def plain(obj):
    """Strip decorations: no border/padding/shadow/outline, no scroll."""
    obj.set_style_border_width(0, 0)
    obj.set_style_pad_all(0, 0)
    try:
        obj.set_style_shadow_width(0, 0)
    except AttributeError:
        pass
    try:
        obj.set_style_outline_width(0, 0)
    except AttributeError:
        pass
    try:
        obj.remove_flag(lv.obj.FLAG.SCROLLABLE)
    except AttributeError:
        try:
            obj.clear_flag(lv.obj.FLAG.SCROLLABLE)
        except AttributeError:
            pass
    return obj


def container(parent):
    """lv.obj configured like a uitk::lvgl_cpp::Container."""
    obj = lv.obj(parent)
    plain(obj)
    obj.set_style_radius(0, 0)
    return obj


def bg(obj, hex_color, opa=255):
    obj.set_style_bg_color(lv.color_hex(hex_color), 0)
    obj.set_style_bg_opa(opa, 0)


def align(obj, alignment, x=0, y=0):
    obj.align(alignment, int(x), int(y))


def align_center(obj, x=0, y=0):
    obj.align(lv.ALIGN.CENTER, int(x), int(y))


def hidden(obj, is_hidden):
    if is_hidden:
        obj.add_flag(lv.obj.FLAG.HIDDEN)
    else:
        obj.remove_flag(lv.obj.FLAG.HIDDEN)


def set_pivot(obj, x, y):
    try:
        obj.set_style_transform_pivot_x(x, 0)
        obj.set_style_transform_pivot_y(y, 0)
    except AttributeError:
        pass


def set_rotation(obj, angle_0_3600):
    """Visual rotation in 0.1 degree units (0..3600)."""
    angle = int(angle_0_3600) % 3600
    try:
        obj.set_style_transform_rotation(angle, 0)
    except AttributeError:
        try:
            obj.set_style_transform_angle(angle, 0)
        except AttributeError:
            pass


def image_recolor(img, hex_color, opa=255):
    for prefix in ('image', 'img'):
        try:
            getattr(img, 'set_style_%s_recolor' % prefix)(lv.color_hex(hex_color), 0)
            getattr(img, 'set_style_%s_recolor_opa' % prefix)(opa, 0)
            return
        except AttributeError:
            continue


def load_image(parent, path):
    """Create an lv.image from a filesystem path, or None on failure."""
    try:
        img = lv.image(parent)
    except AttributeError:
        img = lv.img(parent)
    for candidate in (path, 'S:' + path, path[1:] if path.startswith('/') else path):
        try:
            img.set_src(candidate)
            return img
        except Exception:
            continue
    try:
        img.delete()
    except Exception:
        pass
    return None


def delete(obj):
    if obj is None:
        return
    try:
        obj.delete()
    except Exception:
        pass


def text_width(text, font=None, probe_label=None):
    """Measure rendered text width in px (best effort across bindings)."""
    if not text:
        return 0
    if font is None:
        font = getattr(lv, 'font_montserrat_16', None)
    try:
        point = lv.point_t()
        lv.text_get_size(point, text, font, 0, 0, 0x3FFF, 0)
        return point.x
    except Exception:
        pass
    if probe_label is not None:
        # emulator shim: labels autosize on set_text
        try:
            width = probe_label.get_width()
            if width > 0:
                return width
        except Exception:
            pass
    height = 16
    try:
        height = font.get_line_height()
    except Exception:
        try:
            height = font.px
        except Exception:
            pass
    return int(len(text) * height * 0.55)