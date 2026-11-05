# Challenge 2c: shy Stack-chan (LTR-553 proximity sensor over I2C)
import time
from machine import I2C, Pin, UART
from hardware.stackchan import StackChan

StackChan(i2c=1, uart=1).set_servo_power(True)   # Stack-chan: servo power
i2c = I2C(1, scl=Pin(11), sda=Pin(12), freq=400_000)
uart = UART(1, baudrate=1_000_000, tx=6, rx=7)
LTR553, IOE = 0x23, 0x6F                       # proximity sensor, LED driver


def proximity():                               # infrared bounced back: 0 .. 2047
    low, high = i2c.readfrom_mem(LTR553, 0x8D, 2)
    return (high & 0x07) << 8 | low


def leds(rgb):
    r, g, b = rgb >> 16, rgb >> 8 & 0xFF, rgb & 0xFF
    color = (r & 0xF8) << 8 | (g & 0xFC) << 3 | b >> 3              # RGB565
    i2c.writeto_mem(IOE, 0x30, bytes([color & 0xFF, color >> 8]) * 12)
    i2c.writeto_mem(IOE, 0x24, bytes([12 | 1 << 6]))               # 12 LEDs, show


def turn(steps, ms):                           # head servo (ID 1), as in the bus demo
    body = bytes([1, 9, 0x03, 42, steps >> 8, steps & 0xFF, ms >> 8, ms & 0xFF, 0, 0])
    uart.write(b"\xff\xff" + body + bytes([~sum(body) & 0xFF]))


# The glass reflects some light too: measure it with nothing in front
print("calibrando: no acerques la mano...")
rest = 0
for _ in range(10):
    rest += proximity() / 10
    time.sleep_ms(100)
print("en reposo: %d" % int(rest))

near, shy, last = 0, False, None
while True:
    near = near * 0.7 + (proximity() - rest) * 0.3   # smoothed, above rest
    bar = "█" * max(0, min(10, int(near // 25)))
    if bar != last:                            # how close the hand is
        print("mano %4d %s" % (int(near), bar))
        last = bar
    if near > 120 and not shy:
        shy = True
        print("¡qué vergüenza!")
        leds(0xF7A59E)
        turn(600, 1000)                        # look away, slowly
    elif near < 50 and shy:
        shy = False
        print("ya se ha ido")
        leds(0)
        turn(460, 1200)                        # back to the centre
    time.sleep_ms(100)
