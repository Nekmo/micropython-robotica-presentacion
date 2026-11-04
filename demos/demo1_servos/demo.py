# Challenge 1: move the servos ("yes" and "no")
import time
from hardware.stackchan import StackChan

robot = StackChan(i2c=1, uart=1)
robot.set_servo_power(True)
X, Y = robot.SERVO_ID_X, robot.SERVO_ID_Y
for servo in (X, Y):
    robot.set_servo_torque(servo, True)

# Remember the boot pose as "looking forward"
home_x = robot.get_servo_angle(X)
home_y = robot.get_servo_angle(Y)


def look(dx=0, dy=0, ms=300):
    robot.set_servo_angle(X, home_x + dx, ms)
    robot.set_servo_angle(Y, home_y + dy, ms)
    time.sleep_ms(ms + 50)


for _ in range(3):      # "no"
    look(dx=-30)
    look(dx=30)
look()
for _ in range(3):      # "yes"
    look(dy=12)
    look(dy=-6)
look()
