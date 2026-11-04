# Grand finale: dances from the stackchan-micropython port
import sys
import time
import M5
import m5ui
import lvgl as lv

sys.path.append("/flash/libs")
from stackchan import get_stackchan
from stackchan.hal import get_hal
from stackchan.motion import create_default_motion
from stackchan.skin_default import DefaultAvatar
from stackchan import modifiers as mod
from stackchan import animation as anim

M5.begin()
M5.Widgets.setRotation(1)     # landscape, like the firmware
m5ui.init()
m5ui.M5Page(bg_c=0x000000).screen_load()
get_hal().init()

chan = get_stackchan()
chan.attach_motion(create_default_motion())
face = DefaultAvatar()
face.init(lv.screen_active())
chan.attach_avatar(face)
chan.add_modifier(mod.BlinkModifier())
chan.add_modifier(mod.HeadPetModifier())     # pet me!
chan.add_modifier(mod.ImuEventModifier())    # shake me!

for title, dance in (("Happy!", anim.DANCE_HAPPY), ("Robot!", anim.DANCE_ROBOT),
                     ("Panic!!", anim.DANCE_PANIC)):
    chan.add_modifier(mod.TimedSpeechModifier(title, 2000))
    dance_id = chan.add_modifier(mod.DanceModifier(dance))
    while chan.get_modifier(dance_id) is not None:
        M5.update()
        get_hal().update()
        chan.update()
        time.sleep_ms(10)
