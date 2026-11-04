"""Default avatar skin — port of avatar/skins/default (LVGL).

Same geometry as the original: eyes are a 32x32 rotatable container with a
primary-color circle plus a secondary-color square eyelid sliding over it;
the mouth is a rounded rect whose size/radius map from its weight; the
speech bubble auto-sizes to its text.

All placement goes through ``lvc.align_center`` (see lvcompat notes) and
is re-applied after size changes so it works on the emulator shim too.
"""

import lvgl as lv

from . import lvcompat as lvc
from .uitk import map_range
from .avatar import (Avatar, Feature, SpeechBubble,
                     EMOTION_NEUTRAL, EMOTION_HAPPY, EMOTION_ANGRY,
                     EMOTION_SAD, EMOTION_DOUBT, EMOTION_SLEEPY)

# eyes.cpp constants
_EYE_POS = (-70, -16)
_EYE_MIN_OFFSET = (-16, -16)
_EYE_MAX_OFFSET = (16, 16)
_EYE_SIZE_LIMIT = (8, 32)

# mouth.cpp constants
_MOUTH_POS = (0, 26)
_MOUTH_MIN_OFFSET = (-16, -16)
_MOUTH_MAX_OFFSET = (16, 16)
_MOUTH_MIN_SIZE = (90, 6)
_MOUTH_MAX_SIZE = (60, 50)
_MOUTH_MIN_RADIUS = 0
_MOUTH_MAX_RADIUS = 16

# speech_bubble.cpp constants
_SB_CONTAINER_POS = (0, 89)
_SB_CONTAINER_SIZE = (320, 74)
_SB_ARROW_OFFSET = (40, -15)
_SB_TEXT_MX = 20
_SB_BUBBLE_MIN_WIDTH = 90
_SB_BUBBLE_MAX_WIDTH = 340
_SB_BUBBLE_HEIGHT = 52
_SB_BUBBLE_MIN_OFFSET_X = 66
_SB_BUBBLE_MAX_OFFSET_X = 0


def _default_font():
    return getattr(lv, 'font_montserrat_16', None)


class DefaultEyes(Feature):
    def __init__(self, parent, primary_color, secondary_color, is_left_eye):
        Feature.__init__(self)
        self._is_left_eye = is_left_eye
        self._eyelid_offset_y = 0
        self._eye_px = 0  # current eye/eyelid square size in px

        box = _EYE_SIZE_LIMIT[1]
        self._container = lvc.container(parent)
        lvc.bg(self._container, secondary_color, 0)
        self._container.set_size(box, box)
        lvc.set_pivot(self._container, box // 2, box // 2)
        lvc.align_center(self._container)

        self._eye = lvc.container(self._container)
        self._eye.set_style_radius(lvc.RADIUS_CIRCLE, 0)
        lvc.bg(self._eye, primary_color)

        self._eyelid = lvc.container(self._container)
        lvc.bg(self._eyelid, secondary_color)

        self.set_size(0)
        self.set_weight(100)
        self.set_position(0, 0)
        self.set_rotation(0)

    def on_destroy(self):
        lvc.delete(self._container)
        self._container = self._eye = self._eyelid = None

    def _realign_children(self):
        lvc.align_center(self._eye)
        lvc.align_center(self._eyelid, 0, self._eyelid_offset_y)

    def set_position(self, x, y):
        Feature.set_position(self, x, y)
        px, py = self._position
        pos_x = _EYE_POS[0] if self._is_left_eye else -_EYE_POS[0]
        pos_x += map_range(px, -100, 100, _EYE_MIN_OFFSET[0], _EYE_MAX_OFFSET[0])
        pos_y = _EYE_POS[1] + map_range(py, -100, 100,
                                        _EYE_MIN_OFFSET[1], _EYE_MAX_OFFSET[1])
        lvc.align_center(self._container, pos_x, pos_y)
        self._realign_children()

    def set_weight(self, weight):
        Feature.set_weight(self, weight)
        self._eyelid_offset_y = -map_range(self._weight, 0, 100, 0, self._eye_px)
        lvc.align_center(self._eyelid, 0, self._eyelid_offset_y)

    def set_rotation(self, rotation):
        Feature.set_rotation(self, rotation)
        lvc.set_rotation(self._container, self._rotation)

    def set_emotion(self, emotion):
        if self.get_ignore_emotion():
            return

        def apply_style(weight, rotation):
            self.set_weight(weight)
            self.set_rotation(rotation if self._is_left_eye else -rotation)

        if emotion == EMOTION_NEUTRAL:
            apply_style(100, 0)
        elif emotion == EMOTION_HAPPY:
            apply_style(72, 1550)
        elif emotion == EMOTION_ANGRY:
            apply_style(70, 450)
        elif emotion == EMOTION_SAD:
            apply_style(70, -400)
        elif emotion == EMOTION_DOUBT:
            apply_style(75, 0)
        elif emotion == EMOTION_SLEEPY:
            apply_style(35, -50)

    def set_visible(self, visible):
        Feature.set_visible(self, visible)
        lvc.hidden(self._container, not visible)

    def set_size(self, size):
        Feature.set_size(self, size)
        eye_size = map_range(self._size, -100, 100,
                             _EYE_SIZE_LIMIT[0], _EYE_SIZE_LIMIT[1])
        self._eye_px = int(eye_size)
        self._eye.set_size(self._eye_px, self._eye_px)
        self._eyelid.set_size(self._eye_px, self._eye_px)
        self._realign_children()
        # Force eyelid update
        self.set_weight(self.get_weight())


class DefaultMouth(Feature):
    def __init__(self, parent, primary_color, secondary_color):
        Feature.__init__(self)
        self._w = _MOUTH_MIN_SIZE[0]
        self._h = _MOUTH_MIN_SIZE[1]
        self._center = _MOUTH_POS

        self._mouth = lvc.container(parent)
        lvc.bg(self._mouth, primary_color)

        self.set_position(0, 0)
        self.set_weight(0)
        self.set_rotation(0)

    def on_destroy(self):
        lvc.delete(self._mouth)
        self._mouth = None

    def _realign(self):
        lvc.align_center(self._mouth, self._center[0], self._center[1])

    def set_position(self, x, y):
        Feature.set_position(self, x, y)
        px, py = self._position
        pos_x = _MOUTH_POS[0] + map_range(px, -100, 100,
                                          _MOUTH_MIN_OFFSET[0], _MOUTH_MAX_OFFSET[0])
        pos_y = _MOUTH_POS[1] + map_range(py, -100, 100,
                                          _MOUTH_MIN_OFFSET[1], _MOUTH_MAX_OFFSET[1])
        self._center = (int(pos_x), int(pos_y))
        self._realign()

    def set_weight(self, weight):
        Feature.set_weight(self, weight)
        self._w = int(map_range(self._weight, 0, 100,
                                _MOUTH_MIN_SIZE[0], _MOUTH_MAX_SIZE[0]))
        self._h = int(map_range(self._weight, 0, 100,
                                _MOUTH_MIN_SIZE[1], _MOUTH_MAX_SIZE[1]))
        radius = map_range(self._weight, 0, 100,
                           _MOUTH_MIN_RADIUS, _MOUTH_MAX_RADIUS)
        self._mouth.set_size(self._w, self._h)
        self._mouth.set_style_radius(int(radius), 0)
        self._realign()

    def set_rotation(self, rotation):
        Feature.set_rotation(self, rotation)
        lvc.set_pivot(self._mouth, self._w // 2, self._h // 2)
        lvc.set_rotation(self._mouth, self._rotation)

    def set_visible(self, visible):
        Feature.set_visible(self, visible)
        lvc.hidden(self._mouth, not visible)


class DefaultSpeechBubble(SpeechBubble):
    def __init__(self, parent, primary_color, secondary_color, font=None):
        SpeechBubble.__init__(self)
        self._font = font or _default_font()

        self._container = lvc.container(parent)
        lvc.bg(self._container, secondary_color, 0)
        self._container.set_size(_SB_CONTAINER_SIZE[0], _SB_CONTAINER_SIZE[1])
        lvc.align_center(self._container,
                         _SB_CONTAINER_POS[0], _SB_CONTAINER_POS[1])

        # Bubble tail: the original uses a small PNG arrow; a rotated
        # square whose lower half hides behind the bubble looks the same.
        self._arrow = lvc.container(self._container)
        lvc.bg(self._arrow, primary_color)
        self._arrow.set_size(18, 18)
        lvc.set_pivot(self._arrow, 9, 9)
        lvc.set_rotation(self._arrow, 450)
        lvc.align_center(self._arrow,
                         _SB_ARROW_OFFSET[0], _SB_ARROW_OFFSET[1] + 8)

        self._bubble = lvc.container(self._container)
        self._bubble.set_style_radius(lvc.RADIUS_CIRCLE, 0)
        lvc.bg(self._bubble, primary_color)
        self._bubble.set_size(_SB_BUBBLE_MAX_WIDTH, _SB_BUBBLE_HEIGHT)
        lvc.align_center(self._bubble, 0, 11)

        self._text = lv.label(self._bubble)
        self._text.set_style_text_color(lv.color_hex(secondary_color), 0)
        if self._font is not None:
            try:
                self._text.set_style_text_font(self._font, 0)
            except Exception:
                pass
        try:
            self._text.set_style_text_align(lv.TEXT_ALIGN.CENTER, 0)
        except Exception:
            pass
        try:
            self._text.set_width(320 - _SB_TEXT_MX * 2)
        except Exception:
            pass
        self._set_long_mode()
        lvc.align_center(self._text)

        self.clear_speech()

    def _set_long_mode(self):
        label = self._text
        for enum_name in ('LONG_MODE', 'LONG'):
            enum = getattr(lv.label, enum_name, None)
            if enum is None:
                continue
            mode = getattr(enum, 'SCROLL_CIRCULAR', None)
            if mode is None:
                continue
            try:
                label.set_long_mode(mode)
                return
            except Exception:
                pass

    def on_destroy(self):
        lvc.delete(self._container)
        self._container = self._arrow = self._bubble = self._text = None

    def set_speech(self, text):
        if not text:
            self.clear_speech()
            return

        self._text.set_text(text)

        text_w = lvc.text_width(text, self._font, probe_label=self._text)
        bubble_width = min(text_w + _SB_TEXT_MX * 2, _SB_BUBBLE_MAX_WIDTH)
        bubble_width = max(bubble_width, _SB_BUBBLE_MIN_WIDTH)
        bubble_offset_x = map_range(bubble_width,
                                    _SB_BUBBLE_MIN_WIDTH, _SB_BUBBLE_MAX_WIDTH,
                                    _SB_BUBBLE_MIN_OFFSET_X, _SB_BUBBLE_MAX_OFFSET_X)

        self._bubble.set_size(int(bubble_width), _SB_BUBBLE_HEIGHT)
        lvc.align_center(self._bubble, int(bubble_offset_x), 11)
        lvc.align_center(self._text)

        self.set_visible(True)

    def clear_speech(self):
        self._text.set_text('')
        self.set_visible(False)

    def set_visible(self, visible):
        SpeechBubble.set_visible(self, visible)
        lvc.hidden(self._container, not visible)

    def set_text_font(self, font):
        if font is None:
            return
        self._font = font
        try:
            self._text.set_style_text_font(font, 0)
        except Exception:
            pass


class DefaultAvatar(Avatar):
    def __init__(self):
        Avatar.__init__(self)
        self.primary_color = 0xFFFFFF
        self.secondary_color = 0x000000
        self._panel = None

    def init(self, parent, font=None):
        self._panel = lvc.container(parent)
        self._panel.set_size(320, 240)
        lvc.bg(self._panel, self.secondary_color)
        lvc.align_center(self._panel)

        self._left_eye = DefaultEyes(self._panel, self.primary_color,
                                     self.secondary_color, True)
        self._right_eye = DefaultEyes(self._panel, self.primary_color,
                                      self.secondary_color, False)
        self._mouth = DefaultMouth(self._panel, self.primary_color,
                                   self.secondary_color)
        self._speech_bubble = DefaultSpeechBubble(self._panel,
                                                  self.primary_color,
                                                  self.secondary_color, font)

    def get_panel(self):
        return self._panel

    def destroy(self):
        Avatar.destroy(self)
        lvc.delete(self._panel)
        self._panel = None
