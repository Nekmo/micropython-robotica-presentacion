# Challenge 3a: microphone, LEDs as a VU meter
import array
import time
import M5
from machine import I2C, Pin

i2c = I2C(1, scl=Pin(11), sda=Pin(12), freq=400_000)
IOE = 0x6F                                     # I/O expander: drives the 12 LEDs


def rgb565(rgb):
    r, g, b = rgb >> 16, rgb >> 8 & 0xFF, rgb & 0xFF
    color = (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3
    return bytes([color & 0xFF, color >> 8])


def show(colors):                              # one colour per LED (2 strips of 6)
    i2c.writeto_mem(IOE, 0x30, b"".join(rgb565(c) for c in colors))
    i2c.writeto_mem(IOE, 0x24, bytes([12 | 1 << 6]))


M5.Speaker.end()                               # speaker and mic share the I2S bus
M5.Mic.begin()
samples = array.array("h", [0] * 800)          # 50 ms at 16 kHz


def record():
    M5.Mic.record(samples, 16000, False)
    while M5.Mic.isRecording():
        time.sleep_ms(5)


record()                                       # the first one starts with a click
last = None
while True:
    record()
    peak = max(max(samples), -min(samples))    # loudest sample, 0 .. 32767
    lit = min(6, peak * 6 // 12000)            # how many LEDs to light
    if lit != last:                            # only when the level changes
        show([0xFF4F9A if i < lit else 0 for i in range(6)] * 2)
        print("%5d %s" % (peak, "█" * lit))
        last = lit
