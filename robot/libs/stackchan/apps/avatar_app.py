"""AVATAR app — the default Stack-chan face.

Mirrors the ambient behaviour of the original firmware's avatar display
(stackchan_display.cc SetupUI): breath + blink + head-pet + IMU shake
modifiers, plus idle motion/expression.  Tapping the face cycles the
emotion and shows a speech bubble (standalone stand-in for the original
tap-to-talk hook).
"""

import lvgl as lv

from .. import get_stackchan
from ..skin_default import DefaultAvatar
from ..avatar import (EMOTION_NEUTRAL, EMOTION_HAPPY, EMOTION_ANGRY,
                      EMOTION_SAD, EMOTION_DOUBT, EMOTION_SLEEPY)
from ..modifiers import (BreathModifier, BlinkModifier, HeadPetModifier,
                         ImuEventModifier, IdleMotionModifier,
                         IdleExpressionModifier, SpeakingModifier,
                         TimedSpeechModifier)
from . import App, HomeIndicator, TapTracker, in_home_region

_EMOTION_CYCLE = (
    (EMOTION_NEUTRAL, 'Hello!'),
    (EMOTION_HAPPY, 'I am happy!'),
    (EMOTION_ANGRY, 'Grrr...!'),
    (EMOTION_SAD, 'So sad...'),
    (EMOTION_DOUBT, 'Hmm...?'),
    (EMOTION_SLEEPY, 'Zzz...'),
)

# idleRandomMovementLevel -> IdleMotionModifier intervals
IDLE_MOTION_LEVELS = {
    0: None,
    1: (8000, 12000),
    2: (4000, 8000),
    3: (2000, 4000),
}


class AppAvatar(App):
    name = 'AVATAR'
    theme_color = 0xFF6699

    def __init__(self, idle_motion_level=2):
        App.__init__(self)
        self._idle_motion_level = idle_motion_level
        self._home = None
        self._blink_id = -1
        self._emotion_index = 0
        self._taps = TapTracker()

    def on_open(self):
        self._taps.rearm()
        stackchan = get_stackchan()

        avatar = DefaultAvatar()
        avatar.init(lv.screen_active())
        stackchan.attach_avatar(avatar)

        stackchan.clear_modifiers()
        stackchan.add_modifier(BreathModifier())
        self._blink_id = stackchan.add_modifier(BlinkModifier())
        stackchan.add_modifier(HeadPetModifier())
        stackchan.add_modifier(ImuEventModifier())
        stackchan.add_modifier(IdleExpressionModifier())
        level = IDLE_MOTION_LEVELS.get(self._idle_motion_level)
        if level is not None:
            stackchan.add_modifier(IdleMotionModifier(level[0], level[1]))

        self._emotion_index = 0
        self._home = HomeIndicator(0xFF9ABC)

    def on_running(self):
        stackchan = get_stackchan()

        tap = self._taps.poll()
        if tap is not None:
            if in_home_region(tap[0], tap[1]):
                self.close()
                return
            self._emotion_index = (self._emotion_index + 1) % len(_EMOTION_CYCLE)
            emotion, text = _EMOTION_CYCLE[self._emotion_index]
            if stackchan.has_avatar():
                stackchan.avatar().set_emotion(emotion)
                stackchan.add_modifier(TimedSpeechModifier(text, 3000))
                stackchan.add_modifier(SpeakingModifier(1500, 180, False))
                blink = stackchan.get_modifier(self._blink_id)
                if blink is not None:
                    blink.resync_eye_weights()

        stackchan.update()

    def on_close(self):
        stackchan = get_stackchan()
        stackchan.clear_modifiers()
        stackchan.reset_avatar()
        if self._home is not None:
            self._home.destroy()
            self._home = None
        motion = stackchan.motion()
        if motion is not None:
            motion.set_modify_lock(False)
            motion.go_home(300)