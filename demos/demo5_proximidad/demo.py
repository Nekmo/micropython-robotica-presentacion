# Challenge 2c: shy Stack-chan (proximity + ambient light)
import time
import M5
from hardware.stackchan import StackChan

M5.begin()
robot = StackChan(i2c=1, uart=1)
robot.set_servo_power(True)
X = robot.SERVO_ID_X
home_x = robot.get_servo_angle(X)
shy = False

while True:
    M5.update()
    near = M5.Als.getProximitySensorData()   # 0 (far) .. 2047 (touching)
    lux = M5.Als.getLightSensorData()
    if near > 600 and not shy:
        shy = True
        robot.set_rgb_color(0xF7A59E)
        robot.set_servo_angle(X, home_x + 60, 250)   # look away
    elif near < 300 and shy:
        shy = False
        robot.set_rgb_color(0x000000)
        robot.set_servo_angle(X, home_x, 600)
    if M5.Touch.getCount():
        print("proximity:", near, "light:", lux)
    time.sleep_ms(100)
