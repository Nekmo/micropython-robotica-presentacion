# Challenge 2a: pet the head (Si12T capacitive sensor: 3 zones over I2C)
import time
import M5
from machine import I2C, Pin

i2c = I2C(1, scl=Pin(11), sda=Pin(12), freq=400_000)
SI12T = 0x68                                   # touch controller address
IOE = 0x6F                                     # I/O expander: drives the 12 LEDs


def leds(rgb):
    r, g, b = rgb >> 16, rgb >> 8 & 0xFF, rgb & 0xFF
    color = (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3              # RGB565
    i2c.writeto_mem(IOE, 0x30, bytes([color & 0xFF, color >> 8]) * 12)
    i2c.writeto_mem(IOE, 0x24, bytes([12 | 1 << 6]))               # 12 LEDs, show


ZONES = ("delante", "centro", "detrás")
COLORS = (0x39D0D8, 0xFF4F9A, 0xFFC44D)
LEVELS = ("", "suave", "medio", "fuerte")
last = None
while True:
    raw = i2c.readfrom_mem(SI12T, 0x10, 1)[0]  # 2 bits per zone
    levels = [(raw >> shift) & 0b11 for shift in (0, 2, 4)]
    if levels != last:
        touched = [f"{ZONES[i]} ({LEVELS[v]})" for i, v in enumerate(levels) if v]
        print("toque:", " + ".join(touched) if touched else "-",
              " ".join("█" * v + "·" * (3 - v) for v in levels))
        strongest = levels.index(max(levels))
        leds(COLORS[strongest] if touched else 0)
        if touched:
            M5.Speaker.tone(600 + 200 * strongest, 40)
        last = levels
    time.sleep_ms(50)
