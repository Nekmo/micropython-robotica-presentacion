# Challenge 3a: microphone, LEDs as a VU meter
import array
import time
import M5
from hardware.stackchan import StackChan

M5.begin()
robot = StackChan(i2c=1, uart=1)
M5.Speaker.end()            # speaker and mic share the I2S bus
M5.Mic.begin()
samples = array.array("h", [0] * 800)   # 50 ms at 16 kHz


def level(buf):
    peak = max(max(buf), -min(buf))
    return min(6, peak * 6 // 12000)


while True:
    M5.Mic.record(samples, 16000, False)
    while M5.Mic.isRecording():
        time.sleep_ms(5)
    n = level(samples)
    for strip in (0, 1):
        for i in range(6):
            robot.set_rgb_color(strip, i, 0xFF4F9A if i < n else 0)
