"""Port of stackchan/avatar/avatar (Element, Feature, SpeechBubble, Avatar).

Positions are normalized (-100..100), rotations are 0..3600 (0.1 deg),
weights 0..100 and sizes -100..100, exactly like the original firmware.
"""

from .uitk import clamp
from .pool import ObjectPool, Poolable

# Emotion enum
EMOTION_NEUTRAL = 0
EMOTION_HAPPY = 1
EMOTION_ANGRY = 2
EMOTION_SAD = 3
EMOTION_DOUBT = 4
EMOTION_SLEEPY = 5

EMOTION_NAMES = {
    'neutral': EMOTION_NEUTRAL,
    'happy': EMOTION_HAPPY,
    'laughing': EMOTION_HAPPY,
    'angry': EMOTION_ANGRY,
    'sad': EMOTION_SAD,
    'crying': EMOTION_SAD,
    'doubtful': EMOTION_DOUBT,
    'doubt': EMOTION_DOUBT,
    'sleepy': EMOTION_SLEEPY,
}


class Element(object):
    def __init__(self):
        self._position = (0, 0)
        self._rotation = 0
        self._visible = True
        self._ignore_emotion = False

    def set_position(self, x, y):
        self._position = (clamp(x, -100, 100), clamp(y, -100, 100))

    def get_position(self):
        return self._position

    def set_rotation(self, rotation):
        self._rotation = clamp(rotation, 0, 3600)

    def get_rotation(self):
        return self._rotation

    def set_emotion(self, emotion):
        pass

    def get_emotion(self):
        return EMOTION_NEUTRAL

    def set_ignore_emotion(self, ignore):
        self._ignore_emotion = ignore

    def get_ignore_emotion(self):
        return self._ignore_emotion

    def set_visible(self, visible):
        self._visible = visible

    def get_visible(self):
        return self._visible

    def _update(self):
        pass

    def on_destroy(self):
        pass


class Feature(Element):
    def __init__(self):
        Element.__init__(self)
        self._weight = 0
        self._size = 0

    def set_weight(self, weight):
        self._weight = clamp(weight, 0, 100)

    def get_weight(self):
        return self._weight

    def set_size(self, size):
        self._size = clamp(size, -100, 100)

    def get_size(self):
        return self._size


class SpeechBubble(Element):
    def set_speech(self, text):
        pass

    def clear_speech(self):
        pass

    def set_text_font(self, font):
        pass


class Decorator(Poolable, Element):
    def __init__(self):
        Poolable.__init__(self)
        Element.__init__(self)


class Avatar(object):
    """Avatar base class; skins populate the key elements."""

    def __init__(self):
        self._emotion = EMOTION_NEUTRAL
        self._decorator_pool = ObjectPool()
        self._is_modify_locked = False
        # key elements
        self._left_eye = None
        self._right_eye = None
        self._mouth = None
        self._speech_bubble = None

    # -- key element access -------------------------------------------
    def left_eye(self):
        return self._left_eye

    def right_eye(self):
        return self._right_eye

    def mouth(self):
        return self._mouth

    def _for_each_element(self, callback):
        for element in (self._left_eye, self._right_eye, self._mouth,
                        self._speech_bubble):
            if element is not None:
                callback(element)

    # -- update ---------------------------------------------------------
    def update(self):
        self._for_each_element(lambda e: e._update())
        self._decorator_pool.for_each(lambda d, i: d._update())
        self._decorator_pool.cleanup()

    # -- emotion ---------------------------------------------------------
    def set_emotion(self, emotion):
        self._emotion = emotion
        self._for_each_element(lambda e: e.set_emotion(emotion))
        self._decorator_pool.for_each(lambda d, i: d.set_emotion(emotion))

    def get_emotion(self):
        return self._emotion

    # -- speech ---------------------------------------------------------
    def set_speech(self, text):
        if self._speech_bubble is not None:
            self._speech_bubble.set_speech(text)

    def clear_speech(self):
        if self._speech_bubble is not None:
            self._speech_bubble.clear_speech()

    def set_speech_text_font(self, font):
        if self._speech_bubble is not None:
            self._speech_bubble.set_text_font(font)

    # -- modify lock ------------------------------------------------------
    def set_modify_lock(self, locked):
        self._is_modify_locked = locked

    def is_modify_locked(self):
        return self._is_modify_locked

    # -- decorators --------------------------------------------------------
    def add_decorator(self, decorator):
        return self._decorator_pool.create(decorator)

    def remove_decorator(self, decorator_id):
        if decorator_id is None or decorator_id < 0:
            return False
        return self._decorator_pool.destroy(decorator_id)

    def clear_decorators(self):
        self._decorator_pool.clear()

    # -- teardown ------------------------------------------------------------
    def destroy(self):
        """Release LVGL resources (called by StackChan.reset_avatar())."""
        self.clear_decorators()
        self._for_each_element(lambda e: e.on_destroy())
        self._left_eye = None
        self._right_eye = None
        self._mouth = None
        self._speech_bubble = None