# Challenge 2b: IMU, how have you left me?
import math
import time
import M5
from machine import I2C, Pin

i2c = I2C(1, scl=Pin(11), sda=Pin(12), freq=400_000)
IOE = 0x6F                                     # I/O expander: drives the 12 LEDs


def leds(rgb):
    r, g, b = rgb >> 16, rgb >> 8 & 0xFF, rgb & 0xFF
    color = (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3              # RGB565
    i2c.writeto_mem(IOE, 0x30, bytes([color & 0xFF, color >> 8]) * 12)
    i2c.writeto_mem(IOE, 0x24, bytes([12 | 1 << 6]))               # 12 LEDs, show


def gravity():
    x, y, z = M5.Imu.getAccel()                # in g: at rest, only gravity
    return x, y, z, math.sqrt(x * x + y * y + z * z)


ux, uy, uz, ug = gravity()                     # the pose it starts in is "upright"
last, calm_at = None, 0
while True:
    x, y, z, g = gravity()
    cos = (x * ux + y * uy + z * uz) / (g * ug)
    angle = math.acos(max(-1, min(1, cos))) * 180 / math.pi
    if g > 1.8:                                # a shake: far more than 1 g
        calm_at = time.ticks_add(time.ticks_ms(), 800)
    if time.ticks_diff(calm_at, time.ticks_ms()) > 0:
        state, color = "¡agitado!", 0xFF0000
    elif angle < 20:
        state, color = "de pie", 0x39D0D8
    elif angle < 60:
        state, color = "inclinado", 0xFFC44D
    elif angle < 140:
        state, color = "tumbado", 0xFF4F9A
    else:
        state, color = "boca abajo", 0x8A5CFF
    if state != last:                          # only when something changes
        print("%-10s %3d°" % (state, int(angle)))
        leds(color)
        last = state
    time.sleep_ms(50)
