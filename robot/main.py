"""Stack-chan MicroPython firmware — entry point.

Port of the 2026 M5Stack Stack-chan firmware (app_main in main.cpp):
HAL init -> motion init -> install apps -> main loop.
"""

import sys
import time

if '/flash/libs' not in sys.path:
    sys.path.append('/flash/libs')
if 'libs' not in sys.path:
    sys.path.append('libs')

import M5
import m5ui  # noqa: F401  (initialises LVGL glue on UIFlow)
import lvgl as lv


def main():
    M5.begin()
    try:
        M5.Widgets.setRotation(1)
    except Exception:
        pass
    m5ui.init()

    # A base page keeps lv.screen_active() valid with boot_option=0
    page = m5ui.M5Page(bg_c=0x000000)
    page.screen_load()

    from stackchan.hal import get_hal
    from stackchan import get_stackchan
    from stackchan.motion import create_default_motion
    from stackchan.apps import get_mooncake
    from stackchan.apps.launcher import AppLauncher
    from stackchan.apps.avatar_app import AppAvatar
    from stackchan.apps.dance_app import AppDance
    from stackchan.apps.remote_app import AppRemote

    hal = get_hal()
    hal.init()

    stackchan = get_stackchan()
    stackchan.attach_motion(create_default_motion())

    mooncake = get_mooncake()
    mooncake.install_launcher(AppLauncher())
    mooncake.install_app(AppAvatar())
    mooncake.install_app(AppDance())
    mooncake.install_app(AppRemote())
    mooncake.start()

    while True:
        M5.update()
        hal.update()

        # PWR button also closes the active app (handy without touch)
        try:
            if M5.BtnPWR.wasClicked():
                mooncake.request_close()
        except Exception:
            pass

        mooncake.update()
        time.sleep_ms(10)


main()