"""DANCE app — plays the built-in keyframe dances.

Tap the face to start the next dance (Happy, Robot, Panic, LookAround);
tapping during a dance stops it, like the original avatar app does.
"""

import lvgl as lv

from .. import get_stackchan
from ..skin_default import DefaultAvatar
from ..modifiers import (BreathModifier, BlinkModifier, DanceModifier,
                         TimedSpeechModifier)
from ..animation import (DANCE_HAPPY, DANCE_ROBOT, DANCE_PANIC,
                         DANCE_LOOK_AROUND)
from . import App, HomeIndicator, TapTracker, in_home_region

_DANCES = (
    ('Happy dance!', DANCE_HAPPY),
    ('Robot dance!', DANCE_ROBOT),
    ('Panic!!', DANCE_PANIC),
    ('Looking around...', DANCE_LOOK_AROUND),
)


class AppDance(App):
    name = 'DANCE'
    theme_color = 0xB77BFF

    def __init__(self):
        App.__init__(self)
        self._home = None
        self._dance_index = -1
        self._dance_modifier_id = -1
        self._taps = TapTracker()

    def on_open(self):
        self._taps.rearm()
        stackchan = get_stackchan()

        avatar = DefaultAvatar()
        avatar.init(lv.screen_active())
        stackchan.attach_avatar(avatar)

        stackchan.clear_modifiers()
        stackchan.add_modifier(BreathModifier())
        stackchan.add_modifier(BlinkModifier())
        stackchan.add_modifier(TimedSpeechModifier('Tap me to dance!', 4000))

        self._dance_index = -1
        self._dance_modifier_id = -1
        self._home = HomeIndicator(0xB77BFF)

    def on_running(self):
        stackchan = get_stackchan()

        tap = self._taps.poll()
        if tap is not None:
            if in_home_region(tap[0], tap[1]):
                self.close()
                return
            dance = stackchan.get_modifier(self._dance_modifier_id)
            if dance is not None:
                # tap during a dance stops it
                stackchan.remove_modifier(self._dance_modifier_id)
                self._dance_modifier_id = -1
            else:
                self._dance_index = (self._dance_index + 1) % len(_DANCES)
                name, sequence = _DANCES[self._dance_index]
                stackchan.add_modifier(TimedSpeechModifier(name, 2000))
                self._dance_modifier_id = stackchan.add_modifier(
                    DanceModifier(sequence))

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
            motion.go_home(300)