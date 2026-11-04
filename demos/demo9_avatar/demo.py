# Challenge 4b: LVGL avatar from the stackchan-micropython port
import sys
import time
import M5
import m5ui
import lvgl as lv

sys.path.append("/flash/libs")
from stackchan import get_stackchan
from stackchan.skin_default import DefaultAvatar
from stackchan.modifiers import BlinkModifier, BreathModifier
from stackchan import avatar as av

M5.begin()
M5.Widgets.setRotation(1)     # landscape, like the firmware
m5ui.init()
page = m5ui.M5Page(bg_c=0x000000)
page.screen_load()

chan = get_stackchan()
face = DefaultAvatar()
face.init(lv.screen_active())
chan.attach_avatar(face)
chan.add_modifier(BlinkModifier())
chan.add_modifier(BreathModifier())

emotions = ("happy", "angry", "sad", "doubt", "sleepy", "neutral")
for name in emotions:
    face.set_emotion(av.EMOTION_NAMES[name])
    face.set_speech(name + "!")
    end = time.ticks_add(time.ticks_ms(), 2000)
    while time.ticks_diff(end, time.ticks_ms()) > 0:
        M5.update()
        chan.update()
        time.sleep_ms(15)
face.clear_speech()
