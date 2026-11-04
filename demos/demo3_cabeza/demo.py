# Challenge 2a: pet the head (3 capacitive zones)
import time
import M5
from hardware.stackchan import StackChan

robot = StackChan(i2c=1, uart=1)
COLORS = (0x39D0D8, 0xFF4F9A, 0xFFC44D)   # front, middle, back

while True:
    zones = robot.get_touch()          # e.g. [0, 1, 0]
    color = 0
    for zone, touched in enumerate(zones):
        if touched:
            color = COLORS[zone]
    robot.set_rgb_color(color)
    if any(zones):
        M5.Speaker.tone(600 + 200 * zones.index(max(zones)), 40)
    time.sleep_ms(60)
