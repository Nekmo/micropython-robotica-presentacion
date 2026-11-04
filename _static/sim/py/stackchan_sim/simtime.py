"""``time`` replacement: real MicroPython time, cooperative sleeps.

Planted in ``sys.modules`` by the runner. Sleeping hands control to the
bridge, which keeps servos animating, inputs live and frames flowing
while the user program waits (like the firmware's background tasks).
"""

import time as _rt

ticks_ms = _rt.ticks_ms
ticks_us = _rt.ticks_us
ticks_cpu = _rt.ticks_cpu
ticks_add = _rt.ticks_add
ticks_diff = _rt.ticks_diff
time = _rt.time
time_ns = _rt.time_ns
localtime = _rt.localtime
gmtime = getattr(_rt, "gmtime", _rt.localtime)
mktime = _rt.mktime


def _bridge():
    from stackchan_sim import bridge
    return bridge.get()


def sleep_ms(ms):
    _bridge().sleep_ms(max(0, ms))


def sleep_us(us):
    _bridge().sleep_ms(max(0, us) / 1000)


def sleep(seconds):
    _bridge().sleep_ms(max(0, seconds) * 1000)
