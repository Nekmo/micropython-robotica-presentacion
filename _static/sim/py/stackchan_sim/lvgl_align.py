"""LVGL align constants and resolution helper."""


class ALIGN:
    DEFAULT = 0
    TOP_LEFT = 1
    TOP_MID = 2
    TOP_RIGHT = 3
    LEFT_MID = 4
    RIGHT_MID = 6
    BOTTOM_LEFT = 7
    BOTTOM_MID = 8
    BOTTOM_RIGHT = 9
    CENTER = 10
    OUT_TOP_MID = 12
    OUT_BOTTOM_MID = 16
    OUT_LEFT_MID = 20
    OUT_RIGHT_MID = 24


def resolve(align, cw, ch, w, h):
    """Return (x, y) for a w×h box aligned inside a cw×ch container."""
    xs = {
        ALIGN.TOP_LEFT: 0, ALIGN.LEFT_MID: 0, ALIGN.BOTTOM_LEFT: 0,
        ALIGN.TOP_MID: (cw - w) // 2, ALIGN.CENTER: (cw - w) // 2,
        ALIGN.BOTTOM_MID: (cw - w) // 2, ALIGN.OUT_TOP_MID: (cw - w) // 2,
        ALIGN.OUT_BOTTOM_MID: (cw - w) // 2,
        ALIGN.TOP_RIGHT: cw - w, ALIGN.RIGHT_MID: cw - w,
        ALIGN.BOTTOM_RIGHT: cw - w,
        ALIGN.OUT_LEFT_MID: -w, ALIGN.OUT_RIGHT_MID: cw,
    }
    ys = {
        ALIGN.TOP_LEFT: 0, ALIGN.TOP_MID: 0, ALIGN.TOP_RIGHT: 0,
        ALIGN.LEFT_MID: (ch - h) // 2, ALIGN.CENTER: (ch - h) // 2,
        ALIGN.RIGHT_MID: (ch - h) // 2, ALIGN.OUT_LEFT_MID: (ch - h) // 2,
        ALIGN.OUT_RIGHT_MID: (ch - h) // 2,
        ALIGN.BOTTOM_LEFT: ch - h, ALIGN.BOTTOM_MID: ch - h,
        ALIGN.BOTTOM_RIGHT: ch - h,
        ALIGN.OUT_TOP_MID: -h, ALIGN.OUT_BOTTOM_MID: ch,
    }
    return xs.get(align, 0), ys.get(align, 0)
