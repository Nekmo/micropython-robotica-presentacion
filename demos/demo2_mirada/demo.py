# Challenge 1b: smooth motion with an easing curve
import math
import time
from hardware.stackchan import StackChan

robot = StackChan(i2c=1, uart=1)
robot.set_servo_power(True)
X, Y = robot.SERVO_ID_X, robot.SERVO_ID_Y
home_x = robot.get_servo_angle(X)
home_y = robot.get_servo_angle(Y)


def ease_in_out(t):
    return 0.5 - math.cos(t * math.pi) / 2


def glide(x0, x1, y0, y1, ms=1200, steps=40):
    for i in range(steps + 1):
        k = ease_in_out(i / steps)
        robot.set_servo_angle(X, home_x + x0 + (x1 - x0) * k, 20)
        robot.set_servo_angle(Y, home_y + y0 + (y1 - y0) * k, 20)
        time.sleep_ms(ms // steps)


points = [(0, 0), (-45, 8), (45, 8), (20, -5), (0, 0)]
for (x0, y0), (x1, y1) in zip(points, points[1:]):
    glide(x0, x1, y0, y1)
