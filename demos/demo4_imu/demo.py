# Challenge 2b: IMU, a spirit level made of LEDs
import time
import M5
from hardware.stackchan import StackChan

M5.begin()
robot = StackChan(i2c=1, uart=1)

while True:
    M5.update()
    ax, ay, az = M5.Imu.getAccel()     # in g
    # Map the tilt (-0.5g..0.5g) to one of the 6 LEDs of each strip
    pos = int(min(5, max(0, (ax + 0.5) * 6)))
    for strip in (0, 1):
        for i in range(6):
            robot.set_rgb_color(strip, i, 0x39D0D8 if i == pos else 0x050505)
    if abs(ax) + abs(ay) > 2.2:        # shaken, not stirred
        robot.set_rgb_color(0xFF0000)
        M5.Speaker.tone(220, 200)
    time.sleep_ms(50)
